"""Shared helpers for the DTEK Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_CITY, CONF_HOUSE, CONF_STREET, DOMAIN


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build device info for a DTEK monitored address."""
    city = entry.data[CONF_CITY]
    street = entry.data[CONF_STREET]
    house = entry.data[CONF_HOUSE]

    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=f"{street}, {house}",
        manufacturer="DTEK",
        model=city,
    )
