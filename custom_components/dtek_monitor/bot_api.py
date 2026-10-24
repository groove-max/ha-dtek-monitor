"""Explicit admin bridge for account-bound Telegram profiles; no cabinet secrets."""

from datetime import datetime, timedelta
import hashlib
import json

import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.helpers import entity_registry as er
from homeassistant.exceptions import HomeAssistantError
from .account_reminders import reading_window
from .account_analysis import match_readback
from .account_history import MAX_HISTORY_ROWS, reading_history_page

from .account import AccountAPIChanged, AccountAuthError, AccountError, AccountRateLimitError
from .account_schedule import cabinet_groups, compare_cabinet_groups, selection
from .account_submission import SubmissionError
from .account_photos import MAX_PHOTO_ENCODED
from .account_submission_api import resolve
from .helpers import build_entity_unique_id
from .schedule import KYIV_TZ
from .schedule_grid import grid_data


def account_snapshot(hass, connection, entry, number):
    """Use ONLY current cabinet groups. UI/manual/building fallback is not a source."""
    address, coordinator, _, link_status = selection(hass, entry, number)
    cabinet = cabinet_groups(entry, number)
    status = cabinet.status if cabinet else "unsupported"
    building = (
        coordinator.address_data.get("schedule_groups", [])
        if coordinator and coordinator.address_success else None
    )
    comparison = compare_cabinet_groups(building, cabinet)
    groups = comparison["verified_cabinet_groups"]
    if comparison["cabinet_groups"] and building is None:
        status = link_status
    # A private cabinet supplies its own group labels. Public display policy
    # must not disable a fresh, matching cabinet assignment (notably Kyiv).
    elif comparison["unverified_cabinet_groups"]:
        status = "partial" if groups else "cabinet_group_mismatch"
    entities = {}
    if address:
        registry = er.async_get(hass)
        for key in (
            "power",
            "status",
            "outage_start",
            "outage_end",
            "outage_description",
            "schedule_changed",
            "schedule_status",
            "outage_schedule",
            "possible_schedule",
            "schedule_group",
        ):
            unique = build_entity_unique_id(address, key)
            entity = next(
                (
                    e
                    for e in er.async_entries_for_config_entry(
                        registry, address.entry_id
                    )
                    if e.platform == "dtek_monitor"
                    and e.unique_id == unique
                    and not e.disabled_by
                ),
                None,
            )
            if entity:
                if not connection.user.permissions.check_entity(
                    entity.entity_id, POLICY_READ
                ):
                    raise SubmissionError("unauthorized")
                entities[
                    {
                        "status": "outage_status",
                        "possible_schedule": "possible_outage_schedule",
                    }.get(key, key)
                ] = entity.entity_id
    ready = bool(groups and coordinator and coordinator.notifications_ready)
    snapshot = coordinator.snapshot if coordinator else None
    revision = hashlib.sha256(
        json.dumps(
            [snapshot.snapshot_id if snapshot else None, groups], sort_keys=True
        ).encode()
    ).hexdigest()
    attrs = {
        "schedule_groups": groups,
        # Older bots need this display flag for verified cabinet labels. Keep
        # the website's actual flag separately for newer presentation contexts.
        "group_labels_visible": True,
        "source_group_labels_visible": (
            coordinator.address_data.get("group_labels_visible", False)
            if coordinator and coordinator.address_success else False
        ),
        "schedule_notifications_ready": ready,
        "schedule_snapshot_id": revision,
        "schedule_coverage": coordinator.snapshot_attributes["schedule_coverage"]
        if coordinator
        else [],
        "provider_id": coordinator.address.provider_id if coordinator else None,
        "address_id": coordinator.address.identity if coordinator else None,
        "cabinet_group_status": status,
        **comparison,
        "selection_source": "cabinet",
    }
    now = datetime.now(KYIV_TZ)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    calendars = {}
    for kind in ("outage", "possible"):
        available = bool(
            ready
            and coordinator.schedule
            and all(
                any(
                    c.group_id == g
                    and c.kind == kind
                    and c.end > start
                    and c.start < start + timedelta(days=7)
                    for c in coordinator.schedule.coverage
                )
                for g in groups
            )
        )
        events = (
            coordinator.get_events_for_range(
                start, start + timedelta(days=7), groups, kind
            )
            if available
            else []
        )
        calendars[kind] = {
            "available": available,
            "events": [
                {
                    "start": e.start.isoformat(),
                    "end": e.end.isoformat(),
                    "summary": e.summary,
                    "description": e.description or "",
                }
                for e in events
            ],
        }
    return {
        "version": 1,
        "account": f"••••{number[-4:]}",
        "group_status": status,
        "groups": groups,
        "attributes": attrs,
        "calendars": calendars,
        "entities": entities,
        "address": entry.data["accounts"][number],
        "checked_at": now.isoformat(),
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "dtek_monitor/bot_account",
        vol.Required("entity_id"): str,
        vol.Required("action"): vol.In(
            (
                "snapshot",
                "grid",
                "refresh",
                "context",
                "energy",
                "prepare",
                "confirm",
                "reminder",
                "readback",
                "history",
                "calibration_preview",
                "calibration_save",
                "documents",
                "document",
            )
        ),
        vol.Optional("telegram_user_id"): vol.All(int, vol.Range(min=1)),
        vol.Optional("telegram_bot_id"): vol.All(str, vol.Length(min=1, max=64)),
        vol.Optional("profile_id"): vol.All(str, vol.Length(min=1, max=64)),
        vol.Optional("revision"): vol.All(str, vol.Length(max=64)),
        vol.Optional("values"): {
            vol.All(str, vol.Length(max=40)): vol.All(str, vol.Length(max=8))
        },
        vol.Optional("confirmation"): vol.All(str, vol.Length(max=64)),
        vol.Optional("document_id"): vol.All(str, vol.Match(r"^[a-f0-9]{32}$")),
        vol.Optional("source_token"): vol.All(str, vol.Length(max=64)),
        vol.Optional("photos"): vol.All({
            vol.All(str, vol.Length(max=40)): {
                vol.Required("data"): vol.All(str, vol.Length(max=MAX_PHOTO_ENCODED)),
                vol.Required("mime_type"): vol.In(("image/jpeg", "image/png")),
            },
        }, vol.Length(max=2)),
        vol.Optional("binding_revision"): vol.All(str, vol.Length(max=64)),
        vol.Optional("contemporaneous"): bool,
        vol.Optional("include_inactive"): bool,
        vol.Optional("history_offset"): vol.All(int, vol.Range(min=0, max=MAX_HISTORY_ROWS)),
    }
)
@websocket_api.async_response
async def websocket_bot_account(hass, connection, msg):
    entry = None
    try:
        entry, number, runtime = resolve(hass, connection, msg["entity_id"])

        def authorize(source=None):
            current, selected, coordinator = resolve(hass, connection, msg["entity_id"])
            if current is not entry or selected != number or coordinator is not runtime:
                raise SubmissionError("not_available")
            if source and not connection.user.permissions.check_entity(
                source, POLICY_READ
            ):
                raise SubmissionError("unauthorized")

        action = msg["action"]
        if action == "snapshot":
            result = account_snapshot(hass, connection, entry, number)
        elif action == "reminder":
            now = datetime.now(KYIV_TZ)
            window = reading_window(now.date())
            result = {
                "period": window[0] if window else None,
                "due": bool(window and now.hour >= 19),
            }
            record = await runtime.submissions.last_attempt(number)
            if window and record and record.get("status") == "accepted":
                try:
                    day = (
                        datetime.fromisoformat(record["at"]).astimezone(KYIV_TZ).date()
                    )
                    if window[1] <= day <= window[2]:
                        result["due"] = False
                except (ValueError, KeyError):
                    pass
        elif action in ("grid", "refresh"):
            account_snapshot(
                hass, connection, entry, number
            )  # Check linked-entity access before refreshing.
            _, coordinator, _, _ = selection(hass, entry, number)
            if coordinator is None:
                raise SubmissionError("no_address")
            if action == "refresh":
                await coordinator.async_manual_refresh()
                authorize()
                if selection(hass, entry, number)[1] is not coordinator:
                    raise SubmissionError("not_available")
            groups = account_snapshot(hass, connection, entry, number)["groups"]
            result = grid_data(coordinator, groups)
        else:
            if not all(
                msg.get(k)
                for k in ("telegram_user_id", "telegram_bot_id", "profile_id")
            ):
                raise SubmissionError("unauthorized")
            # Separate people/profile drafts even though the add-on uses one HA principal.
            principal = json.dumps(
                [
                    connection.user.id,
                    msg["telegram_bot_id"],
                    msg["telegram_user_id"],
                    msg["profile_id"],
                ]
            )
            manager = runtime.submissions
            if action == "context":
                result = await manager.context(number, authorize)
                result.update(account=f"••••{number[-4:]}", photo_submission=True)
            elif action in ("history", "readback"):
                attempt = await manager.last_attempt(number)
                year = datetime.now(KYIV_TZ).year
                # Bound repeated button presses without showing the six-hour UI cache.
                history = await runtime.history.get(number, year, max_age=60)
                authorize()
                latest = [r for r in history["readings"] if r["energy"] == "ACTIVE"]
                years = [year]
                checked = history["fetched_at"]
                if not latest:
                    history = await runtime.history.get(number, year - 1, max_age=60)
                    authorize()
                    latest = [r for r in history["readings"] if r["energy"] == "ACTIVE"]
                    checked = history["fetched_at"]
                    years.append(year - 1)
                if action == "readback" and attempt:
                    try:
                        stamp = datetime.fromisoformat(attempt["at"])
                        if stamp.tzinfo is None:
                            raise ValueError
                        attempt_year = stamp.astimezone(KYIV_TZ).year
                    except (TypeError, ValueError, KeyError):
                        attempt_year = None
                    if attempt_year is not None and attempt_year != history.get("year"):
                        history = await runtime.history.get(number, attempt_year, max_age=60)
                        authorize()
                snapshot = (runtime.data or {}).get(number)
                serial = (snapshot.profile or {}).get("serial") if snapshot else None
                result = match_readback(attempt if action == "readback" else None, history, serial)
                result.update(
                    **reading_history_page(
                        latest,
                        include_inactive=msg.get("include_inactive", False),
                        offset=msg.get("history_offset", 0),
                    ),
                    fetched_at=checked, years=years,
                    attempt={k: attempt.get(k) for k in ("at", "status", "readings")} if attempt else None,
                )
            elif action == "energy":
                result = await runtime.energy.get(number, principal, authorize)
            elif action == "documents":
                result = await runtime.documents.get(number)
            elif action == "document":
                result = await runtime.documents.download(number, msg.get("document_id"))
            elif action == "prepare":
                result = await manager.prepare(
                    number,
                    principal,
                    msg.get("revision"),
                    msg.get("values"),
                    authorize,
                    source_token=msg.get("source_token"),
                    photos=msg.get("photos"),
                )
            elif action == "calibration_preview":
                draft = await manager.prepare_calibration(
                    number, principal, msg.get("revision"), msg.get("values"),
                    msg.get("binding_revision"), authorize,
                )
                result = {key: draft[key] for key in ("confirmation", "change")}
            elif action == "calibration_save":
                result = await runtime.energy.save(
                    number, principal, msg.get("confirmation"), authorize,
                    contemporaneous=msg.get("contemporaneous", False),
                )
            else:
                result = await manager.confirm(
                    number, principal, msg.get("confirmation"), authorize
                )
                runtime.history.invalidate(number)
        authorize()
        connection.send_result(msg["id"], result)
    except SubmissionError as error:
        connection.send_error(msg["id"], error.code, "Account operation unavailable")
    except AccountAPIChanged:
        connection.send_error(
            msg["id"], "api_changed", "DTEK service is incompatible; check HA Repairs"
        )
        return
    except AccountAuthError:
        if entry:
            entry.async_start_reauth(hass)
        connection.send_error(
            msg["id"], "auth_required", "Authentication required in Home Assistant"
        )
    except AccountRateLimitError:
        connection.send_error(msg["id"], "rate_limited", "Please wait before retrying")
    except AccountError:
        connection.send_error(msg["id"], "unavailable", "Account service unavailable")
    except HomeAssistantError as error:
        connection.send_error(
            msg["id"],
            error.translation_key or "unavailable",
            "Operation unavailable; retry later",
        )
