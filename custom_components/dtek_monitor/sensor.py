"""Sensor platform for DTEK Monitor."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import DTEKDataCoordinator
from .helpers import build_device_info, build_entity_unique_id, suggested_entity_id
from .account import CONF_ENTRY_KIND, ENTRY_ACCOUNT
from .schedule_status import SCHEDULE_STATUSES, schedule_status, status_attributes
from .schedule_events import EVENT_SENSOR_KEYS, scheduled_event
from .provider_notice import NOTICE_STATES, notice_attributes
from .address_works import WORKS_STATUSES, works_attributes, works_status


@dataclass(frozen=True, kw_only=True)
class DTEKSensorEntityDescription(SensorEntityDescription):
    """Describes a DTEK sensor entity."""

    value_fn: Callable[[dict[str, Any]], str | datetime | None]
    attributes_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None


SENSOR_DESCRIPTIONS: tuple[DTEKSensorEntityDescription, ...] = (
    DTEKSensorEntityDescription(
        key="status",
        translation_key="status",
        icon="mdi:transmission-tower",
        device_class=SensorDeviceClass.ENUM,
        options=["ok", "emergency", "planned", "stabilization"],
        value_fn=lambda data: data.get("outage_type", "ok"),
    ),
    DTEKSensorEntityDescription(
        key="outage_description",
        translation_key="outage_description",
        icon="mdi:text-box-outline",
        value_fn=lambda data: data.get("outage_description") or None,
    ),
    DTEKSensorEntityDescription(
        key="outage_start",
        translation_key="outage_start",
        icon="mdi:clock-start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.get("outage_start"),
    ),
    DTEKSensorEntityDescription(
        key="outage_end",
        translation_key="outage_end",
        icon="mdi:clock-end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.get("outage_end"),
    ),
    DTEKSensorEntityDescription(
        key="schedule_group",
        translation_key="schedule_group",
        icon="mdi:format-list-group",
        value_fn=lambda data: data.get("primary_schedule_group"),
        attributes_fn=lambda data: (
            {"schedule_groups": data.get("schedule_groups", [])}
            if data.get("schedule_groups")
            else {}
        ),
    ),
    DTEKSensorEntityDescription(
        key="schedule_groups",
        translation_key="schedule_groups",
        icon="mdi:format-list-bulleted-square",
        value_fn=lambda data: ", ".join(data.get("schedule_groups", [])) or None,
    ),
    DTEKSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.get("address_updated_at"),
    ),
    DTEKSensorEntityDescription(
        key="schedule_changed",
        translation_key="schedule_changed",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: data.get("schedule_updated_at"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DTEK sensors from a config entry."""
    from .display_sensor import AccountDisplaySensor, DTEKDisplaySensor

    if entry.data.get(CONF_ENTRY_KIND) == ENTRY_ACCOUNT:
        from .account_sensor import account_sensors
        from .account_schedule import (
            AccountGroupSensor, AccountScheduleStatusSensor, AccountScheduleEventSensor,
        )
        from .account import CONF_ACCOUNTS

        discover = account_sensors(entry.runtime_data, entry)
        async_add_entities(
            [
                *discover(),
                *(AccountDisplaySensor(entry, number) for number in entry.data[CONF_ACCOUNTS]),
                *(
                    AccountGroupSensor(entry, number)
                    for number in entry.data[CONF_ACCOUNTS]
                ),
                *(
                    AccountScheduleStatusSensor(entry, number)
                    for number in entry.data[CONF_ACCOUNTS]
                ),
                *(
                    AccountScheduleStatusSensor(entry, number, day_offset=1)
                    for number in entry.data[CONF_ACCOUNTS]
                ),
                *(
                    AccountScheduleEventSensor(entry, number, key)
                    for number in entry.data[CONF_ACCOUNTS]
                    for key in EVENT_SENSOR_KEYS
                ),
            ]
        )
        entry.async_on_unload(
            entry.runtime_data.async_add_listener(
                lambda: async_add_entities(discover())
            )
        )
        return
    coordinator: DTEKDataCoordinator = entry.runtime_data

    async_add_entities(
        [
            *(
                DTEKSensor(coordinator, entry, description)
                for description in SENSOR_DESCRIPTIONS
            ),
            DTEKConnectionSensor(coordinator, entry),
            DTEKProviderNoticeSensor(coordinator, entry),
            DTEKDisplaySensor(coordinator, entry),
            DTEKWorksStatusSensor(coordinator, entry),
            DTEKScheduleStatusSensor(coordinator, entry),
            DTEKScheduleStatusSensor(coordinator, entry, day_offset=1),
            *(DTEKScheduleEventSensor(coordinator, entry, key) for key in EVENT_SENSOR_KEYS),
        ]
    )


