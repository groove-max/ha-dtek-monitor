"""Optional metadata lifecycle, manual overrides and independent public schedules."""

import asyncio
from datetime import datetime, timedelta, timezone
from threading import get_ident
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, Mock, patch

from component_loader import load_component_module
import test_ha_runtime as runtime
import test_account_schedule as schedules
import test_account_runtime as accounts

if runtime.HAS_HA:
    mod = load_component_module("account_groups")
    account = load_component_module("account")
    health = load_component_module("account_api_health")
    from homeassistant.helpers import issue_registry as ir
    from homeassistant.core import callback
    from homeassistant.helpers.event import async_call_later


@unittest.skipUnless(runtime.HAS_HA, "Requires Home Assistant")
class AccountGroupsRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await accounts.AccountRuntimeTests.asyncSetUp(self)
        await self.account_coord.async_refresh()
        self.entry.runtime_data = self.account_coord
        self.manager = self.account_coord.groups
        self.provider = NS(read_groups=AsyncMock(return_value=("GPV3.1",)), close=AsyncMock())
        self.manager.provider = self.provider
        self.numbers = list(self.entry.data["accounts"])
        self.addAsyncCleanup(self.manager.close)

    async def test_failure_clears_current_groups_without_invalidating_meter_data(self):
        await self.manager.refresh()
        self.assertEqual(self.manager.get(self.numbers[0]).groups, ("GPV3.1",))
        snapshot = self.account_coord.data
        self.provider.read_groups.side_effect = account.AccountError("private transport URL")
        await self.manager.refresh()
        result = self.manager.get(self.numbers[0])
        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.groups, ())
        self.assertIs(self.account_coord.data, snapshot)
        self.assertTrue(self.account_coord.last_update_success)
        self.provider.read_groups.side_effect = None
        self.provider.read_groups.return_value = ("GPV5.1",)
        await self.manager.refresh()
        self.assertEqual(self.manager.get(self.numbers[0]).groups, ("GPV5.1",))

    async def test_freshness_empty_and_disabled_are_distinct(self):
        self.provider.read_groups.return_value = ()
        await self.manager.refresh()
        self.assertEqual(self.manager.get(self.numbers[0]).status, "empty")
        self.manager.results[self.numbers[0]] = mod.GroupResult("current", ("GPV3.1",), datetime.now(timezone.utc) - timedelta(minutes=16))
        self.assertEqual(self.manager.get(self.numbers[0]).status, "expired")
        self.assertEqual(self.manager.get(self.numbers[0]).groups, ())
        self.entry.options = {"account_schedules": {
            self.numbers[0]: {"use_cabinet_groups": False}, self.numbers[1]: {"disabled": True},
        }}
        self.provider.read_groups.reset_mock()
        await self.manager.refresh()
        self.provider.read_groups.assert_not_called()
        self.assertEqual(self.manager.get(self.numbers[0]).status, "disabled")
        self.assertEqual(self.manager.get(self.numbers[1]).status, "disabled")

    async def test_one_account_failure_and_retirement_repair_do_not_affect_the_other(self):
        self.provider.read_groups.side_effect = [account.AccountAPIChanged("account_groups", "HTTP 410"), ("GPV5.1",)]
        await self.manager.refresh()
        self.assertEqual(self.manager.get(self.numbers[0]).status, "api_changed")
        self.assertEqual(self.manager.get(self.numbers[1]).groups, ("GPV5.1",))
        registry = ir.async_get(self.hass)
        issue_id = "account_api_dtek_oem_account_groups_" + self.entry.entry_id
        issue = registry.async_get_issue("dtek_monitor", issue_id)
        self.assertIsNotNone(issue)
        self.assertEqual(issue.learn_more_url, health.ISSUES_URL)
        self.assertNotIn("100001", str(issue.translation_placeholders))
        self.provider.read_groups.side_effect = None
        await self.manager.refresh()
        self.assertIsNone(registry.async_get_issue("dtek_monitor", issue_id))

    async def test_rate_limit_stops_remaining_accounts_and_never_reuses_their_old_groups(self):
        await self.manager.refresh()
        self.provider.read_groups.reset_mock()
        self.provider.read_groups.side_effect = account.AccountRateLimitError("limit")
        await self.manager.refresh()
        self.provider.read_groups.assert_awaited_once()
        self.assertNotEqual(self.manager.get(self.numbers[1]).status, "current")
        self.assertEqual(self.manager.get(self.numbers[1]).groups, ())

    async def test_late_result_cannot_restore_removed_or_replaced_account(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def delayed(number):
            started.set()
            await release.wait()
            return ("GPV3.1",)
        self.provider.read_groups.side_effect = delayed
        task = asyncio.create_task(self.manager.refresh())
        await started.wait()
        self.entry.data = {**self.entry.data, "accounts": {}}
        release.set()
        await task
        self.assertEqual(self.manager.results, {})
        self.assertEqual(self.manager.get(self.numbers[0]).groups, ())

    async def test_background_requests_are_single_flight_and_close_cancels_them(self):
        started = asyncio.Event()
        async def blocked(number):
            started.set()
            await asyncio.Event().wait()
        self.provider.read_groups.side_effect = blocked
        self.manager.start()
        await started.wait()
        task = self.manager._task
        for _ in range(3): self.manager._tick()
        self.assertIs(task, self.manager._task)
        self.provider.read_groups.assert_awaited_once()
        await self.manager.close()
        self.assertTrue(task.cancelled())
        self.assertEqual(self.manager.results, {})

    async def test_new_meter_refresh_triggers_groups_without_notification_loop(self):
        self.manager.start()
        await self.manager._task
        self.assertEqual(self.provider.read_groups.await_count, 2)
        # A metadata update notifies HA, without fetching metadata again.
        self.manager._notify()
        self.assertTrue(self.manager._task.done())
        self.account_coord.data = dict(self.account_coord.data)
        self.manager._updated()
        await self.manager._task
        self.assertEqual(self.provider.read_groups.await_count, 4)

    async def test_expiration_notifies_entities_even_without_a_new_response(self):
        loop = asyncio.get_running_loop()
        loop_thread = get_ident()
        notified = loop.create_future()

        @callback
        def observe():
            # Deliver the observation safely even if HA dispatches the timer
            # to its executor, so that the regression fails with a clear reason.
            result = (get_ident(), self.manager.get(self.numbers[0]).status)
            loop.call_soon_threadsafe(notified.set_result, result)

        self.addCleanup(self.account_coord.async_add_listener(observe))
        with patch.object(mod, "REFRESH_INTERVAL", timedelta(0)):
            self.manager._set_result(
                self.numbers[0],
                mod.GroupResult("current", ("GPV3.1",), datetime.now(timezone.utc)),
            )
            thread, status = await asyncio.wait_for(notified, timeout=2)

        self.assertEqual(thread, loop_thread, "Group expiry must notify HA on its event loop")
        self.assertEqual(status, "expired")
        self.provider.read_groups.assert_not_awaited()

    async def test_replaced_removed_and_closed_results_cancel_expiry_notifications(self):
        observed = Mock()
        self.addCleanup(self.account_coord.async_add_listener(observed))
        for action in ("replace", "remove", "close"):
            with self.subTest(action=action):
                result = mod.GroupResult(
                    "current", ("GPV3.1",), datetime.now(timezone.utc)
                )
                with patch.object(mod, "REFRESH_INTERVAL", timedelta(0)):
                    self.manager._set_result(self.numbers[0], result)
                if action == "replace":
                    self.manager._set_result(self.numbers[0], result)
                elif action == "remove":
                    self.manager._set_result(self.numbers[0], None)
                else:
                    await self.manager.close()

                # Drain real HA timer dispatch and any executor work before
                # checking that the cancelled callback did not notify listeners.
                drained = asyncio.get_running_loop().create_future()

                @callback
                def finish(_now):
                    drained.set_result(None)

                cancel = async_call_later(self.hass, 0, finish)
                try:
                    await asyncio.wait_for(drained, timeout=2)
                    await self.hass.async_block_till_done()
                finally:
                    cancel()
                observed.assert_not_called()

    async def test_changed_meter_snapshot_queues_a_fresh_lookup_after_inflight_request(self):
        started, release = asyncio.Event(), asyncio.Event()
        async def read(number):
            if not started.is_set():
                started.set()
                await release.wait()
            return ("GPV3.1",)
        self.provider.read_groups.side_effect = read
        self.manager.start()
        await started.wait()
        first_task = self.manager._task
        self.account_coord.data = dict(self.account_coord.data)
        # A changed object, as returned by an actual new meter refresh.
        self.account_coord.data[self.numbers[0]] = NS()
        self.manager._updated()
        release.set()
        await first_task
        await asyncio.sleep(0)
        await self.manager._task
        self.assertEqual(self.provider.read_groups.await_count, 4)
        self.assertEqual(self.manager.get(self.numbers[0]).status, "current")

    async def test_failed_first_account_is_invalidated_while_second_is_still_waiting(self):
        await self.manager.refresh()
        waiting, release = asyncio.Event(), asyncio.Event()
        async def read(number):
            if number == self.numbers[0]:
                raise account.AccountError("unavailable")
            waiting.set()
            await release.wait()
            return ("GPV5.1",)
        self.provider.read_groups.side_effect = read
        observed = []
        self.account_coord.async_update_listeners = Mock(side_effect=lambda: observed.append(self.manager.get(self.numbers[0]).status))
        task = asyncio.create_task(self.manager.refresh())
        await waiting.wait()
        self.assertIn("unavailable", observed)
        self.assertFalse(task.done())
        release.set()
        await task

    async def test_disabling_or_removing_one_connection_does_not_clear_another_repair(self):
        error = account.AccountAPIChanged("account_groups", "HTTP 410")
        other_id = "account_api_dtek_oem_account_groups_other-connection"
        own_id = "account_api_dtek_oem_account_groups_" + self.entry.entry_id
        health.report_api_issue(self.hass, "dtek_oem", error, scope="other-connection")
        self.provider.read_groups.side_effect = error
        await self.manager.refresh()
        registry = ir.async_get(self.hass)
        self.assertIsNotNone(registry.async_get_issue("dtek_monitor", own_id))
        self.entry.options = {"account_schedules": {n: {"use_cabinet_groups": False} for n in self.numbers}}
        await self.manager.refresh()
        self.assertIsNone(registry.async_get_issue("dtek_monitor", own_id))
        self.assertIsNotNone(registry.async_get_issue("dtek_monitor", other_id))
        health.report_api_issue(self.hass, "dtek_oem", error, scope=self.entry.entry_id)
        setup = load_component_module("__init__")
        await setup.async_remove_entry(self.hass, self.entry)
        self.assertIsNone(registry.async_get_issue("dtek_monitor", own_id))
        self.assertIsNotNone(registry.async_get_issue("dtek_monitor", other_id))


@unittest.skipUnless(runtime.HAS_HA, "Requires Home Assistant")
class CabinetGroupSelectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await schedules.AccountScheduleTests.asyncSetUp(self)
        schedules.AccountScheduleTests.link(self, [])
        self.result = mod.GroupResult("current", ("GPV3.1",), datetime.now(timezone.utc))
        self.personal.runtime_data = NS(groups=NS(get=lambda number: self.result))

    async def test_single_cabinet_group_selects_only_private_calendar_and_tracks_changes(self):
        before = self.coord.address_data.copy()
        self.assertTrue(self.calendar.available)
        self.assertEqual(self.sensor.native_value, "GPV3.1")
        self.assertEqual(self.sensor.extra_state_attributes["selection_source"], "cabinet")
        events = await self.calendar.async_get_events(self.hass, self.start, self.end)
        self.assertEqual(len(events), 1)
        self.result = mod.GroupResult("current", ("GPV5.1",), datetime.now(timezone.utc))
        self.assertEqual(self.sensor.native_value, "GPV5.1")
        self.assertEqual(self.coord.address_data, before)
        public = runtime.calendar.DTEKScheduleCalendar(self.coord, self.entry, "outage", "outage_schedule", "outage_schedule")
        self.assertEqual(len(await public.async_get_events(self.hass, self.start, self.end)), 2)

    async def test_multiple_missing_stale_and_mismatched_groups_never_pick_the_first(self):
        for result, status in (
            (mod.GroupResult("current", ("GPV3.1", "GPV5.1")), "not_selected"),
            (mod.GroupResult("current", ("GPV2.1",)), "cabinet_group_mismatch"),
            (mod.GroupResult("empty"), "not_selected"),
            (mod.GroupResult("expired"), "cabinet_unavailable"),
            (mod.GroupResult("unavailable"), "cabinet_unavailable"),
            (mod.GroupResult("api_changed"), "cabinet_unavailable"),
        ):
            with self.subTest(result=result):
                self.result = result
                self.assertFalse(self.calendar.available)
                self.assertIsNone(self.sensor.native_value)
                self.assertEqual(self.sensor.extra_state_attributes["selection_status"], status)

    async def test_manual_selection_wins_during_errors_and_conflicts(self):
        schedules.AccountScheduleTests.link(self, ["GPV5.1"])
        for result in (self.result, mod.GroupResult("api_changed"), mod.GroupResult("current", ("GPV2.1",))):
            self.result = result
            self.assertTrue(self.calendar.available)
            self.assertEqual(self.sensor.native_value, "GPV5.1")
            self.assertEqual(self.sensor.extra_state_attributes["selection_source"], "user")

    async def test_verified_single_building_group_is_independent_of_optional_failure(self):
        self.coord.address_data["schedule_groups"] = ["GPV3.1"]
        self.result = mod.GroupResult("unavailable")
        self.assertTrue(self.calendar.available)
        self.assertEqual(self.sensor.extra_state_attributes["selection_source"], "building_single_group")

    async def test_automatic_apartment_selection_still_requires_current_cabinet_for_multiple_groups(self):
        self.coord.address_data["group_labels_visible"] = False
        self.assertTrue(self.calendar.available)
        self.assertEqual(self.sensor.extra_state_attributes["cabinet_groups"], ["GPV3.1"])
        self.assertEqual(self.sensor.extra_state_attributes["building_groups"], ["GPV3.1", "GPV5.1"])
        self.assertFalse(self.sensor.extra_state_attributes["group_labels_visible"])
        self.result = mod.GroupResult("expired")
        self.assertFalse(self.calendar.available)
        self.assertEqual(self.sensor.extra_state_attributes["cabinet_groups"], [])

    async def test_group_form_can_disable_lookup_without_changing_manual_groups(self):
        self.options._schedule_account = "100001"
        self.options._schedule_address = self.entry.entry_id
        self.options._schedule_group_choices = None
        form = await self.options.async_step_account_schedule_groups()
        self.assertIn("use_cabinet_groups", [str(k) for k in form["data_schema"].schema])
        saved = await self.options.async_step_account_schedule_groups({"schedule_groups": ["GPV5.1"], "use_cabinet_groups": False})
        link = saved["data"]["account_schedules"]["100001"]
        self.assertFalse(link["use_cabinet_groups"])
        self.assertEqual(link["groups"], ["GPV5.1"])
