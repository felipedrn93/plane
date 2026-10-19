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

    def test_blank_cnpj_is_not_unique(self, workspace):
        client = Client.objects.create(workspace=workspace, name="Acme")
        ClientCompany.objects.create(workspace=workspace, client=client, name="Acme SP", cnpj="")
        ClientCompany.objects.create(workspace=workspace, client=client, name="Acme RJ", cnpj="")
        assert client.companies.count() == 2


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


@pytest.mark.unit
@pytest.mark.django_db
class TestSubIssueInheritsClient:
    """Subtarefa herda o cliente do pai; só tem cliente próprio quando o pai não tem."""

    @pytest.fixture
    def setup(self, workspace, create_user):
        from plane.db.models import Issue, Project, State

        project = Project.objects.create(name="Proj", identifier="PROJ", workspace=workspace, created_by=create_user)
        state = State.objects.create(name="Backlog", group="backlog", project=project, workspace=workspace)
        acme = Client.objects.create(workspace=workspace, name="Acme")
        globex = Client.objects.create(workspace=workspace, name="Globex")

        def make(**kw):
            return Issue.objects.create(name="T", project=project, workspace=workspace, state=state, **kw)

        return make, acme, globex

    def test_child_created_under_parent_with_client_inherits(self, setup):
        make, acme, globex = setup
        parent = make(client=acme)
        child = make(parent=parent, client=globex)
        assert child.client_id == acme.id

    def test_child_cannot_override_parent_client(self, setup):
        make, acme, globex = setup
        child = make(parent=make(client=acme))
        child.client = globex
        child.save()
        child.refresh_from_db()
        assert child.client_id == acme.id

    def test_child_keeps_own_client_when_parent_has_none(self, setup):
        make, acme, globex = setup
        child = make(parent=make(), client=globex)
        child.refresh_from_db()
        assert child.client_id == globex.id

    def test_parent_client_change_propagates_to_all_descendants(self, setup):
        make, acme, globex = setup
        parent = make()
        child = make(parent=parent, client=globex)
        grandchild = make(parent=child)

        parent.client = acme
        parent.save()

        child.refresh_from_db()
        grandchild.refresh_from_db()
        assert child.client_id == acme.id
        assert grandchild.client_id == acme.id

    def test_moving_child_under_parent_with_client_inherits(self, setup):
        make, acme, globex = setup
        parent = make(client=acme)
        child = make(client=globex)
        grandchild = make(parent=child)

        child.parent = parent
        child.save(update_fields=["parent"])

        child.refresh_from_db()
        grandchild.refresh_from_db()
        assert child.client_id == acme.id
        assert grandchild.client_id == acme.id
