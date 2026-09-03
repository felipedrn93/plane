# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

# Module imports
from .base import BaseModel


class Client(BaseModel):
    """Cliente do workspace. Agrupa uma ou mais empresas (CNPJs)."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Client"
        verbose_name_plural = "Clients"
        db_table = "clients"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "workspace",
                condition=Q(deleted_at__isnull=True),
                name="unique_client_name_per_workspace_when_not_deleted",
            )
        ]

    def __str__(self):
        return self.name


class ClientCompany(BaseModel):
    """Empresa (CNPJ) pertencente a um cliente."""

    workspace = models.ForeignKey("db.Workspace", on_delete=models.CASCADE, related_name="client_companies")
    client = models.ForeignKey("db.Client", on_delete=models.CASCADE, related_name="companies")
    name = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=14)

    class Meta:
        verbose_name = "Client Company"
        verbose_name_plural = "Client Companies"
        db_table = "client_companies"
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=["workspace", "cnpj"],
                condition=Q(deleted_at__isnull=True),
                name="unique_client_company_cnpj_per_workspace_when_not_deleted",
            )
        ]

    def __str__(self):
        return f"{self.name} <{self.cnpj}>"
