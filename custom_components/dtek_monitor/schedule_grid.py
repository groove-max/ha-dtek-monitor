"""Read-only operator grid. Unknown coverage never becomes a clear cell."""

from datetime import datetime, timedelta, timezone
import re

from .schedule import KYIV_TZ
from .schedule_status import covers


def grid_data(coordinator, selected=(), now=None):
    now = (now or datetime.now(timezone.utc)).astimezone(KYIV_TZ)
    schedule = coordinator.overview
    base = {"time_zone": "Europe/Kyiv", "today": now.date().isoformat(), "days": []}
    if (
        not coordinator.address_success
        or coordinator.address_error
        or coordinator.schedule_error
    ):
        return {**base, "status": "error"}
    if schedule is None:
        return {**base, "status": "missing"}
    if schedule.state == "unsupported":
        return {**base, "status": "unsupported"}
    # showUserGroup controls labels on DTEK's site, not schedule publication.
    # When no public label is provided, rows below retain their source IDs.
    if schedule.publication.schedule is not True:
        return {**base, "status": "unpublished"}
    home = coordinator.address_data.get("schedule_groups", [])
    groups = sorted(
        schedule.groups,
        key=lambda g: tuple(
            int(x) if x.isdigit() else x for x in re.split(r"(\d+)", g.id)
        ),
    )
    days = []
    # Advance in UTC to retain both repeated hours and skip nonexistent hours.
    for offset in range(7):
        day = (now + timedelta(days=offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        end = (day + timedelta(days=1)).astimezone(timezone.utc)
        cursor = day.astimezone(timezone.utc)
        slots = []
        while cursor < end:
            stop = min(cursor + timedelta(minutes=30), end)
            local = cursor.astimezone(KYIV_TZ)
            slots.append(
                {
                    "start": cursor.isoformat(),
                    "end": stop.isoformat(),
                    "label": local.strftime("%H:%M"),
                    "offset": local.strftime("%z"),
                }
            )
            cursor = stop
        rows = []
        for group in groups:
            intervals = [i for i in schedule.intervals if i.group_id == group.id]
            coverage = [c for c in schedule.coverage if c.group_id == group.id]
            cells = []
            for slot in slots:
                start, stop = (
                    datetime.fromisoformat(slot["start"]),
                    datetime.fromisoformat(slot["end"]),
                )
                if covers(coverage, group.id, "outage", start, stop):
                    if any(
                        i.kind == "outage" and i.start < stop and i.end > start
                        for i in intervals
                    ):
                        cell = "outage"
                    elif any(
                        i.kind == "possible"
                        and i.source == "daily"
                        and i.start < stop
                        and i.end > start
                        for i in intervals
                    ):
                        cell = "possible"
                    else:
                        cell = "clear"
                elif covers(coverage, group.id, "possible", start, stop):
                    cell = (
                        "forecast"
                        if any(i.start < stop and i.end > start for i in intervals)
                        else "forecast_clear"
                    )
                else:
                    cell = "unknown"
                cells.append(cell)
            rows.append(
                {
                    "id": group.id,
                    "label": group.label or group.id,
                    "home": group.id in home,
                    "selected": group.id in selected,
                    "cells": cells,
                }
            )
        days.append({"date": day.date().isoformat(), "slots": slots, "rows": rows})
    return {
        **base,
        "status": "ready",
        "days": days,
        "address": " · ".join(
            (
                coordinator.address.city,
                coordinator.address.street + ", " + coordinator.address.house,
            )
        ),
        "source_updated_at": schedule.source_updated_at.isoformat(),
        "verified_at": schedule.fetched_at.isoformat(),
        "revision": schedule.revision,
    }
