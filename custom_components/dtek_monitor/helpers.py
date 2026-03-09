"""Shared helpers for the DTEK Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_CITY, CONF_HOUSE, CONF_STREET, DOMAIN


def entry_identifier(entry: ConfigEntry) -> str:
    """Return a stable identifier for a config entry."""
    return entry.unique_id or entry.entry_id


def build_entity_unique_id(entry: ConfigEntry, suffix: str) -> str:
    """Build a stable entity unique ID from the config entry."""
    return f"{entry_identifier(entry)}_{suffix}"


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build device info for a DTEK monitored address."""
    city = entry.data[CONF_CITY]
    street = entry.data[CONF_STREET]
    house = entry.data[CONF_HOUSE]

    return DeviceInfo(
        identifiers={(DOMAIN, entry_identifier(entry))},
        name=f"{street}, {house}",
        manufacturer="DTEK",
        model=city,
    )
