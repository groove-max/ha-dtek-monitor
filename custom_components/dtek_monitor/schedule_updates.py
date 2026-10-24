"""Durable change baselines and informational HA notices for public buildings."""

from datetime import datetime, timezone
import logging

from homeassistant.components import persistent_notification as pn
from homeassistant.helpers.storage import Store

from .localization import is_ukrainian
from .const import DOMAIN
from .schedule_changes import changed_groups, remember, revision, schedule_record, validate_record

_LOGGER = logging.getLogger(__name__)
SCHEDULE_CHANGED = "dtek_monitor_schedule_changed"
GROUPS_CHANGED = "dtek_monitor_groups_changed"


class ScheduleUpdates:
    """Saved baselines are for comparison only, never a source of live data."""

    def __init__(self, hass, entry, coordinator):
        self.hass, self.entry, self.coordinator = hass, entry, coordinator
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.schedule_changes")
        self.record = {"groups": None, "schedule": None}
        self.loaded = False

    async def update(self):
        if not self.loaded:
            try:
                saved = await self.store.async_load()
                if saved is not None:
                    groups = saved["groups"]
                    if groups is not None and (not isinstance(groups, list) or not groups or any(not isinstance(g, str) for g in groups)):
                        raise ValueError("Invalid group comparison data")
                    validate_record(saved["schedule"])
                    self.record = saved
            except (OSError, ValueError, TypeError, KeyError, OverflowError):
                _LOGGER.warning("Cannot restore DTEK change baseline; starting a new comparison")
            self.loaded = True
        coordinator = self.coordinator
        data = coordinator.address_data or {}
        if not coordinator.address_success:
            return
        groups = sorted(set(data.get("schedule_groups", [])))
        if not groups:
            return
        now = datetime.now(timezone.utc)
        current = schedule_record(coordinator.schedule) if coordinator.notifications_ready else None
        old = self.record
        changed = changed_groups(old["schedule"], current, now)
        updated = {
            "groups": groups,
            "schedule": remember(old["schedule"], current, now) if current else old["schedule"],
        }
        if updated == old:
            return
        try:
            await self.store.async_save(updated)
        except OSError:
            _LOGGER.warning("Cannot save DTEK change baseline; change delivery postponed")
            return
        self.record = updated
        common = {"entry_id": self.entry.entry_id, "provider_id": coordinator.address.provider_id}
        if old["groups"] is not None and groups != old["groups"]:
            self.hass.bus.async_fire(GROUPS_CHANGED, {
                **common, "previous_groups": old["groups"], "groups": groups,
            })
            uk = is_ukrainian(self.hass.config.language)
            address = ", ".join(coordinator.address.parts)
            transition = f"{', '.join(old['groups'])} → {', '.join(groups)}"
            message = (
                f"{address}\n\nГрупи будинку змінилися: **{transition}**.\n\nГрафіки будинку оновлюються автоматично."
                if uk else f"{address}\n\nBuilding groups changed: **{transition}**.\n\nBuilding schedules update automatically."
            )
            if len(groups) > 1:
                message += (" Якщо групу квартири не визначено, оберіть її в налаштуваннях «Будинок і група відключень»."
                            if uk else " If your apartment group is undetermined, select it in Building and outage group settings.")
            pn.async_create(self.hass, message, "ДТЕК · групи будинку" if uk else "DTEK · building groups",
                            f"{DOMAIN}_{self.entry.entry_id}_groups_changed")
        if changed:
            self.hass.bus.async_fire(SCHEDULE_CHANGED, {
                **common, "groups": groups, "changed_groups": changed,
                "revision": revision(current),
                "source_updated_at": coordinator.schedule.source_updated_at.isoformat(),
            })


async def remove_schedule_updates(hass, entry):
    await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.schedule_changes").async_remove()
    pn.async_dismiss(hass, f"{DOMAIN}_{entry.entry_id}_groups_changed")
