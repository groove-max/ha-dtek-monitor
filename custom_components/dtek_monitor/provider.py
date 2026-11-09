"""Provider-independent address and schedule contract (no Home Assistant imports)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping, Protocol

from .schedule import ScheduleWindow
from .const import EVENT_SUMMARY_OUTAGE, EVENT_SUMMARY_POSSIBLE
from .provider_notice import ProviderNotice


class ProviderError(Exception):
    """A provider cannot verify the requested information."""


@dataclass(frozen=True)
class Address:
    provider_id: str
    city: str
    street: str
    house: str

    @property
    def parts(self) -> tuple[str, str, str]:
        return self.city, self.street, self.house

    @property
    def identity(self) -> str:
        # Delimiters in address names cannot cause cross-address collisions.
        return hashlib.sha256(
            json.dumps([self.provider_id, *self.parts], ensure_ascii=False).encode()
        ).hexdigest()


@dataclass(frozen=True)
class Publication:
    """None means not established, never an affirmative publication signal."""

    schedule: bool | None
    daily: bool | None
    weekly: bool | None
    group_labels: bool | None


@dataclass(frozen=True)
class Group:
    id: str
    label: str | None


@dataclass(frozen=True)
class AddressWork:
    """One operator-reported repair interval, independent of group schedules."""

    start: datetime
    end: datetime
    description: str


@dataclass(frozen=True)
class AddressReading:
    address: Address
    # Already normalized legacy HA attributes, never a provider's wire response.
    values: Mapping[str, Any]
    groups: tuple[str, ...]
    fetched_at: datetime
    source_updated_at: datetime | None
    publication: Publication
    external_operator: bool = False
    # None: unsupported/unverified; (): verified response has no repair records.
    works: tuple[AddressWork, ...] | None = None
    works_incomplete: bool = False

    def as_ha_data(self) -> dict[str, Any]:
        return dict(self.values)


@dataclass(frozen=True)
class Interval:
    group_id: str
    kind: str
    start: datetime
    end: datetime
    source: str  # daily schedule or weekly forecast

    def as_window(self) -> ScheduleWindow:
        return ScheduleWindow(
            self.kind,
            self.start,
            self.end,
            EVENT_SUMMARY_OUTAGE if self.kind == "outage" else EVENT_SUMMARY_POSSIBLE,
            f"{'Planned' if self.kind == 'outage' else 'Possible'}; group={self.group_id}",
        )


@dataclass(frozen=True)
class Coverage:
    """A fully described time range for one group and calendar kind."""

    group_id: str
    kind: str
    start: datetime
    end: datetime


@dataclass(frozen=True)
class ScheduleReading:
    address: Address
    groups: tuple[Group, ...]
    intervals: tuple[Interval, ...]
    coverage: tuple[Coverage, ...]
    fetched_at: datetime
    source_updated_at: datetime
    publication: Publication
    state: str  # current, unpublished, unsupported, missing
    reason: str | None = None

    @property
    def revision(self) -> str:
        """Include source, applicability and identity, but not poll completion time."""
        payload = {
            "address": self.address.identity,
            "groups": [(g.id, g.label) for g in self.groups],
            "intervals": [
                (i.group_id, i.kind, i.start.isoformat(), i.end.isoformat(), i.source)
                for i in self.intervals
            ],
            "coverage": [
                (c.group_id, c.kind, c.start.isoformat(), c.end.isoformat())
                for c in self.coverage
            ],
            "source_updated_at": self.source_updated_at.isoformat(),
            "publication": vars(self.publication),
            "state": self.state,
            "reason": self.reason,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class RefreshResult:
    address: AddressReading | None
    schedule: ScheduleReading | None
    address_error: str | None = None
    schedule_error: str | None = None
    schedule_checked_at: datetime | None = None
    # Optional operator-wide display; never drives address calendars or alerts.
    overview: ScheduleReading | None = None
    notice: ProviderNotice | None = None


class OutageProvider(Protocol):
    """One provider instance owns its session and source-specific parsing/cache."""

    provider_id: str

    @property
    def diagnostics(self) -> Mapping[str, Any]: ...

    async def list_localities(self) -> tuple[str, ...]: ...
    async def list_streets(self, city: str) -> tuple[str, ...]: ...
    async def list_houses(self, city: str, street: str) -> tuple[str, ...]: ...
    async def refresh(
        self, address: Address, start: datetime, end: datetime
    ) -> RefreshResult: ...
    async def close(self) -> None: ...
