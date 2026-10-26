"""Profile privacy, independent forms and asynchronous account selection."""

import importlib.util
from pathlib import Path
import unittest
from card_browser import install_card

HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
if HAS_PLAYWRIGHT:
    from playwright.async_api import async_playwright
SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "custom_components/dtek_monitor/frontend/account-profile-card.js"
)


@unittest.skipUnless(HAS_PLAYWRIGHT, "Requires Playwright Chromium")
class ProfileCardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 390, "height": 900})
        await install_card(self.page, SCRIPT)
        await self.page.evaluate("""() => {
          window.requests=[];window.pending=[];
          window.profile=(entity,reveal=false)=>({address:entity==='sensor.second'?'Second apartment':'<img src=x onerror="window.injected=true"> Example apartment',metadata_available:true,available:true,model:'NIK example',serial:reveal?'PRIVATE-METER':'••••ETER',eics:[reveal?'56X00000000000001':'••••0001'],installation_eic:reveal?'56X00000000000001':'••••0001',contract_power_kw:'3',next_verification_year:2028,seals:[{number:reveal?'PRIVATE-SEAL':'••••SEAL'}],replacement_records:0,fetched_at:'2026-10-18T12:00:00+03:00'});
          window.hass={language:'en',states:{},user:{id:'one'},callWS:async msg=>{requests.push(msg);if(msg.type==='dtek_monitor/account_identity')return {masked:'••••0001',...(msg.reveal?{number:'100001'}:{})};if(msg.type==='dtek_monitor/account_profile')return profile(msg.entity_id,msg.reveal);if(msg.type==='dtek_monitor/account_readback')return {status:'no_attempt',latest:[{date_time:'2026-10-18T00:00:00+03:00',value:'123',zone:'GENERAL',status:'active',source:'Cabinet'}],matches:[],fetched_at:'2026-10-18T12:00:00+03:00'};}};
          window.card=document.createElement('dtek-account-profile-card');card.setConfig({entity:'sensor.first'});card.hass=hass;document.body.append(card);
        }""")
        await self.page.get_by_text("NIK example", exact=True).wait_for()

    async def asyncTearDown(self):
        await self.browser.close()
        await self.p.stop()

    async def test_background_refresh_does_not_collapse_profile_or_reset_focus(self):
        await self.page.get_by_text('Meter details',exact=True).click()
        await self.page.get_by_role('button',name='Refresh',exact=True).focus()
        before=await self.page.evaluate('''() => {
          const normal=hass.callWS;
          hass.callWS=msg=>msg.type==='dtek_monitor/account_profile'
            ? new Promise(resolve=>window.releaseProfile=resolve):normal(msg);
          window.focused=card.shadowRoot.activeElement;
          return card.getBoundingClientRect().height;
        }''')
        await self.page.evaluate("card.hass={...hass,states:{'sensor.first':{last_updated:'new'}}}")
        self.assertEqual(await self.page.evaluate('card.getBoundingClientRect().height'),before)
        self.assertTrue(await self.page.evaluate('card.shadowRoot.activeElement===focused'))
        await self.page.evaluate("releaseProfile({...profile('sensor.first'),fetched_at:'2026-10-18T12:30:00+03:00'})")
        self.assertEqual(await self.page.evaluate('card.getBoundingClientRect().height'),before)
        self.assertTrue(await self.page.evaluate('card.shadowRoot.activeElement===focused'))
        self.assertTrue(await self.page.locator('details').evaluate('(e)=>e.open'))
        self.assertIn('12:30',await self.page.locator('ha-card').inner_text())

    async def test_failed_background_refresh_clears_profile_and_displays_error(self):
        await self.page.evaluate('''() => {
          const normal=hass.callWS;hass.callWS=msg=>msg.type==='dtek_monitor/account_profile'
            ? Promise.reject({code:'unauthorized'}):normal(msg);
          card.hass={...hass,states:{'sensor.first':{last_updated:'failed'}}};
        }''')
        await self.page.get_by_text('Profile unavailable or access denied.',exact=True).wait_for()
        self.assertEqual(await self.page.get_by_text('NIK example',exact=True).count(),0)

    async def test_address_always_visible_masking_copy_safe_render_and_mobile_width(
        self,
    ):
        self.assertIn(
            "Example apartment", await self.page.locator("ha-card").inner_text()
        )
        self.assertEqual(await self.page.locator("img").count(), 0)
        self.assertIsNone(await self.page.evaluate("window.injected"))
        self.assertNotIn(
            "PRIVATE-METER", await self.page.locator("ha-card").inner_text()
        )
        await self.page.get_by_role(
            "button", name="Show meter identifiers", exact=True
        ).click()
        await self.page.get_by_text("PRIVATE-METER", exact=False).wait_for()
        await self.page.evaluate(
            """() => {Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copied=text;}},configurable:true});}"""
        )
        await self.page.get_by_role(
            "button", name="Copy: Meter number", exact=True
        ).click()
        self.assertEqual(await self.page.evaluate("window.copied"), "PRIVATE-METER")
        await self.page.get_by_role(
            "button", name="Hide meter identifiers", exact=True
        ).click()
        await self.page.get_by_role(
            "button", name="Show meter identifiers", exact=True
        ).wait_for()
        self.assertNotIn(
            "PRIVATE-METER", await self.page.locator("ha-card").inner_text()
        )
        self.assertNotIn(
            "56X00000000000001", await self.page.locator("ha-card").inner_text()
        )
        self.assertTrue(
            await self.page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        )
        self.assertEqual(
            await self.page.evaluate(
                "requests.filter(m=>m.type==='dtek_monitor/account_readback').length"
            ),
            0,
        )

    async def test_profile_does_not_duplicate_history_or_touch_other_forms(self):
        await self.page.evaluate(
            """() => {const input=document.createElement('input');input.id='draft';input.value='User edited reading';document.body.append(input);card.hass={...hass,states:{'sensor.first':{last_updated:'new'}}};}"""
        )
        await self.page.get_by_text("NIK example", exact=True).wait_for()
        self.assertEqual(await self.page.locator("#draft").input_value(), "User edited reading")
        self.assertEqual(await self.page.get_by_role("button", name="Check reading history", exact=True).count(), 0)
        self.assertEqual(await self.page.evaluate("requests.filter(m=>['dtek_monitor/account_submission','dtek_monitor/account_readback','dtek_monitor/account_history'].includes(m.type)).length"), 0)

    async def test_late_reveal_cannot_follow_switched_account(self):
        await self.page.evaluate(
            """() => {const normal=hass.callWS;hass.callWS=msg=>((msg.type==='dtek_monitor/account_profile'&&msg.reveal)||msg.type==='dtek_monitor/account_readback')?new Promise(resolve=>pending.push({msg,resolve})):normal(msg);card.hass=hass;}"""
        )
        await self.page.get_by_role(
            "button", name="Show meter identifiers", exact=True
        ).click()
        await self.page.evaluate("card.setConfig({entity:'sensor.second'})")
        await self.page.get_by_text("Second apartment", exact=True).wait_for()
        await self.page.evaluate(
            """() => {pending[0].resolve(profile('sensor.first',true));}"""
        )
        text = await self.page.locator("ha-card").inner_text()
        self.assertNotIn("PRIVATE-METER", text)
        self.assertNotIn("Matching values", text)
        self.assertNotIn("Example apartment", text)
        self.assertIn("Second apartment", text)

    async def test_user_change_and_disconnect_clear_revealed_values(self):
        await self.page.get_by_role(
            "button", name="Show meter identifiers", exact=True
        ).click()
        await self.page.get_by_text("PRIVATE-METER", exact=False).wait_for()
        await self.page.evaluate("card.hass={...hass,user:{id:'two'}}")
        await self.page.get_by_role(
            "button", name="Show meter identifiers", exact=True
        ).wait_for()
        self.assertNotIn(
            "PRIVATE-METER", await self.page.locator("ha-card").inner_text()
        )
        await self.page.get_by_role(
            "button", name="Show meter identifiers", exact=True
        ).click()
        await self.page.get_by_text("PRIVATE-METER", exact=False).wait_for()
        await self.page.evaluate("card.remove()")
        self.assertIsNone(await self.page.evaluate("card._data"))
