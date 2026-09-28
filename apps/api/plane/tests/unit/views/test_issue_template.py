# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import patch
from uuid import uuid4

import pytest
from rest_framework import status

from plane.db.models import Issue, IssueRelation, IssueTemplate, Label, Project, ProjectMember, State


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueTemplateEndpoints:
    @pytest.fixture
    def project(self, create_user, workspace):
        project = Project.objects.create(name="BI", identifier="BI", workspace=workspace, created_by=create_user)
        ProjectMember.objects.create(project=project, member=create_user, workspace=workspace, role=20)
        State.objects.create(name="A Fazer", project=project, workspace=workspace, group="unstarted", default=True)
        return project

    @pytest.fixture
    def source(self, project):
        root = Issue.objects.create(name="Implantar BI Pioneira", project=project, workspace=project.workspace)
        contrato = Issue.objects.create(
            name="Enviar Contrato", project=project, workspace=project.workspace, parent=root
        )
        assinatura = Issue.objects.create(
            name="Aguardar Assinatura", project=project, workspace=project.workspace, parent=root
        )
        IssueRelation.objects.create(
            issue=assinatura, related_issue=contrato, relation_type="blocked_by", project=project
        )
        return root

    def _url(self, project, suffix=""):
        return f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/issue-templates/{suffix}"

    @patch("plane.utils.issue_structure.issue_activity")
    def test_save_list_apply_delete(self, _mock_activity, session_client, project, source):
        response = session_client.post(self._url(project), {"issue_id": str(source.id), "name": "Implantar BI"})
        assert response.status_code == status.HTTP_201_CREATED
        template_id = response.data["id"]

        # same name, different case -> replaces
        response = session_client.post(self._url(project), {"issue_id": str(source.id), "name": "implantar bi"})
        assert response.status_code == status.HTTP_201_CREATED
        assert IssueTemplate.objects.filter(project=project).count() == 1

        response = session_client.get(self._url(project))
        assert response.status_code == status.HTTP_200_OK
        assert [(t["name"], t["sub_issues_count"]) for t in response.data] == [("implantar bi", 2)]
        assert response.data[0]["root"]["name"] == "Implantar BI Pioneira"

        target = Issue.objects.create(name="Implantar BI Cliente X", project=project, workspace=project.workspace)
        response = session_client.post(
            f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/issues/{target.id}/copy-structure/",
            {"template_id": str(template_id)},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data == {"created": 2}
        children = {c.name: c for c in Issue.issue_objects.filter(parent=target)}
        assert IssueRelation.objects.filter(
            issue=children["Aguardar Assinatura"], related_issue=children["Enviar Contrato"]
        ).exists()

        response = session_client.delete(self._url(project, f"{template_id}/"))
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert session_client.get(self._url(project)).data == []

        # applying a deleted template -> 404
        response = session_client.post(
            f"/api/workspaces/{project.workspace.slug}/projects/{project.id}/issues/{target.id}/copy-structure/",
            {"template_id": str(template_id)},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_blank_name_is_rejected(self, session_client, project, source):
        response = session_client.post(self._url(project), {"issue_id": str(source.id), "name": "   "})
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_issue_from_other_project_is_not_found(self, session_client, project, create_user, workspace):
        other = Project.objects.create(name="Outro", identifier="OUT", workspace=workspace, created_by=create_user)
        issue = Issue.objects.create(name="Fora", project=other, workspace=workspace)
        response = session_client.post(self._url(project), {"issue_id": str(issue.id), "name": "X"})
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_guest_cannot_save(self, session_client, project, source, create_user):
        ProjectMember.objects.filter(project=project, member=create_user).update(role=5)
        response = session_client.post(self._url(project), {"issue_id": str(source.id), "name": "X"})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_drops_stale_root_ids(self, session_client, project, create_user):
        label = Label.objects.create(name="Cliente", project=project, workspace=project.workspace)
        IssueTemplate.objects.create(
            project=project,
            name="Modelo",
            structure={
                "root": {
                    "name": "Modelo",
                    "assignee_ids": [str(create_user.id), str(uuid4())],
                    "label_ids": [str(label.id), str(uuid4())],
                },
                "nodes": [],
                "relations": [],
            },
        )
        root = session_client.get(self._url(project)).data[0]["root"]
        assert root["assignee_ids"] == [str(create_user.id)]
        assert root["label_ids"] == [str(label.id)]
