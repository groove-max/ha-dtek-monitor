"""Shared household cabinet API with explicit, non-retried reading submissions."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime
import hashlib
import json
import math
import re
import secrets
import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from zoneinfo import ZoneInfo

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.exceptions import RequestException

from .account import (
    AccountAuthError,
    AccountAPIChanged,
    AccountError,
    AccountRateLimitError,
    AccountSnapshot,
    PersonalAccount,
    normalize_phone,
    parse_consumption,
    parse_readings,
)
from .account_history import (
    MAX_HISTORY_PAGES,
    MAX_HISTORY_ROWS,
    parse_history_page,
    parse_months,
    validate_year,
)
from .account_profile import parse_profile
from .account_links import AccountLinksClientMixin
from .account_providers import AccountProviderSpec, get_account_provider_spec
from .account_group_client import AccountGroupAuthorizationMixin

BILLING = "/api/billing-service/api"


def create_account_provider(provider_id: str) -> DTEKAccountClient:
    """Load transport at module import time, outside HA's event loop."""
    return DTEKAccountClient(spec=get_account_provider_spec(provider_id))


class DTEKAccountClient(AccountLinksClientMixin, AccountGroupAuthorizationMixin):
    """Own cookie jar, PKCE login and serialized short-lived API token renewal."""

    def __init__(
        self, session: Any = None, *, spec: AccountProviderSpec | None = None
    ) -> None:
        self._spec = spec if spec is not None else get_account_provider_spec()
        self._session = session or AsyncSession(
            impersonate="chrome136", timeout=25, allow_redirects=False
        )
        self._lock = asyncio.Lock()
        self._meter_lock = asyncio.Lock()
        self._meter_auth = "raw"
        self._meter_rejections: dict[tuple, float] = {}
        self._token = ""
        self._token_expires = 0.0
        self._accounts: set[str] = set()
        self._linked_profiles: dict[str, dict] = {}
        self.subject: str | None = None
        self.api_issue_handler = None
        self.api_recovered_handler = None

    @property
    def spec(self) -> AccountProviderSpec:
        """A session cannot switch operators while retaining cookies or tokens."""
        return self._spec

    async def close(self) -> None:
        await self._session.close()
        self._token = ""
        self._accounts.clear()
        self._linked_profiles.clear()
        self._meter_rejections.clear()
        self.api_issue_handler = None
        self.api_recovered_handler = None

    def _api_changed(self, interface, reason):
        error = AccountAPIChanged(interface, reason)
        if self.api_issue_handler:
            self.api_issue_handler(error)
        return error

    def _api_recovered(self, interface):
        if self.api_recovered_handler:
            self.api_recovered_handler(interface)

    @staticmethod
    def _billing_interface(path):
        base = BILLING + "/meters/household/"
        if path == base + "customer-book":
            return "meter_consumption"
        match = re.fullmatch(
            re.escape(base) + r"[0-9]+/(data|meters-with-readings|history|readings)",
            path,
        )
        return (
            {
                "data": "meter_details",
                "meters-with-readings": "meter_readings",
                "history": "meter_history",
                "readings": "meter_submission",
            }.get(match[1])
            if match
            else None
        )

    async def _request(
        self, method: str, path: str, *, auth=False, meter_auth=None, **kwargs
    ):
        origin = self.spec.auth_origin if auth else self.spec.cabinet_origin
        headers = {
            "Accept": "application/json",
            "Origin": origin,
            "Referer": origin + "/",
        }
        if method != "GET":
            csrf = self._session.cookies.get("XSRF-TOKEN")
            if csrf:
                headers["X-CSRF"] = unquote(csrf)
        if self._token and not auth:
            style = (meter_auth or self._meter_auth) if path.startswith(BILLING + "/") else "raw"
            headers["X-Id-Token"] = (
                "Bearer " + self._token if style == "bearer" else self._token
            )
        try:
            response = await self._session.request(
                method, origin + path, headers=headers, **kwargs
            )
        except (RequestException, TimeoutError, OSError):
            # curl errors can contain full URLs including account identifiers.
            raise AccountError(
                "Cannot connect to the personal account service"
            ) from None
        # A lookup's 404 means "account not found", not a retired API.
        fixed_routes = {
            "/api/billing/joint/objects/get_advanced": "cabinet",
            "/api/userData/api/login": "login",
            "/api/oauth/api/auth/login": "login",
            "/api/oauth/authorize": "login",
            "/api/oauth/token": "login",
            "/api/oauth/userinfo": "login",
            "/api/billing/joint/info/get_client_info": "link_lookup",
        }
        family = fixed_routes.get(path)
        if response.status_code == 410:
            family = (
                family
                or {
                    "/api/billing/joint/info/get_accounts": "link_lookup",
                    "/api/billing/joint/objects/add": "link_add",
                    "/api/billing/joint/objects/remove": "link_remove",
                }.get(path)
                or self._billing_interface(path)
            )
        if family and response.status_code in (404, 410):
            raise self._api_changed(family, f"HTTP {response.status_code}")
        return response

    @staticmethod
    def _check(response, *, credentials=False) -> None:
        if response.status_code == 401 or (
            credentials and response.status_code in (400, 422)
        ):
            raise AccountAuthError("Personal account authentication required")
        if response.status_code == 429:
            raise AccountRateLimitError("Personal account request limit reached")
        if response.status_code < 200 or response.status_code >= 300:
            # A protection-system 403 is not evidence of an incorrect password.
            raise AccountError("Personal account service rejected the request")

    @classmethod
    def _decode(cls, response) -> Any:
        cls._check(response)
        try:
            return response.json()
        except (ValueError, TypeError):
            raise AccountError(
                "Personal account returned an invalid response"
            ) from None

    async def authenticate(self, phone: str, password: str) -> str:
        async with self._lock:
            self._token = ""
            self._meter_auth = "raw"
            self._meter_rejections.clear()
            self._accounts.clear()
            self._linked_profiles.clear()
            self.subject = None
            self._check(await self._request("GET", "/login", auth=True))
            self._check(
                await self._request(
                    "POST",
                    "/api/oauth/api/auth/login",
                    auth=True,
                    json={"login": normalize_phone(phone), "password": password},
                ),
                credentials=True,
            )
            verifier = secrets.token_urlsafe(64)
            state = secrets.token_urlsafe(24)
            challenge = (
                base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                .decode()
                .rstrip("=")
            )
            response = await self._request(
                "GET",
                "/api/oauth/authorize",
                auth=True,
                params={
                    "redirect_uri": self.spec.callback,
                    "client_id": self.spec.oauth_client_id,
                    "response_type": "code",
                    "state": state,
                    "code_challenge_method": "S256",
                    "code_challenge": challenge,
                },
            )
            if response.status_code not in (302, 303):
                self._check(response)
                raise AccountAuthError("Personal account login was not completed")
            target = urlsplit(response.headers.get("location", ""))
            query = parse_qs(target.query)
            if (
                target._replace(query="", fragment="").geturl() != self.spec.callback
                or query.get("state") != [state]
                or len(query.get("code", [])) != 1
            ):
                raise AccountAuthError("Personal account login redirect was invalid")
            self._check(
                await self._request(
                    "POST",
                    "/api/oauth/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": self.spec.oauth_client_id,
                        "redirect_uri": self.spec.callback,
                        "code": query["code"][0],
                        "code_verifier": verifier,
                    },
                ),
                credentials=True,
            )
            profile = self._decode(await self._request("GET", "/api/oauth/userinfo"))
            if not isinstance(profile, dict) or not isinstance(profile.get("sub"), str):
                raise AccountError("Personal account identity is missing")
            self.subject = profile["sub"]
            await self._issue_token()
            return self.subject

    async def _issue_token(self) -> None:
        response = await self._request("POST", "/api/userData/api/login")
        if response.status_code == 401:
            self._check(
                await self._request(
                    "POST",
                    "/api/oauth/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": self.spec.oauth_client_id,
                    },
                ),
                credentials=True,
            )
            response = await self._request("POST", "/api/userData/api/login")
        data = self._decode(response)
        if not isinstance(data, dict) or not isinstance(data.get("xIdToken"), str):
            raise AccountError("Personal account token is missing")
        token = data["xIdToken"]
        try:
            payload = token.split(".")[1]
            claims = json.loads(
                base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
            )
            ttl = float(claims["exp"]) - time.time() - 60
            if not math.isfinite(ttl) or ttl <= 0:
                raise ValueError
        except (IndexError, KeyError, ValueError, TypeError):
            raise AccountError("Personal account token is invalid") from None
        self._token = token
        self._token_expires = time.monotonic() + min(ttl, 900)
        self._api_recovered("login")

    async def _ensure_token(self, rejected: str | None = None) -> None:
        async with self._lock:
            if not self.subject:
                raise AccountAuthError("Personal account authentication required")
            if (
                not self._token
                or time.monotonic() >= self._token_expires
                or (rejected is not None and self._token == rejected)
            ):
                await self._issue_token()

    async def _read_response(self, path: str, **kwargs):
        await self._ensure_token()
        token = self._token
        response = await self._request("GET", path, **kwargs)
        if response.status_code == 401:
            await self._ensure_token(rejected=token)
            response = await self._request("GET", path, **kwargs)
        return response

    async def _meter_response(self, path: str, interface: str, **kwargs):
        """Negotiate only on reads; never replay or probe a submission POST."""
        key = (path, str(kwargs.get("params", {}).get("accountNumber", "")))
        # Serialize negotiation so concurrent readers reuse the discovered style.
        async with self._meter_lock:
            if self._meter_rejections.get(key, 0) > time.monotonic():
                raise self._api_changed(interface, "authorization_rejected")
            response = await self._read_response(path, **kwargs)
            if response.status_code != 401:
                return response
            alternate = "bearer" if self._meter_auth == "raw" else "raw"
            response = await self._request(
                "GET", path, meter_auth=alternate, **kwargs
            )
            if 200 <= response.status_code < 300:
                self._meter_auth = alternate
                self._meter_rejections.pop(key, None)
                return response
            if response.status_code != 401:
                return response
            # A still-working cabinet distinguishes a meter service rejection
            # from an expired login. This also rechecks current membership.
            await self.list_accounts()
            now = time.monotonic()
            self._meter_rejections = {
                k: until for k, until in self._meter_rejections.items() if until > now
            }
            if len(self._meter_rejections) >= 128:
                self._meter_rejections.pop(next(iter(self._meter_rejections)))
            self._meter_rejections[key] = now + 60
            raise self._api_changed(interface, "authorization_rejected")

    def _parse_meter(self, interface, parser, *args, recover=True):
        """Clear compatibility warnings only after validating the response."""
        try:
            result = parser(*args)
        except AccountError:
            raise self._api_changed(interface, "response_format") from None
        if recover:
            self._api_recovered(interface)
        return result

    async def _get(self, path: str, **kwargs) -> Any:
        interface = self._billing_interface(path)
        response = (
            await self._meter_response(path, interface, **kwargs)
            if interface else await self._read_response(path, **kwargs)
        )
        self._check(response)
        try:
            payload = self._decode(response)
        except AccountError:
            if path == "/api/billing/joint/objects/get_advanced":
                raise self._api_changed("cabinet", "response_format") from None
            if interface:
                raise self._api_changed(interface, "response_format") from None
            raise
        return payload

    async def list_accounts(self) -> tuple[PersonalAccount, ...]:
        accounts: dict[str, PersonalAccount] = {}
        profiles = {}
        for page in range(1, 51):
            response = await self._get(
                "/api/billing/joint/objects/get_advanced",
                params={"page": page, "pageSize": 200},
            )
            if isinstance(response, dict) and (
                response.get("status") == "error" or response.get("error")
            ):
                raise AccountError("Personal account service could not list accounts")
            if (
                not isinstance(response, dict)
                or response.get("status") != "success"
                or response.get("error")
                or not isinstance(response.get("data"), dict)
                or not isinstance(response["data"].get("data"), list)
            ):
                raise self._api_changed("cabinet", "response_format")
            data = response["data"]
            pages = data.get("totalPages")
            if type(pages) is not int or pages < 0 or pages > 50:
                raise self._api_changed("cabinet", "response_format")
            for item in data["data"]:
                if not isinstance(item, dict):
                    raise self._api_changed("cabinet", "response_format")
                if type(item.get("isLegal")) is not bool:
                    raise self._api_changed("cabinet", "response_format")
                if item["isLegal"]:
                    continue
                number, address = item.get("accountNumber"), item.get("address")
                if (
                    not isinstance(number, str)
                    or not number.isascii()
                    or not number.isdigit()
                ):
                    raise self._api_changed("cabinet", "response_format")
                if not isinstance(address, str) or not address.strip():
                    raise self._api_changed("cabinet", "response_format")
                accounts[number] = PersonalAccount(number, address)
                profiles[number] = {
                    key: item.get(key) for key in ("address", "eic", "contractPower")
                }
            if page >= pages:
                self._accounts = set(accounts)
                self._linked_profiles = profiles
                self._api_recovered("cabinet")
                return tuple(accounts.values())
        raise AccountError("Personal account list is too large")

    async def read_account(self, number: str) -> AccountSnapshot:
        if number not in self._accounts:
            raise AccountError("Selected personal account is no longer linked")
        now = datetime.now(ZoneInfo("Europe/Kyiv"))
        path = f"{BILLING}/meters/household/{number}"
        unavailable = []
        try:
            details = await self._get(path + "/data")
            if not isinstance(details, dict) or "accountNumber" not in details:
                raise self._api_changed("meter_details", "response_format")
        except (AccountAuthError, AccountRateLimitError):
            raise
        except AccountError:
            details = None
            unavailable.append("meter_details")
        if details is not None and details.get("accountNumber") != number:
            raise AccountError("Invalid meter details")
        if details is not None:
            self._api_recovered("meter_details")
        try:
            readings = self._parse_meter(
                "meter_readings", parse_readings,
                await self._get(path + "/meters-with-readings"), now.date()
            )
        except (AccountAuthError, AccountRateLimitError):
            raise
        except AccountError:
            readings = ()
            unavailable.append("meter_readings")
        year = now.year if now.month != 1 else now.year - 1
        try:
            consumption, period = self._parse_meter(
                "meter_consumption", parse_consumption,
                await self._get(
                    BILLING + "/meters/household/customer-book",
                    params={"accountNumber": number, "year": year},
                ),
                now.date(),
            )
        except (AccountAuthError, AccountRateLimitError):
            raise
        except AccountError:
            consumption, period = None, None
            unavailable.append("meter_consumption")
        profile = parse_profile(details, self._linked_profiles.get(number))
        return AccountSnapshot(
            profile["model"],
            profile["next_verification_year"],
            readings,
            consumption,
            period,
            now,
            profile,
            tuple(unavailable),
        )

    async def read_history(self, number: str, year: int) -> dict:
        now = datetime.now(ZoneInfo("Europe/Kyiv"))
        validate_year(year, now.date())
        if number not in self._accounts:
            raise AccountError("Selected personal account is no longer linked")
        records = {}
        expected_pages = None
        raw_count = 0
        for page in range(1, MAX_HISTORY_PAGES + 1):
            payload = await self._get(
                f"{BILLING}/meters/household/{number}/history",
                params={"year": year, "page": page, "limit": 100},
            )
            returned_page, pages, rows = self._parse_meter(
                "meter_history", parse_history_page, payload, year, now.date(), recover=False
            )
            if returned_page != page or (
                expected_pages is not None and pages != expected_pages
            ):
                raise AccountError("History changed during pagination; retry later")
            expected_pages = pages
            # An entire page may belong to other years. Bound the received data,
            # not the locally filtered subset, and continue to subsequent pages.
            raw_count += len(payload["data"])
            if raw_count > MAX_HISTORY_ROWS or (pages > 1 and not payload["data"]):
                raise AccountError("Incomplete or excessive history response")
            for identity, row in rows:
                if identity in records and records[identity] != row:
                    raise AccountError("Conflicting history records; retry later")
                records[identity] = row
            if page >= pages:
                break
        self._api_recovered("meter_history")
        unavailable = []
        try:
            months = self._parse_meter(
                "meter_consumption", parse_months,
                await self._get(
                    BILLING + "/meters/household/customer-book",
                    params={"accountNumber": number, "year": year},
                ),
                year, now.date(),
            )
        except (AccountAuthError, AccountRateLimitError):
            raise
        except AccountError:
            months = []
            unavailable.append("meter_consumption")
        return {
            "year": year,
            "fetched_at": datetime.now(ZoneInfo("Europe/Kyiv")).isoformat(),
            "time_zone": "Europe/Kyiv",
            "meter_scope": "account",
            "readings": sorted(
                records.values(),
                key=lambda row: (row["date_time"], row["zone"], row["energy"]),
                reverse=True,
            ),
            "months": months,
            "unavailable": unavailable,
        }

    async def read_submission_context(self, number: str) -> dict:
        from .account_submission import submission_context

        # Recheck household membership for every prepare/confirm, not just on the
        # six-hour sensor refresh. A removed account must not remain writable.
        await self.list_accounts()
        if number not in self._accounts:
            raise AccountError("Selected personal account is no longer linked")
        path = f"{BILLING}/meters/household/{number}"
        details = await self._get(path + "/data")
        readings = await self._get(path + "/meters-with-readings")
        context = submission_context(
            details, readings, number, datetime.now(ZoneInfo("Europe/Kyiv")).date()
        )
        self._api_recovered("meter_details")
        self._api_recovered("meter_readings")
        return context

    async def submit_readings(self, number: str, readings: list, authorize, *, photos=None) -> dict:
        from .account_submission import SubmissionError, submission_result
        from .account_photos import PhotoError, validate_photos

        try:
            photos, _ = validate_photos(photos, [r["zone"] for r in readings])
        except PhotoError as error:
            raise SubmissionError(error.code) from None
        await self._ensure_token()
        authorize()
        if number not in self._accounts:
            raise SubmissionError("not_available")
        body = {
            "accountNumber": number,
            "readings": [
                {
                    "deviceEnergyType": "ACTIVE",
                    "deviceScaleType": r["zone"],
                    "value": r["value"],
                    **({"photo": photos[r["zone"]]["data"],
                        "photoMimeType": photos[r["zone"]]["mime_type"]}
                       if r["zone"] in photos else {}),
                }
                for r in readings
            ],
        }
        # Unlike GET, never retry this POST, including a 401 or a lost response.
        try:
            response = await self._request(
                "POST", f"{BILLING}/meters/household/{number}/readings", json=body
            )
            payload = self._decode(response)
        except AccountError:
            return {"status": "unknown"}
        result = submission_result(payload, len(readings))
        if isinstance(payload, list):
            codes = {r.get("messageCode") for r in payload if isinstance(r, dict)
                     and isinstance(r.get("messageCode"), str)}
            if codes & {"READING_ARE_LARGE_ADD_PHOTO_TO_CHECK", "READING_IS_SMALLER_THAN_PREVIOUS"}:
                # Even an unexpected SUCCESS must not disguise a photo request as acceptance.
                if result["status"] == "accepted":
                    result["status"] = "unknown"
                result["reason"] = "photo_required"
            if photos:
                # Keep only bounded machine codes for investigating new processing states.
                result["upstream_results"] = [
                    {k: r[k] for k in ("status", "messageCode")
                     if isinstance(r.get(k), str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,99}", r[k])}
                    for r in payload[:len(readings)] if isinstance(r, dict)
                ]
        if result.get("status") == "accepted":
            self._api_recovered("meter_submission")
        return result
