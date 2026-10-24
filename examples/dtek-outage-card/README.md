# Compact DTEK schedule

**English** · [Українська](README.uk.md) · [All schedule features](../../docs/SCHEDULES.md)

A compact card for your home dashboard: DTEK's current address status, today's
or tomorrow's schedule, group selection and outage intervals. The day fits into
two rows without horizontal scrolling.

## Add the card

1. Install a DTEK Monitor version containing the compact card, restart HA and reload its page. Connect a building address, or a cabinet with an automatically linked building.
2. On your dashboard, choose **Edit → Add card** and search for **DTEK · Компактний графік / Compact schedule**.
3. Choose the address under **Building**. The editor fills in the required entities automatically.
4. Optionally set a title and initial group, then save the card.

The card ships with the integration and loads automatically. No JS copying,
manual resource registration or separate HACS repository is required.
The `examples/` folder contains only sample YAML and a demonstration.

For several addresses, add a card for each one. Without a custom title, the card
shows the address from the schedule data. If a building has several groups, the
first confirmed building group is shown initially; choose another in the list.
This selection does not change your cabinet's apartment group, calendars or bot notifications.

## Read the card

- The top status is the operator's current report for the address, **not a measurement from a home power sensor**. It may differ from the planned schedule.
- Today/tomorrow changes the schedule date, not the date of the top status.
- Planned, possible and forecast outages and missing data have distinct labels. Unknown hours do not mean there are no outages.
- Times use Europe/Kyiv. On daylight-saving transitions, both interval boundaries include their UTC offsets.
- **Refresh schedule** queries DTEK through the integration with its shared cooldown. Ordinary display updates read local HA data.
- The interface supports English and Ukrainian; HA's Russian language setting uses Ukrainian.

## Troubleshooting

**The card is missing from the picker:** check your integration version, restart HA and reload the page. If you previously installed a standalone `dtek-outage-card.js`, remove its manual resource and reload to use the built-in version.

**An address is missing in the editor:** check that the building is connected and loaded, and its schedule-status sensor and planned/possible outage calendars are enabled and readable by your HA user. Press **Refresh buildings**. A failed schedule publication itself does not remove a configured building from the list.

**DTEK status unavailable:** check the address-status entity and permissions. An available schedule can still work independently of this status.

**Tomorrow has grey hours:** the operator may not have published data yet. This does not confirm a day without outages.

## YAML and demo

[dashboard.yaml](dashboard.yaml) is an optional manual configuration example. The card type is `custom:dtek-outage-card`. The visual editor fills in `status_entity`, `entity` and `updated_entity`; the title and `group` are optional.

For a local demo, run `python3 -m http.server 8888` from the repository root and open `http://localhost:8888/examples/dtek-outage-card/demo/`. All data is fictional; there are no DTEK requests. Production code is in `custom_components/dtek_monitor/frontend/`; tests run from `tests/test_outage_card.py` in the regular CI suite.

The design and original implementation were contributed by [FastivProService in PR #12](https://github.com/groove-max/ha-dtek-monitor/pull/12). Notices for adapted code are retained in [THIRD_PARTY_NOTICES.md](../../custom_components/dtek_monitor/THIRD_PARTY_NOTICES.md); the project's main terms are in [LICENSE](../../LICENSE).
