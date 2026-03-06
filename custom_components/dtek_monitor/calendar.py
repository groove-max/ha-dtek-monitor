"""Calendar platform for DTEK Monitor — outage schedule."""

from __future__ import annotations

import datetime as dt
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import DTEKDataCoordinator
from .helpers import build_device_info

_LOGGER = logging.getLogger(__name__)

_CALENDAR_TYPES: list[tuple[str, str, str]] = [
    # (event_type, translation_key, unique_id_suffix)
    ("outage", "outage_schedule", "outage_schedule"),
    ("possible", "possible_schedule", "possible_schedule"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DTEK calendars from a config entry."""
    coordinator: DTEKDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        DTEKScheduleCalendar(coordinator, entry, event_type, translation_key, uid_suffix)
        for event_type, translation_key, uid_suffix in _CALENDAR_TYPES
    )


class DTEKScheduleCalendar(
    CoordinatorEntity[DTEKDataCoordinator], CalendarEntity
):
    """Calendar entity representing a DTEK outage schedule for an address."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:calendar-alert"

    def __init__(
        self,
        coordinator: DTEKDataCoordinator,
        entry: ConfigEntry,
        event_type: str,
        translation_key: str,
        uid_suffix: str,
    ) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._event_type = event_type
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{uid_suffix}"
        self._attr_device_info = build_device_info(entry)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        if self.coordinator.data is None:
            return None

        groups = self.coordinator.data.get("schedule_groups", [])
        if not groups:
            return None

        now = dt_util.now()
        today = now.date()

        for day_offset in range(2):
            check_date = today + dt.timedelta(days=day_offset)
            day_events = self.coordinator.events_for_date(
                check_date, groups, self._event_type
            )

            for ev in day_events:
                if ev.start_datetime_local <= now < ev.end_datetime_local:
                    return ev

            upcoming = [
                e for e in day_events if e.start_datetime_local > now
            ]
            if upcoming:
                return min(upcoming, key=lambda e: e.start_datetime_local)

        return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: dt.datetime,
        end_date: dt.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        if self.coordinator.data is None:
            return []

        groups = self.coordinator.data.get("schedule_groups", [])
        if not groups:
            return []

        return self.coordinator.get_events_for_range(
            start_date, end_date, groups, self._event_type,
        )
