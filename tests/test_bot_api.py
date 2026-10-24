"""Cabinet-only schedule bridge and Telegram principal isolation."""

from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, Mock, patch
import test_account_submission_api as submission_tests
from component_loader import load_component_module

HAS_HA = submission_tests.runtime.runtime.HAS_HA
if HAS_HA:
    api = load_component_module("bot_api")
    submission_api = load_component_module("account_submission_api")


@unittest.skipUnless(HAS_HA, "Requires Home Assistant")
class BotAccessTests(unittest.IsolatedAsyncioTestCase):
    async def test_photos_are_forwarded_only_to_the_authorized_confirmation_draft(self):
        photos = {"GENERAL": {"mime_type": "image/jpeg", "data": "synthetic"}}
        self.msg.update(action="prepare", revision="meter", values={"GENERAL": "1030"}, photos=photos)
        await self.invoke()
        self.assertIs(self.manager.prepare.call_args.kwargs["photos"], photos)
        self.assertEqual(self.manager.prepare.call_args.args[0], "100001")
        self.assertIn("profile-a", self.manager.prepare.call_args.args[1])
        self.manager.confirm.assert_not_awaited()
        self.manager.prepare.reset_mock()
        self.connection.user.permissions.check_entity.return_value = False
        await self.invoke()
        self.manager.prepare.assert_not_awaited()

    async def test_documents_use_selected_account_and_recheck_permissions_after_fetch(self):
        self.account_coord.documents = SimpleNamespace(get=AsyncMock(return_value={"documents": []}), download=AsyncMock(return_value={"data": "private"}))
        self.msg.update(action="documents")
        await self.invoke()
        self.account_coord.documents.get.assert_awaited_once_with("100001")
        self.msg.update(action="document", document_id="a"*32)
        await self.invoke()
        self.account_coord.documents.download.assert_awaited_once_with("100001", "a"*32)
        self.connection.send_result.reset_mock()
        async def revoked(*args):
            self.connection.user.permissions.check_entity.return_value = False
            return {"data": "private"}
        self.account_coord.documents.download.side_effect = revoked
        await self.invoke()
        self.connection.send_result.assert_not_called()

    async def test_calibration_uses_isolated_principal_and_explicit_local_confirmation(self):
        draft = {"confirmation": "local", "change": {"changes": {}}, "binding": {"private": "not for bot"}}
        self.manager.prepare_calibration = AsyncMock(return_value=draft)
        self.account_coord.energy = SimpleNamespace(save=AsyncMock(return_value={"saved": True}))
        self.msg.update(action="calibration_preview", revision="meter", binding_revision="source",
                        values={"DAY_2_ZONE": "1030", "NIGHT_2_ZONE": "1012"})
        await self.invoke()
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(set(result), {"confirmation", "change"})
        principal = self.manager.prepare_calibration.call_args.args[1]
        self.assertIn("profile-a", principal)
        self.manager.confirm.assert_not_awaited()
        self.msg.update(action="calibration_save", confirmation="local", contemporaneous=True)
        await self.invoke()
        call = self.account_coord.energy.save.call_args
        self.assertEqual(call.args[:3], ("100001", principal, "local"))
        self.assertTrue(call.kwargs["contemporaneous"])
        self.manager.confirm.assert_not_awaited()
        self.connection.user.permissions.check_entity.return_value = False
        self.account_coord.energy.save.reset_mock()
        await self.invoke()
        self.account_coord.energy.save.assert_not_awaited()

    async def asyncSetUp(self):
        await submission_tests.SubmissionAccessTests.asyncSetUp(self)
        self.msg.update(
            type="dtek_monitor/bot_account",
            telegram_user_id=123,
            telegram_bot_id="777",
            profile_id="profile-a",
        )

    async def invoke(self):
        with (
            patch.object(submission_api.er, "async_get", return_value=self.registry),
            patch.object(
                submission_api.er,
                "async_entries_for_config_entry",
                return_value=[self.entity],
            ),
        ):
            await api.websocket_bot_account.__wrapped__(
                self.hass, self.connection, self.msg
            )

    async def test_existing_admin_and_entity_permissions_still_required(self):
        self.connection.user.is_admin = False
        await self.invoke()
        self.manager.confirm.assert_not_awaited()
        self.assertEqual(self.connection.send_error.call_args.args[1], "unauthorized")

    async def test_user_and_profile_are_part_of_confirmation_principal(self):
        await self.invoke()
        first = self.manager.confirm.call_args.args[1]
        self.msg["telegram_user_id"] = 456
        await self.invoke()
        second = self.manager.confirm.call_args.args[1]
        self.assertNotEqual(first, second)
        self.msg["profile_id"] = "profile-b"
        await self.invoke()
        self.assertNotEqual(second, self.manager.confirm.call_args.args[1])
        self.assertEqual(self.manager.confirm.call_args.args[0], "100001")
        self.assertEqual(self.manager.confirm.call_args.args[2], "draft")

    async def test_missing_telegram_identity_cannot_submit(self):
        del self.msg["telegram_user_id"]
        await self.invoke()
        self.manager.confirm.assert_not_awaited()

    async def test_deselection_during_operation_is_checked_again(self):
        async def operation(number, principal, token, authorize):
            self.entry.data = {**self.entry.data, "accounts": {}}
            authorize()

        self.manager.confirm.side_effect = operation
        await self.invoke()
        self.connection.send_result.assert_not_called()

    async def test_private_upstream_errors_are_not_returned(self):
        self.manager.confirm.side_effect = api.AccountError("PRIVATE_TOKEN")
        await self.invoke()
        self.assertNotIn("PRIVATE_TOKEN", str(self.connection.send_error.call_args))

    async def test_service_compatibility_error_does_not_require_new_login(self):
        self.msg["action"] = "context"
        self.manager.context.side_effect = api.AccountAPIChanged("meter_readings", "authorization_rejected")
        await self.invoke()
        self.assertEqual(self.connection.send_error.call_args.args[1], "api_changed")
        self.entry.async_start_reauth.assert_not_called()

    async def test_readback_reads_history_without_repeating_submission(self):
        self.msg["action"] = "readback"
        self.manager.last_attempt = AsyncMock(return_value=None)
        self.account_coord.history.get = AsyncMock(
            return_value={"year": 2026, "fetched_at": "2026-10-19T12:00:00+00:00", "readings": [
                {"date_time": "2026-10-18T00:00:00+03:00", "energy": "ACTIVE", "zone": "GENERAL", "value": "1025", "status": "active"}
            ]}
        )
        await self.invoke()
        self.manager.confirm.assert_not_awaited()
        self.account_coord.history.get.assert_awaited_once()
        self.assertEqual(
            self.connection.send_result.call_args.args[1]["status"], "no_attempt"
        )
        self.assertEqual(self.connection.send_result.call_args.args[1]["latest"][0]["value"], "1025")

    async def test_invalid_attempt_does_not_hide_official_history(self):
        self.msg["action"] = "readback"
        self.manager.last_attempt = AsyncMock(return_value={"at": "bad"})
        self.account_coord.history.get = AsyncMock(return_value={"year": 2026, "fetched_at": "2026-10-19T12:00:00+00:00", "readings": []})
        await self.invoke()
        self.assertEqual(self.connection.send_result.call_args.args[1]["status"], "invalid_attempt")

    async def test_history_filter_applies_before_pagination_and_never_changes_readback(self):
        self.msg["action"] = "readback"
        self.manager.last_attempt = AsyncMock(return_value=None)
        rows = [{"energy": "ACTIVE", "status": "inactive", "value": str(i)} for i in range(8)]
        rows += [{"energy": "ACTIVE", "status": status, "value": "120"} for status in ("active", "blocked", "unknown")]
        data = {"year": 2026, "fetched_at": "2026-10-20T12:00:00+00:00", "readings": rows}
        self.account_coord.history.get = AsyncMock(return_value=data)
        with patch.object(api, "match_readback", return_value={"status": "no_attempt"}) as match:
            await self.invoke()
        self.assertIs(match.call_args.args[1], data)
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual([r["status"] for r in result["latest"]], ["active", "blocked", "unknown"])
        self.assertEqual(result["history_view"]["inactive_count"], 8)
        self.msg.update(action="history", include_inactive=True, history_offset=6)
        await self.invoke()
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(len(result["latest"]), 5)
        self.assertEqual(result["history_view"]["offset"], 6)
        self.assertTrue(result["history_view"]["include_inactive"])
        self.manager.confirm.assert_not_awaited()
        self.assertEqual(len(data["readings"]), 11)

    async def test_history_reads_previous_year_when_current_year_is_empty(self):
        self.msg["action"] = "history"
        self.manager.last_attempt = AsyncMock(return_value=None)
        self.account_coord.history.get = AsyncMock(side_effect=[
            {"year": 2026, "fetched_at": "2026-01-01T12:00:00+00:00", "readings": []},
            {"year": 2025, "fetched_at": "2026-01-01T12:00:01+00:00", "readings": [
                {"date_time": "2025-12-31T00:00:00+02:00", "energy": "ACTIVE", "zone": "GENERAL", "value": "1025"}
            ]},
        ])
        await self.invoke()
        result = self.connection.send_result.call_args.args[1]
        self.assertEqual(result["latest"][0]["value"], "1025")
        self.assertEqual(self.account_coord.history.get.await_count, 2)
        self.assertIsNone(result["attempt"])
        self.manager.context.assert_not_awaited()
        self.manager.confirm.assert_not_awaited()

    async def test_history_failure_never_returns_empty_records(self):
        self.msg["action"] = "history"
        self.manager.last_attempt = AsyncMock(return_value=None)
        self.account_coord.history.get = AsyncMock(side_effect=api.AccountError("private upstream"))
        await self.invoke()
        self.connection.send_result.assert_not_called()
        self.assertEqual(self.connection.send_error.call_args.args[1], "unavailable")

    async def test_history_rechecks_access_after_fetch(self):
        self.msg["action"] = "history"
        self.manager.last_attempt = AsyncMock(return_value=None)
        async def revoke(*args, **kwargs):
            self.entry.data = {**self.entry.data, "accounts": {}}
            return {"fetched_at": "2026-10-19T12:00:00+00:00", "readings": []}
        self.account_coord.history.get = AsyncMock(side_effect=revoke)
        await self.invoke()
        self.connection.send_result.assert_not_called()


