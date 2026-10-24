"""Grid interactions, real PNG downloads, stale replies and accessible mobile UI."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from card_browser import install_card

HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
if HAS_PLAYWRIGHT:
    from playwright.async_api import async_playwright
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(HAS_PLAYWRIGHT, "Requires Playwright Chromium")
class GridCardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 390, "height": 844})
        self.errors = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        await install_card(
            self.page, ROOT / "custom_components/dtek_monitor/frontend/schedule-card.js"
        )
        await self.page.evaluate((ROOT / "tests/fixtures/schedule_grid.js").read_text())
        await self.page.evaluate("""() => {
          window.calls=[];window.data=makeScheduleGrid();window.hass={language:'en',user:{id:'test'},states:{'sensor.status':{state:'current',attributes:{}}},callWS:async msg=>{calls.push(msg);return structuredClone(data)}};
          window.card=document.createElement('dtek-schedule-card');card.setConfig({status_entity:'sensor.status',entities:['calendar.home']});card.hass=hass;document.querySelector('main').append(card);
        }""")
        await self.page.locator("tbody tr").first.wait_for()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.p.stop()
        self.assertEqual(self.errors, [])

    async def test_personal_default_with_home_and_all_groups_available(self):
        self.assertEqual(await self.page.locator("tbody tr").count(), 1)
        self.assertEqual(await self.page.get_by_label("Groups", exact=True).input_value(), "mine")
        self.assertEqual(await self.page.locator("tbody tr.home").count(), 1)
        self.assertEqual(await self.page.locator("tbody tr.selected").count(), 1)
        self.assertEqual(
            await self.page.locator("tbody tr.selected").get_attribute("data-group"),
            "GPV3.1",
        )
        self.assertEqual(
            await self.page.evaluate("calls.map(x=>x.type)"),
            ["dtek_monitor/schedule_grid"],
        )
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        self.assertEqual(await self.page.locator("tbody tr").count(), 2)
        await self.page.get_by_label("Groups", exact=True).select_option("all")
        self.assertEqual(await self.page.locator("tbody tr").count(), 12)

    async def test_date_filter_focus_and_scroll_survive_unrelated_ha_updates(self):
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-19")
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        await self.page.get_by_label("Date", exact=True).focus()
        await self.page.evaluate(
            """() => {const g=card.shadowRoot.querySelector('dtek-schedule-grid');g.q('.scroll').scrollLeft=200;window.table=g.q('table');window.row=table.querySelector('tr[data-group]');for(let i=0;i<10;i++)card.hass={...hass,states:{...hass.states}};}"""
        )
        self.assertEqual(
            await self.page.get_by_label("Date", exact=True).input_value(), "2026-10-19"
        )
        self.assertEqual(await self.page.locator("tbody tr").count(), 2)
        self.assertTrue(
            await self.page.evaluate(
                "card.shadowRoot.querySelector('dtek-schedule-grid').q('select')===card.shadowRoot.querySelector('dtek-schedule-grid').shadowRoot.activeElement"
            )
        )
        self.assertTrue(
            await self.page.evaluate("row===table.querySelector('tr[data-group]')")
        )
        self.assertEqual(await self.page.evaluate("calls.length"), 1)

    async def test_sixty_groups_search_jump_and_refresh_preserve_user_choices(self):
        await self.page.evaluate("""() => {
          for(const day of data.days) day.rows=Array.from({length:60},(_,i)=>({...day.rows[0],id:`GPV${Math.floor(i/2)+1}.${i%2+1}`,label:`GPV${Math.floor(i/2)+1}.${i%2+1}`,home:i>=56&&i<=57,selected:i===56}));
          card.shadowRoot.querySelector('dtek-schedule-grid').load();
        }""")
        await self.page.get_by_role("button", name="GPV29.1: Intervals", exact=True).wait_for()
        self.assertEqual(await self.page.locator("tbody tr").count(), 1)
        await self.page.get_by_label("Groups", exact=True).select_option("all")
        self.assertEqual(await self.page.locator("tbody tr").count(), 60)
        search = self.page.get_by_label("Find a group", exact=True)
        await search.fill("29.")
        self.assertEqual(await self.page.locator("tbody tr").count(), 2)
        await self.page.evaluate("card.shadowRoot.querySelector('dtek-schedule-grid').load()")
        self.assertEqual(await search.input_value(), "29.")
        await search.fill("absent")
        self.assertEqual(await self.page.locator("tbody tr").count(), 0)
        await self.page.get_by_text("No groups match this search.", exact=True).wait_for()
        await self.page.get_by_role("button", name="Go to my group", exact=True).click()
        self.assertEqual(await search.input_value(), "")
        self.assertEqual(await self.page.locator("tbody tr").count(), 60)
        self.assertGreater(await self.page.locator(".scroll").evaluate("e=>e.scrollTop"), 1000)
        self.assertIn("GPV29.1", await self.page.locator(".details").inner_text())

    async def test_unknown_assignment_is_explicit_and_never_selects_first_group(self):
        await self.page.evaluate("""() => {
          for(const day of data.days)for(const row of day.rows){row.selected=false;row.home=false;}
          hass.states['sensor.unassigned']=hass.states['sensor.status'];card.setConfig({...card._config,status_entity:'sensor.unassigned'});card.hass={...hass};
        }""")
        await self.page.get_by_text("Your group is not confirmed. You can view building groups or all groups.", exact=True).wait_for()
        self.assertEqual(await self.page.locator("tbody tr").count(), 12)
        self.assertEqual(await self.page.locator(".details").inner_text(), "")
        await self.page.get_by_label("Groups", exact=True).select_option("mine")
        self.assertEqual(await self.page.locator("tbody tr").count(), 0)
        self.assertTrue(await self.page.get_by_role("button", name="Save PNG").is_disabled())
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        await self.page.evaluate("""() => {
          data.days.forEach(d=>d.rows[4].home=true);card.shadowRoot.querySelector('dtek-schedule-grid').load();
        }""")
        await self.page.locator("tbody tr").wait_for()
        self.assertEqual(await self.page.get_by_label("Groups", exact=True).input_value(), "home")
        self.assertEqual(await self.page.locator("tbody tr").count(), 1)

    async def test_half_hours_unknown_and_forecast_are_distinct(self):
        await self.page.get_by_label("Groups", exact=True).select_option("all")
        await self.page.get_by_role(
            "button", name="GPV3.1: Intervals", exact=True
        ).click()
        self.assertIn("11:00–14:30", await self.page.locator(".details").inner_text())
        self.assertEqual(
            await self.page.locator('tr[data-group="GPV6.2"] td.unknown').count(), 48
        )
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-20")
        self.assertGreater(await self.page.locator("td.forecast").count(), 0)
        self.assertEqual(await self.page.locator("td.clear").count(), 0)
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-24")
        self.assertTrue(
            await self.page.get_by_role("button", name="Save PNG").is_disabled()
        )
        await self.page.get_by_text(
            "No schedule is published for this date yet.", exact=True
        ).wait_for()

    async def test_refresh_preserves_controls_and_group_focus(self):
        await self.page.evaluate(
            "() => {hass.callWS=msg=>msg.type==='dtek_monitor/schedule_refresh'?new Promise(resolve=>window.reply=resolve):Promise.resolve(structuredClone(data));}"
        )
        await self.page.get_by_role("button", name="Refresh").click()
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-19")
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        group = self.page.get_by_role("button", name="GPV3.1: Intervals", exact=True)
        await group.focus()
        await self.page.evaluate("reply({status:'current',changed:false})")
        await self.page.get_by_role("button", name="Refresh").wait_for()
        self.assertEqual(
            await self.page.get_by_label("Date", exact=True).input_value(), "2026-10-19"
        )
        self.assertEqual(await self.page.locator("tbody tr").count(), 2)
        self.assertTrue(await group.evaluate("e=>e===e.getRootNode().activeElement"))

    async def test_png_is_a_real_image_for_selected_date(self):
        async with self.page.expect_download() as event:
            await self.page.get_by_role("button", name="Save PNG").click()
        download = await event.value
        self.assertEqual(download.suggested_filename, "dtek-schedule-2026-10-18.png")
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "grid.png"
            await download.save_as(file)
            raw = file.read_bytes()
            self.assertEqual(raw[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(int.from_bytes(raw[16:20], "big"), 1280)
            self.assertGreater(len(raw), 10000)

    async def test_selected_day_has_one_notice_and_relevant_legend(self):
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        self.assertFalse(await self.page.locator(".status").is_visible())
        self.assertEqual(await self.page.locator(".feedback").inner_text(), "")
        self.assertEqual(await self.page.locator(".legend .key").count(), 3)
        self.assertNotIn("Purple", await self.page.locator(".note").inner_text())
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-20")
        self.assertIn("weekly forecast", await self.page.locator(".feedback").inner_text())
        self.assertEqual(await self.page.locator(".legend .key").count(), 2)
        self.assertIn("Purple", await self.page.locator(".note").inner_text())
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-24")
        self.assertIn("No schedule is published", await self.page.locator(".feedback").inner_text())
        self.assertNotIn("No planned outages today", await self.page.locator(".feedback").inner_text())

    async def test_status_changes_keep_controls_and_recover_selected_date(self):
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-19")
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        await self.page.get_by_label("Date", exact=True).focus()
        await self.page.evaluate("""() => {
          hass.callWS=()=>new Promise(resolve=>window.reply=resolve);
          hass.states['sensor.status']={state:'current',attributes:{updated:2}};card.hass=hass;
        }""")
        self.assertTrue(await self.page.get_by_label("Date", exact=True).evaluate("e=>e===e.getRootNode().activeElement"))
        self.assertFalse(await self.page.get_by_label("Date", exact=True).is_disabled())
        await self.page.evaluate("reply({status:'unpublished',days:[]})")
        await self.page.get_by_text("DTEK has paused schedule publication.", exact=True).wait_for()
        self.assertFalse(await self.page.locator("table").is_visible())
        self.assertTrue(await self.page.get_by_role("button", name="Save PNG").is_disabled())
        await self.page.evaluate("""() => {hass.callWS=msg=>msg.type==='dtek_monitor/schedule_refresh'?new Promise(resolve=>window.reply=resolve):Promise.resolve(structuredClone(data));}""")
        await self.page.get_by_role("button", name="Refresh").click()
        await self.page.evaluate("reply({status:'current',changed:false})")
        await self.page.locator("table").wait_for()
        self.assertEqual(await self.page.get_by_label("Date", exact=True).input_value(), "2026-10-19")
        self.assertEqual(await self.page.locator("tbody tr").count(), 2)

    async def test_grid_does_not_mislabel_connection_setup_or_provider_errors(self):
        for status, text in [
            ("error", "The grid is unavailable"),
            ("no_address", "Link a building"),
            ("address_pending", "Finding the building"),
            ("address_confirmation", "Confirm the building"),
            ("address_lookup_unavailable", "The DTEK address directory is temporarily unavailable"),
            ("address_unavailable", "The building connection is unavailable"),
            ("unsupported", "is not supported"),
            ("unpublished", "paused schedule publication"),
            ("missing", "has not published a grid"),
        ]:
            await self.page.evaluate("status=>{hass.callWS=async()=>({status,days:[]})}", status)
            await self.page.get_by_role("button", name="Refresh").click()
            await self.page.locator(".feedback").filter(has_text=text).wait_for()
            self.assertFalse(await self.page.locator("table").is_visible())
            self.assertEqual(await self.page.locator(".feedback.error").count(), int(status == "error"))

    async def test_partial_grid_keeps_unknown_cells_visible(self):
        await self.page.get_by_label("Groups", exact=True).select_option("all")
        self.assertIn("Only part", await self.page.locator(".feedback").inner_text())
        self.assertEqual(await self.page.locator("td.unknown").count(), 48)
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        self.assertEqual(await self.page.locator(".feedback").inner_text(), "")
        await self.page.get_by_text("Update details", exact=True).click()
        await self.page.evaluate("card.hass={...hass}")
        self.assertTrue(await self.page.locator(".meta").is_visible())

    async def test_pending_export_does_not_save_a_previous_account_or_date(self):
        await self.page.evaluate(
            "() => {HTMLCanvasElement.prototype.toBlob=function(cb){window.finishPNG=()=>cb(new Blob(['demo'],{type:'image/png'}));};window.downloads=0;HTMLAnchorElement.prototype.click=function(){downloads++;};}"
        )
        await self.page.get_by_role("button", name="Save PNG").click()
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-19")
        await self.page.evaluate("finishPNG()")
        self.assertEqual(await self.page.evaluate("downloads"), 0)

    async def test_old_response_cannot_reappear_after_error_or_account_switch(self):
        await self.page.evaluate(
            "() => {hass.callWS=()=>new Promise(resolve=>window.old=resolve);}"
        )
        await self.page.get_by_role("button", name="Refresh").click()
        await self.page.evaluate(
            "hass.callWS=async()=>{throw new Error('gone')};card.setConfig({...card._config,status_entity:'sensor.other'});card.hass=hass;"
        )
        await self.page.get_by_text(
            "The grid is unavailable. Refresh or check the connection.", exact=True
        ).wait_for()
        await self.page.evaluate("old(data)")
        self.assertFalse(await self.page.locator("table").is_visible())
        self.assertTrue(
            await self.page.get_by_role("button", name="Save PNG").is_disabled()
        )

    async def test_phone_theme_and_untrusted_labels_cannot_overflow_or_inject_html(
        self,
    ):
        await self.page.evaluate(
            """() => {hass.language='uk';data.address='<img src=x onerror=alert(1)>'.repeat(10);hass.states['sensor.status']={state:'current',attributes:{updated:1}};card.hass=hass;document.body.style.cssText='--primary-text-color:#edf2f5;--card-background-color:#20272c;--secondary-background-color:#30383e;--secondary-text-color:#bbc5ce;--divider-color:#52616e';}"""
        )
        await self.page.get_by_role("button", name="Зберегти PNG").wait_for()
        self.assertEqual(
            await self.page.locator("table").evaluate("e=>getComputedStyle(e).color"),
            "rgb(237, 242, 245)",
        )
        for width in [320, 390, 1280]:
            await self.page.set_viewport_size({"width": width, "height": 900})
            self.assertTrue(
                await self.page.evaluate(
                    "document.documentElement.scrollWidth<=innerWidth"
                )
            )
            self.assertTrue(await self.page.locator(".tools").evaluate("""e=>{
              const rects=[...e.querySelectorAll('button,select')].map(n=>n.getBoundingClientRect());
              return rects.every((a,i)=>rects.every((b,j)=>i===j || a.right<=b.left || b.right<=a.left || a.bottom<=b.top || b.bottom<=a.top));
            }"""))
        self.assertEqual(await self.page.locator("img").count(), 0)

    async def test_manual_refresh_has_one_network_action_and_preserves_selected_date(self):
        await self.page.evaluate("""() => {hass.callWS=msg=>{
          calls.push(msg);
          return msg.type==='dtek_monitor/schedule_refresh'?new Promise(resolve=>window.finishRefresh=resolve):Promise.resolve(structuredClone(data));
        }}""")
        await self.page.get_by_role("button", name="Refresh schedule").click()
        await self.page.get_by_label("Date", exact=True).select_option("2026-10-19")
        await self.page.get_by_label("Groups", exact=True).select_option("home")
        await self.page.evaluate("card.hass={...hass};card.shadowRoot.querySelector('dtek-schedule-grid').refresh()")
        self.assertEqual(await self.page.evaluate("calls.filter(x=>x.type==='dtek_monitor/schedule_refresh').length"), 1)
        await self.page.evaluate("finishRefresh({status:'current',changed:false})")
        await self.page.get_by_text("Checked: the schedule has not changed.", exact=True).wait_for()
        self.assertEqual(await self.page.get_by_label("Date", exact=True).input_value(), "2026-10-19")
        self.assertEqual(await self.page.get_by_label("Groups", exact=True).input_value(), "home")
        self.assertFalse(await self.page.get_by_role("button", name="Refresh schedule").is_disabled())
        self.assertEqual(self.errors, [])

    async def test_refresh_cooldown_and_language_are_clear_and_do_not_remove_the_grid(self):
        await self.page.evaluate("""() => {hass.callWS=async msg=>{if(msg.type==='dtek_monitor/schedule_refresh')throw {code:'schedule_refresh_cooldown',translation_placeholders:{seconds:'125'}};return structuredClone(data)};}""")
        await self.page.get_by_role("button", name="Refresh schedule").click()
        await self.page.get_by_text("Another refresh is available in 125 seconds.").wait_for()
        self.assertTrue(await self.page.locator("table").is_visible())
        await self.page.evaluate("hass.language='uk';card.hass={...hass}")
        await self.page.get_by_text("Наступне оновлення доступне через 125 с.").wait_for()
        self.assertFalse(await self.page.get_by_role("button", name="Оновити графік").is_disabled())
        self.assertLessEqual(await self.page.evaluate("document.documentElement.scrollWidth"), 390)

    async def test_late_refresh_result_does_not_affect_another_account(self):
        await self.page.evaluate("""() => {hass.callWS=msg=>msg.type==='dtek_monitor/schedule_refresh'?new Promise(resolve=>window.finishRefresh=resolve):Promise.resolve(structuredClone(data));}""")
        await self.page.get_by_role("button", name="Refresh schedule").click()
        await self.page.evaluate("card.setConfig({...card._config,status_entity:'sensor.other'});card.hass={...hass}")
        await self.page.evaluate("finishRefresh({status:'current',changed:true})")
        self.assertTrue(await self.page.locator(".refresh-result").is_hidden())
        self.assertFalse(await self.page.get_by_role("button", name="Refresh schedule").is_disabled())
        self.assertEqual(self.errors, [])
