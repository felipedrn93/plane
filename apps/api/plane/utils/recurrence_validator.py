# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Kept dependency-free so it can be imported by serializers without pulling
# Celery/bgtasks (which import serializers and would create a cycle).

_FREQUENCIES = {"daily", "weekly", "monthly", "yearly"}
_WEEKDAYS = {"MO", "TU", "WE", "TH", "FR", "SA", "SU"}


def validate_recurrence_pattern(value):
    """Return (is_valid, error_message). `value` may be None or a dict."""
    if value is None:
        return True, None
    if not isinstance(value, dict):
        return False, "recurrence_pattern must be an object"

    if value.get("frequency") not in _FREQUENCIES:
        return False, "recurrence_pattern.frequency must be one of daily, weekly, monthly, yearly"

    interval = value.get("interval", 1)
    try:
        interval_int = int(interval)
    except (TypeError, ValueError):
        return False, "recurrence_pattern.interval must be a positive integer"
    if interval_int < 1:
        return False, "recurrence_pattern.interval must be a positive integer"

    weekdays = value.get("by_weekday")
    if weekdays is not None:
        if not isinstance(weekdays, list) or not all(d in _WEEKDAYS for d in weekdays):
            return False, "recurrence_pattern.by_weekday must be a list of MO/TU/WE/TH/FR/SA/SU"

    monthday = value.get("by_monthday")
    if monthday is not None:
        try:
            monthday_int = int(monthday)
        except (TypeError, ValueError):
            return False, "recurrence_pattern.by_monthday must be an integer"
        if monthday_int == 0 or monthday_int < -31 or monthday_int > 31:
            return False, "recurrence_pattern.by_monthday must be in 1..31 or -1"

    setpos = value.get("by_setpos")
    if setpos is not None:
        try:
            setpos_int = int(setpos)
        except (TypeError, ValueError):
            return False, "recurrence_pattern.by_setpos must be an integer"
        if setpos_int == 0 or setpos_int < -4 or setpos_int > 4:
            return False, "recurrence_pattern.by_setpos must be in -4..-1 or 1..4"

    return True, None
