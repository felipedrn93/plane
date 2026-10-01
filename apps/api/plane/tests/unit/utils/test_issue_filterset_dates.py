# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import datetime

import pytest
from django.db.models import Q

from plane.db.models import Issue
from plane.utils.filters import IssueFilterSet
from plane.utils.filters.filterset import resolve_relative_date


def build_q(data):
    return IssueFilterSet(data=data, queryset=Issue.objects.none()).build_combined_q()


@pytest.mark.unit
class TestIssueFilterSetDateBounds:
    def test_date_field_gte_lte(self):
        q = build_q({"start_date__gte": "2026-10-01", "target_date__lte": "2026-10-31"})
        assert q == Q(start_date__gte=datetime.date(2026, 10, 1)) & Q(target_date__lte=datetime.date(2026, 10, 31))

    def test_datetime_field_compares_by_day(self):
        # "até 01/10" deve incluir itens criados ao longo do dia 01/10
        assert build_q({"created_at__lte": "2026-10-01"}) == Q(created_at__date__lte=datetime.date(2026, 10, 1))
        assert build_q({"completed_at__gte": "2026-10-01"}) == Q(completed_at__date__gte=datetime.date(2026, 10, 1))


@pytest.mark.unit
class TestResolveRelativeDate:
    WED = datetime.date(2026, 9, 30)  # quarta-feira

    def test_today(self):
        assert resolve_relative_date("today", self.WED) == self.WED

    def test_end_of_week_sunday_start(self):
        # semana domingo-sábado termina no sábado; no próprio sábado é o mesmo dia
        assert resolve_relative_date("end_of_week", self.WED, 0) == datetime.date(2026, 10, 3)
        assert resolve_relative_date("end_of_week", datetime.date(2026, 10, 3), 0) == datetime.date(2026, 10, 3)
        assert resolve_relative_date("end_of_week", datetime.date(2026, 10, 4), 0) == datetime.date(2026, 10, 10)

    def test_end_of_week_monday_start(self):
        assert resolve_relative_date("end_of_week", self.WED, 1) == datetime.date(2026, 10, 4)
        assert resolve_relative_date("end_of_week", datetime.date(2026, 10, 4), 1) == datetime.date(2026, 10, 4)

    def test_end_of_month(self):
        assert resolve_relative_date("end_of_month", self.WED) == self.WED
        assert resolve_relative_date("end_of_month", datetime.date(2028, 2, 3)) == datetime.date(2028, 2, 29)
