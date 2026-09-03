# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from rest_framework import status

from plane.db.models import Client, ClientCompany, WorkspaceMember


@pytest.mark.unit
@pytest.mark.django_db
class TestClientEndpoints:
    def _url(self, workspace):
        return f"/api/workspaces/{workspace.slug}/clients/"

    def test_member_can_create_client(self, session_client, workspace):
        response = session_client.post(self._url(workspace), {"name": "Acme"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Acme"
        assert response.data["is_active"] is True

    def test_list_returns_nested_companies_and_issue_count(self, session_client, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        ClientCompany.objects.create(workspace=workspace, client=client, name="Acme SP", cnpj="11222333000181")
        response = session_client.get(self._url(workspace))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data[0]["companies"]) == 1
        assert response.data[0]["issue_count"] == 0

    def test_guest_cannot_create_client(self, session_client, workspace, create_user):
        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=5)
        response = session_client.post(self._url(workspace), {"name": "Acme"}, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_guest_can_list_clients(self, session_client, workspace, create_user):
        Client.objects.create(workspace=workspace, name="Acme")
        WorkspaceMember.objects.filter(workspace=workspace, member=create_user).update(role=5)
        response = session_client.get(self._url(workspace))
        assert response.status_code == status.HTTP_200_OK

    def test_duplicate_name_is_rejected(self, session_client, workspace):
        Client.objects.create(workspace=workspace, name="Acme")
        response = session_client.post(self._url(workspace), {"name": "acme"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_delete_without_issues_succeeds(self, session_client, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        response = session_client.delete(f"{self._url(workspace)}{client.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_delete_with_issues_is_blocked(self, session_client, workspace, create_user):
        from plane.db.models import Issue, Project, State

        client = Client.objects.create(workspace=workspace, name="Acme")
        project = Project.objects.create(name="Proj", identifier="PROJ", workspace=workspace, created_by=create_user)
        # Criar um Project pelo model não dispara os estados padrão.
        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        Issue.objects.create(name="Tarefa", project=project, workspace=workspace, state=state, client=client)

        response = session_client.delete(f"{self._url(workspace)}{client.id}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Client.objects.filter(id=client.id).exists()


@pytest.mark.unit
@pytest.mark.django_db
class TestClientCompanyEndpoints:
    def test_member_can_add_company(self, session_client, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        url = f"/api/workspaces/{workspace.slug}/clients/{client.id}/companies/"
        response = session_client.post(url, {"name": "Acme SP", "cnpj": "11.222.333/0001-81"}, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["cnpj"] == "11222333000181"

    def test_invalid_cnpj_is_rejected(self, session_client, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        url = f"/api/workspaces/{workspace.slug}/clients/{client.id}/companies/"
        response = session_client.post(url, {"name": "Acme SP", "cnpj": "11222333000182"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_duplicate_cnpj_in_workspace_is_rejected(self, session_client, workspace):
        client_a = Client.objects.create(workspace=workspace, name="Acme")
        client_b = Client.objects.create(workspace=workspace, name="Globex")
        ClientCompany.objects.create(workspace=workspace, client=client_a, name="Acme SP", cnpj="11222333000181")
        url = f"/api/workspaces/{workspace.slug}/clients/{client_b.id}/companies/"
        response = session_client.post(url, {"name": "Globex SP", "cnpj": "11222333000181"}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
