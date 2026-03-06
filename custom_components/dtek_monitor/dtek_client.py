"""HTTP client for the DTEK OEM API."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp

from .const import (
    DTEK_AJAX_URL,
    DTEK_SHUTDOWNS_URL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

CSRF_META_RE = re.compile(r'<meta\s+name="csrf-token"\s+content="([^"]+)"')

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)

COMMON_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": DTEK_SHUTDOWNS_URL,
}


class DTEKApiError(Exception):
    """Base exception for DTEK API errors."""


class DTEKAuthError(DTEKApiError):
    """CSRF or session error — need to re-authenticate."""


class DTEKClient:
    """Async HTTP client for DTEK OEM shutdowns API.

    Handles CSRF token acquisition and all API methods.
    Requires a dedicated aiohttp.ClientSession with its own CookieJar.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session
        self._csrf_token: str | None = None
        self._schedule_data: dict[str, Any] | None = None

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self._session.close()

    async def _ensure_session(self) -> None:
        """Fetch the shutdowns page to obtain CSRF token and session cookie."""
        if self._csrf_token is not None:
            return

        await self._refresh_session()

    async def _refresh_session(self) -> None:
        """Force-refresh CSRF token and session cookies."""
        _LOGGER.debug("Refreshing DTEK session and CSRF token")

        try:
            async with self._session.get(
                DTEK_SHUTDOWNS_URL,
                headers={"User-Agent": BROWSER_UA},
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    raise DTEKApiError(
                        f"Failed to load shutdowns page: HTTP {resp.status}"
                    )

                html = await resp.text()

                match = CSRF_META_RE.search(html)
                if not match:
                    raise DTEKAuthError("CSRF token not found in page HTML")

                self._csrf_token = match.group(1)

                # Cookies are handled automatically by aiohttp CookieJar

                # Parse schedule data embedded in HTML <script> tags
                schedule = _parse_schedule_from_html(html)
                if schedule:
                    self._schedule_data = schedule

                _LOGGER.debug("DTEK session refreshed")

        except aiohttp.ClientError as err:
            self._csrf_token = None
            raise DTEKApiError(f"Network error loading DTEK page: {err}") from err

    async def _post(
        self,
        data: dict[str, str],
        retry: bool = True,
        require_result: bool = True,
    ) -> dict[str, Any]:
        """Send POST request to the DTEK AJAX endpoint.

        Automatically refreshes CSRF on auth errors and retries once.

        Args:
            data: POST form data.
            retry: Whether to retry on CSRF failure.
            require_result: If True, raise on result=false. Set False for
                            methods where result=false is a valid response.
        """
        await self._ensure_session()

        headers = {
            **COMMON_HEADERS,
            "User-Agent": BROWSER_UA,
            "X-Csrf-Token": self._csrf_token,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        try:
            async with self._session.post(
                DTEK_AJAX_URL,
                data=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 400:
                    if retry:
                        _LOGGER.debug("Got 400, refreshing CSRF and retrying")
                        self._csrf_token = None
                        await self._refresh_session()
                        return await self._post(data, retry=False,
                                                require_result=require_result)
                    raise DTEKAuthError("CSRF validation failed after refresh")

                if resp.status != 200:
                    raise DTEKApiError(f"DTEK API returned HTTP {resp.status}")

                result = await resp.json(content_type=None)

                if require_result and (
                    not isinstance(result, dict) or not result.get("result")
                ):
                    raise DTEKApiError(f"DTEK API returned error: {result}")

                return result

        except aiohttp.ClientError as err:
            raise DTEKApiError(f"Network error calling DTEK API: {err}") from err

    async def get_streets(self) -> dict[str, list[str]]:
        """Fetch all cities and their streets.

        Returns dict mapping city names to lists of street names.
        """
        result = await self._post({"method": "getStreets"})
        streets = result.get("streets", {})
        if not isinstance(streets, dict):
            raise DTEKApiError("Unexpected streets format in API response")
        return streets

    async def get_home_status(
        self,
        city: str,
        street: str,
        house_num: str = "",
        update_fact: str = "",
    ) -> dict[str, Any]:
        """Fetch outage status for an address.

        Args:
            city: City name (e.g. "м. Одеса")
            street: Street name (e.g. "дорога Люстдорфська")
            house_num: House number (e.g. "56В"), empty to get all houses
            update_fact: Last known update timestamp for delta updates

        Returns:
            Full API response dict with "data", "updateTimestamp", etc.
        """
        data = {
            "method": "getHomeNum",
            "data[0][name]": "city",
            "data[0][value]": city,
            "data[1][name]": "street",
            "data[1][value]": street,
            "data[2][name]": "house_num",
            "data[2][value]": house_num,
            "data[3][name]": "updateFact",
            "data[3][value]": update_fact,
        }
        return await self._post(data)

    async def check_update(self, timestamp: str) -> dict[str, Any] | None:
        """Check if schedule data has been updated since the given timestamp.

        Args:
            timestamp: Last known update time (format: "DD.MM.YYYY HH:MM")

        Returns:
            Dict with "fact" and "preset" keys if updated, None otherwise.
        """
        result = await self._post(
            {"method": "checkDisconUpdate", "update": timestamp},
            require_result=False,
        )
        if not isinstance(result, dict) or not result.get("result"):
            _LOGGER.debug("No schedule updates since %s", timestamp)
            return None

        # API returns updated fact + preset when there's a change
        update_data: dict[str, Any] = {}
        if "fact" in result:
            update_data["fact"] = result["fact"]
        if "preset" in result:
            update_data["preset"] = result["preset"]

        if update_data:
            self._schedule_data = update_data
            _LOGGER.debug("DTEK schedule updated (new data received)")

        return update_data or None

    def get_schedule_data(self) -> dict[str, Any] | None:
        """Return cached schedule data (fact + preset)."""
        return self._schedule_data

    @staticmethod
    def parse_house_data(api_response: dict[str, Any], house_num: str) -> dict[str, Any]:
        """Extract and normalize data for a specific house from API response.

        Handles both single outage (dict) and multiple outages (list).
        Returns a dict with normalized outage information.
        """
        houses = api_response.get("data", {})
        update_timestamp = api_response.get("updateTimestamp", "")

        no_outage: dict[str, Any] = {
            "power_on": True,
            "outage_type": "ok",
            "outage_description": "",
            "outage_start": None,
            "outage_end": None,
            "schedule_groups": [],
            "dtek_update_time": update_timestamp,
            "raw_type": "",
            "outage_count": 0,
            "all_outages": [],
        }

        house_data = houses.get(house_num)
        if house_data is None:
            # Try case-insensitive match
            for key, value in houses.items():
                if key.lower() == house_num.lower():
                    house_data = value
                    break

        if house_data is None:
            _LOGGER.debug(
                "No data for house %s in API response (keys: %s)",
                house_num, list(houses.keys()),
            )
            return no_outage

        # Normalize to list: API may return a dict (single) or list (multiple)
        if isinstance(house_data, dict):
            entries = [house_data]
        elif isinstance(house_data, list):
            entries = house_data
            _LOGGER.debug(
                "DTEK returned %d outage entries for %s (multiple outages)",
                len(entries), house_num,
            )
        else:
            _LOGGER.warning(
                "Unexpected DTEK data type for %s: %s — raw: %s",
                house_num, type(house_data).__name__, house_data,
            )
            return no_outage

        # Parse each outage entry
        outages: list[dict[str, Any]] = []
        all_groups: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                _LOGGER.warning("Skipping non-dict outage entry: %s", entry)
                continue
            _LOGGER.debug("House %s entry: sub_type_reason=%s, sub_type=%s",
                          house_num, entry.get("sub_type_reason"),
                          entry.get("sub_type", ""))
            parsed = _parse_single_outage(entry)
            if parsed["outage_type"] != "ok":
                outages.append(parsed)
            # Collect schedule groups from all entries (even non-outage ones)
            all_groups.extend(parsed.get("schedule_groups", []))

        if not outages:
            no_outage["schedule_groups"] = list(dict.fromkeys(all_groups))
            return no_outage

        # Select primary outage: most severe, then most recent start
        primary = _select_primary_outage(outages)
        # Merge schedule groups from all outages
        merged_groups = list(dict.fromkeys(all_groups))

        return {
            "power_on": False,
            "outage_type": primary["outage_type"],
            "outage_description": primary["outage_description"],
            "outage_start": primary["outage_start"],
            "outage_end": primary["outage_end"],
            "schedule_groups": merged_groups,
            "dtek_update_time": update_timestamp,
            "raw_type": primary["raw_type"],
            "outage_count": len(outages),
            "all_outages": outages if len(outages) > 1 else [],
        }


KYIV_TZ = ZoneInfo("Europe/Kyiv")

_OUTAGE_SEVERITY = {"emergency": 3, "stabilization": 2, "planned": 1, "ok": 0}


def parse_dtek_datetime(value: str) -> datetime | None:
    """Parse DTEK datetime string into a timezone-aware datetime.

    Handles two formats used by DTEK:
      - 'HH:MM DD.MM.YYYY' (outage start/end times)
      - 'DD.MM.YYYY HH:MM' (schedule update timestamps)
    """
    if not value or not value.strip():
        return None
    stripped = value.strip()
    for fmt in ("%H:%M %d.%m.%Y", "%d.%m.%Y %H:%M"):
        try:
            naive = datetime.strptime(stripped, fmt)
            return naive.replace(tzinfo=KYIV_TZ)
        except ValueError:
            continue
    _LOGGER.warning("Could not parse DTEK datetime: %s", value)
    return None


def _classify_outage_type(sub_type: str) -> str:
    """Classify outage type from DTEK sub_type string."""
    if not sub_type:
        return "ok"
    sub_lower = sub_type.lower()
    if "екстрен" in sub_lower or "аварійн" in sub_lower:
        return "emergency"
    if "стабілізац" in sub_lower:
        return "stabilization"
    return "planned"


def _parse_single_outage(entry: dict[str, Any]) -> dict[str, Any]:
    """Parse a single outage entry from DTEK API."""
    sub_type = entry.get("sub_type", "")
    raw_type = entry.get("type", "")
    start_str = entry.get("start_date", "")
    end_str = entry.get("end_date", "")
    groups = entry.get("sub_type_reason", [])

    return {
        "outage_type": _classify_outage_type(sub_type),
        "outage_description": sub_type,
        "outage_start": parse_dtek_datetime(start_str),
        "outage_end": parse_dtek_datetime(end_str),
        "schedule_groups": groups if isinstance(groups, list) else [],
        "raw_type": raw_type,
    }


def _select_primary_outage(outages: list[dict[str, Any]]) -> dict[str, Any]:
    """Select the most critical outage from a list.

    Priority: emergency > stabilization > planned.
    Ties broken by most recent start time.
    """
    return max(
        outages,
        key=lambda o: (
            _OUTAGE_SEVERITY.get(o["outage_type"], 0),
            o.get("outage_start") or datetime.min.replace(tzinfo=KYIV_TZ),
        ),
    )


# --- Schedule parsing from HTML ---

# Regex to extract JS object assignments: DisconSchedule.fact = {...}
# The JSON is on a single line, may or may not have trailing semicolon,
# and may be followed by </script> or newline.
_SCHEDULE_FACT_RE = re.compile(
    r"DisconSchedule\.fact\s*=\s*(\{.+\})"
)
_SCHEDULE_PRESET_RE = re.compile(
    r"DisconSchedule\.preset\s*=\s*(\{.+\})"
)


def _parse_schedule_from_html(html: str) -> dict[str, Any] | None:
    """Extract DisconSchedule.fact and DisconSchedule.preset from page HTML.

    Returns dict with "fact" and "preset" keys, or None if parsing fails.
    """
    result: dict[str, Any] = {}

    for name, pattern in [("fact", _SCHEDULE_FACT_RE), ("preset", _SCHEDULE_PRESET_RE)]:
        match = pattern.search(html)
        if not match:
            _LOGGER.debug("DisconSchedule.%s not found in HTML", name)
            continue
        try:
            result[name] = json.loads(match.group(1))
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.warning("Failed to parse DisconSchedule.%s: %s", name, err)

    return result or None
