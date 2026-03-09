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
)
from .dtek_client import DTEKApiError, DTEKClient
from .schedule import (
    ScheduleWindow,
    find_current_or_next_window,
    get_schedule_windows_for_date,
    get_schedule_windows_for_range,
)

_LOGGER = logging.getLogger(__name__)


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
        self._address_groups: list[str] = []

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
        )

        super().__init__(
            hass,
            _LOGGER,
            name=f"dtek_monitor_{self.city}_{self.street}_{self.house}",
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

        # Persist all known address groups so calendars keep working after outages clear.
        api_groups = _normalize_groups(outage_data.get("schedule_groups", []))
        if api_groups and api_groups != self._address_groups:
            _LOGGER.info(
                "Address groups changed: %s -> %s",
                self._address_groups or ["(none)"],
                api_groups,
            )
            self._address_groups = api_groups

        outage_data["schedule_groups"] = self._address_groups or api_groups
        outage_data["primary_schedule_group"] = (
            outage_data["schedule_groups"][0]
            if outage_data["schedule_groups"]
            else None
        )

        outage_data["schedule_fact"] = self._schedule_fact
        outage_data["schedule_preset"] = self._schedule_preset
        outage_data["schedule_update_time"] = self._schedule_update_time

        return outage_data

    def _apply_schedule(self, schedule: dict[str, Any]) -> None:
        """Apply new schedule data from HTML parse or API update."""
        if not isinstance(schedule, dict):
            _LOGGER.warning(
                "Unexpected schedule payload type: %s",
                type(schedule).__name__,
            )
            return

        if "fact" in schedule:
            fact = schedule["fact"]
            if isinstance(fact, dict):
                data = fact.get("data", {})
                if isinstance(data, dict):
                    self._schedule_fact = data
                else:
                    _LOGGER.warning("Unexpected fact data type: %s", type(data).__name__)
                update_time = fact.get("update", "")
                if update_time:
                    self._schedule_update_time = update_time
            else:
                _LOGGER.warning("Unexpected fact payload type: %s", type(fact).__name__)
        if "preset" in schedule:
            preset = schedule["preset"]
            if isinstance(preset, dict):
                data = preset.get("data", {})
                if isinstance(data, dict):
                    self._schedule_preset = data
                else:
                    _LOGGER.warning("Unexpected preset data type: %s", type(data).__name__)
                update_time = preset.get("updateFact", "")
                if update_time and not self._schedule_update_time:
                    self._schedule_update_time = update_time
            else:
                _LOGGER.warning(
                    "Unexpected preset payload type: %s",
                    type(preset).__name__,
                )

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
        return [
            _window_to_calendar_event(window)
            for window in get_schedule_windows_for_range(
                start,
                end,
                groups,
                self._schedule_fact,
                self._schedule_preset,
                event_type,
            )
        ]

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
        return [
            _window_to_calendar_event(window)
            for window in get_schedule_windows_for_date(
                date,
                groups,
                self._schedule_fact,
                self._schedule_preset,
                event_type,
            )
        ]

    def current_or_next_event(
        self,
        now: dt.datetime,
        groups: list[str],
        event_type: str | None = None,
    ) -> CalendarEvent | None:
        """Return the current or next event for the configured groups."""
        window = find_current_or_next_window(
            now,
            groups,
            self._schedule_fact,
            self._schedule_preset,
            event_type,
        )
        return _window_to_calendar_event(window) if window else None


def _window_to_calendar_event(window: ScheduleWindow) -> CalendarEvent:
    """Convert a pure schedule window into a Home Assistant CalendarEvent."""
    return CalendarEvent(
        start=window.start,
        end=window.end,
        summary=window.summary,
        description=window.description,
    )


def _normalize_groups(value: Any) -> list[str]:
    """Normalize group lists before storing them in coordinator state."""
    if not isinstance(value, list):
        return []
    groups: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            groups.append(normalized)
    return groups
