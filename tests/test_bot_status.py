"""Native HA actions, private subscription ownership and delivery acknowledgements."""

import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import test_ha_runtime as runtime
from component_loader import load_component_module

if runtime.HAS_HA:
    api = load_component_module('bot_status')
    from homeassistant.core import Context
    from homeassistant.exceptions import HomeAssistantError, Unauthorized
    from homeassistant.helpers.service import async_get_all_descriptions


@unittest.skipUnless(runtime.HAS_HA, 'Requires Home Assistant runtime')
class StatusActionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await runtime.RuntimeTests.asyncSetUp(self)
        api.async_setup_status_actions(self.hass)
        self.bridge = self.hass.data[api.DATA_KEY]
        self.connection = SimpleNamespace(user=SimpleNamespace(is_admin=True), subscriptions={},
                                          send_result=Mock(), send_error=Mock(), send_event=Mock())
        self.subscribe()

    def subscribe(self, instance='addon', refresh=True, connection=None):
        api.websocket_subscribe(self.hass, connection or self.connection, {
            'id': 1, 'type': 'dtek_monitor/bot_status/subscribe', 'version': 1,
            'instance_id': instance,
            'profiles': [{'id': 'home', 'name': 'Fictional home', 'can_refresh': refresh}],
        })

    async def call(self, service='send_bot_status', profile='addon:home'):
        return await self.hass.services.async_call(
            'dtek_monitor', service, {'profile': profile}, blocking=True, return_response=True,
        )

    def reply(self, request_id, status='sent', connection=None):
        api.websocket_result(self.hass, connection or self.connection, {
            'id': 2, 'type': 'dtek_monitor/bot_status/result', 'instance_id': 'addon',
            'request_id': request_id, 'status': status, 'recipients': 2,
        })

    async def test_action_waits_for_actual_ack_and_returns_result(self):
        task = asyncio.create_task(self.call())
        await asyncio.sleep(.01)
        self.assertFalse(task.done())
        event = self.connection.send_event.call_args.args[1]
        self.assertEqual(event['operation'], 'send')
        self.assertTrue(event['silent'])
        self.assertNotIn('chat_id', event)
        self.reply(event['request_id'])
        result = await task
        self.assertEqual(result['status'], 'sent')
        self.assertEqual(result['recipients'], 2)
        self.assertEqual(self.bridge.clients['addon'].pending, {})

    async def test_another_connection_cannot_acknowledge(self):
        task = asyncio.create_task(self.call())
        await asyncio.sleep(.01)
        request = self.connection.send_event.call_args.args[1]['request_id']
        other = SimpleNamespace(user=SimpleNamespace(is_admin=True), send_error=Mock(), send_result=Mock())
        self.reply(request, connection=other)
        other.send_error.assert_called_once()
        self.assertFalse(task.done())
        self.reply(request)
        await task

    async def test_disconnection_raises_and_removes_selector_option(self):
        task = asyncio.create_task(self.call())
        await asyncio.sleep(.01)
        self.connection.subscriptions[1]()
        with self.assertRaises(HomeAssistantError):
            await task
        self.assertEqual(self.bridge.clients, {})
        with self.assertRaises(HomeAssistantError):
            await self.call()

    async def test_timeout_and_partial_delivery_are_errors_not_success(self):
        with patch.object(api, 'TIMEOUT', .01):
            with self.assertRaises(HomeAssistantError):
                await self.call()
        self.assertFalse(self.bridge.clients['addon'].pending)
        task = asyncio.create_task(self.call())
        await asyncio.sleep(.01)
        self.reply(self.connection.send_event.call_args.args[1]['request_id'], 'partial')
        with self.assertRaises(HomeAssistantError):
            await task

    async def test_disabled_pin_does_not_block_send_and_selector_filters_refresh(self):
        self.connection.subscriptions[1]()
        self.subscribe(refresh=False)
        with self.assertRaises(HomeAssistantError):
            await self.call('refresh_bot_status')
        schemas = await async_get_all_descriptions(self.hass)
        fields = schemas['dtek_monitor']['send_bot_status']['fields']
        self.assertEqual(fields['profile']['selector']['select']['options'][0]['value'], 'addon:home')
        self.assertEqual(schemas['dtek_monitor']['refresh_bot_status']['fields']['profile']['selector']['select']['options'], [])

    async def test_unknown_profile_cannot_broadcast_and_duplicate_instance_is_rejected(self):
        with self.assertRaises(HomeAssistantError):
            await self.call(profile='addon:someone_else')
        self.connection.send_event.assert_not_called()
        self.subscribe()
        self.assertEqual(self.connection.send_error.call_args.args[1], 'already_connected')

    async def test_subscription_requires_admin(self):
        self.connection.user.is_admin = False
        with self.assertRaises(Unauthorized):
            self.subscribe(instance='other')
        self.assertNotIn('other', self.bridge.clients)

    async def test_service_rejects_unknown_fields_instead_of_overriding_recipients(self):
        with self.assertRaises(Exception):
            await self.hass.services.async_call('dtek_monitor', 'send_bot_status',
                {'profile': 'addon:home', 'chat_id': 'foreign'}, blocking=True)
        self.connection.send_event.assert_not_called()

    async def test_non_admin_cannot_invoke_action(self):
        self.hass.auth = SimpleNamespace(async_get_user=AsyncMock(return_value=SimpleNamespace(is_admin=False)))
        with self.assertRaises(Unauthorized):
            await self.hass.services.async_call('dtek_monitor', 'send_bot_status',
                {'profile': 'addon:home'}, blocking=True, context=Context(user_id='viewer'))
        self.connection.send_event.assert_not_called()

    async def test_refresh_command_is_distinct_and_reports_updated(self):
        task = asyncio.create_task(self.call('refresh_bot_status'))
        await asyncio.sleep(.01)
        event = self.connection.send_event.call_args.args[1]
        self.assertEqual(event['operation'], 'refresh')
        self.reply(event['request_id'], 'updated')
        self.assertEqual((await task)['status'], 'updated')
