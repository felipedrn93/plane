# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import json

# Django imports
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

# Module imports
from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueAssignee, IssueLabel, IssueRelation, Label, ProjectMember, State
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


def _node_fields(issue):
    return {
        "name": issue.name,
        "description_html": issue.description_html,
        "priority": issue.priority,
        "assignee_ids": [
            str(i) for i in IssueAssignee.objects.filter(issue=issue).values_list("assignee_id", flat=True)
        ],
        "label_ids": [str(i) for i in IssueLabel.objects.filter(issue=issue).values_list("label_id", flat=True)],
    }


def snapshot_issue_structure(source):
    """Photograph `source` and all its descendants (plus the relations between them) as plain JSON.

    Nodes are listed breadth-first, so a node's parent always comes before it. `source` itself is
    the "root" key; relations with an end outside the tree are left out. Dates and state are not kept.
    """
    keys = {source.id: "root"}
    nodes = []
    level = [source.id]
    while level:
        children = list(
            Issue.issue_objects.filter(parent_id__in=level).exclude(id__in=keys.keys()).order_by("sequence_id")
        )
        for child in children:
            keys[child.id] = str(child.id)
            nodes.append({"key": str(child.id), "parent": keys[child.parent_id], **_node_fields(child)})
        level = [child.id for child in children]

    relations = [
        {"issue": keys[r.issue_id], "related_issue": keys[r.related_issue_id], "relation_type": r.relation_type}
        for r in IssueRelation.objects.filter(issue_id__in=keys.keys(), related_issue_id__in=keys.keys())
    ]
    return {"root": _node_fields(source), "nodes": nodes, "relations": relations}


def valid_member_ids(project, ids):
    """Keep only the ids of active members of `project`."""
    return {
        str(i)
        for i in ProjectMember.objects.filter(project=project, member_id__in=ids, is_active=True).values_list(
            "member_id", flat=True
        )
    }


def valid_label_ids(project, ids):
    """Keep only the ids of labels that still exist in `project` (or workspace-wide labels)."""
    labels = Label.objects.filter(Q(project=project) | Q(project__isnull=True, workspace_id=project.workspace_id))
    return {str(i) for i in labels.filter(id__in=ids).values_list("id", flat=True)}


def instantiate_issue_structure(structure, target, actor):
    """Create the snapshot's nodes under `target` (which plays the "root"). Returns how many were created.

    New sub-issues start in the project's default state with no dates. Assignees who left the project
    and labels that were deleted since the snapshot are skipped.
    """
    project = target.project
    nodes = structure.get("nodes", [])
    member_ids = valid_member_ids(project, {i for n in nodes for i in n.get("assignee_ids", [])})
    label_ids = valid_label_ids(project, {i for n in nodes for i in n.get("label_ids", [])})
    state = default_state_for_project(project)

    with transaction.atomic():
        id_map = {"root": target.id}
        created = []
        for node in nodes:
            new_issue = Issue.objects.create(
                workspace=target.workspace,
                project=project,
                name=node["name"],
                description_html=node.get("description_html") or "<p></p>",
                priority=node.get("priority") or "none",
                parent_id=id_map[node["parent"]],
                state=state,
                created_by=actor,
                updated_by=actor,
            )
            id_map[node["key"]] = new_issue.id
            created.append(new_issue)

            IssueAssignee.objects.bulk_create(
                [
                    IssueAssignee(
                        issue=new_issue, assignee_id=i, project=project, workspace=target.workspace, created_by=actor
                    )
                    for i in node.get("assignee_ids", [])
                    if i in member_ids
                ],
                ignore_conflicts=True,
            )
            IssueLabel.objects.bulk_create(
                [
                    IssueLabel(
                        issue=new_issue, label_id=i, project=project, workspace=target.workspace, created_by=actor
                    )
                    for i in node.get("label_ids", [])
                    if i in label_ids
                ],
                ignore_conflicts=True,
            )

        IssueRelation.objects.bulk_create(
            [
                IssueRelation(
                    issue_id=id_map[r["issue"]],
                    related_issue_id=id_map[r["related_issue"]],
                    relation_type=r["relation_type"],
                    project=project,
                    workspace=target.workspace,
                    created_by=actor,
                    updated_by=actor,
                )
                for r in structure.get("relations", [])
                if r["issue"] in id_map and r["related_issue"] in id_map
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


def copy_issue_structure(source, target, actor):
    """Clone every descendant of `source` under `target`, plus the relations between them."""
    return instantiate_issue_structure(snapshot_issue_structure(source), target, actor)
