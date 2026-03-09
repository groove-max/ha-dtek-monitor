"""Config flow for DTEK Monitor integration."""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_CITY,
    CONF_HOUSE,
    CONF_SCAN_INTERVAL,
    CONF_STREET,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)
from .dtek_client import DTEKApiError, DTEKClient

_LOGGER = logging.getLogger(__name__)


def _combo_select(options: list[str]) -> SelectSelector:
    """Create a combo-box selector: dropdown + type-to-filter.

    custom_value=True makes it a real combobox where the user can type,
    and the dropdown filters matching options as they type.
    """
    return SelectSelector(
        SelectSelectorConfig(
            options=[SelectOptionDict(value=o, label=o) for o in options],
            mode=SelectSelectorMode.DROPDOWN,
            custom_value=True,
            sort=False,
        )
    )



class DTEKMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for DTEK Monitor."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for this handler."""
        return DTEKMonitorOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._client: DTEKClient | None = None
        self._streets_data: dict[str, list[str]] = {}
        self._city: str = ""
        self._street: str = ""
        self._house: str = ""
        self._available_houses: list[str] = []

    def _get_client(self) -> DTEKClient:
        """Get or create the DTEK API client."""
        if self._client is None:
            session = async_get_clientsession(self.hass)
            self._client = DTEKClient(session)
        return self._client

    async def _fetch_streets(self) -> dict[str, list[str]]:
        """Fetch and cache streets data from DTEK API."""
        if not self._streets_data:
            client = self._get_client()
            self._streets_data = await client.get_streets()
        return self._streets_data

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: Select city."""
        errors: dict[str, str] = {}

        if user_input is not None:
            city = user_input[CONF_CITY]
            streets_data = await self._fetch_streets()
            if city not in streets_data:
                errors[CONF_CITY] = "invalid_city"
            else:
                self._city = city
                return await self.async_step_street()

        try:
            streets_data = await self._fetch_streets()
            cities = sorted(streets_data.keys())
        except DTEKApiError as err:
            _LOGGER.error("Failed to fetch cities from DTEK: %s", err)
            errors["base"] = "cannot_connect"
            cities = []

        if not cities and not errors:
            errors["base"] = "no_data"

        if not cities:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CITY): _combo_select(cities),
            }),
            errors=errors,
        )

    async def async_step_street(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2: Select street."""
        errors: dict[str, str] = {}

        streets_data = await self._fetch_streets()
        valid_streets = streets_data.get(self._city, [])

        if user_input is not None:
            street = user_input[CONF_STREET]
            if street not in valid_streets:
                errors[CONF_STREET] = "invalid_street"
            else:
                self._street = street
                return await self.async_step_house()

        streets = sorted(valid_streets)

        if not streets:
            errors["base"] = "no_streets"
            return self.async_show_form(
                step_id="street",
                data_schema=vol.Schema({}),
                errors=errors,
            )

        return self.async_show_form(
            step_id="street",
            data_schema=vol.Schema({
                vol.Required(CONF_STREET): _combo_select(streets),
            }),
            errors=errors,
            description_placeholders={"city": self._city},
        )

    async def async_step_house(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 3: Select house number."""
        errors: dict[str, str] = {}

        if user_input is not None:
            house = user_input[CONF_HOUSE]
            self._house = house

            unique_id = f"{self._city}_{self._street}_{self._house}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return await self.async_step_settings()

        try:
            client = self._get_client()
            result = await client.get_home_status(
                self._city, self._street, house_num=""
            )
            houses_data = result.get("data", {})
            self._available_houses = sorted(
                houses_data.keys(),
                key=_natural_sort_key,
            )
        except DTEKApiError as err:
            _LOGGER.error("Failed to fetch houses from DTEK: %s", err)
            errors["base"] = "cannot_connect"
            self._available_houses = []

        if not self._available_houses:
            if not errors:
                errors["base"] = "no_houses"
            return self.async_show_form(
                step_id="house",
                data_schema=vol.Schema({
                    vol.Required(CONF_HOUSE): str,
                }),
                errors=errors,
                description_placeholders={
                    "city": self._city,
                    "street": self._street,
                },
            )

        return self.async_show_form(
            step_id="house",
            data_schema=vol.Schema({
                vol.Required(CONF_HOUSE): _combo_select(self._available_houses),
            }),
            errors=errors,
            description_placeholders={
                "city": self._city,
                "street": self._street,
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 4: Configure settings (scan interval)."""
        if user_input is not None:
            scan_interval = int(user_input[CONF_SCAN_INTERVAL])

            return self.async_create_entry(
                title=f"{self._street}, {self._house}",
                data={
                    CONF_CITY: self._city,
                    CONF_STREET: self._street,
                    CONF_HOUSE: self._house,
                    CONF_SCAN_INTERVAL: scan_interval,
                },
            )

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=DEFAULT_SCAN_INTERVAL_SECONDS,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_SECONDS,
                        max=MAX_SCAN_INTERVAL_SECONDS,
                        step=30,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
            }),
            description_placeholders={
                "city": self._city,
                "street": self._street,
                "house": self._house,
            },
        )


def _natural_sort_key(value: str) -> tuple:
    """Sort house numbers naturally: 1, 2, 10, 10A, 56V."""
    parts = re.split(r"(\d+)", value)
    result = []
    for part in parts:
        if part.isdigit():
            result.append((0, int(part), ""))
        else:
            result.append((1, 0, part.lower()))
    return tuple(result)


class DTEKMonitorOptionsFlow(OptionsFlow):
    """Handle DTEK Monitor options."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize the options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage runtime options for an existing entry."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                },
            )

        current_interval = int(
            self._config_entry.options.get(
                CONF_SCAN_INTERVAL,
                self._config_entry.data.get(
                    CONF_SCAN_INTERVAL,
                    DEFAULT_SCAN_INTERVAL_SECONDS,
                ),
            )
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current_interval,
                ): NumberSelector(
                    NumberSelectorConfig(
                        min=MIN_SCAN_INTERVAL_SECONDS,
                        max=MAX_SCAN_INTERVAL_SECONDS,
                        step=30,
                        unit_of_measurement="s",
                        mode=NumberSelectorMode.SLIDER,
                    )
                ),
            }),
        )
