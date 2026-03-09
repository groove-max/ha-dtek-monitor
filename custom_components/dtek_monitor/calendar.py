"""Calendar platform for DTEK Monitor — outage schedule."""

from __future__ import annotations

import datetime as dt

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .coordinator import DTEKDataCoordinator
from .helpers import build_device_info, build_entity_unique_id

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
    coordinator: DTEKDataCoordinator = entry.runtime_data
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
        self._attr_unique_id = build_entity_unique_id(entry, uid_suffix)
        self._attr_device_info = build_device_info(entry)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current or next upcoming event."""
        if self.coordinator.data is None:
            return None

        groups = self.coordinator.data.get("schedule_groups", [])
        if not groups:
            return None

        return self.coordinator.current_or_next_event(
            dt_util.now(),
            groups,
            self._event_type,
        )

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
