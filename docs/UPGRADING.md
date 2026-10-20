# Install, update or roll back DTEK Monitor

**English** · [Українська](UPGRADING.uk.md) · [README](../README.md)

Install the **[latest regular release](https://github.com/groove-max/ha-dtek-monitor/releases/latest)**. HACS offers it in the normal release channel, without enabling prereleases. Check its release notes for version-specific changes.

Version 2 adds My DTEK, cabinets for four operators, history, readings and suggestions from cumulative energy sensors. Kyiv oblast and Dnipropetrovsk oblast cabinets, including apartment-group lookup, remain experimental and await real-account validation. Building schedules work independently, without a cabinet login.

## Before updating

1. Use Home Assistant **2026.3.0 or newer**.
2. Create a full HA backup and keep a copy you can restore. Include configuration,
   integration files and `.storage`; cabinet credentials and local calibration
   are part of that private backup.
3. Note the installed integration version and the entity IDs used by your
   dashboards, automations and Telegram bot.

Existing addresses, polling options and entity IDs should be preserved. Do not
remove and re-add the integration to upgrade. Existing development versions
`1.8.0b*` also update in place. The integration update does not change bot destinations or power-sensor bindings.
Existing building notifications remain compatible. To use personal Telegram
profiles, install **DTEK Telegram Bot 0.5.0-rc2 or newer** after updating the integration.

## Install with HACS

1. Add `https://github.com/groove-max/ha-dtek-monitor` as an **Integration** under **HACS → ⋮ → Custom repositories**, if it is not already there.
2. Open **DTEK Monitor** and download or update to the latest release. You do not need to enable **Pre-release**.
3. If an older release is shown, refresh the repository information in HACS. If you previously selected a specific version, use **Redownload** and select the latest available release.
4. Restart Home Assistant and reload the browser or HA app page to load the new cards.

## Install manually

Download **dtek_monitor.zip** from [the latest release](https://github.com/groove-max/ha-dtek-monitor/releases/latest).
Extract its contents into `custom_components/dtek_monitor` inside the HA
configuration directory. The resulting file must be
`custom_components/dtek_monitor/manifest.json`. Replace the previous component
folder after backing it up; do not merge two versions or install a second copy
under a different name. Restart HA and reload its page.

## First checks

- Existing user: check the original address devices, calendars and any bot
  connection. Unpublished dates may remain unavailable; this alone is not an
  upgrade failure.
- New user: follow [address setup](../README.md#setup) or
  [cabinet setup](PERSONAL_ACCOUNT.md#section-1).
- Cabinet user: add **My DTEK** through the dashboard card picker, select the
  intended account, and check the address and building link. For multiple
  building groups, choose your apartment group in Settings.
- Optional sensor: verify that it measures this apartment's cumulative grid
  import before [linking and calibrating it](ENERGY_AND_READINGS.md).
- Readings: reviewing a form sends nothing. Use the final send button only for
  actual readings you want recorded by DTEK, never for a test value.

## Return to the previous version

Version 2 migrates HA configuration entries to a format that **1.7.0 cannot
read**. Reinstalling old code alone is not a rollback. Restore the full backup
made before the upgrade, including the old integration files and configuration.
This also returns local settings and records to the backup time.

A HA restore does not undo readings, password changes or account linking already
performed at DTEK. Check the official cabinet before repeating any action whose
outcome is uncertain. If you installed the release candidate on a separate HA, removing that
installation also does not undo remote DTEK actions.

## Report a problem

Open an [issue](https://github.com/groove-max/ha-dtek-monitor/issues) with the
integration version, HA version, operator, steps, expected result and actual
result. Mention whether it was a fresh install or an update. For UI problems,
include the language and phone/desktop browser.

Remove passwords, tokens, phone numbers, exact addresses and account numbers
from logs and screenshots. The eye button can hide an account number, but the
address remains visible. Keep private security reports out of public issues;
see [Security](../SECURITY.md).
