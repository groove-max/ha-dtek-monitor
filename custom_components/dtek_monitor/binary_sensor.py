"""Binary sensor platform for DTEK Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import DTEKDataCoordinator
from .helpers import build_device_info

POWER_DESCRIPTION = BinarySensorEntityDescription(
    key="power",
    translation_key="power",
    device_class=BinarySensorDeviceClass.POWER,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up DTEK binary sensors from a config entry."""
    coordinator: DTEKDataCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DTEKPowerBinarySensor(coordinator, entry)])


class DTEKPowerBinarySensor(
    CoordinatorEntity[DTEKDataCoordinator], BinarySensorEntity
):
    """Binary sensor indicating whether power is currently available."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DTEKDataCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = POWER_DESCRIPTION

        self._attr_unique_id = f"{entry.entry_id}_power"
        self._attr_device_info = build_device_info(entry)

    @property
    def is_on(self) -> bool | None:
        """Return True if power is available."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("power_on", True)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional outage details as attributes."""
        if self.coordinator.data is None:
            return {}

        data = self.coordinator.data
        attrs: dict[str, Any] = {
            "outage_type": data.get("outage_type", "ok"),
            "schedule_groups": data.get("schedule_groups", []),
        }

        if data.get("outage_start"):
            attrs["outage_start"] = data["outage_start"].isoformat()
        if data.get("outage_end"):
            attrs["outage_end"] = data["outage_end"].isoformat()
        if data.get("outage_description"):
            attrs["outage_description"] = data["outage_description"]

        outage_count = data.get("outage_count", 0)
        if outage_count > 1:
            attrs["outage_count"] = outage_count
            all_outages = data.get("all_outages", [])
            for i, outage in enumerate(all_outages, 1):
                prefix = f"outage_{i}"
                attrs[f"{prefix}_type"] = outage.get("outage_type", "")
                attrs[f"{prefix}_description"] = outage.get("outage_description", "")
                if outage.get("outage_start"):
                    attrs[f"{prefix}_start"] = outage["outage_start"].isoformat()
                if outage.get("outage_end"):
                    attrs[f"{prefix}_end"] = outage["outage_end"].isoformat()

        return attrs
