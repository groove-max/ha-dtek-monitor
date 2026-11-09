"""DTEK website adapter: all wire formats stay below the provider boundary."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any

from .dtek_client import DTEKClient, parse_dtek_datetime
from .address_works import address_works
from .provider import (
    Address,
    AddressReading,
    Coverage,
    Group,
    Interval,
    Publication,
    ProviderError,
    RefreshResult,
    ScheduleReading,
)
from .providers import ProviderSpec
from .schedule import KYIV_TZ, get_schedule_windows_for_date

_CODES = {"yes", "no", "maybe", "first", "second", "mfirst", "msecond"}


def normalize_directory(
    value: Any, fixed_city: str | None
) -> dict[str, tuple[str, ...]]:
    if fixed_city is not None and isinstance(value, list):
        value = {fixed_city: value}
    if not isinstance(value, dict) or not value:
        raise ProviderError("Malformed or empty address directory")
    result = {}
    for city, streets in value.items():
        if (
            not isinstance(city, str)
            or not city.strip()
            or not isinstance(streets, list)
        ):
            raise ProviderError("Malformed address directory entry")
        if any(not isinstance(s, str) for s in streets):
            raise ProviderError("Malformed street name")
        result[city.strip()] = tuple(sorted({s.strip() for s in streets if s.strip()}))
    return result


def normalize_address(
    address: Address, response: dict, fetched_at: datetime
) -> AddressReading:
    try:
        values = DTEKClient.parse_house_data(response, address.house)
    except (TypeError, ValueError, AttributeError) as err:
        raise ProviderError("Malformed address fields") from err
    # Missing house data is not proof that the address currently has power.
    record = next(
        (
            v
            for k, v in response["data"].items()
            if isinstance(k, str) and k.casefold() == address.house.casefold()
        ),
        None,
    )
    if not record:
        raise ProviderError("Address not found in provider response")
    entries = record if isinstance(record, list) else [record]

    def flag(key):
        value = response.get(key)
        if value is not None and not isinstance(value, bool):
            raise ProviderError(f"Malformed publication flag: {key}")
        return value

    schedule = flag("showCurSchedule")
    if flag("showTableSchedule") is not True:
        schedule = False if response.get("showTableSchedule") is False else None
    publication = Publication(
        schedule, flag("showTableFact"), flag("showTablePlan"), flag("showUserGroup")
    )
    external_operator = any(bool(e.get("cek")) for e in entries)
    works, incomplete = address_works(values)
    return AddressReading(
        address,
        MappingProxyType(deepcopy(values)),
        tuple(values["schedule_groups"]),
        fetched_at,
        (
            parse_dtek_datetime(values["dtek_update_time"])
            if isinstance(values["dtek_update_time"], str)
            else None
        ),
        publication,
        external_operator,
        None if external_operator else works,
        incomplete,
    )


def _data(raw: dict, key: str) -> dict:
    part = raw.get(key)
    if not isinstance(part, dict):
        raise ProviderError(f"Malformed {key} schedule data")
    data = part.get("data")
    # The website serializes empty PHP maps as [] in a legitimate empty response.
    if data == []:
        return {}
    if not isinstance(data, dict):
        raise ProviderError(f"Malformed {key} schedule data")
    return data


def normalize_schedule(
    reading: AddressReading,
    raw: dict,
    start: datetime,
    end: datetime,
    fetched_at: datetime,
) -> ScheduleReading:
    fact, preset = _data(raw, "fact"), _data(raw, "preset")
    version = raw["fact"].get("update") or raw["preset"].get("updateFact")
    updated = parse_dtek_datetime(version) if isinstance(version, str) else None
    if updated is None:
        raise ProviderError("Schedule timestamp missing; freshness cannot be verified")
    if (
        start.tzinfo is None
        or end.tzinfo is None
        or fetched_at.tzinfo is None
        or end <= start
    ):
        raise ProviderError("Schedule range must be ordered and timezone-aware")
    if end - start > timedelta(days=9):
        raise ProviderError("Schedule range exceeds the supported horizon")
    layout = raw["preset"].get("time_zone")
    if layout is not None:
        expected = {str(h) for h in range(1, 25)}
        if not isinstance(layout, dict) or set(layout) != expected:
            raise ProviderError("Unsupported schedule time grid")
        for hour in range(1, 25):
            cell = layout[str(hour)]
            if (
                not isinstance(cell, list)
                or len(cell) < 3
                or cell[1:] != [f"{hour - 1:02}:00", f"{hour:02}:00"]
            ):
                raise ProviderError("Unsupported schedule time grid")
    names = raw["preset"].get("sch_names", {})
    if not isinstance(names, dict):
        raise ProviderError("Malformed schedule names")
    groups = tuple(
        Group(
            g,
            str(names.get(g, g)) if reading.publication.group_labels is True else None,
        )
        for g in reading.groups
    )
    state, reason = "current", None
    if reading.external_operator:
        state, reason = (
            "unsupported",
            "Address refers to an external distribution operator",
        )
    elif reading.publication.schedule is False:
        state, reason = "unpublished", "Provider has disabled schedule publication"
    elif reading.publication.schedule is not True:
        state, reason = "missing", "Schedule publication could not be verified"
    elif not groups:
        state, reason = "missing", "Address groups could not be verified"
    intervals, coverage = [], []
    day = start.astimezone(KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    while state == "current" and day < end:
        day_end = day + timedelta(days=1)
        day_data = fact.get(str(int(day.timestamp())), {})
        if not isinstance(day_data, dict):
            raise ProviderError("Malformed daily schedule")
        for group in groups:
            daily = (
                day_data.get(group.id) if reading.publication.daily is True else None
            )
            weekly_group = preset.get(group.id, {})
            if not isinstance(weekly_group, dict):
                raise ProviderError("Malformed weekly schedule")
            weekly = (
                weekly_group.get(str(day.isoweekday()))
                if reading.publication.weekly is True
                else None
            )

            def complete(slots):
                if slots is None:
                    return False
                if (
                    not isinstance(slots, dict)
                    or any(
                        v not in _CODES for v in slots.values() if isinstance(v, str)
                    )
                    or any(not isinstance(v, str) for v in slots.values())
                ):
                    raise ProviderError("Malformed schedule slots")
                return all(str(hour) in slots for hour in range(1, 25))

            has_daily = complete(daily)
            # A complete dated schedule supersedes a recurring weekly forecast.
            has_weekly = not has_daily and complete(weekly)
            if not has_daily and not has_weekly:
                continue
            # Weekly forecasts alone cannot confirm the daily outage calendar.
            for kind in ("outage", "possible") if has_daily else ("possible",):
                coverage.append(
                    Coverage(group.id, kind, max(day, start), min(day_end, end))
                )
            fact_for_group = (
                {str(int(day.timestamp())): {group.id: daily}} if has_daily else {}
            )
            preset_for_group = (
                {group.id: {str(day.isoweekday()): weekly}} if has_weekly else {}
            )
            for w in get_schedule_windows_for_date(
                day.date(), [group.id], fact_for_group, preset_for_group
            ):
                if w.end <= start or w.start >= end:
                    continue
                intervals.append(
                    Interval(
                        group.id,
                        w.event_type if has_daily else "possible",
                        max(w.start, start),
                        min(w.end, end),
                        (
                            "weekly"
                            if has_weekly
                            and (w.event_type == "possible" or not has_daily)
                            else "daily"
                        ),
                    )
                )
        day = day_end
    if state == "current":
        missing = [
            g.id
            for g in groups
            if not any(
                c.group_id == g.id and c.start <= fetched_at < c.end for c in coverage
            )
        ]
        if missing:
            state, reason = (
                "missing",
                f"Current schedule coverage is missing for address groups: {', '.join(missing)}",
            )
    return ScheduleReading(
        reading.address,
        groups,
        tuple(sorted(intervals, key=lambda i: (i.start, i.end, i.group_id, i.kind))),
        tuple(coverage),
        fetched_at,
        updated,
        reading.publication,
        state,
        reason,
    )


def normalize_overview(reading, raw, start, end, fetched_at):
    """All published operator groups, isolated from the address notification contract."""
    ids = (
        set(_data(raw, "preset"))
        | set(reading.groups)
        | set(raw["preset"].get("sch_names", {}))
    )
    for day in _data(raw, "fact").values():
        if isinstance(day, dict):
            ids.update(day)
    if len(ids) > 64 or any(
        not isinstance(g, str) or not g or len(g) > 64 for g in ids
    ):
        raise ProviderError("Invalid overview groups")
    groups, intervals, coverage = [], [], []
    for group in sorted(ids):
        groups.append(Group(group, group))
        try:
            item = normalize_schedule(
                replace(reading, groups=(group,)), raw, start, end, fetched_at
            )
        except ProviderError:
            # A malformed unrelated group is shown as unknown; it cannot break
            # the home's verified calendar or acquire a reassuring empty row.
            continue
        groups[-1] = item.groups[0]
        intervals.extend(item.intervals)
        coverage.extend(item.coverage)
    return ScheduleReading(
        reading.address,
        tuple(groups),
        tuple(intervals),
        tuple(coverage),
        fetched_at,
        parse_dtek_datetime(
            raw["fact"].get("update") or raw["preset"].get("updateFact")
        ),
        reading.publication,
        "unsupported" if reading.external_operator else "current",
    )


class DTEKWebProvider:
    def __init__(
        self, spec: ProviderSpec, client: DTEKClient | None = None, *, request_gate=None
    ):
        self.spec = spec
        self.provider_id = spec.id
        self._client = (
            client if client is not None
            else DTEKClient(spec.base_url, request_gate=request_gate)
        )
        self._directory: dict[str, tuple[str, ...]] | None = None
        self._raw: dict[str, Any] = {}

    @property
    def diagnostics(self) -> dict[str, Any]:
        gate = getattr(self._client, "request_gate", None)
        return {
            "transport_errors": self._client.transport_errors,
            "protection_challenges": self._client.waf_challenges,
            "protection_blocks": self._client.waf_hard_blocks,
            "browser_profile": self._client.impersonate_target,
            "public_retry_in_seconds": getattr(gate, "retry_in", None),
            "public_consecutive_failures": getattr(gate, "failures", None),
        }

    async def _get_directory(self) -> dict[str, tuple[str, ...]]:
        if self._directory is None:
            response = await self._client._post({"method": "getStreets"})
            self._directory = normalize_directory(
                response.get("streets"), self.spec.fixed_city
            )
        return self._directory

    async def list_localities(self) -> tuple[str, ...]:
        return tuple(sorted(await self._get_directory()))

    async def list_streets(self, city: str) -> tuple[str, ...]:
        return (await self._get_directory()).get(city, ())

    async def list_houses(self, city: str, street: str) -> tuple[str, ...]:
        data = (
            await self._client.get_home_status(
                "" if self.spec.fixed_city else city, street
            )
        ).get("data")
        if not isinstance(data, dict) or any(not isinstance(h, str) for h in data):
            raise ProviderError("Malformed house list")
        return tuple(sorted(data))

    async def refresh(
        self, address: Address, start: datetime, end: datetime
    ) -> RefreshResult:
        if address.provider_id != self.provider_id:
            raise ProviderError("Address provider mismatch")
        reading = schedule = overview = None
        address_error = schedule_error = None
        checked = None
        try:
            response = await self._client.get_home_status(
                "" if self.spec.fixed_city else address.city,
                address.street,
                address.house,
            )
            reading = normalize_address(address, response, datetime.now(timezone.utc))
        except ProviderError as err:
            address_error = str(err)
        try:
            candidate = deepcopy(self._raw)
            page = self._client.consume_schedule_update()
            if page is None:
                page = self._client.get_schedule_data()
            if page:
                candidate.update(deepcopy(page))
            if not isinstance(candidate.get("fact"), dict) or not isinstance(
                candidate.get("preset"), dict
            ):
                raise ProviderError("Malformed schedule payload")
            if reading is not None:
                for key in ("fact", "preset"):
                    if key in response:
                        candidate[key] = deepcopy(response[key])
            _data(candidate, "fact")
            _data(candidate, "preset")
            stamp = candidate.get("fact", {}).get("update") or candidate.get(
                "preset", {}
            ).get("updateFact")
            if not isinstance(stamp, str) or parse_dtek_datetime(stamp) is None:
                raise ProviderError(
                    "Schedule timestamp missing; freshness cannot be verified"
                )
            delta = await self._client.check_update(stamp)
            if delta:
                candidate.update(deepcopy(delta))
                if reading is not None:
                    flags = {k: v for k, v in delta.items() if k.startswith("show")}
                    reading = normalize_address(
                        address, {**response, **flags}, reading.fetched_at
                    )
            # A verification of the source can succeed even if the address failed.
            _data(candidate, "fact")
            _data(candidate, "preset")
            checked = datetime.now(timezone.utc)
            if reading is not None:
                schedule = normalize_schedule(reading, candidate, start, end, checked)
                try:
                    overview = normalize_overview(
                        reading, candidate, start, end, checked
                    )
                except ProviderError:
                    overview = None
                # Publication/coverage is data, not a transport failure.
                # Keep the reason on ScheduleReading; errors mean failed requests
                # or an invalid response, never a legitimate absent schedule.
            self._raw = candidate
        except ProviderError as err:
            schedule_error = str(err)
        # Optional notice retrieval must not turn a published schedule/address
        # into a failed setup. Its unknown state is exposed independently.
        notice = await self._client.get_provider_notice() if hasattr(self._client, "get_provider_notice") else None
        return RefreshResult(
            reading, schedule, address_error, schedule_error, checked, overview, notice
        )

    async def close(self) -> None:
        await self._client.close()
