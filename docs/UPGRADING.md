# Install, update or roll back DTEK Monitor

**English** · [Українська](UPGRADING.uk.md) · [README](../README.md)

Install the **[latest regular release](https://github.com/groove-max/ha-dtek-monitor/releases/latest)**. HACS offers it in the normal release channel, without enabling prereleases. Check its release notes for version-specific changes.

Version 2 adds My DTEK, cabinets for four operators, history, readings and suggestions from cumulative energy sensors. Kyiv oblast and Dnipropetrovsk oblast cabinets, including apartment-group lookup, remain experimental and await real-account validation. Building schedules work independently, without a cabinet login.

RC4 adds optional [meter photos and cabinet documents](ENERGY_AND_READINGS.md#attach-a-meter-photo). For these features in Telegram, use **Bot 0.5.0-rc4 or newer**. Update Monitor first and restart HA. New-document notifications must be enabled separately in HA and the bot; an accepted photo does not prove that an inspection act has been issued.

## RC7 update

Install **Monitor 2.0.0-rc7** through the normal HACS update channel, restart HA and reload its page. Existing accounts, building links, entity IDs and calibrated energy sources are preserved. Choose a suitable time for the restart; a release update does not avoid it.

Find the new **DTEK announcement** entity on your building device and the announcement block above the schedule. Open it to read the original text, source and check time. Regional announcements are separate from address outages and do not change measured power. A notice can concern only part of an oblast or a particular date.

For automations, [check applicability and freshness](SCHEDULES.md#provider-notices), including the unknown (`null`) case. Published calendar events remain available. Only a fresh, unambiguous matching emergency declaration pauses derived schedule predictions; the interpretation is not a structured DTEK API flag.

For the same notices in Telegram, use the optional **Bot 0.5.0-rc7** and review its per-profile announcement controls. The integration works without the bot. Existing [GeekMagic Hero displays](DISPLAYS.md) and the monthly consumption explanation introduced in RC6 remain available.

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

<a id="main-code"></a>
## Try a fix from `main` before a release

Use this when an issue comment asks you to test an unreleased change. `main`
is the development branch; its code may be newer than the version shown in HA.
Refreshing HACS alone does not install these changes.

1. Make the backup described above and note the commit linked in the issue.
2. Download the [main source archive](https://github.com/groove-max/ha-dtek-monitor/archive/refs/heads/main.zip) and extract it on your computer. For an exact revision, use the commit archive link provided in the issue.
3. In that archive, find **`custom_components/dtek_monitor`**. Replace only the same folder inside your HA configuration directory with this complete folder. The final path must be **`custom_components/dtek_monitor/manifest.json`**. Do not copy the whole repository into `custom_components`, or keep a second integration copy there.
4. Keep your HA configuration, `.storage`, accounts and existing integration entries. There is no need to register or link the address again.
5. **Restart Home Assistant fully**, then reload the browser or HA app page. Reloading the integration alone does not replace all loaded Python modules.
6. Check the feature described in the issue. For regional announcements, look for the building's **DTEK announcement** entity and the announcement block above its schedule. [States, source and interpretation limits](SCHEDULES.md#provider-notices).

Development code can retain the last released version number. Include the commit or archive download date in your feedback. Check the change's migration notes before rolling back and keep the backup made before installing it. Once a release includes the fix, install that release normally through HACS. **Regional announcements are included in RC7; they no longer require `main`.**

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
