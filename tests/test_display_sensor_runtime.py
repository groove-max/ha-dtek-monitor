"""Exercise optional display entities with Home Assistant and changing links."""

import unittest

import test_ha_runtime as runtime
import test_account_schedule as account_tests
from component_loader import load_component_module

if runtime.HAS_HA:
    mod = load_component_module('display_sensor')


@unittest.skipUnless(runtime.HAS_HA, 'Requires Home Assistant')
class DisplaySensorRuntimeTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = account_tests.AccountScheduleTests.asyncSetUp
    link = account_tests.AccountScheduleTests.link

    async def test_address_sensor_opt_in_and_clear_on_error(self):
        entity=mod.DTEKDisplaySensor(self.coord,self.entry)
        self.assertFalse(entity.entity_registry_enabled_default)
        self.assertIn('days',entity._unrecorded_attributes)
        self.assertEqual(entity.native_value,'ready')
        self.assertTrue(entity.extra_state_attributes['days'])
        self.coord.schedule_error='offline'
        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value,'error')
        self.assertEqual(entity.extra_state_attributes['days'],[])

    async def test_account_sensor_keeps_all_groups_and_reacts_to_removed_link(self):
        self.link(['GPV3.1','GPV5.1'])
        entity=mod.AccountDisplaySensor(self.personal,'100001');entity.hass=self.hass
        self.assertFalse(entity.entity_registry_enabled_default)
        self.assertEqual(entity.extra_state_attributes['selected_groups'],['GPV3.1','GPV5.1'])
        self.assertNotIn('building',entity.extra_state_attributes)
        self.personal.options.clear()
        self.assertEqual(entity.native_value,'missing')
        self.assertEqual(entity.extra_state_attributes['selected_groups'],[])
        self.assertEqual(entity.extra_state_attributes['days'],[])

    async def test_invalid_selection_is_not_retained_as_highlight(self):
        self.link(['GPV9.9'])
        entity=mod.AccountDisplaySensor(self.personal,'100001');entity.hass=self.hass
        self.assertEqual(entity.extra_state_attributes['selection_status'],'group_unavailable')
        self.assertEqual(entity.extra_state_attributes['selected_groups'],[])
        self.assertEqual(entity.extra_state_attributes['event']['kind'],'selection_required')


@unittest.skipUnless(runtime.HAS_HA, 'Requires Home Assistant')
class DisplayGridHelperTests(unittest.IsolatedAsyncioTestCase):
    async def test_grid_helper_rejects_stale_missing_invalid_and_restored_measurements(self):
        import tempfile
        from pathlib import Path
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch
        import yaml
        from homeassistant.core import HomeAssistant
        from homeassistant.helpers.template import Template

        with tempfile.TemporaryDirectory() as root:
            hass = HomeAssistant(root)
            data = yaml.safe_load((Path(__file__).resolve().parents[1] / 'examples/geekmagic/power.yaml').read_text())['template'][0]['binary_sensor'][0]
            availability = Template(data['availability'], hass)
            present = Template(data['state'], hass)
            entity = 'sensor.grid_frequency'
            self.assertFalse(availability.async_render())
            for value, valid, on in [('50',True,True),('0',True,False),('unavailable',False,False),('unknown',False,False),('nan',False,False),('-1',False,False)]:
                hass.states.async_set(entity, value)
                self.assertEqual(availability.async_render(), valid, value)
                if valid: self.assertEqual(present.async_render(), on, value)
            hass.states.async_set(entity, '50', {'restored': True})
            self.assertFalse(availability.async_render())
            hass.states.async_set(entity, '50', {})
            stamp = hass.states.get(entity).last_reported
            with patch('homeassistant.util.dt.now', return_value=stamp+timedelta(seconds=181)):
                self.assertFalse(availability.async_render())
            with patch('homeassistant.util.dt.now', return_value=stamp-timedelta(seconds=6)):
                self.assertFalse(availability.async_render())
