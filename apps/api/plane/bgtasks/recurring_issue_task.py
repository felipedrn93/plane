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


def shift_dates(start_date, target_date, delta):
    """Shift start/target dates by a fixed `timedelta`, preserving None values.

    Used to move a sub-issue forward by the same delta the parent moved, so the
    sub-issue keeps its relative offset to the parent (e.g. parent day 20 -> day 20
    of the next period, sub-issue day 15 -> day 15).
    """
    start = _to_date(start_date)
    target = _to_date(target_date)
    return (
        start + delta if start is not None else None,
        target + delta if target is not None else None,
    )


def _default_state_for_project(project):
    """Pick the project's default (non-triage) state, falling back to first by sequence."""
    return (
        State.objects.filter(project=project, default=True).exclude(group=StateGroup.TRIAGE.value).first()
        or State.objects.filter(project=project).exclude(group=StateGroup.TRIAGE.value).order_by("sequence").first()
    )


def _copy_issue_relations(source, new_issue):
    """Clone assignees and labels from `source` issue onto `new_issue`."""
    assignee_ids = list(IssueAssignee.objects.filter(issue=source).values_list("assignee_id", flat=True))
    if assignee_ids:
        IssueAssignee.objects.bulk_create(
            [
                IssueAssignee(
                    issue=new_issue,
                    assignee_id=assignee_id,
                    project=new_issue.project,
                    workspace=new_issue.workspace,
                    created_by=source.created_by,
                    updated_by=source.updated_by,
                )
                for assignee_id in assignee_ids
            ],
            ignore_conflicts=True,
        )

    label_ids = list(IssueLabel.objects.filter(issue=source).values_list("label_id", flat=True))
    if label_ids:
        IssueLabel.objects.bulk_create(
            [
                IssueLabel(
                    issue=new_issue,
                    label_id=label_id,
                    project=new_issue.project,
                    workspace=new_issue.workspace,
                    created_by=source.created_by,
                    updated_by=source.updated_by,
                )
                for label_id in label_ids
            ],
            ignore_conflicts=True,
        )


def _emit_created_activity(new_issue, source):
    """Emit an `issue.activity.created` event linking the clone to its source."""
    issue_activity.delay(
        type="issue.activity.created",
        requested_data=json.dumps(
            {
                "recurring_source_id": str(source.id),
                "name": new_issue.name,
            }
        ),
        actor_id=str(source.created_by_id),
        issue_id=str(new_issue.id),
        project_id=str(new_issue.project_id),
        current_instance=None,
        subscriber=False,
        epoch=int(timezone.now().timestamp()),
        notification=False,
    )


@shared_task
def create_next_recurring_issue(issue_id):
    """Create the next instance of a recurring issue after completion.

    Idempotency: the original issue's recurrence_pattern is consumed in the
    sense that the clone carries the same pattern forward, but the trigger
    only fires on the state-group transition into "completed". Re-saving an
    already-completed issue does not re-trigger (see Issue.save).

    Cascade: when the completed issue is a parent, its direct sub-issues are
    cloned under the new parent occurrence with dates shifted by the same delta
    the parent moved. When the completed issue is itself a sub-issue, the clone
    keeps `parent=issue.parent`, so it stays a child of the same parent.
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

            default_state = _default_state_for_project(issue.project)

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

            _copy_issue_relations(issue, new_issue)
            _emit_created_activity(new_issue, issue)

            # Cascade direct sub-issues under the new parent occurrence, shifting
            # their dates by the same delta the parent moved (preserves the gap,
            # e.g. parent day 20 -> day 20, sub-issue day 15 -> day 15).
            # Past the early-return above, both target dates are non-null.
            delta = new_target - _to_date(issue.target_date)
            children = Issue.issue_objects.filter(parent_id=issue.id)
            for child in children:
                child_start, child_target = shift_dates(child.start_date, child.target_date, delta)
                child_state = (
                    default_state if child.project_id == issue.project_id else _default_state_for_project(child.project)
                )
                new_child = Issue.objects.create(
                    workspace=child.workspace,
                    project=child.project,
                    name=child.name,
                    description_json=child.description_json,
                    description_html=child.description_html,
                    description_binary=child.description_binary,
                    priority=child.priority,
                    point=child.point,
                    estimate_point=child.estimate_point,
                    parent=new_issue,
                    type=child.type,
                    start_date=child_start,
                    target_date=child_target,
                    state=child_state,
                    recurrence_pattern=child.recurrence_pattern,
                    created_by=child.created_by,
                    updated_by=child.updated_by,
                )
                _copy_issue_relations(child, new_child)
                _emit_created_activity(new_child, child)
    except Issue.DoesNotExist:
        return
    except Exception as exc:
        log_exception(exc)
        return
