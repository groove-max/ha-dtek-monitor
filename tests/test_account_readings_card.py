"""The submission UI requires review; unrelated updates never overwrite edits."""

import importlib.util
from pathlib import Path
import unittest
from card_browser import install_card

HAS_PLAYWRIGHT = importlib.util.find_spec("playwright") is not None
if HAS_PLAYWRIGHT:
    from playwright.async_api import async_playwright

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "custom_components/dtek_monitor/frontend/account-readings-card.js"
)


@unittest.skipUnless(HAS_PLAYWRIGHT, "Requires Playwright Chromium")
class ReadingsCardTests(unittest.IsolatedAsyncioTestCase):
    async def test_modern_two_zone_labels_preserve_wire_keys_and_edited_values(self):
        await self.page.evaluate("""() => {
          ctx.zones=['DAY_2_ZONE','NIGHT_2_ZONE'].map(zone=>({zone,previous:'100',date:'2026-09-30'}));
          const original=hass.callWS;
          hass.callWS=async msg=>msg.action==='prepare'
            ? (calls.push(msg), {confirmation:'two',readings:Object.entries(msg.values).map(([zone,value])=>({zone,value,previous:'100',increase:String(Number(value)-100)}))})
            : original(msg);
        }""")
        await self.page.get_by_role("button", name="Load current meter", exact=True).click()
        await self.page.get_by_label("Day (kWh)", exact=True).fill("150")
        await self.page.get_by_label("Night (kWh)", exact=True).fill("120")
        await self.page.evaluate("card.hass={...hass,states:{unrelated:{state:'updated'}}}")
        self.assertEqual(await self.page.get_by_label("Day (kWh)", exact=True).input_value(), "150")
        await self.page.get_by_role("button", name="Review readings", exact=True).click()
        await self.page.get_by_role("checkbox").wait_for()
        self.assertEqual(await self.page.evaluate("calls.find(x=>x.action==='prepare').values"),
                         {"DAY_2_ZONE": "150", "NIGHT_2_ZONE": "120"})
        self.assertNotIn("DAY_2_ZONE", await self.page.locator("main").inner_text())
        self.assertNotIn("confirm", await self.page.evaluate("calls.map(x=>x.action)"))

    async def asyncSetUp(self):
        self.p = await async_playwright().start()
        self.browser = await self.p.chromium.launch(headless=True)
        self.page = await self.browser.new_page(viewport={"width": 390, "height": 844})
        await install_card(self.page, SCRIPT)
        await self.page.evaluate("""() => {
          window.ctx={account:'••••0001',address:'Example address',serial:'TEST',date:'2026-10-18',digits:6,revision:'revision',blocked:false,zones:[{zone:'GENERAL',previous:'100',date:'2026-09-30'}]};
          window.calls=[];window.pending=[];window.deferConfirm=false;window.cabinetUrl='https://my.dtek-oem.com.ua/';
          window.hass={language:'en',callWS:async msg=>{
            if(msg.type==='dtek_monitor/account_identity')return {masked:'••••0001',cabinet_url:cabinetUrl};
            calls.push(msg);
            if(msg.action==='context')return structuredClone(ctx);
            if(msg.action==='prepare')return {confirmation:'draft',readings:[{zone:'GENERAL',value:123,previous:'100',increase:'23'}]};
            if(msg.action==='confirm')return deferConfirm ? new Promise((resolve,reject)=>pending.push({resolve,reject})) : {status:'accepted'};
            return {status:'acknowledged'};
          }};
          window.card=document.createElement('dtek-account-readings-card');card.setConfig({entity:'sensor.example'});
          document.querySelector('main').append(card);card.hass=hass;
        }""")

    async def asyncTearDown(self):
        await self.browser.close()
        await self.p.stop()

    async def load(self):
        await self.page.get_by_role(
            "button", name="Load current meter", exact=True
        ).click()
        await self.page.get_by_label("Single zone (kWh)", exact=True).wait_for()

    async def prepare(self):
        await self.load()
        await self.page.get_by_label("Single zone (kWh)", exact=True).fill("123")
        await self.page.get_by_role(
            "button", name="Review readings", exact=True
        ).click()
        await self.page.get_by_role("checkbox").wait_for()

    async def test_cabinet_link_uses_selected_region_and_never_falls_back(self):
        for region in ["oem", "kem", "krem", "dnem"]:
            url = f"https://my.dtek-{region}.com.ua/"
            await self.page.evaluate("url => {cabinetUrl=url;card.render();}", url)
            link = self.page.get_by_role("link", name="Open DTEK cabinet", exact=True)
            await link.wait_for()
            self.assertEqual(await link.get_attribute("href"), url)
            self.assertEqual(await link.get_attribute("rel"), "noopener noreferrer")
        for invalid in [
            None,
            "",
            "javascript:alert(1)",
            "https://example.invalid/",
            "https://my.dtek-kem.com.ua/other",
            "https://my.dtek-kem.com.ua@evil.invalid/",
        ]:
            await self.page.evaluate("url => {cabinetUrl=url;card.render();}", invalid)
            self.assertEqual(
                await self.page.get_by_role(
                    "link", name="Open DTEK cabinet", exact=True
                ).count(),
                0,
            )
        self.assertEqual(await self.page.evaluate("calls.length"), 0)

    async def test_late_cabinet_link_does_not_replace_typed_readings(self):
        await self.load()
        await self.page.get_by_label("Single zone (kWh)", exact=True).fill("123")
        await self.page.evaluate("""() => {
          const original=hass.callWS;
          hass.callWS=msg=>msg.type==='dtek_monitor/account_identity'
            ? new Promise(resolve=>pending.push({resolve})) : original(msg);
          card.render();
        }""")
        field = self.page.get_by_label("Single zone (kWh)", exact=True)
        await field.fill("456")
        await self.page.evaluate(
            "pending.forEach(p=>p.resolve({masked:'••••0001',cabinet_url:'https://my.dtek-kem.com.ua/'}))"
        )
        await self.page.get_by_role(
            "link", name="Open DTEK cabinet", exact=True
        ).wait_for()
        self.assertEqual(await field.input_value(), "456")
        self.assertEqual(
            await self.page.evaluate("calls.map(x=>x.action)"), ["context"]
        )

    async def test_late_link_from_old_account_cannot_reappear_after_switch(self):
        await self.page.evaluate("""() => {
          const original=hass.callWS;
          hass.callWS=msg=>msg.type==='dtek_monitor/account_identity'
            ? new Promise(resolve=>pending.push({resolve,entity:msg.entity_id})) : original(msg);
          card.render();
          card.setConfig({entity:'sensor.other'});
          pending.filter(p=>p.entity==='sensor.other').forEach(p=>p.resolve({masked:'••••0002',cabinet_url:'https://my.dtek-dnem.com.ua/'}));
        }""")
        link = self.page.get_by_role("link", name="Open DTEK cabinet", exact=True)
        await link.wait_for()
        await self.page.evaluate(
            "pending.filter(p=>p.entity==='sensor.example').forEach(p=>p.resolve({masked:'••••0001',cabinet_url:'https://my.dtek-oem.com.ua/'}))"
        )
        self.assertEqual(
            await link.get_attribute("href"), "https://my.dtek-dnem.com.ua/"
        )

    async def test_opening_and_hass_updates_never_send_or_erase_input(self):
        self.assertEqual(await self.page.evaluate("calls.length"), 0)
        await self.load()
        await self.page.get_by_label("Single zone (kWh)", exact=True).fill("123")
        for _ in range(5):
            await self.page.evaluate(
                "card.hass={...hass,states:{random:Math.random()}}"
            )
        self.assertEqual(
            await self.page.get_by_label("Single zone (kWh)", exact=True).input_value(),
            "123",
        )
        self.assertEqual(
            await self.page.evaluate("calls.map(x=>x.action)"), ["context"]
        )

    async def test_eye_reveals_and_hides_without_overwriting_reading_or_storing_number(
        self,
    ):
        await self.load()
        field = self.page.get_by_label("Single zone (kWh)", exact=True)
        await field.fill("123")
        await self.page.evaluate("""() => {
          const old=hass.callWS;
          hass.callWS=msg=>msg.type==='dtek_monitor/account_identity'
            ? Promise.resolve({masked:'••••0001',...(msg.reveal?{number:'1234500001'}:{})}) : old(msg);
        }""")
        self.assertEqual(
            await self.page.get_by_text(
                "Account number: 1234500001", exact=True
            ).count(),
            0,
        )
        await self.page.get_by_role(
            "button", name="Show account number", exact=True
        ).click()
        await self.page.get_by_text("Account number: 1234500001", exact=True).wait_for()
        await self.page.get_by_role(
            "button", name="Hide account number", exact=True
        ).click()
        self.assertEqual(await field.input_value(), "123")
        self.assertEqual(
            await self.page.get_by_text(
                "Account number: 1234500001", exact=True
            ).count(),
            0,
        )
        self.assertFalse(
            await self.page.evaluate(
                "JSON.stringify(localStorage).includes('1234500001') || JSON.stringify(sessionStorage).includes('1234500001')"
            )
        )
        self.assertEqual(
            await self.page.evaluate("calls.map(x=>x.action)"), ["context"]
        )

    async def test_late_reveal_after_hiding_cannot_expose_number(self):
        await self.page.evaluate("""() => {
          hass.callWS=msg=>new Promise(resolve=>pending.push({resolve}));
        }""")
        await self.page.get_by_role(
            "button", name="Show account number", exact=True
        ).click()
        await self.page.get_by_role(
            "button", name="Hide account number", exact=True
        ).click()
        await self.page.evaluate(
            "pending[0].resolve({masked:'••••0001',number:'1234500001'})"
        )
        self.assertEqual(
            await self.page.get_by_text(
                "Account number: 1234500001", exact=True
            ).count(),
            0,
        )

    async def test_identity_masks_on_user_or_permission_change(self):
        await self.page.evaluate("""() => {const normal=hass.callWS;hass.callWS=async msg=>msg.type==='dtek_monitor/account_identity'?{masked:'••••0001',...(msg.reveal?{number:'1234500001'}:{})}:normal(msg);}""")
        for user in [{'id':'other','is_admin':True},{'id':'other','is_admin':False}]:
            await self.page.get_by_role('button',name='Show account number',exact=True).click()
            # The synthetic endpoint explicitly provides a revealed number.
            await self.page.get_by_text('Account number: 1234500001',exact=True).wait_for()
            await self.page.evaluate("user => {hass={...hass,user};card.shadowRoot.querySelector('dtek-account-number').hass=hass;}",user)
            self.assertEqual(await self.page.get_by_text('Account number: 1234500001',exact=True).count(),0)

    async def test_standalone_number_card_masks_again_after_reconnection(self):
        await self.page.evaluate("""() => {
          card.remove();window.numberCard=document.createElement('dtek-account-number-card');
          numberCard.setConfig({entity:'sensor.example'});
          numberCard.hass={language:'en',callWS:async msg=>({masked:'••••0001',...(msg.reveal?{number:'1234500001'}:{})})};
          document.querySelector('main').append(numberCard);
        }""")
        await self.page.get_by_role(
            "button", name="Show account number", exact=True
        ).click()
        await self.page.get_by_text("Account number: 1234500001", exact=True).wait_for()
        await self.page.get_by_role('button',name='Copy account number',exact=True).focus()
        await self.page.evaluate('''() => {
          window.identity=numberCard.shadowRoot.querySelector('dtek-account-number');
          window.focused=identity.shadowRoot.activeElement;
          numberCard.hass={...identity._hass,states:{unrelated:{state:'new'}}};
        }''')
        self.assertTrue(await self.page.evaluate('identity.shadowRoot.activeElement===focused'))
        await self.page.evaluate(
            "numberCard.remove();document.querySelector('main').append(numberCard)"
        )
        self.assertEqual(
            await self.page.get_by_text(
                "Account number: 1234500001", exact=True
            ).count(),
            0,
        )
        self.assertEqual(
            await self.page.get_by_role(
                "button", name="Show account number", exact=True
            ).count(),
            1,
        )

    async def test_pending_meter_can_display_accepted_attempt_without_unlock_button(
        self,
    ):
        await self.page.evaluate(
            "ctx={...ctx,blocked:true,reason:'pending_or_blocked',last_attempt:{status:'accepted'}}"
        )
        await self.page.get_by_role(
            "button", name="Load current meter", exact=True
        ).click()
        await self.page.get_by_text(
            "DTEK explicitly confirmed receipt for every tariff zone. This does not mean the billing calculation is final.",
            exact=True,
        ).wait_for()
        self.assertEqual(
            await self.page.get_by_role(
                "button", name="Unlock new entry after checking", exact=True
            ).count(),
            0,
        )
        self.assertEqual(
            await self.page.get_by_role(
                "button", name="Review readings", exact=True
            ).count(),
            0,
        )

    async def test_review_and_checkbox_required_and_double_click_sends_once(self):
        await self.prepare()
        button = self.page.get_by_role(
            "button", name="Confirm and send to DTEK", exact=True
        )
        self.assertTrue(await button.is_disabled())
        self.assertEqual(
            await self.page.evaluate("calls.map(x=>x.action)"), ["context", "prepare"]
        )
        await self.page.get_by_role("checkbox").check()
        await self.page.evaluate("deferConfirm=true")
        await button.click()
        await self.page.evaluate("card.act('confirm')")
        self.assertEqual(
            await self.page.evaluate("calls.filter(x=>x.action==='confirm').length"), 1
        )
        await self.page.evaluate("pending[0].resolve({status:'accepted'})")
        await self.page.get_by_text(
            "DTEK explicitly confirmed receipt for every tariff zone. This does not mean the billing calculation is final.",
            exact=True,
        ).wait_for()

    async def test_back_to_editing_retains_values_and_requires_new_review(self):
        await self.prepare()
        await self.page.get_by_role(
            "button", name="Back to editing", exact=True
        ).click()
        self.assertEqual(
            await self.page.get_by_label("Single zone (kWh)", exact=True).input_value(),
            "123",
        )
        self.assertEqual(
            await self.page.get_by_role(
                "button", name="Confirm and send to DTEK", exact=True
            ).count(),
            0,
        )
        self.assertEqual(
            await self.page.evaluate("calls.filter(x=>x.action==='confirm').length"), 0
        )

    async def test_lost_response_never_retries_and_requires_status_check(self):
        await self.prepare()
        await self.page.get_by_role("checkbox").check()
        await self.page.evaluate("deferConfirm=true")
        await self.page.get_by_role(
            "button", name="Confirm and send to DTEK", exact=True
        ).click()
        await self.page.evaluate(
            "pending[0].reject(new Error('private upstream text'))"
        )
        await self.page.get_by_role(
            "button", name="Check submission status", exact=True
        ).wait_for()
        self.assertEqual(
            await self.page.get_by_label("Single zone (kWh)", exact=True).count(), 0
        )
        self.assertEqual(
            await self.page.get_by_text("private upstream text", exact=True).count(), 0
        )
        await self.page.evaluate(
            "ctx={...ctx,blocked:true,last_attempt:{id:'attempt',status:'unknown'}}"
        )
        await self.page.get_by_role(
            "button", name="Check submission status", exact=True
        ).click()
        unlock = self.page.get_by_role(
            "button", name="Unlock new entry after checking", exact=True
        )
        self.assertTrue(await unlock.is_disabled())
        await self.page.get_by_role("checkbox").check()
        await unlock.click()
        self.assertEqual(
            await self.page.evaluate("calls.filter(x=>x.action==='confirm').length"), 1
        )
        self.assertEqual(await self.page.evaluate("calls.at(-1).action"), "acknowledge")

    async def test_late_reply_for_changed_account_is_discarded(self):
        await self.page.evaluate(
            "() => {hass.callWS=msg=>msg.type==='dtek_monitor/account_identity'?Promise.resolve({masked:'••••0001'}):new Promise(resolve=>pending.push({resolve}));}"
        )
        await self.page.get_by_role(
            "button", name="Load current meter", exact=True
        ).click()
        await self.page.evaluate(
            "card.setConfig({entity:'sensor.other'});pending[0].resolve(ctx)"
        )
        self.assertEqual(
            await self.page.get_by_text("Example address", exact=True).count(),
            0,
        )

    async def test_ukrainian_mobile_and_untrusted_address_render_as_text(self):
        await self.page.evaluate(
            "card._hass=null;card.hass={...hass,language:'uk'};ctx.address='<img src=x onerror=alert(1)>'"
        )
        await self.page.get_by_role(
            "button", name="Завантажити дані лічильника", exact=True
        ).click()
        await self.page.get_by_label("Одна зона (kWh)", exact=True).wait_for()
        self.assertEqual(await self.page.locator("img").count(), 0)
        self.assertTrue(
            await self.page.evaluate("document.documentElement.scrollWidth<=innerWidth")
        )

    async def upload_photo(self, label="Meter photo · Single zone"):
        import base64
        png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5XcAAAAASUVORK5CYII="
        await self.page.get_by_label(label, exact=True).set_input_files({
            "name": "synthetic-meter.png", "mimeType": "image/png", "buffer": base64.b64decode(png),
        })
        await self.page.get_by_role("img", name=label, exact=True).wait_for()

    async def test_photo_preview_survives_updates_and_is_sent_only_with_confirmation(self):
        await self.load()
        await self.page.get_by_label("Single zone (kWh)", exact=True).fill("123")
        async with self.page.expect_file_chooser():
            await self.page.get_by_role("button", name="Choose a photo · Single zone", exact=True).click()
        self.assertFalse(await self.page.get_by_label("Meter photo · Single zone", exact=True).is_visible())
        await self.upload_photo()
        await self.page.get_by_role("button", name="Replace photo · Single zone", exact=True).wait_for()
        original = await self.page.get_by_role("img", name="Meter photo · Single zone").get_attribute("src")
        self.assertTrue(original.startswith("data:image/jpeg;base64,"))
        self.assertEqual(await self.page.evaluate("calls.map(c=>c.action)"), ["context"])
        await self.page.evaluate("card.hass={...hass,states:{other:{state:'changed'}}};card.render()")
        self.assertEqual(await self.page.get_by_label("Single zone (kWh)", exact=True).input_value(), "123")
        await self.page.get_by_role("button", name="Review readings", exact=True).click()
        await self.page.get_by_role("checkbox").wait_for()
        self.assertEqual(await self.page.get_by_role("img", name="Meter photo · Single zone").get_attribute("src"), original)
        sent = await self.page.evaluate("calls.find(c=>c.action==='prepare').photos")
        self.assertEqual("data:"+sent["GENERAL"]["mime_type"]+";base64,"+sent["GENERAL"]["data"], original)
        self.assertNotIn("confirm", await self.page.evaluate("calls.map(c=>c.action)"))
        await self.page.get_by_role("button", name="Back to editing", exact=True).click()
        self.assertEqual(await self.page.get_by_role("img", name="Meter photo · Single zone").get_attribute("src"), original)
        await self.page.get_by_role("button", name="Review readings", exact=True).click()
        await self.page.get_by_role("checkbox").check()
        await self.page.get_by_role("button", name="Confirm and send to DTEK", exact=True).click()
        await self.page.get_by_role("button", name="Check submission status", exact=True).wait_for()
        self.assertEqual(await self.page.evaluate("calls.filter(c=>c.action==='confirm').length"), 1)
        self.assertEqual(await self.page.evaluate("Object.keys(card._photos).length"), 0)
        self.assertEqual(await self.page.locator("img.meter-photo").count(), 0)
        self.assertFalse(await self.page.evaluate("JSON.stringify(localStorage).includes('image/jpeg')"))

    async def test_removing_photo_and_invalid_file_do_not_erase_entered_reading(self):
        await self.load()
        field = self.page.get_by_label("Single zone (kWh)", exact=True)
        await field.fill("123")
        await self.upload_photo()
        await self.page.get_by_label("Meter photo · Single zone", exact=True).set_input_files({
            "name":"unsafe.svg", "mimeType":"image/svg+xml", "buffer":b"<svg onload='alert(1)'/>"})
        await self.page.get_by_role("alert").wait_for()
        self.assertTrue(await self.page.get_by_role("button", name="Review readings", exact=True).is_disabled())
        await field.fill("124")
        self.assertTrue(await self.page.get_by_role("button", name="Review readings", exact=True).is_disabled())
        await self.page.get_by_role("button", name="Remove photo", exact=True).click()
        self.assertEqual(await field.input_value(), "124")
        self.assertEqual(await self.page.locator("img.meter-photo").count(), 0)
        await self.page.get_by_role("button", name="Review readings", exact=True).click()
        await self.page.get_by_role("checkbox").wait_for()
        self.assertNotIn("photos", await self.page.evaluate("calls.find(c=>c.action==='prepare')"))

    async def test_day_and_night_photos_keep_their_zone_keys(self):
        await self.page.evaluate("ctx.zones=['DAY_2_ZONE','NIGHT_2_ZONE'].map(zone=>({zone,previous:'100',date:'2026-09-30'}))")
        await self.page.get_by_role("button", name="Load current meter", exact=True).click()
        await self.page.get_by_label("Day (kWh)", exact=True).fill("123")
        await self.page.get_by_label("Night (kWh)", exact=True).fill("456")
        await self.upload_photo("Meter photo · Day")
        await self.upload_photo("Meter photo · Night")
        await self.page.get_by_role("button", name="Review readings", exact=True).click()
        await self.page.get_by_role("checkbox").wait_for()
        self.assertEqual(set(await self.page.evaluate("Object.keys(calls.find(c=>c.action==='prepare').photos)")), {"DAY_2_ZONE","NIGHT_2_ZONE"})
        self.assertEqual(await self.page.locator("img.meter-photo").count(), 2)
        self.assertTrue(await self.page.evaluate("document.documentElement.scrollWidth<=innerWidth"))

    async def test_late_image_conversion_cannot_attach_to_another_account(self):
        import base64
        await self.load()
        await self.page.evaluate("""() => {
          window.photoReads=[];const Original=window.FileReader;
          window.FileReader=class extends Original {readAsDataURL(blob){photoReads.push(()=>super.readAsDataURL(blob));}};
        }""")
        await self.page.get_by_label("Meter photo · Single zone", exact=True).set_input_files({
            "name":"late.png", "mimeType":"image/png", "buffer":base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a5XcAAAAASUVORK5CYII=")})
        await self.page.wait_for_function("photoReads.length===1")
        self.assertTrue(await self.page.get_by_role("button", name="Review readings", exact=True).is_disabled())
        await self.page.evaluate("card.setConfig({entity:'sensor.other'});photoReads.forEach(f=>f())")
        await self.page.wait_for_timeout(50)
        self.assertEqual(await self.page.evaluate("Object.keys(card._photos).length"),0)
        self.assertEqual(await self.page.locator("img.meter-photo").count(),0)
