"""HTTP client for the DTEK website API.

Transport/CSRF improvements adapted from Zerstoren/ha-dtek-krem-monitor
(e1fb7cf), licensed under MIT; see THIRD_PARTY_NOTICES.md for those portions.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import re
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from curl_cffi.requests import AsyncSession

from .public_requests import PublicRequestError, PublicRequestGate, retry_after_seconds
from .provider_notice import NoticeCache

from .const import (
    DTEK_BASE_URL,
    DTEK_SHUTDOWNS_URL,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)

CSRF_META_TAG_RE = re.compile(
    r"<meta\b[^>]*(?:csrf-token|csrf_token)[^>]*>",
    re.IGNORECASE,
)
CSRF_CONTENT_RE = re.compile(
    r"""content\s*=\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)
CSRF_INPUT_RE = re.compile(
    r"""<input\b(?=[^>]*\bname\s*=\s*['"]_token['"])(?=[^>]*\bvalue\s*=\s*['"]([^'"]+)['"])[^>]*>""",
    re.IGNORECASE,
)
CSRF_JS_RE = re.compile(
    r"""(?:csrfToken|csrf_token|_token)\s*[:=]\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)

# Use a supported desktop Chrome profile from the installed curl_cffi.
# Its TLS/HTTP2 fingerprint, User-Agent and sec-ch-ua client hints come as one
# consistent set. Never override User-Agent by hand: a Chrome/133 UA on top of
# a chrome120 TLS fingerprint (or a Linux UA with sec-ch-ua-platform "macOS")
# is a textbook bot signal for Incapsula.
IMPERSONATE_FALLBACK = "chrome120"


# Conservative profiles, filtered against the installed curl_cffi targets.
_PREFERRED_TARGETS = ("chrome136", "chrome131", "chrome124", "chrome120")


def _supported_targets() -> set[str]:
    """Return plain desktop ``chromeNNN`` targets known to curl_cffi."""
    try:
        from curl_cffi import BrowserType  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover - older curl_cffi layout
        try:
            from curl_cffi.requests import BrowserType  # type: ignore[no-redef]
        except ImportError:
            return {IMPERSONATE_FALLBACK}
    return {
        str(browser.value)
        for browser in BrowserType
        if re.fullmatch(r"chrome\d+", str(browser.value))
    }


def _candidate_targets(supported: set[str] | None = None) -> list[str]:
    """Impersonation targets to try, in order, for the installed curl_cffi."""
    supported = _supported_targets() if supported is None else supported
    targets = [t for t in _PREFERRED_TARGETS if t in supported]
    return targets or [IMPERSONATE_FALLBACK]


IMPERSONATE_TARGET = _candidate_targets()[0]


ACCEPT_LANGUAGE = "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7"

# Top-level navigation (typing the URL / reload): curl_cffi defaults already
# look like a Chrome document request, we only localize the language.
PAGE_HEADERS = {
    "Accept-Language": ACCEPT_LANGUAGE,
}

# jQuery $.ajax POST issued by the shutdowns page itself. curl_cffi defaults
# describe a navigation (Sec-Fetch-Mode: navigate, Upgrade-Insecure-Requests,
# Accept: text/html...), which never happens for XHR in a real browser.
# A value of None removes the default header.
XHR_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": ACCEPT_LANGUAGE,
    "X-Requested-With": "XMLHttpRequest",
    "Origin": DTEK_BASE_URL,
    "Referer": DTEK_SHUTDOWNS_URL,
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-User": None,
    "Upgrade-Insecure-Requests": None,
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
}


class DTEKApiError(PublicRequestError):
    """Base exception for DTEK API errors."""


class DTEKAuthError(DTEKApiError):
    """CSRF or session error — need to re-authenticate."""


class DTEKProtectionError(DTEKApiError):
    """DTEK answered with the Incapsula/DDoS-Guard interstitial."""


# Every page load is a fresh chance for Incapsula to challenge us, so keep the
# CSRF session as long as the site accepts it (a 400 forces a refresh anyway).
SESSION_MAX_AGE = timedelta(hours=6)
_PAGE_RETRY_ATTEMPTS = 3
# Pause before attempt N (index 0 unused). A real browser also needs a moment
# to run the Incapsula script before it reloads; hammering makes it worse.
_PAGE_RETRY_DELAYS = (0.0, 2.0, 8.0)
_RETRY_JITTER = 0.5


def _create_session(target: str = "") -> AsyncSession:
    """Create a curl_cffi session impersonating desktop Chrome."""
    target = target or IMPERSONATE_TARGET
    _LOGGER.debug("Creating DTEK session impersonating %s", target)
    return AsyncSession(impersonate=target)


def _is_transport_error(err: BaseException) -> bool:
    """Return True for TLS/HTTP2 level failures where a new connection may help.

    curl codes: 16 HTTP/2 framing, 35 TLS handshake, 52 empty reply,
    55/56 send/recv failure, 92 HTTP/2 stream error.
    """
    code = getattr(err, "code", None)
    try:
        code = int(code) if code is not None else None
    except (TypeError, ValueError):
        code = None
    if code in (16, 35, 52, 55, 56, 92):
        return True
    text = str(err).lower()
    return "curl: (16)" in text or "http/2" in text or "http2" in text


async def _sleep_with_jitter(base: float) -> None:
    """Sleep for base seconds +/- jitter (no-op for base <= 0)."""
    if base <= 0:
        return
    await asyncio.sleep(base * random.uniform(1 - _RETRY_JITTER, 1 + _RETRY_JITTER))


class DTEKClient:
    """Async HTTP client for the DTEK shutdowns API.

    Uses curl_cffi with Chrome TLS impersonation because aiohttp is served
    the Incapsula interstitial instead of the real shutdowns page.
    """

    def __init__(
        self,
        base_url: str = DTEK_BASE_URL,
        *,
        request_gate: PublicRequestGate | None = None,
    ) -> None:
        self.request_gate = request_gate or PublicRequestGate()
        self.base_url = base_url.rstrip("/")
        self.shutdowns_url = f"{self.base_url}/ua/shutdowns"
        if not hasattr(self.request_gate, "notice_cache"):
            self.request_gate.notice_cache = NoticeCache(self.shutdowns_url)
        self.notice_cache = self.request_gate.notice_cache
        self.ajax_url = f"{self.base_url}/ua/ajax"
        self.xhr_headers = {
            **XHR_HEADERS,
            "Origin": self.base_url,
            "Referer": self.shutdowns_url,
        }
        self._http: AsyncSession | None = None
        self._csrf_token: str | None = None
        self._schedule_data: dict[str, Any] | None = None
        self._session_created: datetime | None = None
        self._schedule_dirty: bool = False
        self._targets: list[str] = _candidate_targets()
        self._target_index: int = 0
        # Diagnostics (since integration start).
        self.transport_errors: int = 0
        self.waf_challenges: int = 0
        self.waf_hard_blocks: int = 0
        self.last_waf_at: datetime | None = None

    async def close(self) -> None:
        """Close the underlying HTTP session."""
        await self._reset_http()
        self._csrf_token = None
        self._session_created = None

    async def _ensure_http(self) -> AsyncSession:
        """Create the Chrome-impersonating session on first use."""
        if self._http is None:
            self._http = _create_session(self.impersonate_target)
        return self._http

    @property
    def impersonate_target(self) -> str:
        """Browser profile currently in use."""
        return self._targets[self._target_index]

    async def _recycle_connection(self) -> AsyncSession:
        """Open a fresh connection with the same cookies and profile.

        After a 403 stub Incapsula closes the HTTP/2 connection; reusing it
        fails with curl error 16, while a new connection carrying the cookies
        it just set can complete the page handshake.
        """
        jar = list(self._http.cookies.jar) if self._http is not None else []
        await self._reset_http()
        session = await self._ensure_http()
        for cookie in jar:
            session.cookies.jar.set_cookie(cookie)
        return session

    async def _switch_target(self) -> bool:
        """Move to the next browser profile, keeping cookies. False if none."""
        if self._target_index + 1 >= len(self._targets):
            return False
        self._target_index += 1
        await self._recycle_connection()
        _LOGGER.warning(
            "DTEK transport error, switching browser profile to %s",
            self.impersonate_target,
        )
        return True

    def _note_waf(self) -> None:
        """Count a bot-protection page for diagnostics."""
        self.waf_challenges += 1
        self.last_waf_at = datetime.now(KYIV_TZ)

    async def _reset_http(self) -> None:
        """Drop the curl session (and its cookies) after a hard block."""
        if self._http is not None:
            await self._http.close()
            self._http = None

    async def _ensure_session(self) -> None:
        """Fetch the shutdowns page to obtain CSRF token and session cookie."""
        if self._csrf_token is not None:
            if (
                self._session_created
                and datetime.now(KYIV_TZ) - self._session_created < SESSION_MAX_AGE
            ):
                return
            _LOGGER.debug("Session expired (age > %s), refreshing", SESSION_MAX_AGE)

        await self._refresh_session()

    async def _refresh_session(self) -> None:
        """Force-refresh CSRF token and session cookies."""
        _LOGGER.debug("Refreshing DTEK session and CSRF token")
        self._csrf_token = None
        self._session_created = None

        try:
            html = await self._load_shutdowns_page()
            token = _extract_csrf_token(html)
            if token is None:
                if _is_protection_page(html):
                    raise DTEKProtectionError(_csrf_missing_message(html))
                raise DTEKAuthError(_csrf_missing_message(html))

            self._csrf_token = token
            self._session_created = datetime.now(KYIV_TZ)
            self.notice_cache.capture(html)

            schedule = _parse_schedule_from_html(html)
            if schedule:
                self._schedule_data = schedule
                self._schedule_dirty = True

            _LOGGER.debug("DTEK session refreshed")

        except DTEKApiError:
            self._csrf_token = None
            self._session_created = None
            raise
        except (TimeoutError, OSError, UnicodeError) as err:
            self._csrf_token = None
            self._session_created = None
            raise DTEKApiError(f"Network error loading DTEK page: {err}") from err

    async def _load_shutdowns_page(self) -> str:
        """Download the shutdowns page HTML.

        Incapsula first returns an ~800-byte iframe stub and sets cookies.
        The next GET on the same session is usually the real page. Between
        attempts we pause (with jitter) like a browser running the challenge
        script would, instead of firing three requests in the same second.
        """
        session = await self._ensure_http()
        html = ""
        consecutive_transport_errors = 0
        for attempt in range(1, _PAGE_RETRY_ATTEMPTS + 1):
            delay_index = min(attempt - 1, len(_PAGE_RETRY_DELAYS) - 1)
            await _sleep_with_jitter(_PAGE_RETRY_DELAYS[delay_index])
            headers = dict(PAGE_HEADERS)
            if attempt > 1:
                # The challenge page reloads itself: same-origin navigation.
                headers["Sec-Fetch-Site"] = "same-origin"
                headers["Referer"] = self.shutdowns_url
            try:
                resp = await session.get(
                    self.shutdowns_url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    allow_redirects=True,
                )
            except (TimeoutError, OSError) as err:
                self.transport_errors += 1
                consecutive_transport_errors += 1
                _LOGGER.debug(
                    "DTEK page request failed with %s (attempt %s/%s): %s",
                    self.impersonate_target,
                    attempt,
                    _PAGE_RETRY_ATTEMPTS,
                    err,
                )
                if attempt >= _PAGE_RETRY_ATTEMPTS:
                    raise
                if consecutive_transport_errors >= 2 and _is_transport_error(err):
                    # A fresh connection did not help either: try another
                    # browser profile (keeps cookies).
                    await self._switch_target()
                    session = await self._ensure_http()
                else:
                    session = await self._recycle_connection()
                continue
            consecutive_transport_errors = 0
            html = resp.text
            if resp.status_code == 429 or resp.status_code >= 500:
                raise DTEKApiError(
                    f"Failed to load shutdowns page: HTTP {resp.status_code}",
                    retry_after=retry_after_seconds(
                        getattr(resp, "headers", {}).get("Retry-After")
                    ),
                )
            # Incapsula serves its stub with 200 *or* 403; either way the
            # next GET with the freshly set cookies usually passes.
            if _is_protection_page(html):
                if resp.status_code not in (200, 403):
                    raise DTEKApiError(
                        f"Failed to load shutdowns page: HTTP {resp.status_code}"
                    )
            elif resp.status_code != 200:
                raise DTEKApiError(
                    f"Failed to load shutdowns page: HTTP {resp.status_code}"
                )
            else:
                return html
            self._note_waf()
            _LOGGER.debug(
                "DTEK returned a WAF challenge (HTTP %s, attempt %s/%s, %s)",
                resp.status_code,
                attempt,
                _PAGE_RETRY_ATTEMPTS,
                _html_debug_summary(html),
            )
            if attempt < _PAGE_RETRY_ATTEMPTS:
                session = await self._recycle_connection()
        if _is_hard_block(html):
            # "Request unsuccessful. Incapsula incident ID" — the current
            # cookies are burned; start clean next time instead of reusing them.
            _LOGGER.debug("Incapsula hard block, dropping session cookies")
            self.waf_hard_blocks += 1
            await self._reset_http()
        return html

    async def _post(
        self,
        data: dict[str, str],
        retry: bool = True,
        require_result: bool = True,
    ) -> dict[str, Any]:
        """Run one bounded AJAX operation through the shared operator gate."""
        return await self.request_gate.run(
            lambda: self._post_unlocked(data, retry, require_result)
        )

    async def get_provider_notice(self):
        return await self.notice_cache.get(
            lambda: self.request_gate.run(self._refresh_session)
        )

    async def _post_unlocked(
        self, data: dict[str, str], retry: bool = True, require_result: bool = True
    ) -> dict[str, Any]:
        """Send POST request to the DTEK AJAX endpoint.

        Automatically refreshes CSRF on auth errors and retries once.
        """
        await self._ensure_session()
        session = await self._ensure_http()

        headers = {
            **self.xhr_headers,
            "X-Csrf-Token": self._csrf_token or "",
        }

        try:
            resp = await session.post(
                self.ajax_url,
                data=data,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                raise DTEKApiError(
                    f"DTEK API returned HTTP {resp.status_code}",
                    retry_after=retry_after_seconds(
                        getattr(resp, "headers", {}).get("Retry-After")
                    ),
                )
            if resp.status_code == 400:
                if retry:
                    _LOGGER.debug("Got 400, refreshing CSRF and retrying")
                    await self._refresh_session()
                    return await self._post_unlocked(
                        data,
                        retry=False,
                        require_result=require_result,
                    )
                raise DTEKAuthError("CSRF validation failed after refresh")

            if resp.status_code not in (200, 403):
                raise DTEKApiError(f"DTEK API returned HTTP {resp.status_code}")

            if _is_protection_page(resp.text):
                self._note_waf()
                # Incapsula can also interpose on XHR. Re-run the page
                # handshake (which waits and retries) and try once more.
                if retry:
                    _LOGGER.debug("AJAX answered with WAF page, re-handshaking")
                    await self._refresh_session()
                    return await self._post_unlocked(
                        data,
                        retry=False,
                        require_result=require_result,
                    )
                raise DTEKProtectionError(
                    "DTEK bot protection blocked the AJAX request "
                    f"({_html_debug_summary(resp.text)})"
                )

            if resp.status_code != 200:
                raise DTEKApiError(f"DTEK API returned HTTP {resp.status_code}")

            try:
                result = resp.json()
            except (json.JSONDecodeError, ValueError) as err:
                raise DTEKApiError(
                    f"Invalid JSON from DTEK API: {err} "
                    f"({_html_debug_summary(resp.text)})"
                ) from err

            if not isinstance(result, dict) or "result" not in result:
                raise DTEKApiError("Malformed DTEK API response")
            if require_result and not result["result"]:
                raise DTEKApiError("DTEK API returned result=false")

            return result

        except DTEKApiError:
            raise
        except (TimeoutError, OSError) as err:
            self.transport_errors += 1
            if retry and _is_transport_error(err):
                _LOGGER.debug(
                    "AJAX transport error, retrying on a new connection: %s", err
                )
                await self._recycle_connection()
                return await self._post_unlocked(
                    data,
                    retry=False,
                    require_result=require_result,
                )
            raise DTEKApiError(f"Network error calling DTEK API: {err}") from err

    async def get_streets(self) -> dict[str, list[str]]:
        """Fetch all cities and their streets.

        Returns dict mapping city names to lists of street names.
        """
        result = await self._post({"method": "getStreets"})
        streets = result.get("streets", {})
        if not isinstance(streets, dict):
            raise DTEKApiError("Unexpected streets format in API response")
        return {
            city.strip(): sorted(
                {
                    street.strip()
                    for street in values
                    if isinstance(street, str) and street.strip()
                }
            )
            for city, values in streets.items()
            if isinstance(city, str) and city.strip() and isinstance(values, list)
        }

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
            street: Street name (e.g. "вулиця Прикладна")
            house_num: House number (e.g. "12А"), empty to get all houses
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
        if result.get("result") is False:
            _LOGGER.debug("No schedule updates since %s", timestamp)
            return None

        if result.get("result") is not True or not any(
            key in result for key in ("fact", "preset")
        ):
            raise DTEKApiError("Malformed schedule update response")

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

    def consume_schedule_update(self) -> dict[str, Any] | None:
        """Return schedule data if it was refreshed since last consume, else None."""
        if self._schedule_dirty and self._schedule_data:
            self._schedule_dirty = False
            return self._schedule_data
        return None

    @staticmethod
    def parse_house_data(
        api_response: dict[str, Any], house_num: str
    ) -> dict[str, Any]:
        """Extract and normalize data for a specific house from API response.

        Handles both single outage (dict) and multiple outages (list).
        Returns a dict with normalized outage information.
        """
        if not isinstance(api_response, dict) or not isinstance(
            api_response.get("data"), dict
        ):
            raise DTEKApiError("Malformed house response")
        houses = api_response["data"]
        update_timestamp = api_response.get("updateTimestamp", "")

        no_outage: dict[str, Any] = {
            "power_on": True,
            "outage_type": "ok",
            "outage_description": "",
            "outage_start": None,
            "outage_end": None,
            "schedule_groups": [],
            "primary_schedule_group": None,
            "dtek_update_time": update_timestamp,
            "raw_type": "",
            "outage_count": 0,
            "all_outages": [],
        }

        if not isinstance(houses, dict):
            _LOGGER.warning(
                "Unexpected DTEK houses payload type: %s",
                type(houses).__name__,
            )
            return no_outage

        house_data = houses.get(house_num)
        if house_data is None:
            # Try case-insensitive match
            for key, value in houses.items():
                if isinstance(key, str) and key.lower() == house_num.lower():
                    house_data = value
                    break

        if house_data is None:
            _LOGGER.debug(
                "No data for house %s in API response (keys: %s)",
                house_num,
                list(houses.keys()),
            )
            return no_outage

        # Normalize to list: API may return a dict (single) or list (multiple)
        if isinstance(house_data, dict):
            entries = [house_data]
        elif isinstance(house_data, list):
            entries = house_data
            _LOGGER.debug(
                "DTEK returned %d outage entries for %s (multiple outages)",
                len(entries),
                house_num,
            )
        else:
            _LOGGER.warning(
                "Unexpected DTEK data type for %s: %s — raw: %s",
                house_num,
                type(house_data).__name__,
                house_data,
            )
            raise DTEKApiError("Malformed address payload")

        if any(not isinstance(entry, dict) or not entry for entry in entries):
            raise DTEKApiError("Malformed outage entry")

        # Parse each outage entry
        outages: list[dict[str, Any]] = []
        all_groups: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                _LOGGER.warning("Skipping non-dict outage entry: %s", entry)
                continue
            _LOGGER.debug(
                "House %s entry: sub_type_reason=%s, sub_type=%s",
                house_num,
                entry.get("sub_type_reason"),
                entry.get("sub_type", ""),
            )
            parsed = _parse_single_outage(entry)
            if parsed["outage_type"] != "ok":
                outages.append(parsed)
            # Collect schedule groups from all entries (even non-outage ones)
            all_groups.extend(parsed.get("schedule_groups", []))

        if not outages:
            no_outage["schedule_groups"] = sorted(set(all_groups))
            no_outage["primary_schedule_group"] = (
                no_outage["schedule_groups"][0]
                if no_outage["schedule_groups"]
                else None
            )
            return no_outage

        # Select primary outage: most severe, then most recent start
        primary = _select_primary_outage(outages)
        # Merge schedule groups from all outages
        merged_groups = sorted(set(all_groups))

        return {
            "power_on": False,
            "outage_type": primary["outage_type"],
            "outage_description": primary["outage_description"],
            "outage_start": primary["outage_start"],
            "outage_end": primary["outage_end"],
            "schedule_groups": merged_groups,
            "primary_schedule_group": merged_groups[0] if merged_groups else None,
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
    def text_field(name: str) -> str:
        value = entry.get(name)
        if value is None:
            return ""
        if not isinstance(value, str):
            raise DTEKApiError(f"Malformed outage field: {name}")
        return value.strip()

    sub_type = text_field("sub_type")
    raw_type = entry.get("type", "")
    start_str = text_field("start_date")
    end_str = text_field("end_date")
    groups = _normalize_groups(entry.get("sub_type_reason", []))
    start = parse_dtek_datetime(start_str)
    end = parse_dtek_datetime(end_str)

    # DTEK's public page supplies its own caption for type 1 repair records.
    # An entirely empty record still means no outage, even with that type code.
    if str(raw_type).strip() == "1" and not sub_type and (start_str or end_str):
        if (
            (start_str and start is None)
            or (end_str and end is None)
            or (start is not None and end is not None and end <= start)
        ):
            raise DTEKApiError("Malformed planned repair dates")
        sub_type = "Планові ремонтні роботи"

    return {
        "outage_type": _classify_outage_type(sub_type),
        "outage_description": sub_type,
        "outage_start": start,
        "outage_end": end,
        "schedule_groups": groups,
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


def _parse_schedule_from_html(html: str) -> dict[str, Any] | None:
    """Extract DisconSchedule.fact and DisconSchedule.preset from page HTML.

    Returns dict with "fact" and "preset" keys, or None if parsing fails.
    """
    result: dict[str, Any] = {}

    for name in ("fact", "preset"):
        payload = _extract_js_object(html, f"DisconSchedule.{name}")
        if payload is None:
            _LOGGER.debug("DisconSchedule.%s not found in HTML", name)
            continue
        try:
            result[name] = json.loads(payload)
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.warning("Failed to parse DisconSchedule.%s: %s", name, err)

    return result or None


def _normalize_groups(value: Any) -> list[str]:
    """Normalize schedule groups into a clean string list."""
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if not isinstance(value, list):
        return []

    groups: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if normalized:
            groups.append(normalized)
    return groups


def _extract_js_object(html: str, assignment_name: str) -> str | None:
    """Extract a JSON object assigned to a JS variable using brace matching."""
    assignment_index = html.find(assignment_name)
    if assignment_index == -1:
        return None

    start = html.find("{", assignment_index)
    if start == -1:
        return None

    depth = 0
    in_string = False
    string_quote = ""
    escaped = False

    for index in range(start, len(html)):
        char = html[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == string_quote:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            string_quote = char
            continue

        if char == "{":
            depth += 1
            continue

        if char == "}":
            depth -= 1
            if depth == 0:
                return html[start : index + 1]

    return None


def _is_protection_page(html: str) -> bool:
    """Return True when HTML looks like an Incapsula/DDoS-Guard interstitial.

    The real shutdowns page also embeds an ``_Incapsula_Resource`` script, so
    WAF markers alone are not enough: a page carrying the CSRF token or the
    schedule data is the real one, whatever else it contains.
    """
    if _looks_like_real_page(html):
        return False
    lowered = html.lower()
    compact = lowered.replace(" ", "")
    if "incapsula" in lowered or "_incapsula_resource" in lowered:
        return True
    if "ddos-guard" in lowered or "check.ddos-guard.net" in lowered:
        return True
    if "noindex" in lowered and "nofollow" in lowered and "height:100%" in compact:
        return True
    return False


def _looks_like_real_page(html: str) -> bool:
    """Return True for the actual shutdowns page (token or schedule present)."""
    if "DisconSchedule" in html:
        return True
    return _extract_csrf_token(html) is not None


def _is_hard_block(html: str) -> bool:
    """Return True for the Incapsula 'Request unsuccessful' incident page."""
    lowered = html.lower()
    return "incident id" in lowered or "wudnsai" in lowered


def _csrf_missing_message(html: str) -> str:
    """Build an error that distinguishes a WAF page from a missing token."""
    if _is_protection_page(html):
        return (
            "DTEK returned a bot-protection page instead of the shutdowns form "
            f"({_html_debug_summary(html)})"
        )
    return f"CSRF token not found in page HTML ({_html_debug_summary(html)})"


def _extract_csrf_token(html: str) -> str | None:
    """Extract a CSRF token from DTEK HTML variants."""
    if not html:
        return None

    meta = CSRF_META_TAG_RE.search(html)
    if meta:
        content = CSRF_CONTENT_RE.search(meta.group(0))
        if content and content.group(1).strip():
            return content.group(1).strip()

    for pattern in (CSRF_INPUT_RE, CSRF_JS_RE):
        match = pattern.search(html)
        if match and match.group(1).strip():
            return match.group(1).strip()

    return None


def _html_debug_summary(html: str) -> str:
    """Build a short HTML summary for logs when CSRF parsing fails."""
    return f"len={len(html)} protection={_is_protection_page(html)}"
