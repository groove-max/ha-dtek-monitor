"""Read access to a status alone cannot unlock calendars or another account."""

import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import test_ha_runtime as runtime
from component_loader import load_component_module
from test_schedule_grid import overview_fixture

if runtime.HAS_HA:
    api = load_component_module("schedule_grid_api")
    from homeassistant.config_entries import ConfigEntryState


@unittest.skipUnless(runtime.HAS_HA, "Requires Home Assistant")
class GridAPITests(unittest.TestCase):
    def setUp(self):
        c, _, _, _ = overview_fixture()
        self.entry = SimpleNamespace(
            domain="dtek_monitor",
            entry_id="entry",
            unique_id="building",
            state=ConfigEntryState.LOADED,
            data={},
            runtime_data=c,
        )
        self.entity = SimpleNamespace(
            entity_id="sensor.status",
            config_entry_id="entry",
            platform="dtek_monitor",
            disabled_by=None,
            unique_id="building_schedule_status",
        )
        self.entities = [
            self.entity,
            *[
                SimpleNamespace(
                    entity_id="calendar." + kind,
                    platform="dtek_monitor",
                    disabled_by=None,
                    unique_id="building_" + kind + "_schedule",
                )
                for kind in ("outage", "possible")
            ],
        ]
        self.hass = SimpleNamespace(
            config_entries=SimpleNamespace(
                async_get_entry=Mock(return_value=self.entry)
            )
        )
        self.connection = Mock()
        self.connection.user.permissions.check_entity.return_value = True

    def invoke(self):
        with (
            patch.object(
                api.er,
                "async_get",
                return_value=SimpleNamespace(async_get=Mock(return_value=self.entity)),
            ),
            patch.object(
                api.er, "async_entries_for_config_entry", return_value=self.entities
            ),
        ):
            api.websocket_grid(
                self.hass, self.connection, {"id": 1, "entity_id": "sensor.status"}
            )

    def test_requires_both_calendars_and_loaded_matching_integration(self):
        self.invoke()
        self.assertEqual(
            self.connection.send_result.call_args.args[1]["status"], "ready"
        )
        self.connection.reset_mock()
        self.connection.user.permissions.check_entity.side_effect = (
            lambda entity, policy: entity != "calendar.possible"
        )
        self.invoke()
        self.assertEqual(self.connection.send_error.call_args.args[1], "unauthorized")
        self.connection.send_result.assert_not_called()
        self.connection.user.permissions.check_entity.side_effect = None
        self.entity.platform = "another"
        self.invoke()
        self.assertEqual(self.connection.send_error.call_args.args[1], "not_available")

    def test_personal_selection_highlights_without_filtering_other_groups(self):
        self.entry.data = {"entry_kind": "account"}
        self.entity.unique_id = "account:hash:account_schedule_status:all"
        for e, key in zip(self.entities[1:], ("outage", "possible")):
            e.unique_id = "account:hash:account_" + key + "_schedule:all"
        with (
            patch.object(
                api,
                "resolve_readable_account",
                return_value=(self.entry, "fictional", self.entity),
            ),
            patch.object(
                api,
                "selection",
                return_value=(None, self.entry.runtime_data, ["GPV5.2"], "selected"),
            ),
        ):
            self.invoke()
        rows = self.connection.send_result.call_args.args[1]["days"][0]["rows"]
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["id"] for r in rows if r["selected"]], ["GPV5.2"])


