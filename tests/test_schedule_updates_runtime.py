"""Persistent group notices and automation events across failure/restart."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_ha_runtime as runtime
from component_loader import load_component_module

if runtime.HAS_HA:
    mod = load_component_module("schedule_updates")
    changes = load_component_module("schedule_changes")
    buttons = load_component_module("button")
    from homeassistant.exceptions import HomeAssistantError, ServiceValidationError


@unittest.skipUnless(runtime.HAS_HA, "Requires real Home Assistant")
class ScheduleUpdateRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await runtime.RuntimeTests.asyncSetUp(self)
        self.day = datetime.now(runtime.coordinator.KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        # Use tomorrow for time-independent future-change assertions.
        self.tomorrow = self.day + timedelta(days=1)
        self.schedule["fact"]["data"] = {
            str(int(day.timestamp())): {
                g: {str(h): "yes" for h in range(1, 25)} for g in ("GPV3.1", "GPV5.1")
            } for day in (self.day, self.tomorrow)
        }
        self.create = patch.object(mod.pn, "async_create", wraps=mod.pn.async_create).start()
        self.addCleanup(patch.stopall)
        self.events = []
        self.addCleanup(self.hass.bus.async_listen(mod.SCHEDULE_CHANGED, self.events.append))
        self.groups = []
        self.addCleanup(self.hass.bus.async_listen(mod.GROUPS_CHANGED, self.groups.append))
        await self.coord.async_refresh()
        await self.hass.async_block_till_done()

    async def refresh(self):
        await self.coord.async_refresh()
        await self.hass.async_block_till_done()

    def assign(self, groups):
        self.client.get_home_status.return_value["data"]["12А"]["sub_type_reason"] = groups

    async def test_first_poll_repetition_reordering_and_restart_do_not_notify(self):
        self.create.assert_not_called()
        self.assertEqual(self.events, [])
        self.assign(["GPV5.1", "GPV3.1"])
        await self.refresh()
        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(self.groups[0].data["previous_groups"], ["GPV5.1"])
        self.assertEqual(self.groups[0].data["groups"], ["GPV3.1", "GPV5.1"])
        self.assign(["GPV3.1", "GPV5.1", "GPV3.1"])
        await self.refresh()
        self.coord = runtime.coordinator.DTEKDataCoordinator(self.hass, self.provider, self.entry)
        await self.refresh()
        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(self.events, [])

    async def test_schedule_event_is_semantic_and_survives_restart(self):
        self.schedule["fact"]["update"] = self.tomorrow.strftime("%d.%m.%Y 12:00")
        await self.refresh()
        self.assertEqual(self.events, [])
        self.schedule["fact"]["data"][str(int(self.tomorrow.timestamp()))]["GPV5.1"]["14"] = "no"
        await self.refresh()
        self.assertEqual(len(self.events), 1)
        payload = self.events[0].data
        self.assertEqual(payload["changed_groups"], ["GPV5.1"])
        self.assertEqual(payload["entry_id"], self.entry.entry_id)
        self.assertEqual(len(payload["revision"]), 64)
        self.assertNotIn("street", payload)
        self.coord = runtime.coordinator.DTEKDataCoordinator(self.hass, self.provider, self.entry)
        await self.refresh()
        self.assertEqual(len(self.events), 1)
        self.create.assert_not_called()  # A schedule event is not an unsolicited notice.

    async def test_unavailable_hidden_empty_and_recovery_are_not_group_changes(self):
        self.client.get_home_status.side_effect = runtime.client_module.DTEKApiError("offline")
        await self.refresh()
        self.client.get_home_status.side_effect = None
        self.client.get_home_status.return_value["showUserGroup"] = False
        await self.refresh()
        self.client.get_home_status.return_value["showUserGroup"] = True
        await self.refresh()
        self.create.assert_not_called()
        self.assertEqual(self.events, [])
        self.assertEqual(self.groups, [])

    async def test_group_change_does_not_require_a_published_schedule(self):
        self.hass.config.language = "uk"
        self.assign(["GPV3.1"])
        self.client.get_home_status.return_value["showCurSchedule"] = False
        await self.refresh()
        self.assertFalse(self.coord.notifications_ready)
        self.assertEqual(self.create.call_count, 1)
        self.assertIn("GPV5.1 → GPV3.1", self.create.call_args.args[1])
        self.assertEqual(self.events, [])

    async def test_website_hidden_ids_are_used_for_group_and_schedule_change_notices(self):
        self.client.get_home_status.return_value["showUserGroup"] = False
        await self.refresh()
        self.create.assert_not_called()
        self.schedule["fact"]["data"][str(int(self.tomorrow.timestamp()))]["GPV5.1"]["14"] = "no"
        await self.refresh()
        self.assertEqual(self.events[0].data["changed_groups"], ["GPV5.1"])
        self.assign(["GPV3.1"])
        await self.refresh()
        self.assertIn("GPV5.1 → GPV3.1", self.create.call_args.args[1])
        self.assertEqual(self.groups[0].data["groups"], ["GPV3.1"])
        self.assertFalse(self.coord.address_data["group_labels_visible"])
        await self.refresh()
        self.assertEqual(self.create.call_count, 1)
        self.assertEqual(len(self.groups), 1)

    async def test_missing_day_and_recovery_never_cancel_verified_outages(self):
        self.schedule["fact"]["data"][str(int(self.tomorrow.timestamp()))]["GPV5.1"]["14"] = "no"
        await self.refresh()
        baseline = deepcopy(self.schedule["fact"]["data"])
        self.schedule["fact"]["data"].pop(str(int(self.tomorrow.timestamp())))
        await self.refresh()
        self.schedule["fact"]["data"] = baseline
        await self.refresh()
        self.assertEqual(len(self.events), 1)

    async def test_store_failure_does_not_invalidate_data_or_forget_the_change(self):
        self.assign(["GPV3.1"])
        with patch.object(self.coord.changes.store, "async_save", AsyncMock(side_effect=OSError)):
            await self.refresh()
        self.assertTrue(self.coord.last_update_success)
        self.create.assert_not_called()
        await self.refresh()
        self.assertEqual(self.create.call_count, 1)

    async def test_manual_refresh_button_failure_and_shared_cooldown(self):
        self.entry.runtime_data = self.coord
        add = Mock()
        await buttons.async_setup_entry(self.hass, self.entry, add)
        button = add.call_args.args[0][0]
        self.assertEqual(button.unique_id, "test-address_schedule_refresh")
        before = self.client.get_home_status.await_count
        await button.async_press()
        self.assertEqual(self.client.get_home_status.await_count, before + 1)
        with self.assertRaises(ServiceValidationError):
            await self.coord.async_manual_refresh()
        self.assertEqual(self.client.get_home_status.await_count, before + 1)
        self.coord._last_manual_refresh = None
        self.client.get_home_status.side_effect = runtime.client_module.DTEKApiError("offline")
        with self.assertRaises(HomeAssistantError):
            await button.async_press()
        self.assertFalse(self.coord.last_update_success)

    async def test_unpublished_manual_refresh_is_not_a_transport_error(self):
        self.client.get_home_status.return_value["showCurSchedule"] = False
        await self.coord.async_manual_refresh()
        self.assertTrue(self.coord.last_update_success)
        self.assertFalse(self.coord.notifications_ready)

    async def test_remove_cleans_baseline_and_notice(self):
        await mod.remove_schedule_updates(self.hass, self.entry)
        self.assertIsNone(await self.coord.changes.store.async_load())

    async def test_operator_cooldown_prevents_any_manual_network_request(self):
        self.coord.provider = SimpleNamespace(diagnostics={"public_retry_in_seconds": 240})
        before = self.client.get_home_status.await_count
        with self.assertRaises(ServiceValidationError) as caught:
            await self.coord.async_manual_refresh()
        self.assertEqual(caught.exception.translation_placeholders, {"seconds": "240"})
        self.assertEqual(self.client.get_home_status.await_count, before)

    async def test_concurrent_clicks_share_the_same_cooldown(self):
        import asyncio
        ready, release = asyncio.Event(), asyncio.Event()
        response = self.client.get_home_status.return_value
        async def read(*args, **kwargs):
            ready.set()
            await release.wait()
            return response
        self.client.get_home_status.side_effect = read
        first = asyncio.create_task(self.coord.async_manual_refresh())
        await ready.wait()
        second = asyncio.create_task(self.coord.async_manual_refresh())
        release.set()
        await first
        with self.assertRaises(ServiceValidationError):
            await second
        self.assertEqual(self.client.get_home_status.await_count, 2)  # Baseline + one click.
