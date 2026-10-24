"""HA replaces its element registry at startup; defer automatic card imports."""

import unittest
import test_account_workspace_card as workspace
from card_browser import install_card


@unittest.skipUnless(workspace.HAS_PLAYWRIGHT, "Requires Playwright Chromium")
class LoaderTests(unittest.IsolatedAsyncioTestCase):
    async def test_waits_for_ha_before_registering_card_dependencies(self):
        async with workspace.async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await install_card(
                    page, workspace.SCRIPT.with_name("account-loader.js")
                )
                self.assertFalse(
                    await page.evaluate("!!customElements.get('dtek-energy-editor')")
                )
                self.assertFalse(
                    await page.evaluate(
                        "!!customElements.get('dtek-account-workspace-card')"
                    )
                )
                await page.evaluate(
                    "customElements.define('home-assistant',class extends HTMLElement{})"
                )
                await page.wait_for_function(
                    "!!customElements.get('dtek-account-workspace-card')"
                )
                await page.wait_for_function("!!customElements.get('dtek-outage-card')")
                self.assertTrue(await page.evaluate("!!customElements.get('dtek-outage-card-editor')"))
                self.assertEqual(await page.evaluate("customCards.filter(c=>c.type==='dtek-outage-card').length"), 1)
                self.assertEqual(
                    await page.evaluate(
                        "customElements.get('dtek-energy-editor').workspaceVersion"
                    ),
                    2,
                )
                self.assertEqual(
                    await page.evaluate(
                        "customElements.get('dtek-energy-settings').workspaceVersion"
                    ),
                    1,
                )
                self.assertTrue(
                    await page.evaluate("!!customElements.get('dtek-account-options')")
                )
            finally:
                await browser.close()
