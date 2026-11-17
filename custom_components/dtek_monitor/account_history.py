"""Dated cabinet records, kept out of HA state history and energy statistics."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from datetime import date, datetime
import re
from decimal import Decimal
from time import monotonic
from zoneinfo import ZoneInfo

from .account import AccountError, AccountRateLimitError, decimal_value

KYIV = ZoneInfo("Europe/Kyiv")
MAX_HISTORY_ROWS = 1000
MAX_HISTORY_PAGES = 20


def reading_history_page(rows, *, include_inactive=False, offset=0):
    """A display-only page; retain raw records for readback and accounting."""
    energy = [row for row in rows if row.get("energy") == "ACTIVE"]
    inactive = sum(row.get("status") == "inactive" for row in energy)
    visible = [row for row in energy if include_inactive or row.get("status") != "inactive"]
    size = 6
    offset = min(max(0, offset // size), max(0, (len(visible) - 1) // size)) * size
    return {
        "latest": visible[offset:offset + size],
        "history_view": {
            "include_inactive": include_inactive,
            "inactive_count": inactive,
            "total": len(energy),
            "visible": len(visible),
            "offset": offset,
            "previous_offset": offset - size if offset else None,
            "next_offset": offset + size if offset + size < len(visible) else None,
        },
    }


def validate_year(year, today: date) -> int:
    if type(year) is not int or not 2000 <= year <= today.year:
        raise AccountError("Invalid history year")
    return year


def _code(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Z_0-9]{1,40}", value):
        raise AccountError("Invalid history scale or energy type")
    return value


def _number(value):
    result = decimal_value(value)
    # Keep values safely representable by the chart's numeric coordinate system.
    if result.copy_abs() > Decimal("9007199254740991"):
        raise AccountError("History value exceeds the supported numeric range")
    return result


def parse_history_page(payload, year: int, today: date):
    """Keep source flags explicit; inactive does not mean rejected.

    The observed endpoint identifies the account, not each historical meter.
    Never assign the current meter to old rows or derive consumption deltas.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise AccountError("Invalid history response")
    if len(payload["data"]) > MAX_HISTORY_ROWS:
        raise AccountError("Excessive history response")
    page, pages = payload.get("page"), payload.get("totalPages")
    if (
        type(page) is not int
        or page < 1
        or type(pages) is not int
        or not 0 <= pages <= MAX_HISTORY_PAGES
    ):
        raise AccountError("Invalid or excessive history pagination")
    if page > max(pages, 1) or (pages == 0 and payload["data"]):
        raise AccountError("Inconsistent history pagination")
    rows = []
    for item in payload["data"]:
        if not isinstance(item, dict):
            raise AccountError("Invalid history record")
        identity = item.get("id")
        if (
            type(identity) not in (str, int)
            or not str(identity)
            or len(str(identity)) > 200
        ):
            raise AccountError("Missing history record identity")
        try:
            stamp = datetime.fromisoformat(item["dateTime"])
        except (KeyError, ValueError, TypeError):
            raise AccountError("Invalid history date") from None
        stamp = (
            stamp.replace(tzinfo=KYIV)
            if stamp.tzinfo is None
            else stamp.astimezone(KYIV)
        )
        if stamp.date() > today:
            raise AccountError("History record outside the requested period")
        # Some cabinets ignore the year query and paginate the complete history.
        # Compare the Kyiv date, retaining future-date validation before filtering.
        if stamp.year != year:
            continue
        value = _number(item.get("value"))
        if value < 0:
            raise AccountError("Invalid historical meter reading")
        flags = [item.get(k) for k in ("isBlocked", "isInactive")]
        if any(v is not None and type(v) is not bool for v in flags):
            raise AccountError("Invalid history flags")
        blocked, inactive = flags
        status = (
            "blocked"
            if blocked is True
            else (
                "inactive"
                if inactive is True
                else "active"
                if flags == [False, False]
                else "unknown"
            )
        )
        source = item.get("kind")
        if source is not None and (not isinstance(source, str) or len(source) > 200):
            raise AccountError("Invalid history source")
        rows.append(
            (
                str(identity),
                {
                    "date_time": stamp.isoformat(),
                    "value": str(value),
                    "energy": _code(item.get("deviceEnergyType")),
                    "zone": _code(item.get("deviceScaleType")),
                    "source": source,
                    "origin": item.get("origin")
                    if isinstance(item.get("origin"), str)
                    and len(item["origin"]) <= 200
                    else None,
                    "status": status,
                    "blocked": blocked,
                    "inactive": inactive,
                    "has_photo": item.get("hasPhoto") is True,
                    "controller_note": item.get("controllerNote")
                    if isinstance(item.get("controllerNote"), str)
                    and len(item["controllerNote"]) <= 1000 else None,
                },
            )
        )
    return page, pages, rows


