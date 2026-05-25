# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json
from datetime import date, datetime, timedelta

# Third party imports
from celery import shared_task
from dateutil.rrule import (
    DAILY,
    FR,
    MO,
    MONTHLY,
    SA,
    SU,
    TH,
    TU,
    WE,
    WEEKLY,
    YEARLY,
    rrule,
)

# Django imports
from django.db import transaction
from django.utils import timezone

# Module imports
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueAssignee, IssueLabel, State
from plane.db.models.state import StateGroup
from plane.utils.exception_logger import log_exception
from plane.utils.recurrence_validator import validate_recurrence_pattern  # re-exported


FREQUENCY_MAP = {
    "daily": DAILY,
    "weekly": WEEKLY,
    "monthly": MONTHLY,
    "yearly": YEARLY,
}

WEEKDAY_MAP = {
    "MO": MO,
    "TU": TU,
    "WE": WE,
    "TH": TH,
    "FR": FR,
    "SA": SA,
    "SU": SU,
}


def _to_date(value):
    """Coerce a value (date|datetime|isoformat string) to date, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)).date()


def compute_next_date(anchor, pattern):
    """Return the next occurrence strictly after `anchor` for the given pattern.

    Pattern shape:
      {
        "frequency": "daily" | "weekly" | "monthly" | "yearly",
        "interval": int (>=1),
        "by_weekday": ["MO","TU",...]  (optional),
        "by_monthday": int             (optional, 1..31 or -1 for last),
        "by_setpos": int               (optional, e.g. -1 = last)
      }
    """
    if anchor is None or not pattern:
        return None

    frequency = FREQUENCY_MAP.get(pattern.get("frequency"))
    if frequency is None:
        return None

    interval = max(int(pattern.get("interval", 1) or 1), 1)

    byweekday = None
    raw_weekdays = pattern.get("by_weekday")
    if raw_weekdays:
        byweekday = [WEEKDAY_MAP[d] for d in raw_weekdays if d in WEEKDAY_MAP]
        if not byweekday:
            byweekday = None

    bymonthday = pattern.get("by_monthday")
    bysetpos = pattern.get("by_setpos")

    # Use a datetime anchor for rrule, then strip back to date.
    dtstart = datetime.combine(anchor, datetime.min.time())

    occurrences = rrule(
        freq=frequency,
        interval=interval,
        dtstart=dtstart,
        byweekday=byweekday,
        bymonthday=bymonthday,
        bysetpos=bysetpos,
    )

    # rrule with dtstart=anchor may yield the anchor itself; we want strictly after.
    for occ in occurrences:
        candidate = occ.date()
        if candidate > anchor:
            return candidate
    return None


def compute_next_dates(start_date, target_date, pattern):
    """Compute new (start_date, target_date) shifted by the pattern.

    target_date is the anchor for recurrence (must be present).
    start_date, if present, is shifted by the same delta as target_date.
    """
    target = _to_date(target_date)
    if target is None:
        return None, None

    new_target = compute_next_date(target, pattern)
    if new_target is None:
        return None, None

    start = _to_date(start_date)
    if start is None:
        return None, new_target

    delta = new_target - target
    return start + delta, new_target


@shared_task
def create_next_recurring_issue(issue_id):
    """Create the next instance of a recurring issue after completion.

    Idempotency: the original issue's recurrence_pattern is consumed in the
    sense that the clone carries the same pattern forward, but the trigger
    only fires on the state-group transition into "completed". Re-saving an
    already-completed issue does not re-trigger (see Issue.save).
    """
    try:
        with transaction.atomic():
            issue = Issue.all_objects.select_related("project", "workspace", "state").get(pk=issue_id)
            pattern = issue.recurrence_pattern
            if not pattern:
                return

            new_start, new_target = compute_next_dates(issue.start_date, issue.target_date, pattern)
            if new_target is None:
                return

            default_state = (
                State.objects.filter(project=issue.project, default=True)
                .exclude(group=StateGroup.TRIAGE.value)
                .first()
                or State.objects.filter(project=issue.project)
                .exclude(group=StateGroup.TRIAGE.value)
                .order_by("sequence")
                .first()
            )

            new_issue = Issue.objects.create(
                workspace=issue.workspace,
                project=issue.project,
                name=issue.name,
                description_json=issue.description_json,
                description_html=issue.description_html,
                description_binary=issue.description_binary,
                priority=issue.priority,
                point=issue.point,
                estimate_point=issue.estimate_point,
                parent=issue.parent,
                type=issue.type,
                start_date=new_start,
                target_date=new_target,
                state=default_state,
                recurrence_pattern=pattern,
                created_by=issue.created_by,
                updated_by=issue.updated_by,
            )

            assignee_ids = list(
                IssueAssignee.objects.filter(issue=issue).values_list("assignee_id", flat=True)
            )
            if assignee_ids:
                IssueAssignee.objects.bulk_create(
                    [
                        IssueAssignee(
                            issue=new_issue,
                            assignee_id=assignee_id,
                            project=issue.project,
                            workspace=issue.workspace,
                            created_by=issue.created_by,
                            updated_by=issue.updated_by,
                        )
                        for assignee_id in assignee_ids
                    ],
                    ignore_conflicts=True,
                )

            label_ids = list(IssueLabel.objects.filter(issue=issue).values_list("label_id", flat=True))
            if label_ids:
                IssueLabel.objects.bulk_create(
                    [
                        IssueLabel(
                            issue=new_issue,
                            label_id=label_id,
                            project=issue.project,
                            workspace=issue.workspace,
                            created_by=issue.created_by,
                            updated_by=issue.updated_by,
                        )
                        for label_id in label_ids
                    ],
                    ignore_conflicts=True,
                )

            issue_activity.delay(
                type="issue.activity.created",
                requested_data=json.dumps(
                    {
                        "recurring_source_id": str(issue.id),
                        "name": new_issue.name,
                    }
                ),
                actor_id=str(issue.created_by_id),
                issue_id=str(new_issue.id),
                project_id=str(issue.project_id),
                current_instance=None,
                subscriber=False,
                epoch=int(timezone.now().timestamp()),
                notification=False,
            )
    except Issue.DoesNotExist:
        return
    except Exception as exc:
        log_exception(exc)
        return
