# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from plane.bgtasks.recurring_issue_task import (
    compute_next_date,
    compute_next_dates,
    create_next_recurring_issue,
    shift_dates,
    validate_recurrence_pattern,
)
from plane.db.models import Issue, Project, State


@pytest.mark.unit
class TestComputeNextDateDaily:
    def test_daily_interval_one(self):
        assert compute_next_date(date(2026, 5, 24), {"frequency": "daily", "interval": 1}) == date(2026, 5, 25)

    def test_daily_interval_three(self):
        assert compute_next_date(date(2026, 5, 24), {"frequency": "daily", "interval": 3}) == date(2026, 5, 27)


@pytest.mark.unit
class TestComputeNextDateWeekly:
    def test_weekly_no_weekdays_interval_one(self):
        # Sunday 2026-05-24 + 1 week
        assert compute_next_date(date(2026, 5, 24), {"frequency": "weekly", "interval": 1}) == date(2026, 5, 31)

    def test_weekly_with_weekdays(self):
        # Sunday 2026-05-24, repeat Mon/Wed/Fri → next is Monday 2026-05-25
        assert compute_next_date(
            date(2026, 5, 24),
            {"frequency": "weekly", "interval": 1, "by_weekday": ["MO", "WE", "FR"]},
        ) == date(2026, 5, 25)

    def test_weekly_with_weekdays_wraps_to_next_week(self):
        # Friday 2026-05-29 + Mon/Wed/Fri pattern interval=1 → next Monday 2026-06-01
        assert compute_next_date(
            date(2026, 5, 29),
            {"frequency": "weekly", "interval": 1, "by_weekday": ["MO", "WE", "FR"]},
        ) == date(2026, 6, 1)


@pytest.mark.unit
class TestComputeNextDateMonthly:
    def test_monthly_on_monthday(self):
        # From 2026-05-15, monthly on day 15 → next 2026-06-15
        assert compute_next_date(
            date(2026, 5, 15),
            {"frequency": "monthly", "interval": 1, "by_monthday": 15},
        ) == date(2026, 6, 15)

    def test_monthly_last_friday(self):
        # From 2026-05-29 (last Friday of May), next "last Friday" → 2026-06-26
        result = compute_next_date(
            date(2026, 5, 29),
            {
                "frequency": "monthly",
                "interval": 1,
                "by_weekday": ["FR"],
                "by_setpos": -1,
            },
        )
        assert result == date(2026, 6, 26)

    def test_monthly_first_monday(self):
        # From 2026-05-04 (1st Monday of May), next "1st Monday" → 2026-06-01
        result = compute_next_date(
            date(2026, 5, 4),
            {
                "frequency": "monthly",
                "interval": 1,
                "by_weekday": ["MO"],
                "by_setpos": 1,
            },
        )
        assert result == date(2026, 6, 1)


@pytest.mark.unit
class TestComputeNextDateYearly:
    def test_yearly_interval_one(self):
        assert compute_next_date(date(2026, 5, 24), {"frequency": "yearly", "interval": 1}) == date(2027, 5, 24)


@pytest.mark.unit
class TestComputeNextDates:
    def test_shifts_both_dates(self):
        new_start, new_target = compute_next_dates(
            date(2026, 5, 20),
            date(2026, 5, 24),
            {"frequency": "weekly", "interval": 1},
        )
        assert new_target == date(2026, 5, 31)
        assert new_start == date(2026, 5, 27)  # same 4-day delta preserved

    def test_returns_none_when_target_is_none(self):
        assert compute_next_dates(None, None, {"frequency": "daily", "interval": 1}) == (None, None)

    def test_start_none_target_set(self):
        new_start, new_target = compute_next_dates(
            None,
            date(2026, 5, 24),
            {"frequency": "daily", "interval": 1},
        )
        assert new_target == date(2026, 5, 25)
        assert new_start is None


@pytest.mark.unit
class TestValidateRecurrencePattern:
    def test_none_is_valid(self):
        is_valid, err = validate_recurrence_pattern(None)
        assert is_valid is True and err is None

    def test_valid_weekly(self):
        is_valid, _ = validate_recurrence_pattern({"frequency": "weekly", "interval": 2, "by_weekday": ["MO", "FR"]})
        assert is_valid is True

    def test_invalid_frequency(self):
        is_valid, err = validate_recurrence_pattern({"frequency": "hourly", "interval": 1})
        assert is_valid is False
        assert "frequency" in err

    def test_invalid_interval(self):
        is_valid, _ = validate_recurrence_pattern({"frequency": "daily", "interval": 0})
        assert is_valid is False

    def test_invalid_weekday(self):
        is_valid, _ = validate_recurrence_pattern({"frequency": "weekly", "interval": 1, "by_weekday": ["XX"]})
        assert is_valid is False

    def test_invalid_monthday(self):
        is_valid, _ = validate_recurrence_pattern({"frequency": "monthly", "interval": 1, "by_monthday": 32})
        assert is_valid is False

    def test_invalid_setpos(self):
        is_valid, _ = validate_recurrence_pattern({"frequency": "monthly", "interval": 1, "by_setpos": 10})
        assert is_valid is False

    def test_not_a_dict(self):
        is_valid, _ = validate_recurrence_pattern("not-a-dict")
        assert is_valid is False


