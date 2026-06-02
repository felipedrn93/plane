# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.contrib.postgres.aggregates import ArrayAgg
from django.contrib.postgres.fields import ArrayField
from django.db import connection
from django.db.models import Q, UUIDField, Value, QuerySet, OuterRef, Subquery
from django.db.models.functions import Coalesce

# Module imports
from plane.db.models import (
    Cycle,
    Issue,
    Label,
    Module,
    Project,
    ProjectMember,
    State,
    WorkspaceMember,
    IssueAssignee,
    ModuleIssue,
    IssueLabel,
)
from plane.utils.exception_logger import log_exception
from typing import Iterable, Optional, Dict, Tuple, Any, Union, List


def issue_queryset_grouper(
    queryset: QuerySet[Issue],
    group_by: Optional[str],
    sub_group_by: Optional[str],
) -> QuerySet[Issue]:
    FIELD_MAPPER: Dict[str, str] = {
        "label_ids": "labels__id",
        "assignee_ids": "assignees__id",
        "module_ids": "issue_module__module_id",
    }

    GROUP_FILTER_MAPPER: Dict[str, Q] = {
        "assignees__id": Q(issue_assignee__deleted_at__isnull=True),
        "labels__id": Q(label_issue__deleted_at__isnull=True),
        "issue_module__module_id": Q(issue_module__deleted_at__isnull=True),
    }

    for group_key in [group_by, sub_group_by]:
        if group_key in GROUP_FILTER_MAPPER:
            queryset = queryset.filter(GROUP_FILTER_MAPPER[group_key])

    issue_assignee_subquery = Subquery(
        IssueAssignee.objects.filter(
            issue_id=OuterRef("pk"),
            deleted_at__isnull=True,
        )
        .values("issue_id")
        .annotate(arr=ArrayAgg("assignee_id", distinct=True))
        .values("arr")
    )

    issue_module_subquery = Subquery(
        ModuleIssue.objects.filter(
            issue_id=OuterRef("pk"),
            deleted_at__isnull=True,
            module__archived_at__isnull=True,
        )
        .values("issue_id")
        .annotate(arr=ArrayAgg("module_id", distinct=True))
        .values("arr")
    )

    issue_label_subquery = Subquery(
        IssueLabel.objects.filter(issue_id=OuterRef("pk"), deleted_at__isnull=True)
        .values("issue_id")
        .annotate(arr=ArrayAgg("label_id", distinct=True))
        .values("arr")
    )

    annotations_map: Dict[str, Tuple[str, Q]] = {
        "assignee_ids": Coalesce(issue_assignee_subquery, Value([], output_field=ArrayField(UUIDField()))),
        "label_ids": Coalesce(issue_label_subquery, Value([], output_field=ArrayField(UUIDField()))),
        "module_ids": Coalesce(issue_module_subquery, Value([], output_field=ArrayField(UUIDField()))),
    }

    default_annotations: Dict[str, Any] = {}

    for key, expression in annotations_map.items():
        if FIELD_MAPPER.get(key) in {group_by, sub_group_by}:
            continue
        default_annotations[key] = expression

    return queryset.annotate(**default_annotations)


def issue_on_results(
    issues: QuerySet[Issue],
    group_by: Optional[str],
    sub_group_by: Optional[str],
) -> List[Dict[str, Any]]:
    FIELD_MAPPER: Dict[str, str] = {
        "labels__id": "label_ids",
        "assignees__id": "assignee_ids",
        "issue_module__module_id": "module_ids",
    }

    original_list: List[str] = ["assignee_ids", "label_ids", "module_ids"]

    required_fields: List[str] = [
        "id",
        "name",
        "state_id",
        "sort_order",
        "completed_at",
        "estimate_point",
        "priority",
        "start_date",
        "target_date",
        "sequence_id",
        "project_id",
        "parent_id",
        "cycle_id",
        "sub_issues_count",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "attachment_count",
        "link_count",
        "is_draft",
        "archived_at",
        "state__group",
        "recurrence_pattern",
        # parent_chain is computed in Python via attach_parent_chain (single CTE).
        # Kept out of the .values() projection because it isn't a model column.
    ]

    if group_by in FIELD_MAPPER:
        original_list.remove(FIELD_MAPPER[group_by])
        original_list.append(group_by)

    if sub_group_by in FIELD_MAPPER:
        original_list.remove(FIELD_MAPPER[sub_group_by])
        original_list.append(sub_group_by)

    required_fields.extend(original_list)
    rows = list(issues.values(*required_fields))
    attach_parent_chain(rows)
    return rows


