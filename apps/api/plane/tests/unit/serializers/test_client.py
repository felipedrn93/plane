# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.app.serializers import ClientCompanySerializer, ClientSerializer
from plane.db.models import Client, ClientCompany


@pytest.mark.unit
@pytest.mark.django_db
class TestClientCompanySerializer:
    def test_rejects_invalid_cnpj(self):
        serializer = ClientCompanySerializer(data={"name": "Acme SP", "cnpj": "11222333000182"})
        assert serializer.is_valid() is False
        assert "cnpj" in serializer.errors

    def test_normalizes_masked_cnpj(self):
        serializer = ClientCompanySerializer(data={"name": "Acme SP", "cnpj": "11.222.333/0001-81"})
        assert serializer.is_valid() is True
        assert serializer.validated_data["cnpj"] == "11222333000181"

    def test_cnpj_is_optional(self):
        serializer = ClientCompanySerializer(data={"name": "Acme SP", "cnpj": ""})
        assert serializer.is_valid() is True
        assert serializer.validated_data["cnpj"] == ""


@pytest.mark.unit
@pytest.mark.django_db
class TestClientSerializer:
    def test_serializes_nested_companies(self, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        ClientCompany.objects.create(workspace=workspace, client=client, name="Acme SP", cnpj="11222333000181")
        data = ClientSerializer(client).data
        assert data["name"] == "Acme"
        assert len(data["companies"]) == 1
        assert data["companies"][0]["cnpj"] == "11222333000181"

    def test_rejects_blank_name(self):
        serializer = ClientSerializer(data={"name": "   "})
        assert serializer.is_valid() is False
        assert "name" in serializer.errors


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueClientId:
    def test_issue_create_serializer_saves_client_id(self, workspace, create_user):
        from plane.app.serializers import IssueCreateSerializer
        from plane.db.models import Issue, Project, State

        client = Client.objects.create(workspace=workspace, name="Acme")
        project = Project.objects.create(name="Proj", identifier="PROJ", workspace=workspace, created_by=create_user)
        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        issue = Issue.objects.create(name="Tarefa", project=project, workspace=workspace, state=state)

        serializer = IssueCreateSerializer(
            issue, data={"client_id": str(client.id)}, partial=True, context={"project_id": project.id}
        )
        assert serializer.is_valid(), serializer.errors
        serializer.save()
        issue.refresh_from_db()
        assert issue.client_id == client.id
