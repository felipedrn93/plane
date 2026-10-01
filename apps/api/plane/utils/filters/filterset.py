# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import calendar
import copy
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import models
from django.db.models import Q
from django_filters import FilterSet, filters

from plane.db.models import Issue, Profile
from plane.utils.blocked import active_blocked_exists


class UUIDInFilter(filters.BaseInFilter, filters.UUIDFilter):
    pass


class CharInFilter(filters.BaseInFilter, filters.CharFilter):
    pass


class BaseFilterSet(FilterSet):
    @classmethod
    def get_filters(cls):
        """
        Get all filters for the filterset, including dynamically created __exact filters.
        """
        # Get the standard filters first
        filters = super().get_filters()

        # Add __exact versions for filters that have 'exact' lookup
        exact_filters = {}
        for filter_name, filter_obj in filters.items():
            if hasattr(filter_obj, "lookup_expr") and filter_obj.lookup_expr == "exact":
                exact_field_name = f"{filter_name}__exact"
                if exact_field_name not in filters:
                    # Copy the filter object as-is and assign it to the new name
                    exact_filters[exact_field_name] = copy.deepcopy(filter_obj)

        # Add the exact filters to the main filters dict
        filters.update(exact_filters)
        return filters

    def build_combined_q(self):
        """
        Build a combined Q object from all bound filters.

        For filters with custom methods, we call them and expect Q objects (or wrap
        QuerySets as subqueries for backward compatibility).
        For standard field filters, we build Q objects directly from field lookups.

        Returns:
            Q object representing all filter conditions combined.
        """
        # Ensure form validation has occurred
        self.errors

        combined_q = Q()

        # Handle case where cleaned_data might be None or empty
        if not self.form.cleaned_data:
            return combined_q

        # Only process filters that were actually provided in the request data
        # This avoids processing all declared filters with None/empty default values
        provided_filters = set(self.data.keys()) if self.data else set()

        for name, value in self.form.cleaned_data.items():
            # Skip filters that weren't provided in the request
            if name not in provided_filters:
                continue

            f = self.filters[name]

            # Build the Q object for this filter
            if f.method is not None:
                # Custom filter method - call it to get Q object
                res = f.filter(self.queryset, value)
                if isinstance(res, Q):
                    q_piece = res
                elif isinstance(res, models.QuerySet):
                    # Backward compatibility: wrap QuerySet as subquery
                    q_piece = Q(pk__in=res.values("pk"))
                else:
                    raise TypeError(
                        f"Filter method '{name}' must return Q object or QuerySet, got {type(res).__name__}"
                    )
            else:
                # Standard field filter - build Q object directly
                lookup = f"{f.field_name}__{f.lookup_expr}"
                q_piece = Q(**{lookup: value})

            # Apply exclude/include logic
            if getattr(f, "exclude", False):
                combined_q &= ~q_piece
            else:
                combined_q &= q_piece

        return combined_q

    def filter_queryset(self, queryset):
        """
        Override to use Q-based filtering for compatibility with DjangoFilterBackend.

        This allows the same filterset to work with both ComplexFilterBackend
        (which calls build_combined_q directly) and DjangoFilterBackend
        (which calls this method).
        """
        # Ensure form validation
        self.errors

        # Build combined Q and apply to queryset
        combined_q = self.build_combined_q()
        qs = queryset.filter(combined_q)

        # Apply distinct if any filter requires it (typically for many-to-many relations)
        for f in self.filters.values():
            if getattr(f, "distinct", False):
                return qs.distinct()

        return qs


RELATIVE_DATE_CHOICES = (("today", "today"), ("end_of_week", "end_of_week"), ("end_of_month", "end_of_month"))


def resolve_relative_date(value, today, week_start=0):
    """Last day covered by a relative bound. `week_start` follows Profile.start_of_the_week (0 = Sunday)."""
    if value == "end_of_week":
        last_weekday = (week_start - 2) % 7  # day before the week start, in Python's weekday() (0 = Monday)
        return today + timedelta(days=(last_weekday - today.weekday()) % 7)
    if value == "end_of_month":
        return today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return today