def fetch_parent_chains(issue_ids: Iterable[Any]) -> Dict[str, List[Dict[str, Any]]]:
    """For each issue id, return the ancestor chain ordered root-first.

    Each entry: {id, name, project_id, identifier, sequence_id}. Returns an
    empty dict on failure or when the input list is empty. Walks the
    self-referential ``Issue.parent`` chain with a single ``WITH RECURSIVE``
    so listings with N sub-items pay one query, not N.
    """
    ids_list = [iid for iid in issue_ids if iid is not None]
    if not ids_list:
        return {}

    # ``c.depth < 50`` defends against accidentally cyclic parent links
    # (Plane's API guards against them, but a corrupt row shouldn't loop forever).
    sql = """
        WITH RECURSIVE chain AS (
            SELECT i.id AS leaf_id, i.parent_id AS ancestor_id, 1 AS depth
            FROM issues i
            WHERE i.id = ANY(%s::uuid[]) AND i.parent_id IS NOT NULL
            UNION ALL
            SELECT c.leaf_id, a.parent_id, c.depth + 1
            FROM chain c
            JOIN issues a ON a.id = c.ancestor_id
            WHERE a.parent_id IS NOT NULL AND c.depth < 50
        )
        SELECT c.leaf_id, a.id, a.name, a.project_id, p.identifier, a.sequence_id, c.depth
        FROM chain c
        JOIN issues a ON a.id = c.ancestor_id
        JOIN projects p ON p.id = a.project_id
        WHERE a.deleted_at IS NULL
        ORDER BY c.leaf_id, c.depth DESC;
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, [[str(i) for i in ids_list]])
            rows = cursor.fetchall()
    except Exception as exc:  # defensive: never break the listing because of breadcrumb
        log_exception(exc)
        return {}

    result: Dict[str, List[Dict[str, Any]]] = {}
    for leaf_id, ancestor_id, name, project_id, identifier, sequence_id, _depth in rows:
        result.setdefault(str(leaf_id), []).append(
            {
                "id": str(ancestor_id),
                "name": name,
                "project_id": str(project_id),
                "identifier": identifier,
                "sequence_id": sequence_id,
            }
        )
    return result


def attach_parent_chain(rows: Optional[List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    """Mutate each row dict adding ``parent_chain``. Default to ``[]``."""
    if not rows:
        return rows
    ids_with_parent = [r.get("id") for r in rows if r.get("parent_id")]
    chains = fetch_parent_chains(ids_with_parent) if ids_with_parent else {}
    for row in rows:
        row["parent_chain"] = chains.get(str(row.get("id")), [])
    return rows


def attach_parent_chain_to_instances(instances: Iterable[Any]) -> Iterable[Any]:
    """Attach ``parent_chain`` attribute to each model instance."""
    instances_list = list(instances)
    if not instances_list:
        return instances_list
    ids_with_parent = [getattr(i, "id", None) for i in instances_list if getattr(i, "parent_id", None)]
    chains = fetch_parent_chains(ids_with_parent) if ids_with_parent else {}
    for inst in instances_list:
        inst.parent_chain = chains.get(str(getattr(inst, "id", "")), [])
    return instances_list


def search_issue_ids_by_text(project_id: Any, query: Optional[str]) -> List[str]:
    """Ids of issues in ``project_id`` matching ``query`` by name/identifier,
    plus every descendant of a match (so a hit on an ancestor surfaces the whole
    sub-tree — i.e. "search by parent path").

    Powers the inline search box. Matching is done with a single recursive CTE
    that seeds from the (indexable) name/identifier matches and walks *down* the
    ``Issue.parent`` chain to descendants. The resulting set
    ``{matches} ∪ {descendants of matches}`` is exactly
    ``{matches by name/id} ∪ {has an ancestor that matches}``.

    Returns ``[]`` for an empty query or on failure, so the listing keeps working
    without the search filter (same defensive contract as ``fetch_parent_chains``).
    """
    if not query or not str(query).strip():
        return []
    like = f"%{str(query).strip()}%"

    # ``deleted_at IS NULL`` is checked on every hop so a soft-deleted ancestor
    # doesn't bridge unrelated sub-trees (mirrors fetch_parent_chains).
    sql = """
        WITH RECURSIVE matched AS (
            SELECT i.id
            FROM issues i
            JOIN projects p ON p.id = i.project_id
            WHERE i.project_id = %(project_id)s
              AND i.deleted_at IS NULL
              AND (
                i.name ILIKE %(like)s
                OR (p.identifier || '-' || i.sequence_id::text) ILIKE %(like)s
              )
            UNION
            SELECT c.id
            FROM issues c
            JOIN matched m ON c.parent_id = m.id
            WHERE c.deleted_at IS NULL
        )
        SELECT id FROM matched;
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, {"project_id": str(project_id), "like": like})
            rows = cursor.fetchall()
    except Exception as exc:  # defensive: never break the listing because of search
        log_exception(exc)
        return []

    return [str(row[0]) for row in rows]