@unittest.skipUnless(HAS_HA, "Requires Home Assistant")
class BotSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.entry = SimpleNamespace(data={"accounts": {"100001": "Private apartment"}})
        self.connection = SimpleNamespace(
            user=SimpleNamespace(
                permissions=SimpleNamespace(check_entity=lambda *args: True)
            )
        )
        self.coordinator = SimpleNamespace(
            address_success=True,
            address_data={
                "group_labels_visible": True,
                "schedule_groups": ["GPV3.1", "GPV5.1"],
            },
            notifications_ready=True,
            snapshot=SimpleNamespace(snapshot_id="rev"),
            snapshot_attributes={"schedule_coverage": []},
            schedule=SimpleNamespace(coverage=[]),
            address=SimpleNamespace(provider_id="dtek_oem", identity="house"),
        )
        self.registry = SimpleNamespace()

    def snapshot(self, groups=("GPV3.1",), status="current"):
        cabinet = SimpleNamespace(status=status, groups=groups)
        with (
            patch.object(
                api,
                "selection",
                return_value=(None, self.coordinator, ["GPV5.1"], "selected"),
            ),
            patch.object(api, "cabinet_groups", return_value=cabinet),
        ):
            return api.account_snapshot(None, self.connection, self.entry, "100001")

    def test_manual_and_building_group_do_not_override_cabinet(self):
        result = self.snapshot()
        self.assertEqual(result["groups"], ["GPV3.1"])
        self.assertEqual(result["attributes"]["selection_source"], "cabinet")

    def test_hidden_public_labels_do_not_block_verified_cabinet_groups(self):
        self.coordinator.address.provider_id = "dtek_kem"
        self.coordinator.address_data.update(
            group_labels_visible=False, schedule_groups=["GPV57.1", "GPV58.1"],
        )
        result = self.snapshot(("GPV57.1",))
        self.assertEqual(result["groups"], ["GPV57.1"])
        self.assertEqual(result["group_status"], "current")
        self.assertTrue(result["attributes"]["schedule_notifications_ready"])
        self.assertFalse(self.coordinator.address_data["group_labels_visible"])
        self.assertTrue(result["attributes"]["group_labels_visible"])  # Older bots still show cabinet IDs.
        self.assertFalse(result["attributes"]["source_group_labels_visible"])
        for status in ("expired", "unavailable", "pending", "empty", "disabled"):
            result = self.snapshot(("GPV57.1",), status)
            self.assertEqual(result["groups"], [])
            self.assertFalse(result["attributes"]["schedule_notifications_ready"])
        result = self.snapshot(("GPV59.1",))
        self.assertEqual(result["group_status"], "cabinet_group_mismatch")
        self.assertFalse(result["attributes"]["schedule_notifications_ready"])
        self.coordinator.address_success = False
        self.assertFalse(self.snapshot(("GPV57.1",))["attributes"]["schedule_notifications_ready"])

    def test_unavailable_expired_or_unsupported_never_falls_back(self):
        for status in (
            "unavailable",
            "expired",
            "unsupported",
            "pending",
            "api_changed",
        ):
            with self.subTest(status=status):
                result = self.snapshot(status=status)
                self.assertEqual(result["groups"], [])
                self.assertFalse(result["attributes"]["schedule_notifications_ready"])

    def test_multiple_cabinet_groups_preserved_and_order_does_not_change_revision(self):
        a = self.snapshot(("GPV5.1", "GPV3.1"))
        b = self.snapshot(("GPV3.1", "GPV5.1"))
        self.assertEqual(a["groups"], ["GPV3.1", "GPV5.1"])
        self.assertEqual(
            a["attributes"]["schedule_snapshot_id"],
            b["attributes"]["schedule_snapshot_id"],
        )
        self.assertNotEqual(
            a["attributes"]["schedule_snapshot_id"],
            self.snapshot()["attributes"]["schedule_snapshot_id"],
        )

    def test_partial_match_keeps_only_verified_groups_and_stable_notification_revision(self):
        now = datetime.now(timezone.utc)
        self.coordinator.schedule.coverage = [
            SimpleNamespace(group_id="GPV3.1", kind=kind, start=now - timedelta(days=1), end=now + timedelta(days=1))
            for kind in ("outage", "possible")
        ]
        self.coordinator.get_events_for_range = Mock(return_value=[
            SimpleNamespace(start=now, end=now + timedelta(hours=1), summary="Verified outage", description="group=GPV3.1")
        ])
        baseline = self.snapshot()
        self.coordinator.address_data["group_labels_visible"] = False
        result = self.snapshot(("GPV4.1", "GPV3.1"))
        self.assertEqual(result["group_status"], "partial")
        self.assertEqual(result["groups"], ["GPV3.1"])
        attrs = result["attributes"]
        self.assertTrue(attrs["schedule_notifications_ready"])
        self.assertEqual(attrs["cabinet_groups"], ["GPV3.1", "GPV4.1"])
        self.assertEqual(attrs["verified_cabinet_groups"], ["GPV3.1"])
        self.assertEqual(attrs["unverified_cabinet_groups"], ["GPV4.1"])
        self.assertEqual(attrs["schedule_snapshot_id"], baseline["attributes"]["schedule_snapshot_id"])
        self.assertTrue(result["calendars"]["outage"]["available"])
        self.assertEqual(len(result["calendars"]["outage"]["events"]), 1)
        for call in self.coordinator.get_events_for_range.call_args_list:
            self.assertEqual(call.args[2], ["GPV3.1"])
        self.assertEqual(self.coordinator.address_data["schedule_groups"], ["GPV3.1", "GPV5.1"])
        for status in ("expired", "unavailable", "disabled", "pending"):
            stale = self.snapshot(("GPV3.1", "GPV4.1"), status)
            self.assertFalse(stale["attributes"]["schedule_notifications_ready"])
            self.assertEqual(stale["attributes"]["unverified_cabinet_groups"], [])
            self.assertEqual(stale["groups"], [])
        self.coordinator.address_success = False
        unavailable = self.snapshot(("GPV3.1", "GPV4.1"))
        self.assertEqual(unavailable["groups"], [])
        self.assertEqual(unavailable["attributes"]["unverified_cabinet_groups"], [])
        self.coordinator.address_success = True
        self.assertEqual(self.snapshot()["group_status"], "current")

    def test_conflict_and_missing_publication_block_calendar(self):
        result = self.snapshot(("GPV9.1",))
        self.assertEqual(result["group_status"], "cabinet_group_mismatch")
        self.assertEqual(result["groups"], [])
        self.coordinator.notifications_ready = False
        result = self.snapshot()
        self.assertEqual(result["groups"], ["GPV3.1"])
        self.assertFalse(result["calendars"]["outage"]["available"])
        self.assertFalse(result["attributes"]["schedule_notifications_ready"])

    def test_linked_building_permissions_are_enforced(self):
        address = SimpleNamespace(entry_id="house")
        entity = SimpleNamespace(
            platform="dtek_monitor",
            unique_id="unique",
            disabled_by=None,
            entity_id="calendar.private_schedule",
        )
        self.connection.user.permissions.check_entity = lambda *args: False
        with (
            patch.object(
                api,
                "selection",
                return_value=(address, self.coordinator, [], "selected"),
            ),
            patch.object(
                api,
                "cabinet_groups",
                return_value=SimpleNamespace(groups=["GPV3.1"], status="current"),
            ),
            patch.object(api.er, "async_get", return_value=self.registry),
            patch.object(
                api.er, "async_entries_for_config_entry", return_value=[entity]
            ),
            patch.object(api, "build_entity_unique_id", return_value="unique"),
        ):
            with self.assertRaises(api.SubmissionError) as raised:
                api.account_snapshot(None, self.connection, self.entry, "100001")
        self.assertEqual(raised.exception.code, "unauthorized")