class IssueFilterSet(BaseFilterSet):
    # Custom filter methods to handle soft delete exclusion for relations

    assignee_id = filters.UUIDFilter(method="filter_assignee_id")
    assignee_id__in = UUIDInFilter(method="filter_assignee_id_in", lookup_expr="in")

    cycle_id = filters.UUIDFilter(method="filter_cycle_id")
    cycle_id__in = UUIDInFilter(method="filter_cycle_id_in", lookup_expr="in")

    module_id = filters.UUIDFilter(method="filter_module_id")
    module_id__in = UUIDInFilter(method="filter_module_id_in", lookup_expr="in")

    mention_id = filters.UUIDFilter(method="filter_mention_id")
    mention_id__in = UUIDInFilter(method="filter_mention_id_in", lookup_expr="in")

    label_id = filters.UUIDFilter(method="filter_label_id")
    label_id__in = UUIDInFilter(method="filter_label_id_in", lookup_expr="in")

    # Direct field lookups remain the same
    created_by_id = filters.UUIDFilter(field_name="created_by_id")
    created_by_id__in = UUIDInFilter(field_name="created_by_id", lookup_expr="in")

    is_archived = filters.BooleanFilter(method="filter_is_archived")

    state_group = filters.CharFilter(field_name="state__group")
    state_group__in = CharInFilter(field_name="state__group", lookup_expr="in")

    state_id = filters.UUIDFilter(field_name="state_id")
    state_id__in = UUIDInFilter(field_name="state_id", lookup_expr="in")

    client_id = filters.UUIDFilter(field_name="client_id")
    client_id__in = UUIDInFilter(field_name="client_id", lookup_expr="in")

    project_id = filters.UUIDFilter(field_name="project_id")
    project_id__in = UUIDInFilter(field_name="project_id", lookup_expr="in")

    subscriber_id = filters.UUIDFilter(method="filter_subscriber_id")
    subscriber_id__in = UUIDInFilter(method="filter_subscriber_id_in", lookup_expr="in")

    # Blocked filter: true -> only work items actively blocked, false -> only those not blocked
    is_blocked = filters.BooleanFilter(method="filter_is_blocked", distinct=True)

    # Date "on or after" / "on or before" (inclusive); datetime fields compare by day
    start_date__gte = filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date__lte = filters.DateFilter(field_name="start_date", lookup_expr="lte")
    target_date__gte = filters.DateFilter(field_name="target_date", lookup_expr="gte")
    target_date__lte = filters.DateFilter(field_name="target_date", lookup_expr="lte")
    created_at__gte = filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_at__lte = filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    updated_at__gte = filters.DateFilter(field_name="updated_at", lookup_expr="date__gte")
    updated_at__lte = filters.DateFilter(field_name="updated_at", lookup_expr="date__lte")
    completed_at__gte = filters.DateFilter(field_name="completed_at", lookup_expr="date__gte")
    completed_at__lte = filters.DateFilter(field_name="completed_at", lookup_expr="date__lte")

    # "Until end of today / this week / this month", resolved at query time in the user's timezone
    start_date__lte_relative = filters.ChoiceFilter(choices=RELATIVE_DATE_CHOICES, method="filter_lte_relative")
    target_date__lte_relative = filters.ChoiceFilter(choices=RELATIVE_DATE_CHOICES, method="filter_lte_relative")
    created_at__lte_relative = filters.ChoiceFilter(choices=RELATIVE_DATE_CHOICES, method="filter_lte_relative")
    updated_at__lte_relative = filters.ChoiceFilter(choices=RELATIVE_DATE_CHOICES, method="filter_lte_relative")
    completed_at__lte_relative = filters.ChoiceFilter(choices=RELATIVE_DATE_CHOICES, method="filter_lte_relative")

    class Meta:
        model = Issue
        fields = {
            "start_date": ["exact", "range"],
            "target_date": ["exact", "range"],
            "created_at": ["exact", "range"],
            "updated_at": ["exact", "range"],
            "completed_at": ["exact", "range"],
            "is_draft": ["exact"],
            "priority": ["exact", "in"],
        }

    def filter_lte_relative(self, queryset, name, value):
        field = name.removesuffix("__lte_relative")
        user = getattr(self.request, "user", None)
        tz = ZoneInfo(getattr(user, "user_timezone", None) or "UTC")
        week_start = (
            Profile.objects.filter(user_id=user.id).values_list("start_of_the_week", flat=True).first()
            if getattr(user, "is_authenticated", False)
            else None
        ) or 0
        last_day = resolve_relative_date(value, datetime.now(tz).date(), week_start)
        if isinstance(Issue._meta.get_field(field), models.DateTimeField):
            # Everything before the next day starts, in the user's timezone
            return Q(**{f"{field}__lt": datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=tz)})
        return Q(**{f"{field}__lte": last_day})

    def filter_is_archived(self, queryset, name, value):
        """
        Convenience filter: archived=true -> archived_at is not null,
        archived=false -> archived_at is null
        """
        if value in (True, "true", "True", 1, "1"):
            return Q(archived_at__isnull=False)
        if value in (False, "false", "False", 0, "0"):
            return Q(archived_at__isnull=True)
        return Q()  # No filter

    def filter_is_blocked(self, queryset, name, value):
        """
        Convenience filter for active blocking:
        - is_blocked=true  -> work items with a non-deleted "blocked_by" relation
          whose blocker is still open (state group backlog/unstarted/started)
        - is_blocked=false -> the complement (not actively blocked)

        Uses EXISTS/NOT EXISTS (correlated subquery on issue_relations.issue_id)
        instead of a relation join: it never multiplies rows (so it does not depend
        on the outer queryset being distinct()) and the negated case stays a cheap
        NOT EXISTS, which matters on workspace-wide views (e.g. "Your work").
        Shares the subquery with the ``is_blocked`` annotation (see
        plane.utils.blocked.active_blocked_exists).
        """
        if value in (True, "true", "True", 1, "1"):
            return Q(active_blocked_exists())
        if value in (False, "false", "False", 0, "0"):
            return ~Q(active_blocked_exists())
        return Q()  # No filter

    # Filter methods with soft delete exclusion for relations

    def filter_assignee_id(self, queryset, name, value):
        """Filter by assignee ID, excluding soft deleted users"""
        return Q(
            issue_assignee__assignee_id=value,
            issue_assignee__deleted_at__isnull=True,
        )

    def filter_assignee_id_in(self, queryset, name, value):
        """Filter by assignee IDs (in), excluding soft deleted users"""
        return Q(
            issue_assignee__assignee_id__in=value,
            issue_assignee__deleted_at__isnull=True,
        )

    def filter_cycle_id(self, queryset, name, value):
        """Filter by cycle ID, excluding soft deleted cycles"""
        return Q(
            issue_cycle__cycle_id=value,
            issue_cycle__deleted_at__isnull=True,
        )

    def filter_cycle_id_in(self, queryset, name, value):
        """Filter by cycle IDs (in), excluding soft deleted cycles"""
        return Q(
            issue_cycle__cycle_id__in=value,
            issue_cycle__deleted_at__isnull=True,
        )

    def filter_module_id(self, queryset, name, value):
        """Filter by module ID, excluding soft deleted modules"""
        return Q(
            issue_module__module_id=value,
            issue_module__deleted_at__isnull=True,
        )

    def filter_module_id_in(self, queryset, name, value):
        """Filter by module IDs (in), excluding soft deleted modules"""
        return Q(
            issue_module__module_id__in=value,
            issue_module__deleted_at__isnull=True,
        )

    def filter_mention_id(self, queryset, name, value):
        """Filter by mention ID, excluding soft deleted users"""
        return Q(
            issue_mention__mention_id=value,
            issue_mention__deleted_at__isnull=True,
        )

    def filter_mention_id_in(self, queryset, name, value):
        """Filter by mention IDs (in), excluding soft deleted users"""
        return Q(
            issue_mention__mention_id__in=value,
            issue_mention__deleted_at__isnull=True,
        )

    def filter_label_id(self, queryset, name, value):
        """Filter by label ID, excluding soft deleted labels"""
        return Q(
            label_issue__label_id=value,
            label_issue__deleted_at__isnull=True,
        )

    def filter_label_id_in(self, queryset, name, value):
        """Filter by label IDs (in), excluding soft deleted labels"""
        return Q(
            label_issue__label_id__in=value,
            label_issue__deleted_at__isnull=True,
        )

    def filter_subscriber_id(self, queryset, name, value):
        """Filter by subscriber ID, excluding soft deleted users"""
        return Q(
            issue_subscribers__subscriber_id=value,
            issue_subscribers__deleted_at__isnull=True,
        )

    def filter_subscriber_id_in(self, queryset, name, value):
        """Filter by subscriber IDs (in), excluding soft deleted users"""
        return Q(
            issue_subscribers__subscriber_id__in=value,
            issue_subscribers__deleted_at__isnull=True,
        )
