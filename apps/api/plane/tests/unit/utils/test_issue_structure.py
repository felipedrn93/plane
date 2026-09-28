# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date
from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueAssignee, IssueRelation, Project, ProjectMember, State
from plane.utils.issue_structure import copy_issue_structure, instantiate_issue_structure, snapshot_issue_structure


@pytest.mark.unit
class TestCopyIssueStructure:
    @pytest.fixture
    def project(self, create_user, workspace):
        project = Project.objects.create(name="BI", identifier="BI", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
        return project

    @pytest.fixture
    def todo(self, project):
        return State.objects.create(name="A Fazer", project=project, group="unstarted", default=True)

    @pytest.fixture
    def done(self, project):
        return State.objects.create(name="Concluído", project=project, group="completed")

    @pytest.fixture
    def make(self, create_user, workspace, project, todo):
        def _make(name, parent=None, **kwargs):
            kwargs.setdefault("state", todo)
            return Issue.objects.create(
                name=name,
                workspace=workspace,
                project=project,
                parent=parent,
                created_by=create_user,
                updated_by=create_user,
                **kwargs,
            )

        return _make

    def _relate(self, issue, related, relation_type="blocked_by"):
        return IssueRelation.objects.create(
            issue=issue,
            related_issue=related,
            relation_type=relation_type,
            project=issue.project,
            workspace=issue.workspace,
        )

    @pytest.mark.django_db
    @patch("plane.utils.issue_structure.issue_activity")
    def test_copies_tree_and_internal_relations(self, _mock_activity, create_user, make, done, todo):
        source = make("Implantar BI Pioneira")
        contrato = make("Enviar Contrato", parent=source, state=done, target_date=date(2026, 9, 23))
        assinatura = make("Aguardar Assinatura", parent=source, state=done, start_date=date(2026, 9, 20))
        grupo = make("Criar Grupo de Whatsapp", parent=source, priority="high")
        neto = make("Convidar cliente", parent=grupo)
        IssueAssignee.objects.create(
            issue=contrato, assignee=create_user, project=contrato.project, workspace=contrato.workspace
        )
        outside = make("Tarefa de fora")

        self._relate(assinatura, contrato)  # Aguardar Assinatura blocked_by Enviar Contrato
        self._relate(grupo, assinatura)
        self._relate(neto, grupo, "relates_to")
        self._relate(contrato, outside)  # points outside the tree -> ignored

        target = make("Implantar BI Cliente X")
        created = copy_issue_structure(source, target, create_user)

        assert created == 4
        children = {c.name: c for c in Issue.issue_objects.filter(parent=target)}
        assert set(children) == {"Enviar Contrato", "Aguardar Assinatura", "Criar Grupo de Whatsapp"}
        new_neto = Issue.issue_objects.get(parent=children["Criar Grupo de Whatsapp"])
        assert new_neto.name == "Convidar cliente"

        new_ids = {c.id for c in children.values()} | {new_neto.id}
        for issue in new_ids:
            clone = Issue.issue_objects.get(id=issue)
            assert clone.start_date is None and clone.target_date is None
            assert clone.state_id == todo.id
        assert children["Criar Grupo de Whatsapp"].priority == "high"
        assert list(children["Enviar Contrato"].assignees.all()) == [create_user]

        new_relations = set(
            IssueRelation.objects.filter(issue_id__in=new_ids).values_list(
                "issue_id", "related_issue_id", "relation_type"
            )
        )
        assert new_relations == {
            (children["Aguardar Assinatura"].id, children["Enviar Contrato"].id, "blocked_by"),
            (children["Criar Grupo de Whatsapp"].id, children["Aguardar Assinatura"].id, "blocked_by"),
            (new_neto.id, children["Criar Grupo de Whatsapp"].id, "relates_to"),
        }
        # the source tree is untouched
        assert Issue.issue_objects.filter(parent=source).count() == 3

    @pytest.mark.django_db
    @patch("plane.utils.issue_structure.issue_activity")
    def test_snapshot_then_instantiate(self, _mock_activity, create_user, make):
        source = make("Modelo", priority="high")
        a = make("A", parent=source)
        b = make("B", parent=a)
        self._relate(b, a)
        self._relate(a, source, "relates_to")

        structure = snapshot_issue_structure(source)
        assert structure["root"]["name"] == "Modelo"
        assert structure["root"]["priority"] == "high"
        assert [(n["name"], n["parent"]) for n in structure["nodes"]] == [("A", "root"), ("B", str(a.id))]
        assert sorted(structure["relations"], key=lambda r: r["relation_type"]) == [
            {"issue": str(b.id), "related_issue": str(a.id), "relation_type": "blocked_by"},
            {"issue": str(a.id), "related_issue": "root", "relation_type": "relates_to"},
        ]

        target = make("Nova")
        assert instantiate_issue_structure(structure, target, create_user) == 2
        new_a = Issue.issue_objects.get(parent=target)
        new_b = Issue.issue_objects.get(parent=new_a)
        assert IssueRelation.objects.filter(issue=new_b, related_issue=new_a, relation_type="blocked_by").exists()
        assert IssueRelation.objects.filter(issue=new_a, related_issue=target, relation_type="relates_to").exists()

    @pytest.mark.django_db
    @patch("plane.utils.issue_structure.issue_activity")
    def test_instantiate_skips_stale_assignees_and_labels(self, _mock_activity, create_user, make):
        source = make("Modelo")
        make("A", parent=source)
        structure = snapshot_issue_structure(source)
        structure["nodes"][0]["assignee_ids"] = [str(create_user.id), str(uuid4())]
        structure["nodes"][0]["label_ids"] = [str(uuid4())]

        target = make("Nova")
        instantiate_issue_structure(structure, target, create_user)
        child = Issue.issue_objects.get(parent=target)
        assert list(child.assignees.all()) == [create_user]
        assert child.labels.count() == 0

    @pytest.mark.django_db
    def test_instantiate_structure_without_sub_issues(self, create_user, make):
        source = make("Sem filhos")
        assert instantiate_issue_structure(snapshot_issue_structure(source), make("Nova"), create_user) == 0

    @pytest.mark.django_db
    def test_snapshot_skips_sub_issues_from_other_projects(self, create_user, workspace, make):
        other = Project.objects.create(name="Outro", identifier="OUT", workspace=workspace, created_by=create_user)
        source = make("Modelo")
        make("Daqui", parent=source)
        Issue.objects.create(name="Secreta", project=other, workspace=workspace, parent=source)
        assert [n["name"] for n in snapshot_issue_structure(source)["nodes"]] == ["Daqui"]


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueCopyStructureEndpoint:
    @pytest.fixture
    def project(self, create_user, workspace):
        project = Project.objects.create(name="BI", identifier="BI", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
        State.objects.create(name="A Fazer", project=project, workspace=workspace, group="unstarted", default=True)
        return project

    def _issue(self, project, name, parent=None):
        return Issue.objects.create(name=name, project=project, workspace=project.workspace, parent=parent)

    def _url(self, project, issue):
        return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/issues/{issue.id}/copy-structure/"

    @patch("plane.utils.issue_structure.issue_activity")
    def test_copies_sub_issues(self, _mock_activity, session_client, project):
        source = self._issue(project, "Modelo")
        self._issue(project, "Passo 1", parent=source)
        target = self._issue(project, "Cópia")
        response = session_client.post(self._url(project, target), {"source_issue_id": str(source.id)}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data == {"created": 1}
        assert Issue.issue_objects.filter(parent=target).count() == 1

    def test_rejects_copy_into_own_subtree(self, session_client, project):
        source = self._issue(project, "Modelo")
        child = self._issue(project, "Passo 1", parent=source)
        response = session_client.post(self._url(project, child), {"source_issue_id": str(source.id)}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
