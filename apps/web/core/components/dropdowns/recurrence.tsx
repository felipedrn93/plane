/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Fragment, useMemo } from "react";
import { observer } from "mobx-react";
import { Popover, Transition } from "@headlessui/react";
import { Repeat } from "lucide-react";
import { useTranslation } from "@plane/i18n";
import { Tooltip } from "@plane/propel/tooltip";
import type {
  TRecurrenceFrequency,
  TRecurrencePattern,
  TRecurrenceWeekday,
} from "@plane/types";
import { cn, getDate } from "@plane/utils";

type Props = {
  value: TRecurrencePattern | null;
  onChange: (val: TRecurrencePattern | null) => void;
  disabled?: boolean;
  targetDate: string | null;
  className?: string;
  buttonClassName?: string;
  buttonContainerClassName?: string;
};

const WEEKDAYS: TRecurrenceWeekday[] = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"];
const FREQUENCIES: TRecurrenceFrequency[] = ["daily", "weekly", "monthly", "yearly"];

const DEFAULT_PATTERN: TRecurrencePattern = { frequency: "weekly", interval: 1 };

const WEEKDAY_INDEX: Record<TRecurrenceWeekday, number> = {
  MO: 1,
  TU: 2,
  WE: 3,
  TH: 4,
  FR: 5,
  SA: 6,
  SU: 0,
};

const SETPOS_KEYS = ["first", "second", "third", "fourth", "last"] as const;
type SetposKey = (typeof SETPOS_KEYS)[number];

function setposKey(pos: number | undefined): SetposKey {
  if (pos === -1) return "last";
  if (pos === 2) return "second";
  if (pos === 3) return "third";
  if (pos === 4) return "fourth";
  return "first";
}

function setposValue(key: SetposKey): number {
  return key === "last" ? -1 : SETPOS_KEYS.indexOf(key) + 1;
}

function unitKey(frequency: TRecurrenceFrequency): "day" | "week" | "month" | "year" {
  return frequency === "daily"
    ? "day"
    : frequency === "weekly"
      ? "week"
      : frequency === "monthly"
        ? "month"
        : "year";
}

function formatSummary(pattern: TRecurrencePattern, t: (key: string, params?: Record<string, unknown>) => string): string {
  const interval = Math.max(1, pattern.interval ?? 1);
  if (pattern.frequency === "weekly" && pattern.by_weekday?.length) {
    const days = pattern.by_weekday
      .map((d) => t(`issue.recurrence.weekday.short.${d}`))
      .join("/");
    return t("issue.recurrence.summary.weekly_with_days", { count: interval, days });
  }
  if (pattern.frequency === "monthly" && pattern.by_monthday) {
    return t("issue.recurrence.summary.monthly_on_day", { count: interval, day: pattern.by_monthday });
  }
  if (
    pattern.frequency === "monthly" &&
    pattern.by_setpos !== undefined &&
    pattern.by_weekday?.length
  ) {
    return t("issue.recurrence.summary.monthly_on_setpos", {
      count: interval,
      position: t(`issue.recurrence.setpos.${setposKey(pattern.by_setpos)}`),
      weekday: t(`issue.recurrence.weekday.long.${pattern.by_weekday[0]}`),
    });
  }
  return t("issue.recurrence.summary.interval", {
    count: interval,
    unit: t(`issue.recurrence.unit.${unitKey(pattern.frequency)}`, { count: interval }),
  });
}

