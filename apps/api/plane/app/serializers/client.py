# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from rest_framework import serializers

# Module imports
from plane.db.models import Client, ClientCompany
from plane.utils.cnpj import is_valid_cnpj, normalize_cnpj

from .base import BaseSerializer


class ClientCompanySerializer(BaseSerializer):
    # O model guarda 14 dígitos, mas a UI envia o CNPJ mascarado
    # ("11.222.333/0001-81" = 18 caracteres). Sem declarar o campo aqui, o
    # `max_length=14` herdado do model rejeitaria a máscara antes de
    # `validate_cnpj` ter a chance de normalizá-la.
    cnpj = serializers.CharField(max_length=18)

    class Meta:
        model = ClientCompany
        fields = ["id", "name", "cnpj", "client", "created_at", "updated_at"]
        read_only_fields = ["id", "client", "created_at", "updated_at"]

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("O nome da empresa é obrigatório.")
        return name

    def validate_cnpj(self, value):
        cnpj = normalize_cnpj(value)
        if not is_valid_cnpj(cnpj):
            raise serializers.ValidationError("CNPJ inválido.")
        return cnpj


class ClientSerializer(BaseSerializer):
    companies = ClientCompanySerializer(many=True, read_only=True)
    issue_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Client
        fields = [
            "id",
            "name",
            "is_active",
            "companies",
            "issue_count",
            "workspace",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "workspace", "companies", "issue_count", "created_at", "updated_at"]

    def validate_name(self, value):
        name = (value or "").strip()
        if not name:
            raise serializers.ValidationError("O nome do cliente é obrigatório.")
        return name
