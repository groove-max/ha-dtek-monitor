"""Real HA entities expire notice authorization without network IO."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from component_loader import load_component_module
import test_ha_runtime as runtime
import test_schedule_events_runtime as events_runtime

mod=load_component_module('provider_notice')


@unittest.skipUnless(runtime.HAS_HA,'Requires real Home Assistant')
class NoticeEntityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await runtime.RuntimeTests.asyncSetUp(self)
        await runtime.load_registries(self.hass)

    add_entity=events_runtime.ScheduleEventsRuntimeTests.add_entity

    async def test_independent_notice_entity_group_contract_and_local_expiry_timer(self):
        now=datetime.now(timezone.utc)
        self.coord.provider_notice=mod.ProviderNotice('Діють екстрені відключення.',now,'https://www.dtek-oem.com.ua/ua/shutdowns')
        self.coord.address_success=False
        entity=await self.add_entity(runtime.sensors.DTEKProviderNoticeSensor(self.coord,self.entry),'notice')
        self.assertEqual(self.hass.states.get(entity.entity_id).state,'emergency')
        self.assertIs(self.hass.states.get(entity.entity_id).attributes['schedule_applies'],False)
        self.assertEqual(entity.unique_id.rsplit('_',1)[-1],'notice')
        clock=Mock(wraps=datetime);clock.now.return_value=now
        with patch.object(runtime.coordinator,'dt',SimpleNamespace(datetime=clock,timezone=timezone)), patch.object(runtime.coordinator,'async_track_point_in_utc_time') as timer:
            self.coord.async_start_schedule_clock()
            self.assertLessEqual(timer.call_args.args[2],now+timedelta(minutes=10))
        clock.now.return_value=now+timedelta(minutes=10)
        with patch.object(mod,'datetime',clock):
            self.coord._notify_diagnostics()
            self.assertEqual(self.hass.states.get(entity.entity_id).state,'unavailable')
            self.assertIsNone(entity.extra_state_attributes['schedule_applies'])
        self.coord.async_stop_schedule_clock()