function nextOccurrence(anchor: Date, pattern: TRecurrencePattern): Date | null {
  const interval = Math.max(1, pattern.interval ?? 1);
  const base = new Date(anchor);
  base.setHours(0, 0, 0, 0);

  if (pattern.frequency === "daily") {
    const next = new Date(base);
    next.setDate(next.getDate() + interval);
    return next;
  }

  if (pattern.frequency === "weekly") {
    const allowed = (pattern.by_weekday?.length ? pattern.by_weekday : null)?.map((d) => WEEKDAY_INDEX[d]);
    if (!allowed?.length) {
      const next = new Date(base);
      next.setDate(next.getDate() + 7 * interval);
      return next;
    }
    for (let i = 1; i <= 7 * interval; i++) {
      const candidate = new Date(base);
      candidate.setDate(candidate.getDate() + i);
      if (allowed.includes(candidate.getDay())) return candidate;
    }
    return null;
  }

  if (pattern.frequency === "monthly") {
    if (pattern.by_setpos !== undefined && pattern.by_weekday?.length) {
      const target = new Date(base.getFullYear(), base.getMonth() + interval, 1);
      const found = findNthWeekdayOfMonth(
        target.getFullYear(),
        target.getMonth(),
        WEEKDAY_INDEX[pattern.by_weekday[0]],
        pattern.by_setpos
      );
      return found;
    }
    if (pattern.by_monthday) {
      const target = new Date(base.getFullYear(), base.getMonth() + interval, 1);
      const day = pattern.by_monthday === -1
        ? new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate()
        : Math.min(pattern.by_monthday, new Date(target.getFullYear(), target.getMonth() + 1, 0).getDate());
      return new Date(target.getFullYear(), target.getMonth(), day);
    }
    const fallback = new Date(base);
    fallback.setMonth(fallback.getMonth() + interval);
    return fallback;
  }

  if (pattern.frequency === "yearly") {
    const next = new Date(base);
    next.setFullYear(next.getFullYear() + interval);
    return next;
  }

  return null;
}

function findNthWeekdayOfMonth(year: number, month: number, weekday: number, position: number): Date | null {
  if (position === -1) {
    const last = new Date(year, month + 1, 0);
    for (let day = last.getDate(); day >= 1; day--) {
      const d = new Date(year, month, day);
      if (d.getDay() === weekday) return d;
    }
    return null;
  }
  let count = 0;
  const first = new Date(year, month, 1);
  for (let day = 1; day <= 31; day++) {
    const d = new Date(year, month, day);
    if (d.getMonth() !== first.getMonth()) break;
    if (d.getDay() === weekday) {
      count += 1;
      if (count === position) return d;
    }
  }
  return null;
}

function formatPreviewDate(d: Date, locale: string | undefined): string {
  try {
    return new Intl.DateTimeFormat(locale ?? undefined, { dateStyle: "medium" }).format(d);
  } catch {
    return d.toDateString();
  }
}

