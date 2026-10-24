"""Explicit private group selections over independent public building schedules."""

from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntryState, SIGNAL_CONFIG_ENTRY_CHANGED
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, DeviceInfo
from homeassistant.util import dt as dt_util

from .account import CONF_ENTRY_KIND, ENTRY_ACCOUNT, account_key
from .account_providers import account_cabinet_url
from .const import DOMAIN
from .providers import CONF_PROVIDER, DEFAULT_PROVIDER_ID
from .schedule import KYIV_TZ
from .schedule_status import SCHEDULE_STATUSES, schedule_status, status_attributes
from .schedule_events import ScheduledEvent, scheduled_event

CONF_ACCOUNT_SCHEDULES = "account_schedules"
SELECTED_STATUSES = ("selected", "auto_selected", "cabinet_selected")


def cabinet_groups(entry, number):
    manager = getattr(getattr(entry, "runtime_data", None), "groups", None)
    return manager.get(number) if manager is not None else None


def compare_cabinet_groups(building_groups, cabinet):
    """Compare fresh sources; None means the building cannot be checked yet."""
    reported = set(cabinet.groups) if cabinet and cabinet.status == "current" else set()
    building = set(building_groups) if building_groups is not None else None
    return {
        "cabinet_groups": sorted(reported),
        "verified_cabinet_groups": sorted(reported & building) if building is not None else [],
        "unverified_cabinet_groups": sorted(reported - building) if building is not None else [],
    }


def selectable_groups(coordinator):
    """Offer current building IDs, independently of DTEK's label display policy.

    An explicit choice does not change the cabinet assignment or the house's
    calendars. Automatic selection still requires an unambiguous assignment.
    """
    if coordinator is None or not coordinator.address_success:
        return []
    return list(coordinator.address_data.get("schedule_groups", []))


def automatic_selection(building_groups, cabinet):
    """Resolve an unambiguous assignment without guessing from an ordered list."""
    if cabinet and cabinet.status == "current" and cabinet.groups:
        verified = compare_cabinet_groups(building_groups, cabinet)["verified_cabinet_groups"]
        if not verified:
            return [], "cabinet_group_mismatch"
        if len(verified) == 1:
            return verified, "cabinet_selected"
        return [], "not_selected"
    if len(building_groups) == 1:
        return list(building_groups), "auto_selected"
    if cabinet and cabinet.status in ("unavailable", "expired", "api_changed"):
        return [], "cabinet_unavailable"
    return [], "not_selected"


def address_entries(hass, entry):
    return {
        other.entry_id: other
        for other in hass.config_entries.async_entries(DOMAIN)
        if other.data.get(CONF_ENTRY_KIND, "address") != ENTRY_ACCOUNT
        and other.data.get(CONF_PROVIDER, DEFAULT_PROVIDER_ID)
        == entry.data[CONF_PROVIDER]
    }


def selection(hass, entry, number):
    """Resolve every time: removed/reloaded entries must never leave a stale link."""
    link = entry.options.get(CONF_ACCOUNT_SCHEDULES, {}).get(number, {})
    address = address_entries(hass, entry).get(link.get("address_entry_id"))
    groups = link.get("groups", [])
    coordinator = None
    status = "no_address"
    if not link:
        buildings = getattr(getattr(entry, "runtime_data", None), "buildings", None)
        if buildings is not None:
            status = buildings.states.get(number, "address_pending")
    if address is not None:
        if address.state == ConfigEntryState.LOADED:
            coordinator = getattr(address, "runtime_data", None)
        cabinet = cabinet_groups(entry, number)
        data = coordinator.address_data if coordinator and coordinator.address_success else {}
        building_groups = data.get("schedule_groups", [])
        if coordinator is None or not coordinator.address_success:
            status = "address_unavailable"
        elif not groups:
            groups, status = automatic_selection(building_groups, cabinet)
        elif not set(groups).issubset(building_groups):
            status = "group_unavailable"
        else:
            status = "selected"
    return address, coordinator, groups, status


