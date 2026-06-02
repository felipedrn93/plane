# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db.models import Exists, OuterRef

from plane.db.models import IssueRelation

# State groups whose work items count as an "open" blocker.
ACTIVE_BLOCKER_STATE_GROUPS = ["backlog", "unstarted", "started"]


def active_blocked_exists():
    """Return an ``Exists()`` expression that is true when the outer work item is
    *actively* blocked: it has a non-deleted ``blocked_by`` relation whose blocker
    (``related_issue``) is still open (state group in
    :data:`ACTIVE_BLOCKER_STATE_GROUPS`).

    Correlates on the outer issue's ``pk`` so the same expression works both as a
    filter (``Q(active_blocked_exists())`` / ``~Q(active_blocked_exists())``) and as
    an annotation (``annotate(is_blocked=active_blocked_exists())``). Uses the
    ``issue_relations.issue_id`` index and never multiplies rows, so it stays cheap
    even on workspace-wide querysets without ``distinct()``.
    """
    return Exists(
        IssueRelation.objects.filter(
            issue_id=OuterRef("pk"),
            relation_type="blocked_by",
            deleted_at__isnull=True,
            related_issue__deleted_at__isnull=True,
            related_issue__state__group__in=ACTIVE_BLOCKER_STATE_GROUPS,
        )
    )