@unittest.skipUnless(runtime.HAS_HA, "Requires Home Assistant")
class GridRefreshAPITests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        from unittest.mock import AsyncMock
        GridAPITests.setUp(self)
        self.entry.runtime_data.async_manual_refresh = AsyncMock()
        self.entry.runtime_data.schedule = overview_fixture()[1]
        self.entry.runtime_data.schedule_state = "current"
        self.entry.runtime_data.notifications_ready = True

    async def invoke(self):
        with (
            patch.object(api.er, "async_get", return_value=SimpleNamespace(async_get=Mock(return_value=self.entity))),
            patch.object(api.er, "async_entries_for_config_entry", return_value=self.entities),
        ):
            await api.websocket_refresh.__wrapped__(self.hass, self.connection, {"id": 1, "entity_id": "sensor.status"})

    async def test_read_only_user_cannot_trigger_network_refresh(self):
        self.connection.user.permissions.check_entity.side_effect = lambda entity, policy: policy == api.POLICY_READ
        await self.invoke()
        self.assertEqual(self.connection.send_error.call_args.args[1], "unauthorized")
        self.entry.runtime_data.async_manual_refresh.assert_not_awaited()

    async def test_success_still_requires_both_calendars(self):
        await self.invoke()
        self.entry.runtime_data.async_manual_refresh.assert_awaited_once()
        self.connection.send_result.assert_called_once()
        self.connection.reset_mock()
        self.connection.user.permissions.check_entity.side_effect = lambda entity, policy: entity != "calendar.possible"
        await self.invoke()
        self.assertEqual(self.connection.send_error.call_args.args[1], "unauthorized")
        self.assertEqual(self.entry.runtime_data.async_manual_refresh.await_count, 1)

    async def test_shared_cooldown_returns_safe_translated_seconds(self):
        from homeassistant.exceptions import ServiceValidationError
        self.entry.runtime_data.async_manual_refresh.side_effect = ServiceValidationError(
            translation_domain="dtek_monitor", translation_key="schedule_refresh_cooldown",
            translation_placeholders={"seconds": "120"},
        )
        await self.invoke()
        self.assertEqual(self.connection.send_error.call_args.args[1], "schedule_refresh_cooldown")
        self.assertEqual(self.connection.send_error.call_args.kwargs["translation_placeholders"], {"seconds": "120"})
        self.connection.send_result.assert_not_called()

    async def test_changed_binding_during_request_cannot_return_old_result(self):
        original = self.entry.runtime_data
        with patch.object(api, "resolve_grid", side_effect=[(original, (), None), (object(), (), None)]):
            await self.invoke()
        self.connection.send_result.assert_not_called()
        self.assertEqual(self.connection.send_error.call_args.args[1], "not_available")


@unittest.skipUnless(runtime.HAS_HA, "Requires Home Assistant")
class BuildingChoicesTests(unittest.TestCase):
    def setUp(self):
        GridAPITests.setUp(self)
        self.hass.config_entries.async_entries = Mock(return_value=[self.entry])
        for key, entity_id in (("power", "binary_sensor.renamed"), ("last_update", "sensor.renamed_timestamp")):
            self.entities.append(SimpleNamespace(
                unique_id="building_" + key, entity_id=entity_id,
                platform="dtek_monitor", disabled_by=None,
            ))

    def choices(self):
        self.connection.reset_mock()
        with (
            patch.object(api.er, "async_get", return_value=SimpleNamespace(async_get=Mock(return_value=self.entity))),
            patch.object(api.er, "async_entries_for_config_entry", return_value=self.entities),
        ):
            api.websocket_buildings(self.hass, self.connection, {"id": 5})
        return self.connection.send_result.call_args.args[1]

    def test_resolves_renamed_entities_and_uses_no_network_calls(self):
        result = self.choices()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status_entity"], "sensor.status")
        self.assertEqual(result[0]["entity"], "binary_sensor.renamed")
        self.assertEqual(result[0]["updated_entity"], "sensor.renamed_timestamp")
        self.assertIn(self.entry.runtime_data.address.house, result[0]["address"])
        self.assertTrue(result[0]["groups"])

    def test_permissions_and_disabled_calendars_filter_choices(self):
        self.connection.user.permissions.check_entity.side_effect = lambda entity, policy: entity != "calendar.possible"
        self.assertEqual(self.choices(), [])
        self.connection.user.permissions.check_entity.side_effect = lambda entity, policy: entity != "binary_sensor.renamed"
        self.assertNotIn("entity", self.choices()[0])
        self.entities[1].disabled_by = "user"
        self.assertEqual(self.choices(), [])

    def test_accounts_unloaded_and_unavailable_address_groups(self):
        self.entry.data = {"entry_kind": "account"}
        self.assertEqual(self.choices(), [])
        self.entry.data = {}
        self.entry.state = ConfigEntryState.SETUP_RETRY
        self.assertEqual(self.choices(), [])
        self.entry.state = ConfigEntryState.LOADED
        self.entry.runtime_data.address_success = False
        self.assertEqual(self.choices()[0]["groups"], [])
