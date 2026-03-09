"""Pure schedule helpers for DTEK Monitor."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any
from zoneinfo import ZoneInfo

from .const import (
    DEFAULT_NEXT_EVENT_LOOKAHEAD_DAYS,
    EVENT_DESCRIPTION_PLANNED,
    EVENT_DESCRIPTION_POSSIBLE,
    EVENT_SUMMARY_OUTAGE,
    EVENT_SUMMARY_POSSIBLE,
)

KYIV_TZ = ZoneInfo("Europe/Kyiv")

ScheduleSlot = tuple[str, int, int]

_STATUS_MAP: dict[str, ScheduleSlot | None] = {
    "yes": None,
    "no": ("outage", 0, 60),
    "maybe": ("possible", 0, 60),
    "first": ("outage", 0, 30),
    "second": ("outage", 30, 60),
    "mfirst": ("possible", 0, 30),
    "msecond": ("possible", 30, 60),
}


@dataclass(frozen=True)
class ScheduleWindow:
    """A normalized outage or possible-outage window."""

    event_type: str
    start: dt.datetime
    end: dt.datetime
    summary: str
    description: str


def get_day_slots(
    date: dt.date,
    groups: list[str],
    fact: dict[str, Any],
    preset: dict[str, Any],
    event_type: str | None = None,
) -> list[ScheduleSlot]:
    """Collect schedule slots for a date with fact data overriding preset data."""
    fact_slots_all = _get_fact_slots(date, groups, fact)
    fact_slots_filtered = _filter_slots(fact_slots_all, event_type)

    preset_slots = _get_preset_slots(date, groups, preset, event_type)
    if not fact_slots_all:
        return [*fact_slots_filtered, *preset_slots]

    occupied_intervals = _merge_intervals(
        [(start_min, end_min) for _, start_min, end_min in fact_slots_all]
    )
    resolved_preset_slots: list[ScheduleSlot] = []
    for slot in preset_slots:
        resolved_preset_slots.extend(_subtract_intervals(slot, occupied_intervals))

    return [*fact_slots_filtered, *resolved_preset_slots]


def get_schedule_windows_for_date(
    date: dt.date,
    groups: list[str],
    fact: dict[str, Any],
    preset: dict[str, Any],
    event_type: str | None = None,
) -> list[ScheduleWindow]:
    """Build merged schedule windows for a single date."""
    slots = get_day_slots(date, groups, fact, preset, event_type)
    if not slots:
        return []
    return _slots_to_windows(slots, date)


def get_schedule_windows_for_range(
    start: dt.datetime,
    end: dt.datetime,
    groups: list[str],
    fact: dict[str, Any],
    preset: dict[str, Any],
    event_type: str | None = None,
) -> list[ScheduleWindow]:
    """Build merged schedule windows for an arbitrary datetime range."""
    windows: list[ScheduleWindow] = []
    current_date = start.date()
    end_date = end.date()

    while current_date <= end_date:
        day_windows = get_schedule_windows_for_date(
            current_date,
            groups,
            fact,
            preset,
            event_type,
        )
        for window in day_windows:
            if window.end > start and window.start < end:
                windows.append(window)
        current_date += dt.timedelta(days=1)

    return windows


def find_current_or_next_window(
    now: dt.datetime,
    groups: list[str],
    fact: dict[str, Any],
    preset: dict[str, Any],
    event_type: str | None = None,
    lookahead_days: int = DEFAULT_NEXT_EVENT_LOOKAHEAD_DAYS,
) -> ScheduleWindow | None:
    """Return the current or next schedule window within the lookahead period."""
    next_window: ScheduleWindow | None = None

    for day_offset in range(lookahead_days + 1):
        check_date = now.date() + dt.timedelta(days=day_offset)
        day_windows = get_schedule_windows_for_date(
            check_date,
            groups,
            fact,
            preset,
            event_type,
        )

        for window in day_windows:
            if window.start <= now < window.end:
                return window
            if window.start > now and (
                next_window is None or window.start < next_window.start
            ):
                next_window = window

    return next_window


def _get_fact_slots(
    date: dt.date,
    groups: list[str],
    fact: dict[str, Any],
) -> list[ScheduleSlot]:
    """Extract fact slots for a given date."""
    if not isinstance(fact, dict):
        return []

    for ts_str, day_data in fact.items():
        try:
            ts = int(ts_str)
        except (TypeError, ValueError):
            continue

        fact_date = dt.datetime.fromtimestamp(ts, tz=KYIV_TZ).date()
        if fact_date != date:
            continue

        if not isinstance(day_data, dict):
            return []
        return _extract_group_slots(day_data, groups)

    return []


def _get_preset_slots(
    date: dt.date,
    groups: list[str],
    preset: dict[str, Any],
    event_type: str | None,
) -> list[ScheduleSlot]:
    """Extract preset slots for a given date."""
    if not isinstance(preset, dict):
        return []

    dow = str(date.isoweekday())
    blocks: list[ScheduleSlot] = []
    for group in groups:
        group_data = preset.get(group, {})
        if not isinstance(group_data, dict):
            continue

        dow_data = group_data.get(dow, {})
        if not isinstance(dow_data, dict):
            continue

        blocks.extend(_extract_hour_slots(dow_data, event_type))

    return blocks


def _extract_group_slots(
    day_data: dict[str, Any],
    groups: list[str],
    event_type: str | None = None,
) -> list[ScheduleSlot]:
    """Extract fact slots for all relevant groups in a day payload."""
    blocks: list[ScheduleSlot] = []
    for group in groups:
        group_data = day_data.get(group, {})
        if not isinstance(group_data, dict):
            continue
        blocks.extend(_extract_hour_slots(group_data, event_type))
    return blocks


def _extract_hour_slots(
    hour_data: dict[str, Any],
    event_type: str | None = None,
) -> list[ScheduleSlot]:
    """Extract normalized slots from hourly schedule data."""
    blocks: list[ScheduleSlot] = []
    for hour_key in range(1, 25):
        status = hour_data.get(str(hour_key), "yes")
        mapped = _STATUS_MAP.get(status)
        if mapped is None:
            continue

        mapped_type, offset_start, offset_end = mapped
        if event_type and mapped_type != event_type:
            continue

        hour_base = (hour_key - 1) * 60
        blocks.append(
            (mapped_type, hour_base + offset_start, hour_base + offset_end)
        )
    return blocks


def _filter_slots(
    slots: list[ScheduleSlot],
    event_type: str | None,
) -> list[ScheduleSlot]:
    """Filter slots by type when requested."""
    if event_type is None:
        return slots
    return [slot for slot in slots if slot[0] == event_type]


def _merge_intervals(
    intervals: list[tuple[int, int]],
) -> list[tuple[int, int]]:
    """Merge overlapping or adjacent intervals."""
    if not intervals:
        return []

    merged: list[tuple[int, int]] = []
    for start_min, end_min in sorted(intervals):
        if not merged or merged[-1][1] < start_min:
            merged.append((start_min, end_min))
            continue
        merged[-1] = (merged[-1][0], max(merged[-1][1], end_min))

    return merged


def _subtract_intervals(
    slot: ScheduleSlot,
    occupied_intervals: list[tuple[int, int]],
) -> list[ScheduleSlot]:
    """Subtract occupied intervals from a slot, preserving uncovered fragments."""
    event_type, start_min, end_min = slot
    remaining = [(start_min, end_min)]

    for occupied_start, occupied_end in occupied_intervals:
        updated_remaining: list[tuple[int, int]] = []
        for fragment_start, fragment_end in remaining:
            if occupied_end <= fragment_start or occupied_start >= fragment_end:
                updated_remaining.append((fragment_start, fragment_end))
                continue

            if occupied_start > fragment_start:
                updated_remaining.append((fragment_start, occupied_start))
            if occupied_end < fragment_end:
                updated_remaining.append((occupied_end, fragment_end))

        remaining = updated_remaining
        if not remaining:
            break

    return [
        (event_type, fragment_start, fragment_end)
        for fragment_start, fragment_end in remaining
        if fragment_start < fragment_end
    ]


def _slots_to_windows(
    slots: list[ScheduleSlot],
    date: dt.date,
) -> list[ScheduleWindow]:
    """Convert slots into merged schedule windows."""
    merged_slots: list[ScheduleSlot] = []
    for event_type, start_min, end_min in sorted(slots, key=lambda slot: (slot[1], slot[0])):
        if (
            merged_slots
            and merged_slots[-1][0] == event_type
            and merged_slots[-1][2] >= start_min
        ):
            prev_type, prev_start, prev_end = merged_slots[-1]
            merged_slots[-1] = (prev_type, prev_start, max(prev_end, end_min))
            continue
        merged_slots.append((event_type, start_min, end_min))

    windows: list[ScheduleWindow] = []
    for event_type, start_min, end_min in merged_slots:
        start = dt.datetime.combine(
            date,
            dt.time(start_min // 60, start_min % 60),
            tzinfo=KYIV_TZ,
        )
        if end_min >= 1440:
            end = dt.datetime.combine(
                date + dt.timedelta(days=1),
                dt.time(0, 0),
                tzinfo=KYIV_TZ,
            )
        else:
            end = dt.datetime.combine(
                date,
                dt.time(end_min // 60, end_min % 60),
                tzinfo=KYIV_TZ,
            )

        if event_type == "outage":
            summary = EVENT_SUMMARY_OUTAGE
            description = EVENT_DESCRIPTION_PLANNED
        else:
            summary = EVENT_SUMMARY_POSSIBLE
            description = EVENT_DESCRIPTION_POSSIBLE

        windows.append(
            ScheduleWindow(
                event_type=event_type,
                start=start,
                end=end,
                summary=summary,
                description=description,
            )
        )

    return windows
