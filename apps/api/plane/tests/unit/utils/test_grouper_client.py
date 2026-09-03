# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.db.models import F, Func, OuterRef, Subquery

from plane.db.models import Client, CycleIssue, FileAsset, Issue, IssueLink, Project, State
from plane.utils.grouper import issue_group_values, issue_on_results, issue_queryset_grouper


def _annotated_issue_queryset():
    """Reproduz as anotações que as views de issue aplicam antes de chamar
    `issue_on_results` — `required_fields` projeta várias delas (cycle_id,
    link_count, attachment_count, sub_issues_count), que não existem no model cru.
    Ver `IssueListEndpoint.get` em plane/app/views/issue/base.py."""
    queryset = issue_queryset_grouper(queryset=Issue.objects.all(), group_by=None, sub_group_by=None)
    return (
        queryset.annotate(
            cycle_id=Subquery(
                CycleIssue.objects.filter(issue=OuterRef("id"), deleted_at__isnull=True).values("cycle_id")[:1]
            )
        )
        .annotate(
            link_count=IssueLink.objects.filter(issue=OuterRef("id"))
            .order_by()
            .annotate(count=Func(F("id"), function="Count"))
            .values("count")
        )
        .annotate(
            attachment_count=FileAsset.objects.filter(
                issue_id=OuterRef("id"), entity_type=FileAsset.EntityTypeContext.ISSUE_ATTACHMENT
            )
            .order_by()
            .annotate(count=Func(F("id"), function="Count"))
            .values("count")
        )
        .annotate(
            sub_issues_count=Issue.issue_objects.filter(parent=OuterRef("id"))
            .order_by()
            .annotate(count=Func(F("id"), function="Count"))
            .values("count")
        )
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestGrouperClient:
    def test_issue_on_results_includes_client_id(self, workspace, create_user):
        client = Client.objects.create(workspace=workspace, name="Acme")
        project = Project.objects.create(name="Proj", identifier="PROJ", workspace=workspace, created_by=create_user)
        # Criar um Project pelo model não dispara os estados padrão.
        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        Issue.objects.create(name="Tarefa", project=project, workspace=workspace, state=state, client=client)

        rows = issue_on_results(_annotated_issue_queryset(), group_by=None, sub_group_by=None)

        assert rows[0]["client_id"] == client.id

    def test_issue_group_values_lists_active_clients_plus_none(self, workspace):
        active = Client.objects.create(workspace=workspace, name="Acme")
        Client.objects.create(workspace=workspace, name="Inativa", is_active=False)

        values = issue_group_values(field="client_id", slug=workspace.slug)

        assert active.id in values
        assert "None" in values