class AccountScheduleEntity(Entity):
    """Listen to the public coordinator without sharing cabinet data with it."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry, number, key):
        self.entry, self.number = entry, number
        identity = account_key(entry.data[CONF_PROVIDER], number)
        self._attr_unique_id = f"account:{identity}:{key}:all"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"account:{identity}")},
            name=f"DTEK • ••••{number[-4:]}",
            manufacturer="DTEK",
            configuration_url=account_cabinet_url(entry.data[CONF_PROVIDER]),
        )
        self._listened = None
        self._unsubscribe_address = None

    @property
    def selected(self):
        return selection(self.hass, self.entry, self.number)

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        account_coordinator = getattr(self.entry, "runtime_data", None)
        if account_coordinator is not None:
            self.async_on_remove(account_coordinator.async_add_listener(self.async_write_ha_state))
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_CONFIG_ENTRY_CHANGED, self._entry_changed
            )
        )
        self.async_on_remove(self._disconnect_address)
        self._connect_address()

    @callback
    def _disconnect_address(self):
        if self._unsubscribe_address:
            self._unsubscribe_address()
        self._unsubscribe_address = self._listened = None

    @callback
    def _connect_address(self):
        coordinator = self.selected[1]
        if coordinator is self._listened:
            return
        self._disconnect_address()
        self._listened = coordinator
        if coordinator is not None:
            self._unsubscribe_address = coordinator.async_add_listener(
                self.async_write_ha_state
            )

    @callback
    def _entry_changed(self, change, entry):
        link = self.entry.options.get(CONF_ACCOUNT_SCHEDULES, {}).get(self.number, {})
        if entry.entry_id == link.get("address_entry_id"):
            self._connect_address()
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        address, coordinator, groups, status = self.selected
        cabinet = cabinet_groups(self.entry, self.number)
        building = (
            coordinator.address_data.get("schedule_groups", [])
            if coordinator and coordinator.address_success else None
        )
        return {
            "selection_status": status,
            "selection_source": (
                "building_single_group"
                if status == "auto_selected"
                else "cabinet"
                if status == "cabinet_selected"
                else "user"
                if groups
                else None
            ),
            "selected_groups": groups,
            "cabinet_group_status": cabinet.status if cabinet else "unsupported",
            **compare_cabinet_groups(building, cabinet),
            "cabinet_groups_checked_at": cabinet.checked_at.isoformat() if cabinet and cabinet.checked_at else None,
            "building_groups": (
                coordinator.address_data.get("schedule_groups", [])
                if coordinator
                and coordinator.address_success
                else []
            ),
            "group_labels_visible": (
                coordinator.address_data.get("group_labels_visible", False)
                if coordinator and coordinator.address_success else False
            ),
            "building": address.title if address else None,
        }


class AccountGroupSensor(AccountScheduleEntity, SensorEntity):
    _attr_icon = "mdi:home-lightning-bolt-outline"

    def __init__(self, entry, number):
        super().__init__(entry, number, "account_schedule_groups")

    @property
    def native_value(self):
        # Saved selections stay visible if DTEK later removes them; status and
        # unavailable calendars make the need for verification explicit.
        return ", ".join(self.selected[2]) or None


class AccountScheduleStatusSensor(AccountScheduleEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [
        "no_address",
        "address_pending",
        "address_confirmation",
        "address_lookup_unavailable",
        "not_selected",
        "selected",
        "auto_selected",
        "cabinet_selected",
        "cabinet_group_mismatch",
        "cabinet_unavailable",
        "address_unavailable",
        "group_unavailable",
        "labels_hidden",
        "schedule_unavailable",
        *("schedule_" + status for status in SCHEDULE_STATUSES),
    ]

    def __init__(self, entry, number, *, day_offset=0):
        self.day_offset = day_offset
        super().__init__(entry, number, (
            "account_schedule_tomorrow_status" if day_offset else "account_schedule_status"
        ))

    @property
    def native_value(self):
        _, coordinator, groups, status = self.selected
        if status in SELECTED_STATUSES:
            publication = schedule_status(coordinator, groups, day_offset=self.day_offset)
            if self.day_offset or publication != "current":
                return "schedule_" + publication
        return status

    @property
    def extra_state_attributes(self):
        _, coordinator, groups, _ = self.selected
        return {
            **super().extra_state_attributes,
            **(status_attributes(coordinator, groups, day_offset=self.day_offset) if coordinator else {}),
        }


class AccountScheduleEventSensor(AccountScheduleEntity, SensorEntity):
    """Private timestamps use the apartment selection, leaving the building intact."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, entry, number, key):
        self.key = key
        super().__init__(entry, number, "account_" + key)

    @property
    def _event(self):
        _, coordinator, groups, status = self.selected
        if status not in SELECTED_STATUSES:
            return ScheduledEvent(status="group_selection_unavailable")
        return scheduled_event(coordinator, self.key, groups)

    @property
    def available(self):
        return self._event.available

    @property
    def native_value(self):
        return self._event.value

    @property
    def extra_state_attributes(self):
        return {**super().extra_state_attributes, **self._event.attributes}


class AccountScheduleCalendar(AccountScheduleEntity, CalendarEntity):
    _attr_icon = "mdi:calendar-account"

    def __init__(self, entry, number, kind):
        super().__init__(entry, number, "account_" + kind + "_schedule")
        self.kind = kind

    @property
    def available(self):
        _, coordinator, _, status = self.selected
        return (
            status in SELECTED_STATUSES
            and coordinator.notifications_ready
            and any(c.kind == self.kind for c in coordinator.schedule.coverage)
        )

    @property
    def extra_state_attributes(self):
        _, coordinator, groups, _ = self.selected
        return {
            **(coordinator.snapshot_attributes if coordinator else {}),
            **super().extra_state_attributes,
            "schedule_groups": groups,
            "usage": "personal_schedule",
            "notifications_ready": self.available,
        }

    @property
    def event(self):
        if not self.available:
            return None
        _, coordinator, groups, _ = self.selected
        return coordinator.current_or_next_event(dt_util.now(), groups, self.kind)

    async def async_get_events(self, hass, start_date, end_date):
        if not self.available:
            _, coordinator, _, status = self.selected
            raise HomeAssistantError(
                translation_domain="dtek_monitor",
                translation_key=(
                    "schedule_" + schedule_status(coordinator)
                    if coordinator
                    and status in SELECTED_STATUSES
                    and not coordinator.notifications_ready
                    else "personal_schedule_unavailable"
                ),
            )
        _, coordinator, groups, _ = self.selected
        start = (
            start_date.replace(tzinfo=KYIV_TZ)
            if start_date.tzinfo is None
            else start_date
        )
        end = end_date.replace(tzinfo=KYIV_TZ) if end_date.tzinfo is None else end_date
        # Empty events are meaningful only when every selected group has
        # publication coverage in the requested range. No unrelated group fallback.
        if coordinator.schedule is None or not all(
            any(
                c.group_id == group
                and c.kind == self.kind
                and c.start < end
                and c.end > start
                for c in coordinator.schedule.coverage
            )
            for group in groups
        ):
            raise HomeAssistantError(
                translation_domain="dtek_monitor",
                translation_key="schedule_range_missing",
            )
        return coordinator.get_events_for_range(start_date, end_date, groups, self.kind)
