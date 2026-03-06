"""DataUpdateCoordinator for DTEK Monitor."""

from __future__ import annotations

import datetime as dt
import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CITY,
    CONF_HOUSE,
    CONF_SCAN_INTERVAL,
    CONF_STREET,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    EVENT_DESCRIPTION_PLANNED,
    EVENT_DESCRIPTION_POSSIBLE,
    EVENT_SUMMARY_OUTAGE,
    EVENT_SUMMARY_POSSIBLE,
)
from .dtek_client import DTEKApiError, DTEKClient, KYIV_TZ

_LOGGER = logging.getLogger(__name__)

# Mapping of DTEK hour slot statuses to event types
_STATUS_MAP: dict[str, tuple[str, int, int] | None] = {
    "yes": None,
    "no": ("outage", 0, 60),
    "maybe": ("possible", 0, 60),
    "first": ("outage", 0, 30),
    "second": ("outage", 30, 60),
    "mfirst": ("possible", 0, 30),
    "msecond": ("possible", 30, 60),
}


class DTEKDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls DTEK API for address-specific outage data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: DTEKClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.city: str = entry.data[CONF_CITY]
        self.street: str = entry.data[CONF_STREET]
        self.house: str = entry.data[CONF_HOUSE]

        self._schedule_update_time: str = ""
        self._schedule_fact: dict[str, Any] = {}
        self._schedule_preset: dict[str, Any] = {}
        self._address_group: str = ""

        scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)

        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.city}_{self.street}_{self.house}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch outage status and schedule data from DTEK API."""
        try:
            api_response = await self.client.get_home_status(
                self.city, self.street, self.house
            )
        except DTEKApiError as err:
            raise UpdateFailed(f"Error fetching DTEK data: {err}") from err

        outage_data = DTEKClient.parse_house_data(api_response, self.house)

        # Apply schedule data refreshed from HTML (on session init or refresh)
        html_schedule = self.client.consume_schedule_update()
        if html_schedule:
            self._apply_schedule(html_schedule)

        # Check for schedule updates via API
        if self._schedule_update_time:
            try:
                update_data = await self.client.check_update(self._schedule_update_time)
                if update_data:
                    self._apply_schedule(update_data)
            except DTEKApiError as err:
                _LOGGER.debug("Schedule update check failed: %s", err)

        # Persist address group from API (survives across outage clearing)
        api_groups = outage_data.get("schedule_groups", [])
        if api_groups and api_groups[0]:
            new_group = api_groups[0]
            if new_group != self._address_group:
                _LOGGER.info(
                    "Address group changed: %s -> %s",
                    self._address_group or "(none)", new_group,
                )
                self._address_group = new_group

        if self._address_group:
            outage_data["schedule_groups"] = [self._address_group]
        else:
            outage_data["schedule_groups"] = api_groups

        outage_data["schedule_fact"] = self._schedule_fact
        outage_data["schedule_preset"] = self._schedule_preset
        outage_data["schedule_update_time"] = self._schedule_update_time

        return outage_data

    def _apply_schedule(self, schedule: dict[str, Any]) -> None:
        """Apply new schedule data from HTML parse or API update."""
        if "fact" in schedule:
            fact = schedule["fact"]
            data = fact.get("data", {})
            if isinstance(data, dict):
                self._schedule_fact = data
            else:
                _LOGGER.warning("Unexpected fact data type: %s", type(data).__name__)
            update_time = fact.get("update", "")
            if update_time:
                self._schedule_update_time = update_time
        if "preset" in schedule:
            preset = schedule["preset"]
            data = preset.get("data", {})
            if isinstance(data, dict):
                self._schedule_preset = data
            else:
                _LOGGER.warning("Unexpected preset data type: %s", type(data).__name__)
            update_time = preset.get("updateFact", "")
            if update_time and not self._schedule_update_time:
                self._schedule_update_time = update_time

        _LOGGER.debug(
            "Schedule data applied: fact_days=%d, preset_groups=%d",
            len(self._schedule_fact),
            len(self._schedule_preset),
        )

    def get_events_for_range(
        self,
        start: dt.datetime,
        end: dt.datetime,
        groups: list[str],
        event_type: str | None = None,
    ) -> list[CalendarEvent]:
        """Generate CalendarEvent objects for a date range and schedule groups.

        Args:
            event_type: Filter by type — "outage", "possible", or None for all.
        """
        events: list[CalendarEvent] = []
        current_date = start.date()
        end_date = end.date()

        while current_date <= end_date:
            day_events = self.events_for_date(current_date, groups, event_type)
            for ev in day_events:
                if ev.end > start and ev.start < end:
                    events.append(ev)
            current_date += timedelta(days=1)

        return events

    def events_for_date(
        self,
        date: dt.date,
        groups: list[str],
        event_type: str | None = None,
    ) -> list[CalendarEvent]:
        """Generate events for a single date from fact or preset data.

        Args:
            event_type: Filter by type — "outage", "possible", or None for all.
        """
        slots = self._get_day_slots(date, groups, event_type)
        if not slots:
            return []
        return _slots_to_events(slots, date)

    def _get_day_slots(
        self,
        date: dt.date,
        groups: list[str],
        event_type: str | None = None,
    ) -> list[tuple[str, int, int]]:
        """Get outage time blocks for a date from fact and/or preset.

        Both sources are checked and their results merged:
        - fact data contains confirmed outages for specific dates
        - preset data contains the weekly possible-outage template
        """
        blocks: list[tuple[str, int, int]] = []

        # Check fact data for this specific date
        if not isinstance(self._schedule_fact, dict):
            self._schedule_fact = {}
        for ts_str, day_data in self._schedule_fact.items():
            try:
                ts = int(ts_str)
            except (ValueError, TypeError):
                continue
            fact_date = dt.datetime.fromtimestamp(ts, tz=KYIV_TZ).date()
            if fact_date == date:
                blocks.extend(
                    self._extract_slots_from_day(day_data, groups, event_type)
                )
                break

        # Always check preset (weekly template) as well
        if self._schedule_preset:
            dow = str(date.isoweekday())
            preset_blocks = self._extract_slots_from_preset(
                dow, groups, event_type
            )
            # Only add preset slots that don't overlap with fact slots
            fact_minutes = {(s, e) for _, s, e in blocks}
            for slot in preset_blocks:
                if (slot[1], slot[2]) not in fact_minutes:
                    blocks.append(slot)

        return blocks

    def _extract_slots_from_day(
        self,
        day_data: dict[str, Any],
        groups: list[str],
        event_type: str | None = None,
    ) -> list[tuple[str, int, int]]:
        """Extract outage slots from fact day data for specific groups."""
        blocks: list[tuple[str, int, int]] = []
        for group in groups:
            group_data = day_data.get(group, {})
            if not isinstance(group_data, dict):
                continue
            for hour_key in range(1, 25):
                status = group_data.get(str(hour_key), "yes")
                mapped = _STATUS_MAP.get(status)
                if mapped is None:
                    continue
                slot_type, offset_start, offset_end = mapped
                if event_type and slot_type != event_type:
                    continue
                hour_base = (hour_key - 1) * 60
                blocks.append((slot_type, hour_base + offset_start, hour_base + offset_end))
        return blocks

    def _extract_slots_from_preset(
        self,
        day_of_week: str,
        groups: list[str],
        event_type: str | None = None,
    ) -> list[tuple[str, int, int]]:
        """Extract outage slots from preset data for specific groups + day."""
        blocks: list[tuple[str, int, int]] = []
        for group in groups:
            group_data = self._schedule_preset.get(group, {})
            if not isinstance(group_data, dict):
                continue
            dow_data = group_data.get(day_of_week, {})
            if not isinstance(dow_data, dict):
                continue
            for hour_key in range(1, 25):
                status = dow_data.get(str(hour_key), "yes")
                mapped = _STATUS_MAP.get(status)
                if mapped is None:
                    continue
                slot_type, offset_start, offset_end = mapped
                if event_type and slot_type != event_type:
                    continue
                hour_base = (hour_key - 1) * 60
                blocks.append((slot_type, hour_base + offset_start, hour_base + offset_end))
        return blocks


def _slots_to_events(
    blocks: list[tuple[str, int, int]], date: dt.date
) -> list[CalendarEvent]:
    """Convert time blocks into merged CalendarEvent objects."""
    if not blocks:
        return []

    blocks.sort(key=lambda b: (b[1], b[0]))

    merged: list[tuple[str, int, int]] = []
    for event_type, start_min, end_min in blocks:
        if merged and merged[-1][0] == event_type and merged[-1][2] >= start_min:
            prev_type, prev_start, prev_end = merged[-1]
            merged[-1] = (prev_type, prev_start, max(prev_end, end_min))
        else:
            merged.append((event_type, start_min, end_min))

    events: list[CalendarEvent] = []
    for event_type, start_min, end_min in merged:
        start_dt = dt.datetime.combine(
            date,
            dt.time(start_min // 60, start_min % 60),
            tzinfo=KYIV_TZ,
        )
        if end_min >= 1440:
            end_dt = dt.datetime.combine(
                date + timedelta(days=1),
                dt.time(0, 0),
                tzinfo=KYIV_TZ,
            )
        else:
            end_dt = dt.datetime.combine(
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

        events.append(CalendarEvent(
            start=start_dt,
            end=end_dt,
            summary=summary,
            description=description,
        ))

    return events