def parse_months(payload, year: int, today: date):
    """Twelve explicit periods; missing/open months never become closed zeroes."""
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise AccountError("Invalid monthly consumption response")
    found = {}
    for item in payload["items"]:
        if not isinstance(item, dict):
            raise AccountError("Invalid monthly consumption item")
        period = item.get("date")
        if not isinstance(period, str) or not re.fullmatch(r"\d{4}-\d{2}", period):
            raise AccountError("Invalid consumption period")
        try:
            day = date.fromisoformat(period + "-01")
        except ValueError:
            raise AccountError("Invalid consumption period") from None
        if day.year != year or period in found:
            raise AccountError("Foreign or duplicate consumption period")
        total = _number(item.get("consumption"))
        zones = item.get("zones", [])
        if not isinstance(zones, list):
            raise AccountError("Invalid consumption zones")
        normalized = {}
        for zone in zones:
            if not isinstance(zone, dict):
                raise AccountError("Invalid consumption zone")
            key = _code(zone.get("zone"))
            if key in normalized:
                raise AccountError("Duplicate consumption zone")
            normalized[key] = str(_number(zone.get("consumption")))
        found[period] = {"value": str(total), "zones": normalized}
    result = []
    for month in range(1, 13):
        day = date(year, month, 1)
        period = day.strftime("%Y-%m")
        state = (
            "future"
            if day > today.replace(day=1)
            else (
                "open"
                if day == today.replace(day=1)
                else "closed"
                if period in found
                else "missing"
            )
        )
        data = (
            found.get(period, {"value": None, "zones": {}})
            if state != "future"
            else {"value": None, "zones": {}}
        )
        result.append({"period": period, "status": state, **data})
    return result


class HistoryCache:
    """Bounded per-connection cache; failures are never cached as empty history."""

    def __init__(self, client):
        self.client = client
        self._lock = asyncio.Lock()
        self._cache = OrderedDict()
        self._attempts = OrderedDict()
        self._blocked_until = 0
        self._generation = 0

    def invalidate(self, number):
        self._generation += 1
        for key in list(self._cache):
            if key[0] == number:
                del self._cache[key]

    async def get(self, number, year, *, force=False, max_age=6 * 3600):
        validate_year(year, datetime.now(KYIV).date())
        key = (number, year)
        async with self._lock:
            now = monotonic()
            cached = self._cache.get(key)
            ttl = min(max_age, 60) if cached and cached[1].get("unavailable") else max_age
            if cached and not force and now - cached[0] < ttl:
                self._cache.move_to_end(key)
                return cached[1]
            if (
                now < self._blocked_until
                or now - self._attempts.get(key, -float("inf")) < 60
            ):
                raise AccountRateLimitError("History refresh is temporarily limited")
            self._attempts[key] = now
            self._attempts.move_to_end(key)
            while len(self._attempts) > 64:
                self._attempts.popitem(last=False)
            try:
                generation = self._generation
                result = await self.client.read_history(number, year)
            except AccountRateLimitError:
                self._blocked_until = monotonic() + 300
                raise
            if generation != self._generation:
                raise AccountError(
                    "Account history changed during refresh; retry later"
                )
            # Store completion time; a failed refresh retains only an old, dated cache.
            self._cache[key] = (monotonic(), result)
            self._cache.move_to_end(key)
            while len(self._cache) > 16:
                self._cache.popitem(last=False)
            return result