class DTEKSensor(CoordinatorEntity[DTEKDataCoordinator], SensorEntity):
    """Representation of a DTEK sensor."""

    entity_description: DTEKSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DTEKDataCoordinator,
        entry: ConfigEntry,
        description: DTEKSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description

        self._attr_unique_id = build_entity_unique_id(entry, description.key)
        self.entity_id = suggested_entity_id(entry, "sensor", description.key)
        self._attr_device_info = build_device_info(entry)

    @property
    def available(self) -> bool:
        if self.entity_description.key == "schedule_changed":
            return self.coordinator.notifications_ready
        return self.coordinator.address_success

    @property
    def _data(self) -> dict[str, Any] | None:
        if self.entity_description.key == "schedule_changed":
            return self.coordinator.data
        return self.coordinator.address_data

    @property
    def native_value(self) -> str | datetime | None:
        if self._data is None:
            return None
        return self.entity_description.value_fn(self._data)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._data
        attrs = (
            self.entity_description.attributes_fn(data)
            if data is not None and self.entity_description.attributes_fn
            else {}
        )
        if self.entity_description.key in ("schedule_group", "schedule_groups"):
            attrs.update(
                {
                    **notice_attributes(self.coordinator),
                    "schedule_groups": data.get("schedule_groups", []) if data else [],
                    "group_labels_visible": (
                        data.get("group_labels_visible", False) if data else False
                    ),
                    "provider_id": self.coordinator.address.provider_id,
                    "address_id": self.coordinator.address.identity,
                    "schedule_coverage": self.coordinator.snapshot_attributes[
                        "schedule_coverage"
                    ],
                    "schedule_notifications_ready": self.coordinator.notifications_ready,
                    "schedule_snapshot_id": (
                        self.coordinator.snapshot.snapshot_id
                        if self.coordinator.snapshot
                        else None
                    ),
                }
            )
        return attrs


class DTEKConnectionSensor(SensorEntity):
    """Independent diagnostics remain available when upstream polls fail."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "connection"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ok", "error"]
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: DTEKDataCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._attr_unique_id = build_entity_unique_id(entry, "connection")
        self.entity_id = suggested_entity_id(entry, "sensor", "connection")
        self._attr_device_info = build_device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.async_add_diagnostic_listener(self.async_write_ha_state)
        )

    @property
    def native_value(self) -> str:
        return self.coordinator.connection_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        c = self.coordinator
        return {
            **c.snapshot_attributes,
            "address_last_success": c.address_last_success,
            "schedule_last_success": c.schedule_last_success,
            "address_error": c.address_error,
            "schedule_error": c.schedule_error,
            "snapshot_storage_error": c.snapshot_storage_error,
            "retry_interval_seconds": c.update_interval.total_seconds(),
            "last_success": c.last_success,
            "last_error": c.last_error,
            "consecutive_failures": c.consecutive_failures,
            **c.provider.diagnostics,
        }


class DTEKProviderNoticeSensor(DTEKConnectionSensor):
    """Regional announcement, independent of address/calendar API availability."""

    _attr_translation_key = "provider_notice"
    _attr_options = list(NOTICE_STATES)
    _attr_entity_category = None
    _attr_icon = "mdi:bullhorn-outline"
    _unrecorded_attributes = frozenset({"provider_notice_text"})

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = build_entity_unique_id(entry, "provider_notice")
        self.entity_id = suggested_entity_id(entry, "sensor", "provider_notice")

    @property
    def available(self):
        return self.extra_state_attributes.get("provider_notice_state") in NOTICE_STATES

    @property
    def native_value(self):
        value = self.extra_state_attributes.get("provider_notice_state")
        return value if value in NOTICE_STATES else None

    @property
    def extra_state_attributes(self):
        return notice_attributes(self.coordinator)


class DTEKWorksStatusSensor(DTEKConnectionSensor):
    """Distinguish no reported works, missing dates and a failed address fetch."""

    _attr_translation_key = "address_works_status"
    _attr_options = list(WORKS_STATUSES)
    _attr_icon = "mdi:wrench-clock"

    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = build_entity_unique_id(entry, "address_works_status")
        self.entity_id = suggested_entity_id(entry, "sensor", "address_works_status")

    @property
    def native_value(self):
        return works_status(self.coordinator)

    @property
    def extra_state_attributes(self):
        return works_attributes(self.coordinator)


class DTEKScheduleStatusSensor(DTEKConnectionSensor):
    """Explain missing schedules even before the first successful calendar fetch."""

    _attr_translation_key = "schedule_status"
    _attr_options = list(SCHEDULE_STATUSES)

    def __init__(self, coordinator, entry, *, day_offset=0):
        super().__init__(coordinator, entry)
        self.day_offset = day_offset
        key = "schedule_tomorrow_status" if day_offset else "schedule_status"
        self._attr_translation_key = key
        self._attr_unique_id = build_entity_unique_id(entry, key)
        self.entity_id = suggested_entity_id(entry, "sensor", key)

    @property
    def native_value(self):
        return schedule_status(self.coordinator, day_offset=self.day_offset)

    @property
    def extra_state_attributes(self):
        return {
            **status_attributes(self.coordinator, day_offset=self.day_offset),
            "notifications_ready": self.coordinator.notifications_ready,
            "last_verified_at": self.coordinator.snapshot_attributes[
                "last_verified_at"
            ],
        }


class DTEKScheduleEventSensor(DTEKConnectionSensor):
    """Upcoming times from the schedule, never measurements of actual power."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = None
    _attr_options = None
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator, entry, key):
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_translation_key = key
        self._attr_unique_id = build_entity_unique_id(entry, key)
        self.entity_id = suggested_entity_id(entry, "sensor", key)

    @property
    def available(self):
        return scheduled_event(self.coordinator, self.key).available

    @property
    def native_value(self):
        return scheduled_event(self.coordinator, self.key).value

    @property
    def extra_state_attributes(self):
        return {
            **scheduled_event(self.coordinator, self.key).attributes,
            "schedule_groups": (
                [g.id for g in self.coordinator.schedule.groups]
                if self.coordinator.notifications_ready and self.coordinator.schedule else []
            ),
        }
