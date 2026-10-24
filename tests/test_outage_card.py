"""Compact card: contributor regressions plus built-in setup and permissions UX."""

from pathlib import Path
import unittest
import test_account_workspace_card as workspace
from card_browser import install_card

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(workspace.HAS_PLAYWRIGHT, "Requires Playwright Chromium")
class OutageCardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = await workspace.async_playwright().start()
        self.browser = await self.p.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 390, "height": 844})
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        await install_card(self.page, ROOT / "custom_components/dtek_monitor/frontend/outage-card.js")
        await self.page.evaluate((ROOT / "tests/fixtures/outage_card.js").read_text())
        await self.page.locator(".interval").first.wait_for()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.p.stop()
        self.assertEqual(self.errors, [])

    async def settled(self):
        await self.page.wait_for_function("!card._busy")

    async def test_home_group_three_intervals_mobile_and_unknown_day(self):
        self.assertEqual(await self.page.locator(".interval").count(), 3)
        self.assertEqual(await self.page.locator("select").input_value(), "GPV2.2")
        for width in [1200, 375, 320]:
            await self.page.set_viewport_size({"width": width, "height": 760})
            self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"))
        await self.page.get_by_role("button", name="Завтра", exact=True).click()
        self.assertIn("без даних", await self.page.locator(".feedback").inner_text())
        self.assertEqual(await self.page.locator(".cell.clear").count(), 0)
        await self.page.locator("select").select_option("GPV1.1")
        self.assertIn("планових відключень немає", await self.page.locator(".empty").inner_text())

    async def test_focus_option_nodes_and_scroll_survive_updates(self):
        result = await self.page.evaluate("""async () => {
          const select=card.shadowRoot.querySelector('select'), option=select.options[1];
          select.focus();
          card.hass={...demoHass,states:{...demoHass.states,'sensor.other':{state:'42'}}};
          const unrelated=card.shadowRoot.activeElement===select && select.options[1]===option;
          await card._load();
          return [unrelated,card.shadowRoot.activeElement===select && select.options[1]===option];
        }""")
        self.assertEqual(result, [True, True])

    async def test_reconfiguration_resets_previous_house_group(self):
        await self.page.locator("select").select_option("GPV1.1")
        await self.page.evaluate("card.setConfig({entity:'binary_sensor.other',status_entity:'sensor.other'})")
        await self.settled()
        self.assertEqual(await self.page.locator("select").input_value(), "GPV2.2")

    async def test_old_session_success_failure_and_refresh_are_discarded(self):
        for change in ["user", "connection"]:
            for reject in [False, True]:
                with self.subTest(change=change, reject=reject):
                    result = await self.page.evaluate("""async ({change,reject}) => {
                      let resolveOld,rejectOld;
                      const pending=new Promise((resolve,fail)=>{resolveOld=resolve;rejectOld=fail;});
                      const old={...demoHass,user:{id:'old'},connection:{},callWS:()=>pending};
                      card.hass=old;
                      let calls=0;
                      card.hass={...old,user:{id:change==='user'?'new':'old'},connection:change==='connection'?{}:old.connection,
                        callWS:async()=>{calls++;return {...demoData,marker:'new'};}};
                      await new Promise(resolve=>setTimeout(resolve,0));
                      if(reject)rejectOld(new Error('old'));else resolveOld({...demoData,marker:'old'});
                      await new Promise(resolve=>setTimeout(resolve,0));
                      return [card._data.marker,card._busy,card._error,calls];
                    }""", {"change": change, "reject": reject})
                    self.assertEqual(result, ["new", False, "", 1])
        self.assertTrue(await self.page.evaluate("""async () => {
          let finish,grids=0;const waiting=new Promise(resolve=>finish=resolve);
          const old={...demoHass,user:{id:'refresh-old'},connection:{},callWS:msg=>{
            if(msg.type.endsWith('schedule_refresh'))return waiting;
            grids++;return Promise.resolve(demoData);
          }};
          card.hass=old;await new Promise(resolve=>setTimeout(resolve,0));const initial=grids;
          const pending=card._load(true);card.hass={...old,user:{id:'refresh-new'},callWS:async()=>demoData};
          finish({});await pending;return grids===initial;
        }"""))

    async def test_unauthorized_new_user_cannot_keep_previous_grid(self):
        await self.page.evaluate("""() => {card.hass={...demoHass,user:{id:'restricted'},connection:{},callWS:async()=>{throw {code:'unauthorized'};}};}""")
        await self.settled()
        self.assertEqual(await self.page.locator(".cell").count(), 0)

    async def test_dst_boundaries_50_and_46_slots(self):
        for date, start, count in [("2026-10-25", "2026-10-24T21:00:00Z", 50), ("2026-03-29", "2026-03-28T22:00:00Z", 46)]:
            await self.page.evaluate("""async ({date,start,count}) => {
              const slots=Array.from({length:count},(_,i)=>{
                const time=new Date(Date.parse(start)+i*1800000);
                return {label:new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Kyiv',hour:'2-digit',minute:'2-digit'}).format(time),
                  offset:count===50?(i<8?'+0300':'+0200'):(i<6?'+0200':'+0300')};
              });
              const data={status:'ready',days:[{date,slots,rows:[{id:'GPV2.2',label:'2.2',home:true,cells:slots.map((_,i)=>i===7?'outage':'clear')}]}]};
              card.hass={...demoHass,user:{id:date},callWS:async()=>data};
            }""", {"date": date, "start": start, "count": count})
            await self.settled()
            self.assertEqual(await self.page.locator(".cell").count(), count)
            if count == 50:
                self.assertEqual(await self.page.locator(".interval b").inner_text(), "03:30 UTC+0300–03:00 UTC+0200")

    async def test_language_switch_empty_setup_and_safe_text(self):
        await self.page.evaluate("card.hass={...demoHass,language:'en'}")
        self.assertTrue(await self.page.get_by_role("button", name="Tomorrow", exact=True).is_visible())
        await self.page.evaluate("card.hass={...demoHass,language:'ru'}")
        self.assertTrue(await self.page.get_by_role("button", name="Завтра", exact=True).is_visible())
        await self.page.evaluate("card.setConfig({title:'<img src=x onerror=alert(1)>'})")
        self.assertEqual(await self.page.locator("img").count(), 0)
        self.assertIn("Оберіть будинок", await self.page.locator(".feedback").inner_text())
        self.assertTrue(await self.page.get_by_role("button", name="Оновити графік").is_disabled())

    async def test_request_timeout_clears_grid_and_allows_retry(self):
        await self.page.clock.install()
        await self.page.evaluate("() => {demoHass.callWS=()=>new Promise(()=>{});void card._load();}")
        await self.page.clock.fast_forward(21000)
        await self.settled()
        self.assertEqual(await self.page.locator(".cell").count(), 0)
        self.assertFalse(await self.page.get_by_role("button", name="Оновити графік").is_disabled())
        await self.page.evaluate("() => {demoHass.callWS=async()=>demoData;return card._load();}")
        self.assertEqual(await self.page.locator(".cell").count(), 48)

    async def test_bad_data_never_becomes_empty_schedule(self):
        await self.page.evaluate("() => {demoHass.callWS=async()=>({status:'ready',days:[{date:'bad',slots:[],rows:[]}]});return card._load();}")
        self.assertEqual(await self.page.locator(".cell").count(), 0)
        self.assertEqual(await self.page.locator(".empty").count(), 0)

    async def editor(self):
        await self.page.evaluate("""() => {
          card.remove();window.events=[];
          window.buildings=[{status_entity:'sensor.first',entity:'binary_sensor.renamed',updated_entity:'sensor.timestamp',address:'Одеса · Прикладна, 12',groups:['GPV2.2']},
            {status_entity:'sensor.second',address:'Київ · Тестова, 4',groups:['GPV1.1','GPV3.1']}];
          window.editor=customElements.get('dtek-outage-card').getConfigElement();
          editor.setConfig({type:'custom:dtek-outage-card'});
          editor.hass={...demoHass,callWS:async()=>buildings};
          editor.addEventListener('config-changed',e=>events.push(e.detail.config));
          document.querySelector('main').append(editor);
        }""")
        await self.page.wait_for_function("editor._buildings?.length===2")

    async def test_editor_selects_address_and_its_renamed_entities(self):
        await self.editor()
        await self.page.get_by_label("Будинок", exact=True).select_option("sensor.first")
        self.assertEqual(await self.page.evaluate("events.at(-1).entity"), "binary_sensor.renamed")
        await self.page.get_by_label("Початкова черга").select_option("GPV2.2")
        await self.page.get_by_label("Будинок", exact=True).select_option("sensor.second")
        result = await self.page.evaluate("events.at(-1)")
        self.assertEqual(result, {"type": "custom:dtek-outage-card", "status_entity": "sensor.second"})

    async def test_editor_keeps_title_focus_and_removed_building_selection(self):
        await self.editor()
        await self.page.get_by_label("Будинок", exact=True).select_option("sensor.first")
        title = self.page.get_by_label("Заголовок (необов’язково)")
        await title.fill("My unfinished title")
        await self.page.evaluate("editor.hass={...editor._hass,states:{...demoHass.states}}")
        self.assertEqual(await title.input_value(), "My unfinished title")
        self.assertTrue(await title.evaluate("e=>e===e.getRootNode().activeElement"))
        await self.page.evaluate("buildings=[];editor._load()")
        await self.page.wait_for_function("!editor._loading")
        self.assertEqual(await self.page.get_by_label("Будинок", exact=True).input_value(), "sensor.first")
        self.assertIn("недоступний", await self.page.locator("option:checked").first.inner_text())

    async def test_editor_ignores_previous_user_catalog(self):
        await self.editor()
        await self.page.evaluate("""() => {
          editor.hass={...editor._hass,user:{id:'old'},callWS:()=>new Promise(resolve=>window.reply=resolve)};
          editor.hass={...editor._hass,user:{id:'new'},callWS:async()=>[]};reply(buildings);
        }""")
        await self.page.wait_for_function("!editor._loading")
        self.assertEqual(await self.page.evaluate("editor._buildings"), [])
