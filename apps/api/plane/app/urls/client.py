# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views import ClientCompanyViewSet, ClientViewSet

urlpatterns = [
    path(
        "workspaces/<str:slug>/clients/",
        ClientViewSet.as_view({"get": "list", "post": "create"}),
        name="clients",
    ),
    path(
        "workspaces/<str:slug>/clients/<uuid:pk>/",
        ClientViewSet.as_view({"get": "retrieve", "patch": "partial_update", "delete": "destroy"}),
        name="client-detail",
    ),
    path(
        "workspaces/<str:slug>/clients/<uuid:client_id>/companies/",
        ClientCompanyViewSet.as_view({"get": "list", "post": "create"}),
        name="client-companies",
    ),
    path(
        "workspaces/<str:slug>/clients/<uuid:client_id>/companies/<uuid:pk>/",
        ClientCompanyViewSet.as_view({"patch": "partial_update", "delete": "destroy"}),
        name="client-company-detail",
    ),
]
