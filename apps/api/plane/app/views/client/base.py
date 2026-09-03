# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db.models import Count, Q
from django.db.models.functions import Lower

# Third party imports
from rest_framework import status
from rest_framework.response import Response

# Module imports
from plane.app.permissions import WorkspaceEntityPermission
from plane.app.serializers import ClientCompanySerializer, ClientSerializer
from plane.app.views.base import BaseViewSet
from plane.db.models import Client, ClientCompany, Workspace


class ClientViewSet(BaseViewSet):
    serializer_class = ClientSerializer
    model = Client
    permission_classes = [WorkspaceEntityPermission]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"))
            .select_related("workspace")
            .prefetch_related("companies")
            .annotate(issue_count=Count("issues", filter=Q(issues__deleted_at__isnull=True), distinct=True))
            .order_by("name")
        )

    def list(self, request, slug):
        clients = self.get_queryset()
        if request.query_params.get("is_active") == "true":
            clients = clients.filter(is_active=True)
        return Response(ClientSerializer(clients, many=True).data, status=status.HTTP_200_OK)

    def create(self, request, slug):
        workspace = Workspace.objects.get(slug=slug)
        serializer = ClientSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if self._name_taken(workspace, serializer.validated_data["name"]):
            return Response(
                {"name": ["Já existe um cliente com esse nome neste workspace."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(workspace_id=workspace.id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, slug, pk):
        client = self.get_queryset().get(pk=pk)
        serializer = ClientSerializer(client, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        name = serializer.validated_data.get("name")
        if name and self._name_taken(client.workspace, name, exclude_id=client.id):
            return Response(
                {"name": ["Já existe um cliente com esse nome neste workspace."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, slug, pk):
        client = self.get_queryset().get(pk=pk)
        if client.issue_count > 0:
            return Response(
                {
                    "error": "Este cliente está vinculado a tarefas. Inative-o em vez de excluir.",
                    "issue_count": client.issue_count,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        client.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _name_taken(self, workspace, name, exclude_id=None):
        queryset = (
            Client.objects.filter(workspace=workspace)
            .annotate(lower_name=Lower("name"))
            .filter(lower_name=name.lower())
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()


class ClientCompanyViewSet(BaseViewSet):
    serializer_class = ClientCompanySerializer
    model = ClientCompany
    permission_classes = [WorkspaceEntityPermission]

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(workspace__slug=self.kwargs.get("slug"), client_id=self.kwargs.get("client_id"))
            .order_by("name")
        )

    def create(self, request, slug, client_id):
        client = Client.objects.get(workspace__slug=slug, pk=client_id)
        serializer = ClientCompanySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        if self._cnpj_taken(client.workspace_id, serializer.validated_data["cnpj"]):
            return Response(
                {"cnpj": ["Este CNPJ já está cadastrado neste workspace."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save(workspace_id=client.workspace_id, client_id=client.id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, slug, client_id, pk):
        company = self.get_queryset().get(pk=pk)
        serializer = ClientCompanySerializer(company, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        cnpj = serializer.validated_data.get("cnpj")
        if cnpj and self._cnpj_taken(company.workspace_id, cnpj, exclude_id=company.id):
            return Response(
                {"cnpj": ["Este CNPJ já está cadastrado neste workspace."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, slug, client_id, pk):
        company = self.get_queryset().get(pk=pk)
        company.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _cnpj_taken(self, workspace_id, cnpj, exclude_id=None):
        queryset = ClientCompany.objects.filter(workspace_id=workspace_id, cnpj=cnpj)
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        return queryset.exists()
