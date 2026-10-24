# Building and apartment schedules

**English** · [Українська](SCHEDULES.uk.md) · [Connection and dashboard](PERSONAL_ACCOUNT.md)

A schedule is the operator's plan, not a measurement of electricity at home.

- [Schedule grid](#section-1)
- [Compact dashboard card](#compact-card)
- [My apartment group and the building schedules](#section-2)
- [Address repair works](#address-works)
- [Upcoming times and tomorrow's schedule](#upcoming-times)
- [Refresh and change notifications](#changes)

<a id="section-1"></a>
## Schedule grid

The **Schedule** tab now opens a half-hour grid of all groups published by the
selected operator. Building groups have an outline and a **My building** label;
your confirmed personal group also has **My group**. Choosing a row shows its
exact intervals below the grid. This display does not change building groups,
personal selection, calendars or Telegram notifications.

Use **Grid / List** to choose the format. In the grid, choose today or one of the
next six days, then **Groups → My building** to filter rows or **All groups** to
see every group. In **List**, choose **My group** or **My building · all groups**.
Each calendar keeps its own navigation; returning to the grid retains the date,
filter and scroll position. These controls do not change your apartment's group.
On a phone, scroll the grid
horizontally; group labels stay visible. Dates and hours use Europe/Kyiv,
including repeated or skipped hours at daylight-saving changes.

The legend distinguishes planned outages, possible outages, no scheduled
outage, weekly forecasts and missing data. A white cell does not prove the house
has power. Missing, hidden or failed publication never produces a reassuring
empty schedule. Unpublished dates show unknown cells; a connection failure hides
the old grid. The notice above the grid describes the selected date and visible
groups. Only relevant legend entries appear; expand **Update details** for the
source and verification times. The grid reads HA's local snapshot without extra DTEK requests.

**Save PNG** exports the selected date and visible groups with the building
highlights, legend and update times. It contains the building address, not the
apartment number or account number. The saved image is a snapshot and does not
update. Download is unavailable while data is loading or all visible cells are
unknown. Day/filter selections survive ordinary HA updates.

A standalone `custom:dtek-schedule-card` also opens the grid by default; set
`view: list` to retain its previous default. Its `status_entity` and the planned
and possible calendar entities must be enabled and readable by the HA user.

<a id="compact-card"></a>
## Compact dashboard card

For a small daily timeline alongside your other home controls, choose **Edit dashboard → Add card → DTEK · Компактний графік / Compact schedule**. Select a building in the visual editor; the integration fills in its entities and loads the card automatically. No extra HACS repository or manual resource is needed.

The card shows DTEK's current address status and today's/tomorrow's schedule for the selected group. The group's display selection does not change cabinet settings or bot alerts. Buildings connected automatically from a cabinet also appear in the editor. [Setup, optional YAML and troubleshooting](../examples/dtek-outage-card/README.md).

<a id="section-2"></a>
## My apartment group and the building schedules

A building may have several groups. Its **Primary schedule group** is a
compatibility value, not a claim about your apartment. For household accounts in the four supported regions, HA can also look up the account's groups through an optional cabinet
service. The panel identifies whether your group comes from the cabinet, a manual
choice or the building's only verified group.

1. When HA starts monitoring an account, it matches its city, street and building
   against the operator’s public directory. A unique match connects the building
   automatically; an existing connection is reused, including for multiple
   apartments in the same building. This also applies to accounts selected later.
2. If the address needs confirmation, open **My DTEK → Settings → Building and
   outage group → Choose another building from the directory**. Confirm the city,
   street and building in the same dialog. Apartment numbers and cabinet credentials
   are never included in the public building connection.
3. Leave **My apartment groups** empty for automatic selection. If exactly one
   cabinet group is confirmed by the building data, it is selected automatically.
   Without a cabinet assignment, the building's sole verified group can be used.
   If several cabinet groups are confirmed, choose yours in the same settings. Manual
   choices take priority while they still belong to the building. Building calendars and
   the building-mode bot keep every building group.

**Look up apartment groups in the DTEK cabinet** is enabled by default for all four operators.
Turn it off in the group settings to use only your manual choice or the sole
building group. The lookup refreshes in the background every 15 minutes and after
account data updates. It does not delay loading the cabinet or submitting readings.
Errors immediately invalidate the optional result; a result older than 15 minutes
is also unverified. No old assignment is silently reused. With several building
groups, the personal calendar then waits for confirmation or a manual choice;
the building calendars continue independently. An explicit empty response means
the cabinet has not assigned a group, not that there are no outages.

**What if the cabinet and building list different groups?** Only groups present
in both fresh responses are used automatically. For example, if the cabinet lists
3.1 and 4.1, but the building confirms only 3.1, your personal schedule and
personal-mode bot continue using 3.1. The overview and schedule explain that 4.1
is unconfirmed for this building; it is excluded from personal outage notifications.
With no matching groups, automatic personal schedules and the personal bot's
schedule notifications wait for confirmation. Check the linked building; you can
still choose a verified building group manually for the HA calendar. The personal
bot always requires a fresh cabinet match. Building calendars keep every building
group. Changing only the unconfirmed groups does not send a group-change notification.

If the legacy
service disappears or its response changes, **Settings → System → Repairs** shows
an issue for the optional account-group service with update/support links. Other
cabinet features remain independent. Optional group lookup is currently enabled
for all four operators. Kyiv oblast and Dnipropetrovsk oblast are experimental and await live validation.

A directory outage does not block cabinet data or readings. HA reports that
matching is pending and retries every five minutes. **Do not link a building**
disables automatic linking for this account until you choose a building again;
it does not delete the shared building connection.

The account device exposes **My group**, **My schedule status**,
**My outage schedule** and **My possible outage schedule**. Add the personal
calendars to your apartment dashboard; keep the building calendars alongside them
when you want to compare all groups. The building calendars and building-mode Telegram bot keep
all address groups. Different accounts can select different groups in one building.

If the building gains a second group and the cabinet does not verify a single
apartment group, only the personal calendar waits for a selection; public building
calendars and the building-mode bot keep all groups.
If a manually selected group disappears, HA switches to automatic selection only
when a fresh cabinet assignment or the building's sole verified group provides an
unambiguous replacement. HA notifies you of the change; the obsolete manual choice
is cleared so it cannot silently return later. Cabinet groups absent from the
building do not authorize replacement. If several confirmed candidates remain, choose your group
in Settings. If the public website hides group labels, the private schedule and bot can still use a cabinet-provided group after checking that it belongs to the building. Hidden groups without this confirmation, a removed building or failed verification leave the personal schedule unavailable; missing data never authorize a reassignment.
Choosing **Do not link a building** removes only the personal link and prevents automatic relinking.

<a id="changes"></a>
## Refresh and change notifications

Press **Refresh schedule** above the grid to ask DTEK for fresh building data.
The same action is available as a button on the building device. All callers share
a one-minute limit; the operator's retry delay may be longer. The grid shows the
result and keeps your selected date and group filter. Its ordinary background
updates read HA's data and do not force extra DTEK requests.

Building groups follow verified address responses automatically. Your personal
schedule follows the cabinet's verified assignment or the building's only group
when automatic selection is active. A still-valid manual selection takes priority.
Changes appear in **Home Assistant notifications**, with the previous and new
groups. They are informational messages, not Repairs. Building and personal
changes are identified separately; all building groups remain available to building-mode bot profiles.
These notices do not send Telegram messages or mobile push notifications by themselves.

The first verified group/schedule establishes a baseline. Repeated polls, group
reordering, temporary errors and recovery of the same data do not generate changes.
Comparison baselines survive HA restarts and are never used as live schedules.

For your own automations, use `dtek_monitor_schedule_changed`. It reports changes
to verified future daily intervals, including confirmed cancellations and newly
published dates, even when a new date has no outages. A publication timestamp
change, an elapsed interval, midnight rollover, a weekly forecast or lost coverage
alone does not fire this event. `dtek_monitor_groups_changed` separately reports
building group changes. [Event fields and an example](REFERENCE.md#schedule-change-events).

## Schedules without a personal cabinet

Just [add your building address](../README.md#setup). After restarting HA,
reload its page and add a built-in calendar card or the
[DTEK grid card](REFERENCE.md#schedule-card), using that building's availability
sensor and calendars. No phone login is required. Set `view: list` for a calendar
list; the default is the grid.

<a id="upcoming-times"></a>
## Upcoming times and tomorrow's schedule

Open **Settings → Devices & services → DTEK Monitor → your building** and add these
sensors to an **Entities** card. Each monitored account also has personal versions
on its account device; those use only the apartment's selected groups.

| Sensor | What it means |
| --- | --- |
| **Next planned outage (scheduled)** | The next future start in the published planned schedule. An outage already in progress is skipped. |
| **Next possible outage (scheduled)** | The next future possible start, including a weekly forecast when provided. This is not a confirmed planned outage. |
| **Outage end (scheduled)** | The end of an ongoing planned outage; when none is ongoing, the end of the next planned outage. |
| **Tomorrow’s schedule availability** | Whether tomorrow has a complete schedule, verified no planned outages, incomplete data, only a forecast, or unavailable data. |

These times describe the **schedule**, not electricity measured at home. For a
building with multiple groups, the start is the earliest future start among them.
If several groups are currently in an outage, the end sensor shows the earliest
end among those ongoing outages. It does not promise restoration for the whole
building. The `event_groups` attribute identifies the affected groups. Use the
personal sensors when you need only your apartment's group; until its selection
is resolved, personal timestamps stay unavailable.

A blank/unknown timestamp can mean there is no next event in the verified time
range. It does not mean there will be no outages beyond it. If publication stops
at an event's end, that end remains unknown: a schedule ending at midnight alone
does not confirm restoration at midnight. Missing coverage for a selected group
or a request failure makes the relevant timestamps unavailable. Saved schedules
never supply these times. [Technical status attributes](REFERENCE.md#scheduled-times)
distinguish these cases for automations.

The sensors update when a schedule changes, an event starts/ends, or the Kyiv date
changes, without extra network requests. Tomorrow's status uses Kyiv dates even
when your HA is in another timezone. It creates no extra calendar events or
Telegram messages.

Continuous outages across midnight appear as one calendar event, for example
**23:00–02:00**, when both days are verified for the same group, event type and
source. Different groups and forecasts remain separate. Native calendar titles
use HA's configured system language (English or Ukrainian, with English fallback);
the machine-readable group and event type remain unchanged.

<a id="address-works"></a>
## Address repair works

Each building also has **Address repair works** and **Repair report availability**.
Open **Settings → Devices & services → DTEK Monitor → your building** to find them.
Add a built-in **Calendar** card to your dashboard and select **Address repair works**;
add the availability sensor to an **Entities** card alongside it. No extra login or
configuration is needed. The calendar uses the same address response as the status
sensors, without additional requests.

This calendar shows repair intervals reported for the building, with the reason
and source in each event. It does not merge them into GPV schedules or filter them
by your apartment's group. Emergency and stabilization status records remain in
the address sensors, not in this repair calendar. Several repair records are kept;
identical records are shown once. It can work even when group schedules are missing.

- **DTEK reported repair works:** complete repair intervals are available.
- **No repair works in the DTEK response:** the latest successful address response
  contains no repair records. This does not confirm electricity or rule out outages.
- **Repair times are incomplete:** at least one repair lacks valid start/end times.
  The calendar is unavailable rather than inventing an end time or showing a partial
  list as complete. Check the address status/description for the available information.
- **Failed to fetch address data:** old repair events are not reused as current.
- **Repair reports not supported:** the source cannot verify these records, including
  addresses served by an external operator.

DTEK may publish a repair only after it has started. End times are estimates and can
change. Events disappear when removed from the current response: this is not a history
archive. An empty future calendar does not guarantee that no repairs will occur.
This calendar does not automatically enable new Telegram notifications.
