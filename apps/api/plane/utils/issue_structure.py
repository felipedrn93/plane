# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.db import transaction
from django.utils import timezone

# Module imports
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueAssignee, IssueLabel, IssueRelation, State
from plane.db.models.state import StateGroup


def default_state_for_project(project):
    """Pick the project's default (non-triage) state, falling back to first by sequence."""
    return (
        State.objects.filter(project=project, default=True).exclude(group=StateGroup.TRIAGE.value).first()
        or State.objects.filter(project=project).exclude(group=StateGroup.TRIAGE.value).order_by("sequence").first()
    )


def copy_assignees_and_labels(source, new_issue):
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


def copy_issue_structure(source, target, actor):
    """Clone every descendant of `source` under `target`, plus the relations between them.

    The clones start in the project's default state with no dates; assignees and labels
    are kept. Relations are copied only when both ends are inside the copied tree
    (`source` itself maps to `target`). Returns the number of sub-issues created.
    """
    with transaction.atomic():
        # Walk the tree level by level: parents are always created before their children.
        id_map = {source.id: target.id}
        created = []
        level = [source.id]
        while level:
            children = list(
                Issue.issue_objects.filter(parent_id__in=level)
                .exclude(id__in=id_map.keys())
                .select_related("project")
                .order_by("sequence_id")
            )
            for child in children:
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
                    parent_id=id_map[child.parent_id],
                    type=child.type,
                    state=default_state_for_project(child.project),
                    created_by=actor,
                    updated_by=actor,
                )
                copy_assignees_and_labels(child, new_child)
                id_map[child.id] = new_child.id
                created.append(new_child)
            level = [child.id for child in children]

        relations = IssueRelation.objects.filter(issue_id__in=id_map.keys(), related_issue_id__in=id_map.keys())
        IssueRelation.objects.bulk_create(
            [
                IssueRelation(
                    issue_id=id_map[relation.issue_id],
                    related_issue_id=id_map[relation.related_issue_id],
                    relation_type=relation.relation_type,
                    project_id=target.project_id,
                    workspace_id=target.workspace_id,
                    created_by=actor,
                    updated_by=actor,
                )
                for relation in relations
            ],
            ignore_conflicts=True,
        )

    for new_issue in created:
        issue_activity.delay(
            type="issue.activity.created",
            requested_data=json.dumps({"name": new_issue.name}),
            actor_id=str(actor.id),
            issue_id=str(new_issue.id),
            project_id=str(new_issue.project_id),
            current_instance=None,
            subscriber=False,
            epoch=int(timezone.now().timestamp()),
            notification=False,
        )
    return len(created)
