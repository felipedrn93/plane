# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.db.utils import IntegrityError

from plane.bgtasks.deletion_task import soft_delete_related_objects
from plane.db.models import Client, ClientCompany


@pytest.mark.unit
@pytest.mark.django_db
class TestClientModel:
    def test_defaults_to_active(self, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        assert client.is_active is True

    def test_name_is_unique_per_workspace(self, workspace):
        Client.objects.create(workspace=workspace, name="Acme")
        with pytest.raises(IntegrityError):
            Client.objects.create(workspace=workspace, name="Acme")

    def test_companies_are_cascade_deleted(self, workspace):
        """O Plane usa soft delete: `client.delete()` marca `deleted_at` e delega a
        cascata ao Celery. Aqui a task é chamada de forma síncrona, como o worker
        faria em produção."""
        client = Client.objects.create(workspace=workspace, name="Acme")
        ClientCompany.objects.create(workspace=workspace, client=client, name="Acme SP", cnpj="11222333000181")

        client.delete()
        soft_delete_related_objects(client._meta.app_label, client._meta.model_name, client.pk)

        assert ClientCompany.objects.filter(client_id=client.id).count() == 0


@pytest.mark.unit
@pytest.mark.django_db
class TestClientCompanyModel:
    def test_cnpj_is_unique_per_workspace(self, workspace):
        client_a = Client.objects.create(workspace=workspace, name="Acme")
        client_b = Client.objects.create(workspace=workspace, name="Globex")
        ClientCompany.objects.create(workspace=workspace, client=client_a, name="Acme SP", cnpj="11222333000181")
        with pytest.raises(IntegrityError):
            ClientCompany.objects.create(workspace=workspace, client=client_b, name="Globex SP", cnpj="11222333000181")


@pytest.mark.unit
@pytest.mark.django_db
class TestIssueClientField:
    def test_deleting_client_nulls_the_issue_field(self, workspace, create_user):
        """Mesmo caso do soft delete: a task do Celery é quem aplica o SET_NULL."""
        from plane.db.models import Issue, Project, State

        client = Client.objects.create(workspace=workspace, name="Acme")
        project = Project.objects.create(name="Proj", identifier="PROJ", workspace=workspace, created_by=create_user)
        # Criar um Project pelo model não dispara os estados padrão (isso é feito
        # na view de criação de projeto), então o estado é criado explicitamente.
        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        issue = Issue.objects.create(name="Tarefa", project=project, workspace=workspace, state=state, client=client)

        client.delete()
        soft_delete_related_objects(client._meta.app_label, client._meta.model_name, client.pk)
        issue.refresh_from_db()

        assert issue.client_id is None

    def test_display_properties_default_includes_client(self):
        from plane.db.models.issue import get_default_display_properties

        assert get_default_display_properties()["client"] is True
