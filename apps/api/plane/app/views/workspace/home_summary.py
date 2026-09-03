# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from plane.app.permissions import WorkspaceViewerPermission
from plane.app.views.base import BaseAPIView
from plane.db.models import Issue


ASSIGNED_OPEN_SCOPE = "assigned-open"
ASSIGNED_OVERDUE_SCOPE = "assigned-overdue"
HOME_ASSIGNMENT_SCOPES = {ASSIGNED_OPEN_SCOPE, ASSIGNED_OVERDUE_SCOPE}


def workspace_issue_permission_filters(user):
    """Match the project visibility rules used by workspace-wide issue views."""
    return Q(
        Q(project__project_projectmember__role=5, project__guest_view_all_features=True)
        | Q(
            project__project_projectmember__role=5,
            project__guest_view_all_features=False,
            created_by=user,
        )
        | Q(project__project_projectmember__role__gt=5),
        project__project_projectmember__member=user,
        project__project_projectmember__is_active=True,
    )


def filter_home_assignment_scope(queryset, user, scope):
    """Apply the fixed filters used by the home summary cards and their views."""
    queryset = queryset.filter(
        assignees__in=[user],
        target_date__isnull=False,
    ).exclude(state__group__in=["completed", "cancelled"])

    if scope == ASSIGNED_OVERDUE_SCOPE:
        queryset = queryset.filter(target_date__lt=timezone.localdate())

    return queryset.distinct()


class WorkspaceHomeSummaryEndpoint(BaseAPIView):
    permission_classes = [WorkspaceViewerPermission]

    def get(self, request, slug):
        open_issues = filter_home_assignment_scope(
            Issue.issue_objects.filter(workspace__slug=slug).filter(workspace_issue_permission_filters(request.user)),
            request.user,
            ASSIGNED_OPEN_SCOPE,
        )

        summary = open_issues.aggregate(
            assigned_open_count=Count("id", distinct=True),
            assigned_overdue_count=Count(
                "id",
                filter=Q(target_date__lt=timezone.localdate()),
                distinct=True,
            ),
        )

        return Response(summary, status=status.HTTP_200_OK)
