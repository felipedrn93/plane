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