def issue_group_values(
    field: str,
    slug: str,
    project_id: Optional[str] = None,
    filters: Dict[str, Any] = {},
    queryset: Optional[QuerySet] = None,
) -> List[Union[str, Any]]:
    if field == "state_id":
        queryset = State.objects.filter(is_triage=False, workspace__slug=slug).values_list("id", flat=True)
        if project_id:
            return list(queryset.filter(project_id=project_id))
        return list(queryset)

    if field == "labels__id":
        queryset = Label.objects.filter(workspace__slug=slug).values_list("id", flat=True)
        if project_id:
            return list(queryset.filter(project_id=project_id)) + ["None"]
        return list(queryset) + ["None"]

    if field == "assignees__id":
        if project_id:
            return list(
                ProjectMember.objects.filter(workspace__slug=slug, project_id=project_id, is_active=True).values_list(
                    "member_id", flat=True
                )
            )
        return list(
            WorkspaceMember.objects.filter(workspace__slug=slug, is_active=True).values_list("member_id", flat=True)
        )

    if field == "issue_module__module_id":
        queryset = Module.objects.filter(workspace__slug=slug).values_list("id", flat=True)
        if project_id:
            return list(queryset.filter(project_id=project_id)) + ["None"]
        return list(queryset) + ["None"]

    if field == "cycle_id":
        queryset = Cycle.objects.filter(workspace__slug=slug).values_list("id", flat=True)
        if project_id:
            return list(queryset.filter(project_id=project_id)) + ["None"]
        return list(queryset) + ["None"]

    if field == "project_id":
        queryset = Project.objects.filter(workspace__slug=slug).values_list("id", flat=True)
        return list(queryset)

    if field == "priority":
        return ["low", "medium", "high", "urgent", "none"]

    if field == "state__group":
        return ["backlog", "unstarted", "started", "completed", "cancelled"]

    if field == "target_date":
        queryset = queryset.values_list("target_date", flat=True).distinct()
        if project_id:
            return list(queryset.filter(project_id=project_id))
        else:
            return list(queryset)

    if field == "start_date":
        queryset = queryset.values_list("start_date", flat=True).distinct()
        if project_id:
            return list(queryset.filter(project_id=project_id))
        else:
            return list(queryset)

    if field == "created_by":
        queryset = queryset.values_list("created_by", flat=True).distinct()
        if project_id:
            return list(queryset.filter(project_id=project_id))
        else:
            return list(queryset)

    return []
