"""Authenticated, acknowledged status actions for connected Telegram add-ons."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import time
from uuid import uuid4

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.service import async_register_admin_service, async_set_service_schema

from .const import DOMAIN

DATA_KEY = f"{DOMAIN}_bot_status"
TIMEOUT = 60
ID = vol.All(str, vol.Length(min=1, max=128), vol.Match(r"^[a-zA-Z0-9_-]+$"))
OPERATIONS = {"refresh_bot_status": "refresh", "send_bot_status": "send"}
ERRORS = {
    "offline": "Telegram add-on is disconnected. Start it and try again.",
    "disabled": "Enable reusable pinned status for this profile before refreshing it.",
    "rate_limited": "Status requests are too frequent. Wait before trying again.",
    "expired": "The request expired before delivery. Check the add-on connection.",
    "unknown": "Delivery could not be confirmed. Check Telegram before sending again.",
    "partial": "Only some recipients received the status. Check Telegram before retrying.",
    "failed": "The status could not be delivered. Check the Telegram add-on diagnostics.",
}


@dataclass
class Client:
    connection: object
    subscription: int
    profiles: dict[str, dict]
    pending: dict[str, asyncio.Future] = field(default_factory=dict)


class StatusBridge:
    def __init__(self, hass):
        self.hass = hass
        self.clients: dict[str, Client] = {}

    @callback
    def descriptions(self):
        """Keep the native action selector aligned with live add-on profiles."""
        uk = self.hass.config.language in ("uk", "ru")
        for service, operation in OPERATIONS.items():
            options = [
                {"value": f"{instance}:{key}", "label": profile["name"]}
                for instance, client in self.clients.items()
                for key, profile in client.profiles.items()
                if operation == "send" or profile["can_refresh"]
            ]
            fields = {"profile": {
                "name": "Профіль бота" if uk else "Bot profile", "required": True,
                "selector": {"select": {"options": options, "mode": "dropdown", "custom_value": False}},
            }}
            if operation == "send":
                fields["silent"] = {
                    "name": "Без звуку" if uk else "Silent", "default": True,
                    "selector": {"boolean": {}},
                }
            async_set_service_schema(self.hass, DOMAIN, service, {
                "name": (("Оновити закріплений статус бота" if operation == "refresh" else "Надіслати поточний статус бота")
                         if uk else ("Refresh pinned bot status" if operation == "refresh" else "Send current bot status")),
                "description": ("Використовує шаблони та налаштованих одержувачів профілю."
                                if uk else "Uses the profile's templates and configured recipients."),
                "fields": fields,
            })

    @callback
    def disconnect(self, instance, client):
        if self.clients.get(instance) is not client:
            return
        del self.clients[instance]
        for future in client.pending.values():
            if not future.done():
                future.set_result({"status": "unknown"})
        self.descriptions()

    async def execute(self, call):
        instance, _, key = call.data["profile"].partition(":")
        client = self.clients.get(instance)
        if client is None:
            raise self.error("offline")
        profile = client.profiles.get(key)
        if profile is None:
            raise ServiceValidationError("Unknown Telegram profile. Select a connected profile again.")
        operation = OPERATIONS[call.service]
        if operation == "refresh" and not profile["can_refresh"]:
            raise self.error("disabled")
        if len(client.pending) >= 20:
            raise self.error("rate_limited")
        request_id = uuid4().hex
        future = asyncio.get_running_loop().create_future()
        client.pending[request_id] = future
        try:
            client.connection.send_event(client.subscription, {
                "request_id": request_id, "profile_id": key, "operation": operation,
                "silent": call.data.get("silent", True), "expires": time.time() + TIMEOUT - 5,
            })
            result = await asyncio.wait_for(future, TIMEOUT)
        except TimeoutError as exc:
            raise self.error("unknown") from exc
        finally:
            client.pending.pop(request_id, None)
        if result["status"] not in ("sent", "updated"):
            raise self.error(result["status"])
        return {"request_id": request_id, **result}

    @staticmethod
    def error(code):
        return HomeAssistantError(
            ERRORS.get(code, ERRORS["failed"]), translation_domain=DOMAIN,
            translation_key=f"bot_status_{code if code in ERRORS else 'failed'}",
        )


@websocket_api.websocket_command({
    vol.Required("type"): "dtek_monitor/bot_status/subscribe",
    vol.Required("version"): 1,
    vol.Required("instance_id"): ID,
    vol.Required("profiles"): vol.All([{
        vol.Required("id"): ID,
        vol.Required("name"): vol.All(str, vol.Length(min=1, max=256)),
        vol.Required("can_refresh"): bool,
    }], vol.Length(max=100)),
})
@websocket_api.require_admin
@callback
def websocket_subscribe(hass, connection, msg):
    bridge = hass.data[DATA_KEY]
    instance = msg["instance_id"]
    if instance in bridge.clients:
        connection.send_error(msg["id"], "already_connected", "This add-on instance is already connected")
        return
    profiles = {p["id"]: p for p in msg["profiles"]}
    if len(profiles) != len(msg["profiles"]):
        connection.send_error(msg["id"], "invalid_format", "Profile IDs must be unique")
        return
    client = Client(connection, msg["id"], profiles)
    bridge.clients[instance] = client
    connection.subscriptions[msg["id"]] = lambda: bridge.disconnect(instance, client)
    bridge.descriptions()
    connection.send_result(msg["id"], {"version": 1})


@websocket_api.websocket_command({
    vol.Required("type"): "dtek_monitor/bot_status/result",
    vol.Required("instance_id"): ID,
    vol.Required("request_id"): ID,
    vol.Required("status"): vol.In(["sent", "updated", *ERRORS]),
    vol.Optional("recipients", default=0): vol.All(int, vol.Range(min=0, max=100)),
})
@websocket_api.require_admin
@callback
def websocket_result(hass, connection, msg):
    client = hass.data[DATA_KEY].clients.get(msg["instance_id"])
    if client is None or client.connection is not connection:
        connection.send_error(msg["id"], "unauthorized", "Result does not belong to this connection")
        return
    future = client.pending.get(msg["request_id"])
    if future is not None and not future.done():
        future.set_result({"status": msg["status"], "recipients": msg["recipients"]})
    connection.send_result(msg["id"])


@callback
def async_setup_status_actions(hass):
    if DATA_KEY in hass.data:
        return
    bridge = hass.data[DATA_KEY] = StatusBridge(hass)
    for name, operation in OPERATIONS.items():
        schema = {vol.Required("profile"): vol.All(str, vol.Length(min=3, max=257))}
        if operation == "send":
            schema[vol.Optional("silent", default=True)] = bool
        async_register_admin_service(
            hass, DOMAIN, name, bridge.execute, vol.Schema(schema), SupportsResponse.OPTIONAL,
        )
    bridge.descriptions()
    websocket_api.async_register_command(hass, websocket_subscribe)
    websocket_api.async_register_command(hass, websocket_result)
