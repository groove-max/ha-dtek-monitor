"""DataUpdateCoordinator for DTEK Monitor."""

from __future__ import annotations

import datetime as dt
import logging
import random
import asyncio
import math
from time import monotonic
from datetime import timedelta
from typing import Any
from collections.abc import Callable

from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_CITY,
    CONF_HOUSE,
    CONF_SCAN_INTERVAL,
    CONF_STREET,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from .provider import Address, OutageProvider, ProviderError, ScheduleReading
from .snapshot import ScheduleSnapshot, SNAPSHOT_DAYS
from .providers import CONF_PROVIDER, DEFAULT_PROVIDER_ID
from .schedule import (
    KYIV_TZ,
    ScheduleWindow,
)
from .schedule_events import event_summary, merge_schedule_intervals, next_schedule_boundary
from .schedule_updates import ScheduleUpdates

_LOGGER = logging.getLogger(__name__)


class DTEKDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls DTEK API for address-specific outage data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        provider: OutageProvider,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.provider = provider
        self.city: str = entry.data[CONF_CITY]
        self.street: str = entry.data[CONF_STREET]
        self.house: str = entry.data[CONF_HOUSE]

        self._schedule_update_time: str = ""
        self.schedule: ScheduleReading | None = None
        self.overview: ScheduleReading | None = None
        self.provider_notice = None
        self.schedule_state = "missing"
        self.schedule_reason: str | None = None
        self.address = Address(
            entry.data.get(CONF_PROVIDER, DEFAULT_PROVIDER_ID),
            self.city,
            self.street,
            self.house,
        )
        if self.provider.provider_id != self.address.provider_id:
            raise ProviderError("Config entry provider mismatch")
        self._address_groups: list[str] = []
        self.connection_state = "error"
        self.last_success: dt.datetime | None = None
        self.last_error: str | None = None
        self.consecutive_failures = 0
        self.snapshot: ScheduleSnapshot | None = None
        self.notifications_ready = False
        self.address_data: dict[str, Any] | None = None
        self.address_works = None
        self.works_incomplete = False
        self.address_success = False
        self.address_last_success: dt.datetime | None = None
        self.schedule_last_success: dt.datetime | None = None
        self.address_error: str | None = None
        self.schedule_error: str | None = None
        self.snapshot_storage_error: str | None = None
        self._snapshot_store = Store(
            hass, 1, f"dtek_monitor.{entry.entry_id}.schedule_snapshot"
        )
        self._diagnostic_listeners: set[Callable[[], None]] = set()
        self._clock_started = False
        self._cancel_clock: Callable[[], None] | None = None
        self.changes = ScheduleUpdates(hass, entry, self)
        self._manual_refresh_lock = asyncio.Lock()
        self._last_manual_refresh: float | None = None

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS),
        )

        self._normal_interval = timedelta(seconds=scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name=f"dtek_monitor_{self.city}_{self.street}_{self.house}",
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )

    async def async_manual_refresh(self):
        """Refresh an address with a shared per-entry limit for all UI callers."""
        async with self._manual_refresh_lock:
            remaining = max(
                60 - (monotonic() - self._last_manual_refresh)
                if self._last_manual_refresh is not None else 0,
                self.provider.diagnostics.get("public_retry_in_seconds", 0) or 0,
            )
            if remaining > 0:
                raise ServiceValidationError(
                    translation_domain="dtek_monitor", translation_key="schedule_refresh_cooldown",
                    translation_placeholders={"seconds": str(math.ceil(remaining))},
                )
            self._last_manual_refresh = monotonic()
            await self.async_refresh()
            if not self.last_update_success:
                raise HomeAssistantError(
                    translation_domain="dtek_monitor", translation_key="schedule_refresh_failed",
                )

    def async_add_diagnostic_listener(
        self, listener: Callable[[], None]
    ) -> Callable[[], None]:
        """Notify diagnostics even when HA suppresses repeated failed updates."""
        self._diagnostic_listeners.add(listener)
        return lambda: self._diagnostic_listeners.discard(listener)

    @callback
    def async_start_schedule_clock(self):
        """Keep derived states current between network polls."""
        self._clock_started = True
        self._schedule_clock()

    @callback
    def async_stop_schedule_clock(self):
        self._clock_started = False
        if self._cancel_clock:
            self._cancel_clock()
            self._cancel_clock = None

    @callback
    def _schedule_clock(self):
        if self._cancel_clock:
            self._cancel_clock()
            self._cancel_clock = None
        if self._clock_started:
            from .provider_notice import MAX_AGE
            now = dt.datetime.now(dt.timezone.utc)
            boundary = next_schedule_boundary(self.schedule if self.notifications_ready else None, now)
            notice = self.provider_notice
            if notice and notice.checked_at and not notice.error:
                expiry = notice.checked_at + MAX_AGE
                if expiry > now:
                    boundary = min(boundary, expiry)
            self._cancel_clock = async_track_point_in_utc_time(self.hass, self._clock_tick, boundary)

    @callback
    def _clock_tick(self, now):
        self._cancel_clock = None
        self.async_update_listeners()
        self._notify_diagnostics()
        self._schedule_clock()

    @callback
    def _notify_diagnostics(self):
        for listener in tuple(self._diagnostic_listeners):
            try:
                listener()
            except Exception:
                _LOGGER.exception("Failed to update DTEK connection diagnostics")

    @property
    def snapshot_attributes(self) -> dict[str, Any]:
        from .provider_notice import notice_attributes
        snapshot = self.snapshot
        return {
            **notice_attributes(self),
            "data_status": (
                "current"
                if self.notifications_ready
                else "stale" if snapshot else "missing"
            ),
            "notifications_ready": self.notifications_ready,
            "snapshot_id": snapshot.snapshot_id if snapshot else None,
            "last_verified_at": snapshot.checked_at.isoformat() if snapshot else None,
            "source_updated_at": snapshot.source_updated_at if snapshot else None,
            "schedule_groups": list(snapshot.groups) if snapshot else [],
            "coverage_start": snapshot.coverage_start.isoformat() if snapshot else None,
            "coverage_end": snapshot.coverage_end.isoformat() if snapshot else None,
            "provider_id": self.address.provider_id,
            "address_id": self.address.identity,
            "schedule_state": self.schedule_state,
            "schedule_reason": self.schedule_reason,
            "schedule_coverage": (
                [
                    {
                        "group_id": c.group_id,
                        "kind": c.kind,
                        "start": c.start.isoformat(),
                        "end": c.end.isoformat(),
                    }
                    for c in self.schedule.coverage
                ]
                if self.notifications_ready and self.schedule
                else []
            ),
        }

    async def async_load_snapshot(self) -> None:
        """Restoring a snapshot never makes live data available."""
        try:
            value = await self._snapshot_store.async_load()
            if value is not None:
                self.snapshot = ScheduleSnapshot.from_dict(
                    value,
                    provider_id=self.address.provider_id,
                    address=(self.city, self.street, self.house),
                )
                self.last_success = self.snapshot.checked_at
        except (ValueError, TypeError, KeyError, OSError, OverflowError) as err:
            self.snapshot_storage_error = str(err)
            _LOGGER.warning("Cannot restore DTEK schedule snapshot: %s", err)

    async def _async_update_data(self) -> dict[str, Any]:
        """A fresh address and schedule are both required for notifications."""
        self.notifications_ready = False
        try:
            data = await self._fetch_data()
        except ProviderError as err:
            self.connection_state = "error"
            self.last_error = str(err)
            self.consecutive_failures += 1
            delay = min(60 * 2 ** min(self.consecutive_failures - 1, 4), 600)
            retry_in = self.provider.diagnostics.get("public_retry_in_seconds", 0)
            retry_in = retry_in if type(retry_in) is int else 0
            self.update_interval = timedelta(
                seconds=max(retry_in, delay * random.uniform(0.9, 1.1))
            )
            raise UpdateFailed(f"Error fetching DTEK data: {err}") from err
        else:
            self.connection_state = "ok"
            self.last_success = dt.datetime.now(dt.timezone.utc)
            self.last_error = None
            self.consecutive_failures = 0
            self.update_interval = self._normal_interval
            if self.schedule is None or self.schedule.state != "current":
                # A verified address without a published schedule is a successful
                # poll. Preserve only the separate display snapshot; no live
                # calendar or notification may use it as a confirmed empty day.
                return data
            start = self.last_success.astimezone(KYIV_TZ).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = start + timedelta(days=SNAPSHOT_DAYS)
            self.snapshot = ScheduleSnapshot(
                self.address.provider_id,
                (self.city, self.street, self.house),
                tuple(self._address_groups),
                self.last_success,
                self._schedule_update_time,
                start,
                end,
                tuple(i.as_window() for i in self.schedule.intervals),
                contract_revision=self.schedule.revision,
            )
            try:
                await self._snapshot_store.async_save(self.snapshot.to_dict())
                self.snapshot_storage_error = None
            except OSError as err:
                self.snapshot_storage_error = str(err)
                _LOGGER.warning("Cannot persist DTEK schedule snapshot: %s", err)
            self.notifications_ready = True
            return data
        finally:
            await self.changes.update()
            # HA normally suppresses listeners on consecutive failures. Address
            # status and display snapshots still need updates during that time.
            if not self.last_update_success:
                self.hass.loop.call_soon(self.async_update_listeners)
            self._notify_diagnostics()
            self._schedule_clock()

    async def _fetch_data(self) -> dict[str, Any]:
        """Only normalized provider results cross into Home Assistant."""
        self.address_success = False
        self.address_works = None
        self.works_incomplete = False
        self.overview = None
        self.address_error = self.schedule_error = None
        self.schedule_state = "missing"
        self.schedule_reason = None
        now = dt.datetime.now(dt.timezone.utc)
        start = now.astimezone(KYIV_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        try:
            result = await self.provider.refresh(
                self.address, start, start + timedelta(days=SNAPSHOT_DAYS)
            )
            self.provider_notice = result.notice
        except ProviderError as err:
            self.address_error = self.schedule_error = str(err)
            raise
        self.address_error, self.schedule_error = (
            result.address_error,
            result.schedule_error,
        )
        if result.address is not None:
            if result.address.address != self.address:
                raise ProviderError("Provider returned a foreign address")
            self.address_data = {
                **result.address.as_ha_data(),
                "address_updated_at": result.address.source_updated_at,
                "group_labels_visible": result.address.publication.group_labels is True,
            }
            self.address_success = True
            self.address_works = result.address.works
            self.works_incomplete = result.address.works_incomplete
            self.address_last_success = result.address.fetched_at
        if result.schedule_checked_at is not None:
            self.schedule_last_success = result.schedule_checked_at
        if result.schedule is not None:
            self.schedule_state = result.schedule.state
            self.schedule_reason = result.schedule.reason
        if self.address_error or self.schedule_error:
            raise ProviderError(self.address_error or self.schedule_error)
        schedule = result.schedule
        if result.address is None or schedule is None:
            raise ProviderError("Provider could not verify address and schedule")
        if schedule.state not in ("current", "missing", "unpublished", "unsupported"):
            raise ProviderError("Unknown schedule publication state")
        if (
            schedule.address != self.address
            or tuple(g.id for g in schedule.groups) != result.address.groups
        ):
            raise ProviderError("Schedule does not match the verified address/groups")
        self.schedule = merge_schedule_intervals(schedule)
        if result.overview is not None and result.overview.address != self.address:
            raise ProviderError("Overview belongs to a different address")
        self.overview = result.overview
        self._address_groups = list(result.address.groups)
        self._schedule_update_time = schedule.source_updated_at.astimezone(
            KYIV_TZ
        ).strftime("%d.%m.%Y %H:%M")
        return {
            **self.address_data,
            "schedule_update_time": self._schedule_update_time,
            "schedule_updated_at": schedule.source_updated_at,
            "provider_id": self.address.provider_id,
            "address_id": self.address.identity,
            "group_labels": {g.id: g.label for g in schedule.groups},
        }

    def get_events_for_range(
        self, start, end, groups, event_type=None
    ) -> list[CalendarEvent]:
        if not self.notifications_ready or self.schedule is None:
            return []
        start = start.replace(tzinfo=KYIV_TZ) if start.tzinfo is None else start
        end = end.replace(tzinfo=KYIV_TZ) if end.tzinfo is None else end
        return [
            _window_to_calendar_event(i.as_window(), self.hass.config.language)
            for i in self.schedule.intervals
            if i.group_id in groups
            and (event_type is None or i.kind == event_type)
            and i.end > start
            and i.start < end
        ]

    def events_for_date(self, date, groups, event_type=None) -> list[CalendarEvent]:
        start = dt.datetime.combine(date, dt.time(), tzinfo=KYIV_TZ)
        return self.get_events_for_range(
            start, start + timedelta(days=1), groups, event_type
        )

    def current_or_next_event(
        self, now, groups, event_type=None
    ) -> CalendarEvent | None:
        events = self.get_events_for_range(
            now, now + timedelta(days=SNAPSHOT_DAYS), groups, event_type
        )
        return events[0] if events else None


def _window_to_calendar_event(window: ScheduleWindow, language="en") -> CalendarEvent:
    """Convert a pure schedule window into a Home Assistant CalendarEvent."""
    return CalendarEvent(
        start=window.start,
        end=window.end,
        summary=event_summary(window.event_type, language),
        description=window.description,
    )
