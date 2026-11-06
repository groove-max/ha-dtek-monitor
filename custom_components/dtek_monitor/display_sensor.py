"""Opt-in external display entities; no additional DTEK polling."""

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .account_schedule import AccountScheduleEntity, SELECTED_STATUSES
from .helpers import build_device_info, build_entity_unique_id, suggested_entity_id
from .schedule_display import display_data


class DisplaySensor:
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:monitor-dashboard"
    _unrecorded_attributes = frozenset({"days"})

    @property
    def available(self):
        # Explicit missing/error states clear previous rows in consumer templates.
        return True

    @property
    def native_value(self):
        return self.display["status"]

    @property
    def extra_state_attributes(self):
        return {key: value for key, value in self.display.items() if key != "status"}


class DTEKDisplaySensor(DisplaySensor, CoordinatorEntity, SensorEntity):
    _attr_translation_key = "schedule_display"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        self._attr_unique_id = build_entity_unique_id(entry, "schedule_display")
        self.entity_id = suggested_entity_id(entry, "sensor", "schedule_display")
        self._attr_device_info = build_device_info(entry)

    @property
    def display(self):
        return display_data(self.coordinator)


class AccountDisplaySensor(DisplaySensor, AccountScheduleEntity, SensorEntity):
    def __init__(self, entry, number):
        super().__init__(entry, number, "account_schedule_display")

    @property
    def display(self):
        _, coordinator, groups, status = self.selected
        selected = groups if status in SELECTED_STATUSES else ()
        return display_data(coordinator, selected, personal=True, selection_status=status)