export const RecurrenceDropdown = observer(function RecurrenceDropdown(props: Props) {
  const {
    value,
    onChange,
    disabled = false,
    targetDate,
    className,
    buttonClassName,
    buttonContainerClassName,
  } = props;
  const { t, currentLocale } = useTranslation();

  const pattern = value;
  const isEnabled = !!pattern;
  const isDisabled = disabled || !targetDate;

  const label = useMemo(() => {
    if (!pattern) return t("issue.recurrence.no_recurrence");
    return formatSummary(pattern, t);
  }, [pattern, t]);

  const previewLabel = useMemo(() => {
    if (!pattern || !targetDate) return null;
    const anchor = getDate(targetDate);
    if (!anchor) return null;
    const next = nextOccurrence(anchor, pattern);
    return next ? formatPreviewDate(next, currentLocale) : null;
  }, [pattern, targetDate, currentLocale]);

  const update = (next: Partial<TRecurrencePattern>) => {
    if (!pattern) return;
    const merged: TRecurrencePattern = { ...pattern, ...next };
    // When switching frequency, drop fields specific to the previous one.
    if (next.frequency && next.frequency !== pattern.frequency) {
      delete merged.by_weekday;
      delete merged.by_monthday;
      delete merged.by_setpos;
    }
    onChange(merged);
  };

  const toggleWeekday = (day: TRecurrenceWeekday) => {
    if (!pattern) return;
    const current = pattern.by_weekday ?? [];
    const exists = current.includes(day);
    const next = exists ? current.filter((d) => d !== day) : [...current, day];
    onChange({ ...pattern, by_weekday: next.length ? next : undefined });
  };

  const setMonthlyMode = (mode: "monthday" | "setpos") => {
    if (!pattern) return;
    if (mode === "monthday") {
      onChange({
        ...pattern,
        by_monthday: pattern.by_monthday ?? Math.min(getDate(targetDate)?.getDate() ?? 1, 28),
        by_weekday: undefined,
        by_setpos: undefined,
      });
    } else {
      const anchor = getDate(targetDate);
      const weekday = anchor ? (WEEKDAYS[(anchor.getDay() + 6) % 7]) : "MO";
      onChange({
        ...pattern,
        by_monthday: undefined,
        by_weekday: [weekday],
        by_setpos: pattern.by_setpos ?? 1,
      });
    }
  };

  const enable = () => onChange(DEFAULT_PATTERN);
  const disableRecurrence = () => onChange(null);

  return (
    <Popover className={cn("relative w-full", className)}>
      {({ open }) => (
        <>
          <Tooltip
            disabled={!!targetDate || disabled}
            tooltipContent={t("issue.recurrence.needs_target_date")}
          >
            <span className={cn("flex w-full", buttonContainerClassName)}>
              <Popover.Button
                as="button"
                type="button"
                disabled={isDisabled}
                className={cn(
                  "group flex h-7.5 w-full items-center gap-2 rounded px-2 text-left text-body-xs-medium",
                  "hover:bg-layer-2 focus-visible:bg-layer-2 outline-none",
                  isDisabled && "cursor-not-allowed opacity-60",
                  !isEnabled && "text-placeholder",
                  buttonClassName
                )}
              >
                <Repeat className="size-3.5 shrink-0" />
                <span className="truncate">{label}</span>
              </Popover.Button>
            </span>
          </Tooltip>

          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="opacity-0 translate-y-1"
            enterTo="opacity-100 translate-y-0"
            leave="transition ease-in duration-75"
            leaveFrom="opacity-100 translate-y-0"
            leaveTo="opacity-0 translate-y-1"
          >
            <Popover.Panel className="absolute right-0 z-20 mt-1 w-72 origin-top-right rounded-md border border-strong bg-layer-1 p-3 shadow-lg focus:outline-none">
              <div className="flex items-center justify-between gap-2 pb-2">
                <span className="text-body-xs-medium text-primary">{t("issue.recurrence.label")}</span>
                <label className="flex items-center gap-2 text-body-xs-medium text-secondary">
                  <input
                    type="checkbox"
                    checked={isEnabled}
                    onChange={(e) => (e.target.checked ? enable() : disableRecurrence())}
                    className="size-3.5 accent-primary"
                  />
                  {t("issue.recurrence.enable")}
                </label>
              </div>

              {isEnabled && pattern && (
                <div className="space-y-3 pt-2">
                  <div className="flex items-center gap-2 text-body-xs-regular">
                    <span className="text-secondary">{t("issue.recurrence.repeat_every")}</span>
                    <input
                      type="number"
                      min={1}
                      value={pattern.interval}
                      onChange={(e) => {
                        const n = parseInt(e.target.value, 10);
                        if (!Number.isNaN(n) && n >= 1) update({ interval: n });
                      }}
                      className="h-7 w-14 rounded border border-strong bg-layer-1 px-2 text-center"
                    />
                    <select
                      value={pattern.frequency}
                      onChange={(e) => update({ frequency: e.target.value as TRecurrenceFrequency })}
                      className="h-7 flex-1 rounded border border-strong bg-layer-1 px-2"
                    >
                      {FREQUENCIES.map((f) => (
                        <option key={f} value={f}>
                          {t(`issue.recurrence.frequency.${f}`)}
                        </option>
                      ))}
                    </select>
                  </div>

                  {pattern.frequency === "weekly" && (
                    <div className="flex flex-wrap gap-1">
                      {WEEKDAYS.map((d) => {
                        const active = pattern.by_weekday?.includes(d);
                        return (
                          <button
                            key={d}
                            type="button"
                            onClick={() => toggleWeekday(d)}
                            className={cn(
                              "size-8 rounded-full border text-body-xs-medium transition-colors",
                              active
                                ? "border-primary bg-primary text-on-primary"
                                : "border-strong text-secondary hover:bg-layer-2"
                            )}
                          >
                            {t(`issue.recurrence.weekday.short.${d}`)}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {pattern.frequency === "monthly" && (
                    <div className="space-y-2 text-body-xs-regular">
                      <label className="flex flex-wrap items-center gap-2">
                        <input
                          type="radio"
                          checked={pattern.by_monthday !== undefined}
                          onChange={() => setMonthlyMode("monthday")}
                          className="accent-primary"
                        />
                        <span>{t("issue.recurrence.monthly.monthday_prefix")}</span>
                        <input
                          type="number"
                          min={1}
                          max={31}
                          value={pattern.by_monthday ?? ""}
                          disabled={pattern.by_monthday === undefined}
                          onChange={(e) => {
                            const n = parseInt(e.target.value, 10);
                            if (!Number.isNaN(n) && n >= 1 && n <= 31)
                              onChange({ ...pattern, by_monthday: n, by_weekday: undefined, by_setpos: undefined });
                          }}
                          className="h-6 w-14 rounded border border-strong bg-layer-1 px-1 text-center"
                        />
                        <span>{t("issue.recurrence.monthly.monthday_suffix")}</span>
                      </label>

                      <label className="flex flex-wrap items-center gap-2">
                        <input
                          type="radio"
                          checked={pattern.by_setpos !== undefined}
                          onChange={() => setMonthlyMode("setpos")}
                          className="accent-primary"
                        />
                        <span>{t("issue.recurrence.monthly.setpos_prefix")}</span>
                        <select
                          value={setposKey(pattern.by_setpos)}
                          disabled={pattern.by_setpos === undefined}
                          onChange={(e) =>
                            onChange({ ...pattern, by_setpos: setposValue(e.target.value as SetposKey) })
                          }
                          className="h-6 rounded border border-strong bg-layer-1 px-1"
                        >
                          {SETPOS_KEYS.map((k) => (
                            <option key={k} value={k}>
                              {t(`issue.recurrence.setpos.${k}`)}
                            </option>
                          ))}
                        </select>
                        <select
                          value={pattern.by_weekday?.[0] ?? "MO"}
                          disabled={pattern.by_setpos === undefined}
                          onChange={(e) =>
                            onChange({ ...pattern, by_weekday: [e.target.value as TRecurrenceWeekday] })
                          }
                          className="h-6 rounded border border-strong bg-layer-1 px-1"
                        >
                          {WEEKDAYS.map((d) => (
                            <option key={d} value={d}>
                              {t(`issue.recurrence.weekday.long.${d}`)}
                            </option>
                          ))}
                        </select>
                        <span>{t("issue.recurrence.monthly.setpos_suffix")}</span>
                      </label>
                    </div>
                  )}

                  {previewLabel && (
                    <div className="border-t border-strong pt-2 text-body-xs-regular text-secondary">
                      {t("issue.recurrence.next_occurrence")} <span className="text-primary">{previewLabel}</span>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={disableRecurrence}
                    className="w-full rounded border border-strong px-2 py-1 text-body-xs-medium text-danger-primary hover:bg-layer-2"
                  >
                    {t("issue.recurrence.disable")}
                  </button>
                </div>
              )}
            </Popover.Panel>
          </Transition>
        </>
      )}
    </Popover>
  );
});
