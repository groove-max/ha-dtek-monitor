"""External displays retain exact evidence, multiple groups and safe unknowns."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest

from component_loader import load_component_module
from test_schedule_grid import overview_fixture

mod = load_component_module('schedule_display')
contract = load_component_module('provider')
ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    c, home, _, _ = overview_fixture()
    c.notifications_ready = True
    c.schedule_state = 'current'
    c.schedule = c.overview
    day = home.fetched_at.astimezone(mod.KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return c, day


class DisplayTests(unittest.TestCase):
    def test_all_operator_rows_and_multiple_highlights_without_private_address(self):
        c, day = snapshot()
        c.address_data['schedule_groups'] = ['GPV3.1', 'GPV5.2']
        result = mod.display_data(c, ['GPV3.1', 'GPV5.2'], personal=True, now=day)
        rows = result['days'][0]['rows']
        self.assertEqual(len(result['days']), 1)
        self.assertEqual({r['id'] for r in rows}, {'GPV3.1', 'GPV4.1', 'GPV5.2'})
        self.assertEqual({r['id'] for r in rows if r['selected']}, {'GPV3.1', 'GPV5.2'})
        self.assertNotIn('address', result)
        self.assertNotIn('cells', rows[0])
        self.assertEqual({s['kind'] for s in next(r for r in rows if r['id']=='GPV4.1')['segments']}, {'unknown'})

    def test_exact_minutes_and_dst_day_lengths(self):
        for text, length in [('2026-03-29',1380),('2026-10-25',1500),('2026-11-04',1440)]:
            c, _ = snapshot()
            day = datetime.fromisoformat(text).replace(tzinfo=mod.KYIV_TZ)
            start = day.astimezone(timezone.utc)
            c.overview = replace(c.overview, intervals=(contract.Interval('GPV3.1','outage',start+timedelta(minutes=727),start+timedelta(minutes=742),'daily'),), coverage=(contract.Coverage('GPV3.1','outage',day,day+timedelta(days=1)),))
            result = mod.display_data(c, now=day)['days'][0]
            self.assertEqual(result['minutes'], length)
            self.assertEqual(result['ticks'][-1], {'label':'24','minute':length})
            row = next(r for r in result['rows'] if r['id']=='GPV3.1')
            self.assertIn({'start':727,'end':742,'kind':'outage'}, row['segments'])

    def test_failures_remove_old_grid_and_countdown(self):
        for field in ('address_error','schedule_error'):
            c, day = snapshot()
            setattr(c, field, 'offline')
            result = mod.display_data(c, ['GPV5.2'], personal=True, now=day)
            self.assertEqual(result['status'], 'error')
            self.assertEqual(result['days'], [])
            self.assertIsNone(result['event']['at'])
        self.assertEqual(mod.display_data(None)['status'], 'missing')

    def test_personal_selection_is_not_guessed_from_building_groups(self):
        c, day = snapshot()
        result = mod.display_data(c, personal=True, now=day)
        self.assertTrue(result['building_groups'])
        self.assertEqual(result['selected_groups'], [])
        self.assertEqual(result['event']['kind'], 'selection_required')
        self.assertTrue(result['days'][0]['rows'])

    def test_multiple_groups_choose_earliest_boundary_and_name_its_groups(self):
        c, day = snapshot()
        groups = ('GPV3.1','GPV5.2')
        c.schedule = replace(c.schedule,
            intervals=tuple(contract.Interval(g,'outage',day+timedelta(hours=a),day+timedelta(hours=b),'daily') for g,a,b in [('GPV3.1',10,15),('GPV5.2',13,16)]),
            coverage=tuple(contract.Coverage(g,'outage',day,day+timedelta(days=1)) for g in groups))
        for hour, expected_kind, expected_hour, expected_groups in [(9,'outage_start',10,['GPV3.1']),(12,'outage_start',13,['GPV5.2']),(14,'outage_end',15,['GPV3.1']),(15,'outage_end',16,['GPV5.2'])]:
            event = mod.display_data(c,groups,personal=True,now=day+timedelta(hours=hour))['event']
            self.assertEqual(event, {'kind':expected_kind,'at':(day+timedelta(hours=expected_hour)).timestamp(),'groups':expected_groups})

    def test_unconfirmed_end_and_missing_coverage_do_not_predict_restoration(self):
        c, day = snapshot()
        c.schedule = replace(c.schedule, intervals=(contract.Interval('GPV5.2','outage',day,day+timedelta(days=1),'daily'),))
        self.assertEqual(mod.display_data(c,['GPV5.2'],personal=True,now=day+timedelta(hours=12))['event']['kind'], 'end_unconfirmed')
        self.assertEqual(mod.display_data(c,['GPV4.1'],personal=True,now=day+timedelta(hours=12))['event']['kind'], 'unknown')


class TemplateTests(unittest.TestCase):
    def setUp(self):
        from jinja2.sandbox import SandboxedEnvironment
        self.env = SandboxedEnvironment(autoescape=False)
        self.now = datetime(2026,11,4,12,30,tzinfo=mod.KYIV_TZ)
        self.data = {'schema_version':1,'today':'2026-11-04','selected_groups':['GPV2.1','GPV3.1'],'building_groups':['GPV2.1','GPV3.1'],'personal':True,'event':{'kind':'outage_start','at':self.now.timestamp()+3600,'groups':['GPV3.1']}}

    def render(self, name, **context):
        return self.env.from_string((ROOT/'examples/geekmagic'/f'{name}.html').read_text()).render(state='ready',attributes=self.data,now=self.now,**context)

    def test_signed_power_zero_and_unavailable_are_distinct(self):
        for power, expected, color in [('120','+120 Вт','#47dfa7'),('-148','−148 Вт','#ff7070'),('0','0 Вт','#a2b6ca'),('unavailable','— Вт','#a2b6ca'),('nan','— Вт','#a2b6ca')]:
            html = self.render('battery', states=lambda e: '79' if e.endswith('_percent') else power)
            self.assertIn(expected, html)
            self.assertIn(color, html)
            self.assertIn('79%', html)
        self.assertNotIn('nan%', self.render('battery',states=lambda e:'nan'))

    def test_multiple_groups_are_all_visible_and_event_has_group_label(self):
        html = self.render('groups')
        self.assertIn('2.1<br>3.1',html)
        self.assertIn('МОЇ ГРУПИ',html)
        html = self.render('clock')
        self.assertIn('До планового · 3.1',html)
        self.assertIn('1г 0хв',html)

    def test_more_than_four_home_groups_rotate_without_dropping_ids(self):
        self.data['selected_groups'] = [f'GPV{i}.1' for i in range(1,8)]
        all_html = ''
        for offset in (0,20):
            self.now += timedelta(seconds=offset)
            all_html += self.render('groups')
        for i in range(1,8): self.assertIn(f'{i}.1',all_html)

    def test_grid_paginates_sixty_rows_keeps_home_and_escapes_labels(self):
        rows = [{'id':f'GPV{i}.1','label':f'{i}.1','home':i==2,'selected':i==2,'segments':[{'start':0,'end':1440,'kind':'unknown'}]} for i in range(1,61)]
        rows[0]['id'] = '<script>bad</script>'
        self.data['days'] = [{'rows':rows,'minutes':1440,'start':self.now.timestamp()-3600,'end':self.now.timestamp()+23*3600,'ticks':[{'label':'00','minute':0},{'label':'24','minute':1440}]}]
        rendered=[]
        for i in range(6):
            self.now += timedelta(seconds=20)
            html=self.render('grid');rendered.append(html)
            self.assertEqual(html.count('class="gm-row'),12 if '>6/6<' not in html else 5)
            self.assertIn('gm-home gm-selected',html)
            self.assertNotIn('<script>',html)
        self.assertIn('&lt;script&gt;', ''.join(rendered))
        for i in range(2,61):self.assertIn(f'>{i}.1</span>', ''.join(rendered))
        self.data['today']='2026-11-03'
        self.assertIn('Графік<br>недоступний',self.render('grid'))

    def test_view_builder_uses_native_hero_and_only_battery_animation(self):
        spec=importlib.util.spec_from_file_location('display_builder',ROOT/'examples/geekmagic/build_view.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        view=module.build_view('sensor.schedule','sensor.soc','sensor.watts')
        self.assertEqual(view['layout'],'hero')
        self.assertEqual(len(view['widgets']),4)
        self.assertEqual([w['slot'] for w in view['widgets'] if w['options'].get('animate')],[3])
        self.assertIn("states('sensor.watts')",view['widgets'][3]['options']['html'])

    def test_elapsed_mask_tracks_real_instant_including_dst_and_preserves_selection(self):
        import re
        for text, length in [('2026-03-29', 1380), ('2026-10-25', 1500), ('2026-11-04', 1440)]:
            start = datetime.fromisoformat(text).replace(tzinfo=mod.KYIV_TZ)
            end = start + timedelta(days=1)
            self.now = datetime.fromtimestamp(start.timestamp() + 210 * 60, mod.KYIV_TZ)
            self.data.update(today=text, days=[{'start':start.timestamp(), 'end':end.timestamp(), 'minutes':length, 'ticks':[], 'rows':[
                {'id':'GPV2.1', 'home':True, 'selected':True, 'segments':[{'start':0, 'end':length, 'kind':'outage'}]},
                {'id':'GPV3.1', 'home':False, 'selected':False, 'segments':[{'start':0, 'end':length, 'kind':'unknown'}]},
            ]}])
            html = self.render('grid')
            widths = re.findall(r'class="gm-past" style="width:([0-9.]+)%"', html)
            self.assertEqual(len(widths), 2)
            for width in widths: self.assertAlmostEqual(float(width), 210 / length * 100)
            self.assertIn('gm-home gm-selected', html)
            self.assertIn('class="gm-now"', html)
            self.now = start
            self.assertNotIn('class="gm-past"', self.render('grid'))
            self.now = end
            self.assertNotIn('class="gm-past"', self.render('grid'))
            self.assertNotIn('class="gm-now"', self.render('grid'))

    def test_actual_power_is_independent_of_schedule_and_visible_without_it(self):
        # A scheduled outage must never override a live grid observation.
        self.data['event'] = {'kind': 'outage_end', 'at': self.now.timestamp()+3600}
        for state, label in [('on', 'СВІТЛО Є'), ('off', 'СВІТЛА НЕМАЄ'), ('unavailable', 'СТАН НЕВІДОМИЙ'), ('unknown', 'СТАН НЕВІДОМИЙ')]:
            html = self.render('grid', states=lambda _: state)
            self.assertIn(label, html)
            self.assertIn('Графік<br>недоступний', html)
            if state != 'on': self.assertNotIn('СВІТЛО Є</span>', html)

    def test_builder_accepts_only_binary_actual_status_and_omits_unconfigured_status(self):
        spec=importlib.util.spec_from_file_location('display_builder',ROOT/'examples/geekmagic/build_view.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        view=module.build_view('sensor.schedule','sensor.soc','sensor.watts','binary_sensor.grid_present')
        self.assertIn("states('binary_sensor.grid_present')",view['widgets'][0]['options']['html'])
        with self.assertRaises(__import__("argparse").ArgumentTypeError):
            module.build_view('sensor.schedule','sensor.soc','sensor.watts',"sensor.bad')")
        default=module.build_view('sensor.schedule','sensor.soc','sensor.watts')
        self.assertNotIn("states('binary_sensor",default['widgets'][0]['options']['html'])
