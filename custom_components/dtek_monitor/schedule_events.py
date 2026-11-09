"""Time-based views over verified schedules, without inferring actual power."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

from .localization import is_ukrainian
from .provider import ScheduleReading
from .schedule import KYIV_TZ
from .schedule_status import covers
from .provider_notice import notice_attributes

EVENT_SENSOR_KEYS = ("next_planned_outage", "next_possible_outage", "scheduled_outage_end")


def merge_schedule_intervals(schedule: ScheduleReading) -> ScheduleReading:
    """Join adjacent verified intervals without mixing groups, types or sources."""
    merged = []
    for interval in sorted(
        schedule.intervals,
        key=lambda i: (i.group_id, i.kind, i.source, i.start, i.end),
    ):
        previous = merged[-1] if merged else None
        if (
            previous is not None
            and (previous.group_id, previous.kind, previous.source)
            == (interval.group_id, interval.kind, interval.source)
            and previous.end == interval.start
            and covers(schedule.coverage, interval.group_id, interval.kind,
                       previous.start, interval.end)
        ):
            merged[-1] = replace(previous, end=interval.end)
        else:
            merged.append(interval)
    return replace(schedule, intervals=tuple(sorted(
        merged, key=lambda i: (i.start, i.end, i.group_id, i.kind, i.source)
    )))


def _coverage_end(schedule, group, kind, now):
    cursor = now
    for part in sorted(
        (c for c in schedule.coverage if c.group_id == group and c.kind == kind),
        key=lambda c: c.start,
    ):
        if part.start > cursor:
            break
        cursor = max(cursor, part.end)
    return cursor


@dataclass(frozen=True)
class ScheduledEvent:
    value: datetime | None = None
    status: str = "unavailable"
    groups: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    coverage_end: datetime | None = None
    ongoing: bool = False

    @property
    def available(self):
        return self.status in ("scheduled", "no_event_in_coverage", "end_unconfirmed")

    @property
    def attributes(self):
        return {
            "event_status": self.status,
            "event_groups": list(self.groups),
            "schedule_sources": list(self.sources),
            "verified_until": self.coverage_end,
            "ongoing_scheduled_outage": self.ongoing,
            "basis": "schedule",
        }


def scheduled_event(coordinator, key, groups=None, now=None):
    """Return the next event within continuous coverage for every selected group.

    Starts exclude ongoing outages. The end belongs to an ongoing planned outage,
    or to the next planned outage if none is ongoing. With multiple groups, the
    earliest such end is reported and its groups are included explicitly.
    """
    if key not in EVENT_SENSOR_KEYS:
        raise ValueError(f"Unknown schedule event: {key}")
    if (
        coordinator is None
        or not coordinator.notifications_ready
        or coordinator.address_error
        or coordinator.schedule_error
        or coordinator.schedule_state != "current"
        or coordinator.schedule is None
    ):
        return ScheduledEvent()
    schedule = coordinator.schedule
    groups = tuple(groups if groups is not None else (g.id for g in schedule.groups))
    if not groups:
        return ScheduledEvent(status="no_groups")
    # UTC comparisons distinguish both occurrences of the repeated autumn hour.
    now = (now or datetime.now(KYIV_TZ)).astimezone(timezone.utc)
    notice = notice_attributes(coordinator, now)
    if notice.get('schedule_applies') is False:
        return ScheduledEvent(status='not_applicable')
    kind = "possible" if key == "next_possible_outage" else "outage"
    horizon = min(_coverage_end(schedule, g, kind, now) for g in groups)
    if horizon <= now:
        return ScheduledEvent(status="missing_coverage")
    intervals = [
        i for i in schedule.intervals
        if i.group_id in groups and i.kind == kind and i.end > now
    ]
    ongoing = key == "scheduled_outage_end" and any(i.start <= now for i in intervals)
    if ongoing:
        candidates = [i for i in intervals if i.start <= now]
    else:
        candidates = [i for i in intervals if now < i.start < horizon]
        if candidates:
            first_start = min(i.start for i in candidates)
            candidates = [i for i in candidates if i.start == first_start]
    if not candidates:
        return ScheduledEvent(status="no_event_in_coverage", coverage_end=horizon)
    is_end = key == "scheduled_outage_end"
    value = min(i.end if is_end else i.start for i in candidates)
    offset = (value.astimezone(KYIV_TZ).date()-now.astimezone(KYIV_TZ).date()).days
    target_notice = notice_attributes(coordinator, now, day_offset=offset)
    if target_notice.get('schedule_applies') is False:
        return ScheduledEvent(status='not_applicable')
    selected = [i for i in candidates if (i.end if is_end else i.start) == value]
    result = ScheduledEvent(
        value=value, status="scheduled",
        groups=tuple(sorted({i.group_id for i in selected})),
        sources=tuple(sorted({i.source for i in selected})),
        coverage_end=horizon, ongoing=ongoing,
    )
    if is_end and (
        value >= horizon
        or any(
            i.group_id in result.groups and i.start <= value < i.end
            for i in intervals
        )
    ):
        # An interval clipped at the publication edge does not prove restoration.
        return replace(result, value=None, status="end_unconfirmed")
    return result


def next_schedule_boundary(schedule, now):
    """Recompute at events, publication edges and Kyiv midnight, without HTTP."""
    now = now.astimezone(timezone.utc)
    midnight = now.astimezone(KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    candidates = [(midnight + timedelta(days=1)).astimezone(timezone.utc)]
    if schedule:
        candidates.extend(
            value.astimezone(timezone.utc)
            for part in (*schedule.intervals, *schedule.coverage)
            for value in (part.start, part.end)
            if value.astimezone(timezone.utc) > now
        )
    return min(candidates)


def event_summary(kind, language="en"):
    """Backend calendars follow HA's configured language, with English fallback."""
    if is_ukrainian(language):
        return "Планове відключення" if kind == "outage" else "Можливе відключення"
    return "Planned outage" if kind == "outage" else "Possible outage"