@pytest.mark.unit
class TestShiftDates:
    def test_shifts_both_dates_by_delta(self):
        # Parent moves +30 days (e.g. day 20 -> day 20 next month); sub-issue
        # day 15 -> day 15, keeping its relative offset.
        new_start, new_target = shift_dates(date(2026, 6, 10), date(2026, 6, 15), timedelta(days=30))
        assert new_start == date(2026, 7, 10)
        assert new_target == date(2026, 7, 15)

    def test_preserves_gap_between_dates(self):
        new_start, new_target = shift_dates(date(2026, 6, 10), date(2026, 6, 15), timedelta(days=21))
        assert (new_target - new_start).days == 5  # 5-day gap preserved

    def test_start_none_keeps_none(self):
        new_start, new_target = shift_dates(None, date(2026, 6, 20), timedelta(days=7))
        assert new_start is None
        assert new_target == date(2026, 6, 27)

    def test_target_none_keeps_none(self):
        new_start, new_target = shift_dates(date(2026, 6, 20), None, timedelta(days=7))
        assert new_start == date(2026, 6, 27)
        assert new_target is None


@pytest.mark.unit
class TestRecurringIssueCascade:
    """DB-backed tests for the cascade of sub-issues when a recurring issue completes."""

    @pytest.fixture
    def project(self, create_user, workspace):
        return Project.objects.create(
            name="Recurrence Project",
            identifier="REC",
            workspace=workspace,
            created_by=create_user,
        )

    @pytest.fixture
    def backlog_state(self, project):
        return State.objects.create(name="Backlog", project=project, group="backlog", default=True)

    @pytest.mark.django_db
    @patch("plane.bgtasks.recurring_issue_task.issue_activity")
    def test_parent_recurrence_cascades_to_subissues(
        self, _mock_activity, create_user, workspace, project, backlog_state
    ):
        # Parent due day 20 (monthly), sub-issue due day 15.
        parent = Issue.objects.create(
            name="Parent",
            workspace=workspace,
            project=project,
            state=backlog_state,
            target_date=date(2026, 6, 20),
            recurrence_pattern={"frequency": "monthly", "interval": 1, "by_monthday": 20},
            created_by=create_user,
            updated_by=create_user,
        )
        child = Issue.objects.create(
            name="Child",
            workspace=workspace,
            project=project,
            state=backlog_state,
            parent=parent,
            target_date=date(2026, 6, 15),
            created_by=create_user,
            updated_by=create_user,
        )

        create_next_recurring_issue(parent.id)

        # New top-level occurrence of the parent (keeps the recurrence pattern).
        new_parent = (
            Issue.objects.filter(project=project, parent__isnull=True, recurrence_pattern__isnull=False)
            .exclude(id=parent.id)
            .get()
        )
        assert new_parent.target_date == date(2026, 7, 20)

        # Sub-issue cloned under the NEW parent, shifted by the same +30d delta.
        new_children = Issue.objects.filter(parent=new_parent)
        assert new_children.count() == 1
        new_child = new_children.first()
        assert new_child.id != child.id
        assert new_child.name == "Child"
        assert new_child.target_date == date(2026, 7, 15)

    @pytest.mark.django_db
    @patch("plane.bgtasks.recurring_issue_task.issue_activity")
    def test_recurring_subissue_stays_under_same_parent(
        self, _mock_activity, create_user, workspace, project, backlog_state
    ):
        # Requirement 2: recurrence applied directly on a sub-issue -> the new
        # sub-issue must remain a child of the same parent.
        parent = Issue.objects.create(
            name="Parent",
            workspace=workspace,
            project=project,
            state=backlog_state,
            created_by=create_user,
            updated_by=create_user,
        )
        sub = Issue.objects.create(
            name="Recurring Sub",
            workspace=workspace,
            project=project,
            state=backlog_state,
            parent=parent,
            target_date=date(2026, 6, 24),  # Wednesday
            recurrence_pattern={"frequency": "weekly", "interval": 1},
            created_by=create_user,
            updated_by=create_user,
        )

        create_next_recurring_issue(sub.id)

        new_sub = Issue.objects.filter(parent=parent, recurrence_pattern__isnull=False).exclude(id=sub.id).get()
        assert new_sub.parent_id == parent.id
        assert new_sub.target_date == date(2026, 7, 1)  # +7 days
