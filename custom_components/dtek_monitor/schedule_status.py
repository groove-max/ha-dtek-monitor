"""Presentation of publication, request failures and verified empty days."""

from datetime import datetime, timedelta

from .schedule import KYIV_TZ
from .provider_notice import notice_attributes

SCHEDULE_STATUSES = (
    "current",
    "empty",
    "partial",
    "forecast",
    "missing",
    "unpublished",
    "unsupported",
    "error",
)


def covers(coverage, group, kind, start, end):
    """Require a continuous verified range, not merely one intersecting slot."""
    cursor = start
    for part in sorted(
        (c for c in coverage if c.group_id == group and c.kind == kind),
        key=lambda c: c.start,
    ):
        if part.start > cursor:
            break
        cursor = max(cursor, part.end)
        if cursor >= end:
            return True
    return False


def schedule_status(coordinator, groups=None, now=None, *, day_offset=0):
    """A day's planned schedule, independent of cached display-only events.

    `empty` is justified only by complete dated coverage for all selected groups.
    A weekly forecast, a missing group or a gap never proves no planned outages.
    """
    if coordinator.address_error or coordinator.schedule_error:
        return "error"
    if coordinator.schedule_state != "current":
        return coordinator.schedule_state
    if not coordinator.notifications_ready or coordinator.schedule is None:
        return "error"
    now = now or datetime.now(KYIV_TZ)
    start = now.astimezone(KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    start += timedelta(days=day_offset)
    end = start + timedelta(days=1)
    schedule = coordinator.schedule
    groups = list(groups if groups is not None else (g.id for g in schedule.groups))
    if not groups:
        return "missing"
    complete = all(covers(schedule.coverage, g, "outage", start, end) for g in groups)
    if not complete:
        if any(
            c.group_id in groups
            and c.kind == "outage"
            and c.start < end
            and c.end > start
            for c in schedule.coverage
        ):
            return "partial"
        if all(covers(schedule.coverage, g, "possible", start, end) for g in groups):
            return "forecast"
        return "missing"
    if any(
        i.group_id in groups and i.kind == "outage" and i.start < end and i.end > start
        for i in schedule.intervals
    ):
        return "current"
    return "empty"


def status_attributes(coordinator, groups=None, now=None, *, day_offset=0):
    now = now or datetime.now(KYIV_TZ)
    return {
        **notice_attributes(coordinator, now, day_offset=day_offset),
        "schedule_status": schedule_status(coordinator, groups, now, day_offset=day_offset),
        "status_date": (now.astimezone(KYIV_TZ).date() + timedelta(days=day_offset)).isoformat(),
        "status_timezone": "Europe/Kyiv",
        "reason": coordinator.schedule_reason,
        "request_error": coordinator.address_error or coordinator.schedule_error,
    }
