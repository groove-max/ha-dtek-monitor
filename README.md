# DTEK Monitor for Home Assistant

**English** · [Українська](README.uk.md)

[![Open DTEK Monitor in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=groove-max&repository=ha-dtek-monitor&category=integration)

[![Latest release](https://img.shields.io/github/v/release/groove-max/ha-dtek-monitor)](https://github.com/groove-max/ha-dtek-monitor/releases/latest)
[![Tests](https://github.com/groove-max/ha-dtek-monitor/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/groove-max/ha-dtek-monitor/actions/workflows/tests.yml)
[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm_Noncommercial-blue.svg)](LICENSE)

**DTEK outage schedules, your personal account and meter readings — together in Home Assistant.** Follow your building’s outage groups, view electricity consumption and review readings before sending them to DTEK.

Supports **Odesa oblast, Kyiv city, Kyiv oblast and Dnipropetrovsk oblast** in Ukraine. Address schedules work without a cabinet login; personal-account features are optional.

**[Install](docs/UPGRADING.md)** · [Documentation](https://groove-max.github.io/ha-dtek-monitor/en/) · [Latest release](https://github.com/groove-max/ha-dtek-monitor/releases/latest) · [Telegram companion](https://github.com/groove-max/ha-dtek-telegram-bot)

![My DTEK dashboard in Home Assistant: a fictional account, cumulative meter reading, monthly consumption and outage group](docs/images/my-dtek-overview.en.png)


Requires **Home Assistant 2026.3.0 or newer**. Available through HACS Custom repositories in the regular release channel. Cabinet features for **Kyiv oblast and Dnipropetrovsk oblast are experimental**; see [regional support](#regions).

[Set up an address](#setup) · [Connect a personal account](#personal-account) · [Understand the data](#data) · [Troubleshoot](#troubleshooting)

## Choose what you need

| I want | Connect |
| --- | --- |
| Building schedules and outage status | An address without a cabinet login; all four operators below. |
| My apartment's readings, consumption and account information | A phone-based personal cabinet; household accounts in all four regions; Kyiv oblast and Dnipropetrovsk oblast are experimental. |
| Reading suggestions from my home meter | An optional cumulative HA energy sensor linked to the appropriate account. |
| Telegram notifications | The separate [DTEK Telegram Bot](https://github.com/groove-max/ha-dtek-telegram-bot): building alerts in any chat, or your cabinet in a private conversation. |

[Cabinet and dashboard](docs/PERSONAL_ACCOUNT.md) · [Readings and sensors](docs/ENERGY_AND_READINGS.md) · [Schedules and groups](docs/SCHEDULES.md)

<a id="features"></a>
## What you get

- The outage status, reason and estimated restoration time reported by DTEK for your address.
- Separate calendars for planned outages and possible outage windows.
- An [address repair calendar](docs/SCHEDULES.md#address-works), with a separate status for missing or unavailable repair times.
- All schedule groups returned for the address, including addresses with multiple groups.
- A clearly labeled **last known schedule** for viewing when DTEK is unavailable.
- Connection diagnostics that distinguish failed requests from an empty published schedule.
- Multiple addresses: add a separate integration entry for each one.

DTEK's address status is **not a physical measurement of electricity in your home**. A scheduled outage, the operator's current status and a local meter reading describe different things. During emergency outages, the published schedule may not apply. This is an independent community project, not an official DTEK product.

<a id="regions"></a>
## Supported operators

Choose the distribution operator serving the address, not just the nearest city.

| Area | Operator | Address lookup |
| --- | --- | --- |
| Odesa oblast | ДТЕК Одеські електромережі — OEM | [Official outage page](https://www.dtek-oem.com.ua/ua/shutdowns) |
| Kyiv oblast | ДТЕК Київські регіональні електромережі — KREM | [Official outage page](https://www.dtek-krem.com.ua/ua/shutdowns) |
| Dnipropetrovsk oblast | ДТЕК Дніпровські електромережі — DNEM | [Official outage page](https://www.dtek-dnem.com.ua/ua/shutdowns) |
| Kyiv city | ДТЕК Київські електромережі — KEM | [Official outage page](https://www.dtek-kem.com.ua/ua/shutdowns) |

**Experimental regions:** Kyiv oblast and Dnipropetrovsk oblast cabinets are enabled, including sign-in, registration, account management, readings and apartment-group lookup. These functions use the shared API but have not yet been checked with real linked accounts in those regions. Verify the address, meter and tariff zones before confirming changes. Report problems in [GitHub Issues](https://github.com/groove-max/ha-dtek-monitor/issues), with the operator, HA/integration versions and redacted diagnostics; do not attach credentials or full account details. A failed group lookup does not block meter data.

Kyiv city and Kyiv oblast use different operators. For Kyiv city, the setup skips city selection. An address within one of these regions may still be served by another distributor; first check that the address is available on the operator's website. Other operators are not currently supported.

<a id="installation"></a>
## Install

Requires **Home Assistant 2026.3.0 or newer** and internet access from Home Assistant to the selected DTEK website. HACS is convenient but optional.

### Through HACS

1. Open **HACS → ⋮ → Custom repositories**.
2. Add `https://github.com/groove-max/ha-dtek-monitor` with type **Integration**.
3. Find **DTEK Monitor** and download the [latest release](https://github.com/groove-max/ha-dtek-monitor/releases/latest). No prerelease switch is needed. [Upgrade guide](docs/UPGRADING.md).
4. Restart Home Assistant.
5. Continue with [address setup](#setup) or [personal cabinet setup](#personal-account).

This is a [HACS custom repository](https://hacs.dev/docs/faq/custom_repositories/); adding it to HACS installs the files, not the address configuration.

The noncommercial license does not meet the requirements for the default HACS catalog. Install it through **Custom repositories** as described above.

### Manually

1. Download **dtek_monitor.zip** from the [latest release](https://github.com/groove-max/ha-dtek-monitor/releases/latest).
2. Extract the archive into `custom_components/dtek_monitor` inside your Home Assistant configuration directory.
3. Check that the resulting path is `custom_components/dtek_monitor/manifest.json`, without an extra nested folder.
4. Restart Home Assistant and continue below.

<a id="setup"></a>
## Add your address

1. Open **Settings → Devices & services → Add integration**.
2. Search for **DTEK Monitor**.
3. Choose the operator, then **Outage schedules by address**, settlement, street and house number. Use the spelling offered by DTEK.
4. Keep the initial polling interval at **300 seconds (5 minutes)**.
5. Open the newly created device and check its entities.

To change the polling interval later, open the integration's **Configure** menu. The range is 60–3600 seconds. Shorter intervals cannot make DTEK publish new information sooner.

**First check:** the connection diagnostic should show `ok` after a successful refresh. Compare the address status with the official website, then add the **Outage schedule** calendar to a dashboard calendar card. An empty calendar is not always an error: DTEK may not have published that date yet.

Add another integration entry for another address. You do not need to edit `configuration.yaml`.

<a id="personal-account"></a>
## Personal cabinet and My DTEK dashboard

1. Add the integration and choose your distribution operator, then **Personal account and meter readings**.
2. Sign in with your phone and password. Registration and password recovery through SMS are also available.
3. Select the personal accounts to monitor. If the cabinet is empty, add an account here or later in settings.
4. Reload the HA page. On your dashboard choose **Edit → Add card → My DTEK**, select an account and save.
5. Check the building link. Unique directory matches connect automatically; ambiguous addresses need confirmation. A single verified cabinet group or the building's only group is automatic. Otherwise, choose your apartment group in Settings. HA notifies you of verified group changes and automatically replaces a disappeared manual group when the replacement is unambiguous. [How group selection works](docs/SCHEDULES.md#section-2).

**Overview** shows the address, latest cumulative reading and separately labelled
monthly consumption. **Schedule** offers a grid of all groups with building and
apartment highlights, a list and PNG export. **Readings** lets you review and send
values. **Consumption** shows monthly history. **Settings** contains account,
EIC and meter details, your group, energy sensor and optional reminders.

For several apartments, choose an account on each card or enable its account
selector. This does not change other panels or which accounts HA monitors.
Use the eye button to reveal or hide an account number.

An energy sensor is optional. It need not be ATORCH: use a cumulative grid-import
sensor for the correct apartment. Linking, official-meter calibration, corrections,
scheduled checks and reminders are covered in the [readings guide](docs/ENERGY_AND_READINGS.md).
**There is no automatic submission.** In HA, an administrator confirms each send; in the companion bot, only the assigned user with submission permission can confirm it.

[Complete cabinet setup and features](docs/PERSONAL_ACCOUNT.md).

**Language:** English and Ukrainian are supported. If HA uses Russian, DTEK Monitor shows Ukrainian, including setup, cards and its notifications. HA’s own language stays unchanged.

<a id="data"></a>
## Understand the entities

Entity names follow your Home Assistant language. Open the integration's device page to find their actual IDs; older installations and renamed entities can have different IDs.

| Entity | How to use it |
| --- | --- |
| **Power** | `on` means DTEK reports no active outage; `off` means DTEK reports an outage. It does not measure your sockets. |
| **Outage status / description** | Reported type and reason: normal, emergency, planned or stabilization outage. |
| **Outage start / end** | Reported start and estimated end; absent values can be normal when there is no active outage. |
| **Primary schedule group / All schedule groups** | The address's group assignments. The first group is not necessarily the only one. |
| **DTEK last update / Schedule changed** | Source update timestamps, not local power-transition times. |
| **Next planned / possible outage; Outage end (scheduled)** | Upcoming schedule times for the building or selected apartment groups. [Details and limits](docs/SCHEDULES.md#upcoming-times). |
| **Tomorrow’s schedule availability** | Distinguishes tomorrow's published schedule, verified empty day, forecast, incomplete data and failures. |
| **Outage schedule** | Published planned outage intervals. A plan is not proof that the power actually went off. |
| **Possible outage schedule** | Possible windows, when available from the source; overlaps with planned intervals are removed. |
| **Last known schedule (view only)** | Saved events with their verification time. Use for reference, not automatic alerts. |
| **DTEK connection** | Connection and freshness diagnostics, including separate address/schedule errors. |
| **Address repair works / Repair report availability** | Operator-reported repair intervals and their completeness. Separate from group schedules; advance notice is not guaranteed. |

### Multiple groups and hidden group numbers

When DTEK returns several groups, the integration keeps them all and preserves each calendar event's group. It cannot determine which entrance or apartment belongs to which group without additional information.

Some operators, including Kyiv city, do not publish meaningful public group numbers. Internal identifiers may still appear in HA attributes. In building mode, the companion bot displays these as local **“Variant 1”, “Variant 2”** labels in its Ukrainian messages. These are not official queue numbers and can change when the address assignment changes.

### When a schedule is unavailable

A failed verification makes the live calendars unavailable. The integration does not silently reuse old data as fresh or interpret an unpublished day as “no outages.” Address sensors can still update if only the schedule request failed.

An address confirmed by DTEK can also finish its first setup without a schedule.
Check **Schedule availability** for the reason; retries and recovery are automatic.

The separate saved calendar remains viewable, including after a restart. It stores concrete events within an eight-day snapshot horizon; it does not invent dates that DTEK has not published or repeat an old weekly template indefinitely. Details: [freshness and automation rules](docs/REFERENCE.md#freshness).

<a id="troubleshooting"></a>
## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Integration is not in “Add integration” | Restart HA after installation; verify the folder path for a manual install. |
| City, street or house is missing | Check the selected operator and the address on its website. Kyiv city is separate from Kyiv oblast. |
| Sensors or live calendars are unavailable | Open **DTEK connection** and inspect `address_error`, `schedule_error` and the last successful refresh. The integration retries automatically. |
| There are no future events | Check whether DTEK has published those dates. Empty or unpublished data does not establish uninterrupted power. |
| DTEK says power is on, but the home is dark | This integration reflects the operator's data. Use a local power sensor with the [Telegram companion](https://github.com/groove-max/ha-dtek-telegram-bot#power-detection) for physical evidence. |
| Telegram messages are missing | Telegram is handled by [DTEK Telegram Bot](https://github.com/groove-max/ha-dtek-telegram-bot), installed separately. |

Do not repeatedly remove and re-add an address to recover from a temporary website failure. See [diagnostics and update guidance](docs/REFERENCE.md#diagnostics).

<a id="support"></a>
## Help, development and releases

- [Report an issue](https://github.com/groove-max/ha-dtek-monitor/issues): include HA/integration versions, operator, expected behavior and sanitized errors. You can attach a [diagnostic download](docs/REFERENCE.md#diagnostics) from the connection's menu in HA. English and Ukrainian reports are welcome.
- [Detailed reference](docs/REFERENCE.md): entity IDs, automation attributes, freshness and backups.
- [Changelog](CHANGELOG.md) and [releases](https://github.com/groove-max/ha-dtek-monitor/releases).
- [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md).

Licensed under [PolyForm Noncommercial 1.0.0](LICENSE). Noncommercial use, modification and redistribution are permitted under its terms; commercial use is not granted. This is source-available software, not an OSI open-source license. Earlier MIT releases retain their original terms. Dependencies keep their own licenses. See [NOTICE](NOTICE).
