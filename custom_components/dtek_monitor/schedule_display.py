"""Small, address-free schedule snapshots for external display templates."""

from datetime import datetime, timezone

from .schedule import KYIV_TZ
from .schedule_events import scheduled_event
from .schedule_grid import grid_data


def display_data(coordinator, groups=(), *, personal=False, selection_status=None, now=None):
    """Expose exact intervals and the next relevant boundary, without network IO.

    Personal selection highlights rows but never removes other building/operator
    groups. No selected apartment group means no personal countdown. Bulky rows
    are deliberately limited to today and excluded from Recorder by the entity.
    """
    now = now or datetime.now(KYIV_TZ)
    base = {
        "schema_version": 1,
        "time_zone": "Europe/Kyiv",
        "today": now.astimezone(KYIV_TZ).date().isoformat(),
        "personal": personal,
        "selection_status": selection_status,
        "selected_groups": list(groups) if personal else [],
        "building_groups": [],
        "days": [],
        "event": {"kind": "unknown", "at": None, "groups": []},
    }
    if coordinator is None:
        return {**base, "status": "missing"}
    home = list((coordinator.address_data or {}).get("schedule_groups", [])) if coordinator.address_success else []
    base["building_groups"] = home
    grid = grid_data(coordinator, groups, now, personal=personal, day_count=1)
    base.update(status=grid["status"], verified_at=grid.get("verified_at"), source_updated_at=grid.get("source_updated_at"))
    if grid["status"] != "ready":
        return base
    for day in grid["days"]:
        slots = day["slots"]
        start = datetime.fromisoformat(slots[0]["start"]).timestamp()
        end = datetime.fromisoformat(slots[-1]["end"]).timestamp()
        ticks = [
            {"label": slot["label"][:2], "minute": (datetime.fromisoformat(slot["start"]).timestamp() - start) / 60}
            for slot in slots if slot["label"] in ("00:00", "06:00", "12:00", "18:00")
        ]
        ticks.append({"label": "24", "minute": (end - start) / 60})
        base["days"].append({
            "date": day["date"], "start": start, "end": end,
            "minutes": (end - start) / 60, "ticks": ticks,
            "rows": [{k: row[k] for k in ("id", "label", "home", "selected", "segments")} for row in day["rows"]],
        })
    effective = tuple(groups if personal else home)
    if not effective:
        base["event"]["kind"] = "selection_required" if personal else "unknown"
        return base
    next_start = scheduled_event(coordinator, "next_planned_outage", effective, now)
    next_end = scheduled_event(coordinator, "scheduled_outage_end", effective, now)
    candidates = []
    if next_start.value:
        candidates.append((next_start.value, "outage_start", next_start))
    if next_end.ongoing and next_end.value:
        candidates.append((next_end.value, "outage_end", next_end))
    if candidates:
        value, kind, event = min(candidates, key=lambda item: item[0].astimezone(timezone.utc))
        base["event"] = {"kind": kind, "at": value.timestamp(), "groups": list(event.groups)}
    elif next_end.ongoing:
        base["event"]["kind"] = "end_unconfirmed"
    elif next_start.status == "no_event_in_coverage":
        base["event"]["kind"] = "no_event_in_coverage"
    return base
