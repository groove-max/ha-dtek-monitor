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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DTEKDataCoordinator
from .dtek_client import parse_dtek_datetime
from .helpers import build_device_info


@dataclass(frozen=True, kw_only=True)
class DTEKSensorEntityDescription(SensorEntityDescription):
    """Describes a DTEK sensor entity."""

    value_fn: Callable[[dict[str, Any]], str | datetime | None]


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
        value_fn=lambda data: ", ".join(data.get("schedule_groups", [])) or None,
    ),
    DTEKSensorEntityDescription(
        key="last_update",
        translation_key="last_update",
        icon="mdi:update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: parse_dtek_datetime(
            data.get("dtek_update_time", "")
        ),
    ),
    DTEKSensorEntityDescription(
        key="schedule_changed",
        translation_key="schedule_changed",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda data: parse_dtek_datetime(
            data.get("schedule_update_time", "")
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DTEK sensors from a config entry."""
    coordinator: DTEKDataCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        DTEKSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
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

        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = build_device_info(entry)

    @property
    def native_value(self) -> str | datetime | None:
        """Return the current sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
