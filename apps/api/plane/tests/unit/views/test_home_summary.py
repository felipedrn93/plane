# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date
from unittest.mock import MagicMock, patch

from plane.app.views.workspace.home_summary import (
    ASSIGNED_OPEN_SCOPE,
    ASSIGNED_OVERDUE_SCOPE,
    WorkspaceHomeSummaryEndpoint,
    filter_home_assignment_scope,
)


def test_filter_home_assignment_scope_applies_open_filters():
    queryset = MagicMock()
    user = MagicMock()

    result = filter_home_assignment_scope(queryset, user, ASSIGNED_OPEN_SCOPE)

    queryset.filter.assert_called_once_with(
        issue_assignee__assignee_id=user.id,
        issue_assignee__deleted_at__isnull=True,
        target_date__isnull=False,
    )
    queryset.filter.return_value.exclude.assert_called_once_with(state__group__in=["completed", "cancelled"])
    assert result == queryset.filter.return_value.exclude.return_value.distinct.return_value


@patch("plane.app.views.workspace.home_summary.timezone.localdate", return_value=date(2026, 9, 3))
def test_filter_home_assignment_scope_limits_overdue_to_before_today(mock_localdate):
    queryset = MagicMock()

    result = filter_home_assignment_scope(queryset, MagicMock(), ASSIGNED_OVERDUE_SCOPE)

    open_queryset = queryset.filter.return_value.exclude.return_value
    open_queryset.filter.assert_called_once_with(target_date__lt=date(2026, 9, 3))
    assert result == open_queryset.filter.return_value.distinct.return_value
    mock_localdate.assert_called_once_with()


@patch("plane.app.views.workspace.home_summary.filter_home_assignment_scope")
@patch("plane.app.views.workspace.home_summary.workspace_issue_permission_filters")
@patch("plane.app.views.workspace.home_summary.Issue.issue_objects.filter")
def test_home_summary_endpoint_returns_both_counts(mock_issue_filter, mock_permission_filters, mock_scope_filter):
    request = MagicMock()
    request.user = MagicMock()
    mock_scope_filter.return_value.aggregate.return_value = {
        "assigned_open_count": 7,
        "assigned_overdue_count": 2,
    }

    response = WorkspaceHomeSummaryEndpoint().get(request, "acme")

    mock_issue_filter.assert_called_once_with(workspace__slug="acme")
    visible_issues = mock_issue_filter.return_value.filter.return_value
    mock_permission_filters.assert_called_once_with(request.user)
    mock_issue_filter.return_value.filter.assert_called_once_with(mock_permission_filters.return_value)
    mock_scope_filter.assert_called_once_with(visible_issues, request.user, ASSIGNED_OPEN_SCOPE)
    assert response.status_code == 200
    assert response.data == {"assigned_open_count": 7, "assigned_overdue_count": 2}
