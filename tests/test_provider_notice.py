"""Announcements never replace published coverage or measured power."""
import asyncio
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from component_loader import load_component_module

mod = load_component_module('provider_notice')
NOW = datetime(2026, 11, 8, 12, tzinfo=mod.KYIV_TZ)
URL = 'https://www.dtek-dnem.com.ua/ua/shutdowns'
MIXED = ('У Дніпрі діють екстрені відключення світла.\n'
         'У Павлоградському, Самарівському, Камʼянському та Дніпровському районах — аварійні відключення. Тут графіки не діють.\n'
         'Для решти області продовжуються стабілізаційні відключення.')
DISTRICT_NOTICE = ('У Павлоградському, частині Самарського та Синельниківського районів - аварійні відключення. '
                   'Тут графіки не діють. Для решти області стабілізаційні відключення.')


def html(text):
    return '<div id="modal-attention"><div class="m-attention__text">'+text+'</div></div>'


def attrs(text, city='Дніпро', **kw):
    return mod.ProviderNotice(text, NOW, URL).attributes(city, NOW, **kw)


class NoticeTests(unittest.TestCase):
    def test_extract_exact_container_inline_words_entities_and_line_breaks(self):
        page='<div class="faq">Графіки не діють</div>'+html('<p>У <span>Дні</span><b>прі</b> діють екстрені відключення.</p><p>Графіки<br>не діють &amp; &lt;x&gt;</p><script>ignore</script>')
        self.assertEqual(mod.extract_announcement(page), 'У Дніпрі діють екстрені відключення.\nГрафіки\nне діють & <x>')
        self.assertEqual(mod.extract_announcement(html('')), '')
        for page in ('<h1>Checking browser</h1>', '<div class="m-attention__text">x</div>', html('x')*2, html('a'*8001)):
            with self.assertRaises(ValueError): mod.extract_announcement(page)

    def test_mixed_dnem_does_not_suspend_whole_oblast(self):
        a=attrs(MIXED)
        self.assertEqual(a['provider_notice_state'], 'mixed')
        self.assertIs(a['schedule_applies'], False)
        self.assertEqual(a['provider_notice_scope'], 'city')
        for city in ('м. Павлоград', 'Самар', 'Камʼянське', 'Новодніпровське', ''):
            with self.subTest(city=city): self.assertIsNone(attrs(MIXED, city)['schedule_applies'])

    def test_issue_13_district_notice_is_mixed_without_guessing_address_applicability(self):
        now=NOW.replace(day=9)
        notice=mod.ProviderNotice(DISTRICT_NOTICE,now,URL)
        for city in ('Дніпро','м. Дніпро','Павлоград','Самар','Синельникове',''):
            for offset in (0,1):
                with self.subTest(city=city,day_offset=offset):
                    a=notice.attributes(city,now,day_offset=offset)
                    self.assertEqual(a['provider_notice_state'],'mixed')
                    self.assertEqual(a['provider_notice_scope'],'unverified')
                    self.assertIsNone(a['schedule_applies'])
                    self.assertEqual(a['provider_notice_text'],DISTRICT_NOTICE)
                    self.assertEqual(a['provider_notice_source'],URL)

    def test_short_stabilization_statements_classify_the_notice_only(self):
        for text in (
            'Стабілізаційні відключення.',
            'Для решти області стабілізаційні відключення.',
            'Для решти регіону — стабілізаційні відключення світла.',
            'Для решти області: стабілізаційні відключення електроенергії.',
            'На решті території області – стабілізаційні відключення електропостачання.',
            'Для  решти\u00a0області  стабілізаційні   відключення!',
        ):
            with self.subTest(text=text):
                self.assertEqual(attrs(text)['provider_notice_state'],'stabilization')
                self.assertIsNone(attrs(text)['schedule_applies'])
                self.assertEqual(attrs('У Дніпрі діють екстрені відключення. '+text)['provider_notice_state'],'mixed')
                # A summary-only classification must not supply an all-clear.
                self.assertIs(attrs('У Дніпрі діють екстрені відключення. '+text)['schedule_applies'],False)

    def test_short_stabilization_advice_negation_and_hypotheses_are_not_declarations(self):
        for text in (
            'Для решти області можливі стабілізаційні відключення.',
            'Для решти області очікуються стабілізаційні відключення.',
            'Для решти області стабілізаційні відключення скасовано.',
            'Для решти області — не стабілізаційні відключення.',
            'Якщо будуть стабілізаційні відключення.',
            'Будь ласка, враховуйте стабілізаційні відключення.',
            'Стабілізаційні відключення?',
            'Вчора для решти області стабілізаційні відключення.',
        ):
            with self.subTest(text=text):
                self.assertEqual(attrs(text)['provider_notice_state'],'notice')
                self.assertIsNone(attrs(text)['schedule_applies'])
                self.assertEqual(attrs('У Дніпрі діють екстрені відключення. '+text)['provider_notice_state'],'emergency')

    def test_mixed_short_notice_does_not_override_expiry_or_failure(self):
        notice=mod.ProviderNotice(DISTRICT_NOTICE,NOW,URL)
        for value,now in ((notice,NOW+timedelta(minutes=10)), (replace(notice,error='request_failed'),NOW)):
            a=value.attributes('Дніпро',now)
            self.assertEqual(a['provider_notice_state'],'unavailable')
            self.assertIsNone(a['schedule_applies'])

    def test_district_notice_keeps_published_schedule_and_derived_forecast(self):
        from test_schedule_events import ScheduleEventsTests
        case=ScheduleEventsTests();case.setUp();case.set_intervals(case.interval(23,24))
        case.coord.address=SimpleNamespace(city='Дніпро')
        case.coord.provider_notice=mod.ProviderNotice(DISTRICT_NOTICE,case.now,URL)
        self.assertEqual(case.coord.provider_notice.state,'mixed')
        self.assertEqual(case.event().status,'scheduled')
        self.assertEqual(case.coord.schedule_state,'current')
        self.assertEqual(len(case.coord.schedule.intervals),1)

    def test_precaution_is_not_emergency_and_stable_oem_full_day_is_supported(self):
        stable='За наказом НЕК Укренерго сьогодні з 00:00 до 24:00 діють стабілізаційні відключення електроенергії.'
        precaution='Будь ласка, розумно споживайте електроенергію — це допоможе уникнути екстрених відключень.'
        a=attrs(stable+'\n'+precaution, 'м. Одеса')
        self.assertEqual(a['provider_notice_state'], 'stabilization')
        self.assertIs(a['schedule_applies'], True)
        local='Через ворожу атаку фіксуються відключення світла в частині Подільського району області.'
        self.assertIsNone(attrs(stable+'\n'+precaution+'\n'+local, 'Одеса')['schedule_applies'])

    def test_negations_future_and_historic_text_do_not_suspend(self):
        for text in ('Можливі екстрені відключення.', 'Екстрені відключення скасовано.',
                     'Вчора діяли екстрені відключення.', 'Не діють екстрені відключення.',
                     'Завтра діють екстрені відключення.', 'За потреби можливі екстрені відключення.'):
            with self.subTest(text=text): self.assertIsNot(attrs(text)['schedule_applies'], False)

    def test_explicit_dates_and_partial_windows_are_not_guessed(self):
        for date in ('08.11', '8.11', '08.11.2026'):
            self.assertIs(attrs(f'{date} діють стабілізаційні відключення.')['schedule_applies'], True)
        for date in ('07.11', '08.11.2025', '08.11–09.11'):
            self.assertIsNone(attrs(f'{date} діють екстрені відключення.')['schedule_applies'])
        self.assertIsNone(attrs('Сьогодні з 16:00 до 20:00 діють екстрені відключення.')['schedule_applies'])
        self.assertIs(attrs('Завтра діють екстрені відключення.', day_offset=1)['schedule_applies'], False)
        self.assertIsNone(attrs('Діють екстрені відключення.', day_offset=1)['schedule_applies'])

    def test_detached_date_or_exception_does_not_become_todays_regionwide_warning(self):
        for text in ('Завтра.\nДіють екстрені відключення.',
                     '09.11.2026\nДіють екстрені відключення.',
                     'У всій області діють екстрені відключення.\nВиняток: місто Одеса.'):
            with self.subTest(text=text):
                self.assertIsNone(attrs(text, 'Одеса')['schedule_applies'])

    def test_unqualified_or_whole_operator_and_exact_city(self):
        for text in ('Діють екстрені відключення.', 'Графіки не діють.', 'У всій області діють аварійні відключення.', 'У м. Дніпрі діють екстрені відключення.'):
            with self.subTest(text=text): self.assertIs(attrs(text)['schedule_applies'], False)
        self.assertIsNone(attrs('У Кривому Розі діють екстрені відключення.')['schedule_applies'])
        self.assertIsNone(attrs('')['schedule_applies'])
        self.assertEqual(attrs('')['provider_notice_state'], 'none')

    def test_expired_failed_and_previous_day_do_not_grant_clearance(self):
        notice=mod.ProviderNotice('', NOW, URL)
        for value, now in ((notice, NOW+timedelta(minutes=10)), (replace(notice,error='request_failed'),NOW), (replace(notice,checked_at=NOW+timedelta(seconds=10)),NOW), (replace(notice,checked_at=NOW.replace(hour=23,minute=59)),(NOW+timedelta(days=1)).replace(hour=0,minute=1))):
            a=value.attributes('Дніпро',now)
            self.assertIsNone(a['schedule_applies'])
            self.assertEqual(a['provider_notice_state'],'unavailable')

    def test_contract_includes_tomorrow_and_finite_validity(self):
        coord=SimpleNamespace(address=SimpleNamespace(city='Дніпро'),provider_notice=mod.ProviderNotice('',NOW,URL))
        a=mod.notice_attributes(coord,NOW)
        self.assertEqual(a['schedule_applicability_days'], {'2026-11-08':None,'2026-11-09':None})
        self.assertEqual(datetime.fromisoformat(a['provider_notice_valid_until']), NOW+timedelta(minutes=10))

    def test_published_schedule_remains_visible_but_event_forecast_is_suspended(self):
        from test_schedule_events import ScheduleEventsTests
        case=ScheduleEventsTests();case.setUp();case.set_intervals(case.interval(23,24))
        case.coord.address=SimpleNamespace(city='Дніпро')
        case.coord.provider_notice=mod.ProviderNotice('Діють екстрені відключення.',case.now,URL)
        self.assertEqual(case.event().status,'not_applicable')
        self.assertEqual(case.coord.schedule_state,'current')
        self.assertEqual(len(case.coord.schedule.intervals),1)
        case.coord.provider_notice=replace(case.coord.provider_notice,text='Неоднозначне оголошення')
        self.assertEqual(case.event().status,'scheduled')
        case.coord.provider_notice=replace(case.coord.provider_notice,error='notice_request_failed')
        self.assertEqual(case.event().status,'scheduled')
        case.coord.provider_notice=replace(case.coord.provider_notice,error=None,checked_at=case.now-timedelta(minutes=10))
        self.assertEqual(case.event().status,'scheduled')
        case.coord.provider_notice=replace(case.coord.provider_notice,text='')
        self.assertEqual(case.event().status,'scheduled')


    def test_exceptions_and_district_notices_never_suspend_unmatched_address(self):
        for text in ('У всій області діють екстрені відключення, крім Одеси.',
                     'В окремих районах діють екстрені відключення.',
                     'Через ворожу атаку відсутнє світло в частині Подільського району.'):
            with self.subTest(text=text):
                result=attrs(text, 'Одеса')
                self.assertIsNone(result['schedule_applies'])
                self.assertEqual(result['provider_notice_text'], text)
                self.assertEqual(result['provider_notice_interpretation'], 'text_rules')


class CacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_single_flight_bounded_polling_failure_and_recovery(self):
        tick=[0];cache=mod.NoticeCache(URL,clock=lambda:tick[0])
        async def refresh():
            await asyncio.sleep(0)
            cache.capture(html('Діють екстрені відключення.'))
        fetch=AsyncMock(side_effect=refresh)
        values=await asyncio.gather(*(cache.get(fetch) for _ in range(8)))
        self.assertEqual(fetch.await_count,1)
        self.assertTrue(all(v is values[0] for v in values))
        tick[0]=301;fetch.side_effect=TimeoutError()
        failed=await cache.get(fetch)
        self.assertEqual(failed.text,values[0].text)
        self.assertEqual(failed.checked_at,values[0].checked_at)
        self.assertEqual(failed.error,'notice_request_failed')
        await cache.get(fetch);self.assertEqual(fetch.await_count,2)
        tick[0]=362;fetch.side_effect=refresh
        self.assertIsNone((await cache.get(fetch)).error)

    async def test_changed_markup_is_unavailable_and_does_not_clear_previous_alarm(self):
        cache=mod.NoticeCache(URL)
        cache.capture('<html>new structure</html>')
        self.assertEqual(cache.value.error,'unsupported_notice_format')
        self.assertIsNone(cache.value.attributes('Дніпро')['schedule_applies'])

    async def test_clients_share_notice_poll_across_addresses_and_reload(self):
        client=load_component_module('dtek_client')
        gate=load_component_module('public_requests').PublicRequestGate()
        first=client.DTEKClient(request_gate=gate)
        second=client.DTEKClient(request_gate=gate)
        page='<meta name="csrf-token" content="fictional-csrf">'+html('Діють екстрені відключення.')
        first._load_shutdowns_page=AsyncMock(return_value=page)
        second._load_shutdowns_page=AsyncMock(side_effect=AssertionError('extra GET'))
        try:
            a,b=await asyncio.gather(first.get_provider_notice(),second.get_provider_notice())
            self.assertIs(a,b)
            self.assertEqual(a.state,'emergency')
            first._load_shutdowns_page.assert_awaited_once()
            second._load_shutdowns_page.assert_not_awaited()
            self.assertIs(first.notice_cache,second.notice_cache)
        finally:
            await first.close()
            await second.close()

    async def test_cancellation_propagates(self):
        cache=mod.NoticeCache(URL)
        with self.assertRaises(asyncio.CancelledError):
            await cache.get(AsyncMock(side_effect=asyncio.CancelledError()))
