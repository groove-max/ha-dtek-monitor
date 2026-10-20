# Personal accounts and My DTEK

**English** · [Українська](PERSONAL_ACCOUNT.uk.md) · [Installation](../README.md#installation)

Connect your **DTEK household cabinet** to see your
address, meter, readings and consumption in Home Assistant. You can also send
readings after checking and confirming them. This connection is optional: outage
schedules by address work without a phone login or energy sensor.

This guide covers **DTEK Monitor 2**. Read the [installation, upgrade and
rollback instructions](UPGRADING.md) before installing it.

[Schedules and groups](SCHEDULES.md) · [Readings, sensors and reminders](ENERGY_AND_READINGS.md)

- [Connect your cabinet](#section-1)
- [My DTEK workspace](#section-2)
- [Apartment and cabinet settings](#section-3)
- [Registration and SMS recovery](#section-4)
- [Manage household accounts](#section-5)
- [Available data](#section-6)
- [Change accounts and refresh](#section-7)
- [Several accounts and dashboards](#section-8)
- [Account profile: address, EIC and meter](#section-9)
- [History and monthly chart](#section-10)
- [Show or hide the account number](#section-11)
- [Dashboard card](#section-12)
- [Building monitoring and the Telegram bot](#section-13)
- [If DTEK changes its API](#section-14)
- [Current limits](#section-15)

**Experimental regions:** Kyiv oblast and Dnipropetrovsk oblast cabinets are enabled, including sign-in, registration, account management, readings and apartment-group lookup. These functions use the shared API but have not yet been checked with real linked accounts in those regions. Verify the address, meter and tariff zones before confirming changes. Report problems in [GitHub Issues](https://github.com/groove-max/ha-dtek-monitor/issues), with the operator, HA/integration versions and redacted diagnostics; do not attach credentials or full account details. A failed group lookup does not block meter data.

<a id="section-1"></a>
## Connect your cabinet

1. Open **Settings → Devices & services → Add integration → DTEK Monitor**.
2. Select your distribution operator. Kyiv city (**ДТЕК Київські електромережі**) and Kyiv oblast (**ДТЕК Київські регіональні електромережі**) are separate options.
3. Select **Personal account and meter readings**. For schedules without a login, select
   **Outage schedules by address** instead.
4. Choose **Sign in**, **Create a DTEK account** or **Forgot your password?**.
   For sign-in, enter the phone number and password used on the DTEK website.
5. Choose accounts to monitor, or add a household account to DTEK first.
6. Open the devices created under the new personal account connection.

For Kyiv city, enter either the modern 12-digit account number starting with **452** or the older 11-digit number. DTEK resolves the old number to its current account. Check the returned number and address before confirming; if several accounts match, choose yours. HA stores the current number. Sign in separately to each operator, even when using the same phone number.

New connections show the operator name and the last four digits of your phone
number in the integration list. **Open DTEK cabinet** in the reading form and the
device's website link open that operator's cabinet. Opening the link does not
submit readings or transfer your HA login to the website.

Home Assistant stores the login credentials in its configuration; protect your
configuration and backups. Authentication cookies and API tokens are held in
memory. If authentication expires, use Home Assistant's reauthentication flow
with the same DTEK account.

<a id="section-2"></a>
## My DTEK workspace

The setup completion screen explains the next steps. Finish setup, reload the
HA page, then open your dashboard → **Edit dashboard → Add card** and search for
**My DTEK**. Choose your account in the visual editor and save. The integration
loads its cards automatically; manual resource registration is not needed.
Existing standalone cards remain supported.

If you connected an empty cabinet, first open **Settings → Devices & services →
DTEK Monitor → Configure** to add or select accounts. You do not need to sign in again.

You can use the cabinet and enter readings **without a home energy sensor**.
To add sensor suggestions later, open **My DTEK → Settings → Home energy meter**.
The expandable **Getting started** section explains account selection, sensor
references and building groups. It does not open automatically or change settings.

The YAML equivalent is optional:

```yaml
type: custom:dtek-account-workspace-card
entity: sensor.example_account_data_updated
show_account_selector: false
```

Choose your real account in the visual editor. With no initial account configured,
a sole connected account opens automatically; multiple accounts require a choice.
Enable the account selector to switch within this card. To keep separate apartment
panels, set an account on each card and disable its selector. There is no global
active account.

- **Overview:** address, latest cumulative reading, separately labelled monthly
  consumption, and personal schedule status. **Enter readings** is below the
  latest reading; **View schedule** is inside the group block.
- **Schedule:** your group or all building groups. These views do not change the
  building calendars used by the Telegram bot.
- **Readings:** manual entry or an explicitly inserted sensor suggestion, review,
  confirmation, submission result and an expandable reading history.
- **Consumption:** monthly consumption and comparisons, without a second reading list.
- **Settings:** account/EIC/meter details, sensor setup, integration settings and
  the optional local check journal.

Tabs preserve unfinished input. Switching accounts asks before discarding an edit;
while a submission is pending, switching is blocked. HA updates never insert new
sensor readings into an edited form. Users without submission rights can view
history without being offered a submission form.

### Interface examples

These screenshots use fictional accounts and readings.

![My DTEK overview with separate cumulative readings and monthly consumption](images/my-dtek-overview.en.png)

<details>
<summary>Schedule, readings and settings</summary>

![Operator schedule grid with building and apartment groups highlighted](images/my-dtek-schedule.en.png)

![Readings form with an optional home sensor suggestion](images/my-dtek-readings.en.png)

![Settings grouped by apartment, cabinet and optional energy sensor](images/my-dtek-settings.en.png)

</details>

<a id="section-3"></a>
## Apartment and cabinet settings

In **My DTEK → Settings**, choose the action you need:

- **Building and outage group** opens the building/group selection for the
  apartment shown at the top of the panel. Every building group remains available
  to the building calendars and Telegram bot.
- **Reading reminders** controls the reminder time and optional sensor estimate
  for this account. **Meter notifications** controls verification/replacement
  notices. Both appear in Home Assistant.
- Under **DTEK cabinet**, **Add or unlink an account** manages links in the
  cabinet. **Choose accounts to monitor** selects the accounts HA loads.
  These actions apply to the cabinet, not just the apartment on this panel.
- **Additional settings → Scheduled reading checks** configures local checks
  without submitting readings.

Forms open over the panel and retain edits during HA updates. Opening a form
never saves settings. If readings or sensor setup are unfinished, choose to keep
editing or explicitly discard that draft first. Canceling an edited settings form
also asks before discarding it. A lost save response is not retried automatically:
close the form and check its settings before trying again.

Choosing an account on a card only changes that card. Selecting accounts for HA
monitoring controls which entities HA loads; deselecting an account removes its
monitored entities but keeps the DTEK cabinet link and local sensor references.
Unlinking from the cabinet is a separate confirmed action. These settings require
an HA administrator. If a form cannot load, its fallback link opens the integration
settings separately.

<a id="section-4"></a>
## Registration and SMS recovery

Both flows are available in the HA setup wizard after choosing a personal account.
Opening a form sends nothing. Submitting your phone number requests a four-digit
SMS code from DTEK. Keep any leading zeros. Another SMS is sent only when you
explicitly request it, at least 60 seconds later; DTEK can impose a longer limit.

- **Registration:** phone → SMS → name → new password and personal-data consent.
  The account is created only at the final step.
- **Recovery:** phone → SMS → new password and an explicit confirmation to change it.
  Verifying the code does not change the password. Cancel the final step to keep
  your current password. After a successful change, HA signs in with the new
  password and updates the matching connection if one already exists.

Passwords need 8–64 characters, at least two uppercase letters, one lowercase
letter and one digit, with no spaces. SMS codes and challenge identifiers are
not saved in configuration. The SMS setup session closes after 15 minutes of
inactivity. If the response to a password change is lost, HA does not repeat the
request: try signing in with the new password or use official password recovery.

<a id="section-5"></a>
## Manage household accounts

After signing in, choose existing accounts to monitor or **Add an account to DTEK**.
A newly registered cabinet can be empty: add an account now or finish setup and
return later through **Configure → Household accounts in the DTEK cabinet**. No sensors are created
until you select an account for monitoring.

There are three independent choices:

- **DTEK links:** add or unlink an account in the operator's cabinet.
- **HA monitoring:** select which linked accounts create devices, sensors and calendars.
- **Dashboard display:** choose an account on each card; different panels may show different accounts.

To add an account, enter its modern 12-digit household number starting with `572`
for Odesa oblast, `452` for Kyiv city, `842` for Kyiv oblast, or `12` for Dnipropetrovsk oblast. Kyiv city also accepts an old 11-digit
number and looks up the current number through DTEK.
HA looks up the address; verify the full number and address, then explicitly
confirm. Only confirmation sends the linking request. Afterwards, choose whether
HA should monitor it. Other legacy formats and business accounts must be managed
on the DTEK website for now.

To unlink, first deselect the account in **Choose personal accounts**, save and
wait for HA to reload the connection. Then open **Household accounts in the DTEK cabinet → Unlink from the DTEK cabinet**, select the account and confirm its address. Unlinking removes
it from your DTEK cabinet; it does not close the electricity contract. An account
still monitored by another HA connection cannot be unlinked here.

You may deselect every account: the authenticated connection remains available
for account management. Deselecting does not unlink anything at DTEK. Stored
energy calibration and submission records are retained, while HA entities for
deselected accounts are removed. Existing building monitoring is independent.

Confirmation expires after five minutes. A failed or uncertain linking/unlinking
request is never retried automatically. If its result is unknown, check the
account list in the DTEK cabinet before starting another attempt.

Official [registration](https://auth.my.dtek-oem.com.ua/signup) and
[password recovery](https://auth.my.dtek-oem.com.ua/recovery) remain available
if DTEK changes its API. This integration uses the official website's requests,
not a documented public API.


<a id="section-6"></a>
## Available data

- Recorded meter readings and their dates, separately for each returned tariff
  scale. These use DTEK's unblocked **previous** readings, not pending input.
- Consumption for the latest available closed month, with a `period` attribute.
- Meter model and the year of the next verification.
- The time the account data was successfully fetched.

Updates run every six hours. These are billing records, not live electricity
measurements. A new fetch does not mean a new meter reading. Missing data stays
unknown, and unavailable accounts do not report zero consumption.

Monthly corrections can be negative. Historical records do not currently feed
the Energy dashboard: the integration deliberately sets no statistics `state_class`.
Historical statistics need a separate implementation that respects reporting
dates and retrospective corrections.

One meter per household account is supported initially. Returned tariff scales
are kept separate. Odesa single-zone and Kyiv city Day/Night data have been read
from live accounts. Actual submission has been verified only for the Odesa
single-zone case; two-zone submission uses automated tests. Business accounts are not supported. Kyiv oblast and Dnipropetrovsk oblast cabinets, including apartment-group lookup, are enabled experimentally; authenticated household data has not been verified live for these two regions.

<a id="section-7"></a>
## Change accounts and refresh

Choose **Configure → Select personal accounts** on the personal account connection.
The list is fetched when the form opens and stays unchanged while you edit it.
You may deselect every account and keep the cabinet connected for account management. Saving reloads only this connection. Entities
and devices belonging only to deselected accounts are removed; automations using
those entities will need updating. The DTEK website's linked accounts are not changed.

Each account device has a **Refresh all accounts** button. It updates all selected
accounts in that connection. A shared 60-second limit applies after any refresh
attempt, including automatic refreshes and failures. A failure leaves affected
sensors unavailable; successfully refreshed accounts remain usable. The time of
fetching data is distinct from the date of the recorded reading.

<a id="section-8"></a>
## Several accounts and dashboards

One phone login can contain several personal accounts. **Configure → Select personal
accounts** determines which ones HA monitors. Each selected account has its own HA
device, readings, calendars, energy binding, reference pairs, reminders and check
schedule. Connecting a second account does not copy the first account’s sensor or
calibration. Bind a cumulative grid-import source for the correct apartment.

Dashboard visibility is a separate choice:

- Monitor two accounts and show only one: leave both selected in the integration,
  then add cards for the account you want to see.
- Show both together: add a separate set of cards for each account.
- Use two dashboards or views: select the appropriate account in each card.

The visual editors for the number, history, readings and check-journal cards have
a **Personal account** list with the masked number and address. There is no global
active account. Changing one card never redirects another card’s readings or
changes which accounts the integration monitors. A missing account stays selected
until you explicitly choose another; it never falls back to the first account.
Use **Refresh account list** after adding accounts in the integration settings.
Only connected accounts readable by your HA user appear in this list; to connect
another account, use the integration’s **Select personal accounts** form.

Existing YAML still works: `entity` may be any enabled entity belonging to the
intended account. You can rename HA devices to distinguish apartments. Hiding a
card or dashboard does not revoke access to its entities; HA permissions remain
responsible for access control.

<a id="section-9"></a>
## Account profile: address, EIC and meter

Choose **DTEK account profile** in the card picker for a standalone profile, or
open **Account and meter details** in My DTEK. Its visual editor selects one connected account independently
of every other card. A manual example:

```yaml
type: custom:dtek-account-profile-card
entity: sensor.example_account_data_updated
```

The full address, including the apartment when DTEK provides it, is always visible.
The card shows the meter model, tariff scheme, contract power and next verification
year. Expand **Meter details** for manufacture, installation and verification dates,
agreement details, seals and the number of replacement records. Open the official
cabinet to see individual replacement records; these details are not yet displayed
in HA.

An **EIC identifies a distribution point**, not a meter number, account number or
outage group. All EICs returned for the account are kept; the current installation's
EIC is labelled separately. These codes do not determine an apartment's outage group.

Account, EIC, meter and seal numbers start masked. Reveal them explicitly and use
**Copy**, or hide them before sharing a screenshot. The address itself stays visible:
check it before sharing. Masking is a display preference; HA read permissions protect
access. Full numbers are not added to entity names or sensor history. The account
profile requires the same account-wide read permission as the history card.

Profile data uses the existing six-hour cabinet refresh. **Refresh**
reads the latest HA cache; use the account device's refresh button to fetch new DTEK
data. Missing optional fields show **Not provided**, not zero. Failure to fetch meter
details does not discard valid readings; old cached data is labelled with its date
when the overall account refresh fails. Profile display does not require permission
or eligibility to submit readings.

### Check whether readings appear in the cabinet

**Check whether DTEK has these readings**, beside a submission result in the
readings card, performs a fresh, rate-limited read. When this HA has a
submission record, it compares every submitted tariff scale with the cabinet's
active-energy records for the same reading date in Kyiv. The result distinguishes
all scales matching, partial matches, multiple possible matches and no match yet.
The separate reading history retains record statuses and sources. An unmatched record is
not proof of rejection; DTEK may publish later or assign another reading date.

A match is evidence of a corresponding account record, **not proof that this specific
request created it or that a monthly settlement is final**. Historical rows do not
identify their individual meter. A known change from the submitted meter is reported
separately. Checking never repeats a submission, changes calibration or acknowledges
an uncertain delivery. If this HA has no submission journal, use Reading history
to view cabinet records. The profile does not duplicate them.

### Optional meter notifications

Open **Configure → Meter verification and replacement**, select the account and
enable either notification. Both are off by default and independent of reading
reminders. These are local HA notifications, visible to users of that HA, with a
masked account number; no private account data is sent to the building bot.

- **Verification:** one notice in the listed year, then one per following calendar
  year until DTEK updates the information. A year alone cannot establish the exact
  deadline or whether verification is overdue; check with the operator.
- **Meter number change:** establishes a baseline on the first successful observation
  and reports later changes, including after a restart. Missing metadata never resets
  the baseline. A change can mean a replacement or a cabinet correction. Check the new
  meter and explicitly set new energy reference readings; old bindings are not moved.

Notices follow the six-hour profile refresh. Dismissal survives restarts. Disabling
a notification removes it; re-enabling verification may show the current year's
notice again. Changes observed while replacement notices are disabled establish a
new baseline rather than a backlog of alerts.

<a id="section-10"></a>
## History and monthly chart

The bundled **DTEK account history** card shows an account's readings and monthly
consumption for a selected year. Each card belongs to one account. It uses your
Home Assistant session and requires permission to read the configured entity
and all sensors of that account; the browser never receives your DTEK password or API tokens.

Choose **DTEK account history** in the card picker and select its account.
The module is loaded automatically. For manual configuration, replace the entity
below with **Account data updated** from the desired account device.

```yaml
type: custom:dtek-account-history-card
entity: sensor.example_account_data_updated
title: My DTEK account
```

Choose a year in the card; optionally set `year: 2025` in its configuration to
start with that year. The default is the current year in Kyiv. The month table
below the chart also shows returned tariff-zone values. The readings table has
ten rows per page and shows Kyiv dates, values, scale, energy type, source and
status. **Active**, **inactive**, **blocked** and **unknown** reflect DTEK's flags;
inactive does not necessarily mean a rejected submission. Inactive records are hidden by default; blocked and unknown statuses stay visible. Select **Show all DTEK records** to include inactive records. The selection survives refreshes and HA state updates. Filtering applies before pagination and never merges equal readings across dates or tariff zones. It does not modify monthly consumption, source history or submission verification.

Only closed months are plotted. Zero is a real returned value; a gap means no
data was returned. Open months are labeled separately. Negative corrections
remain negative. The API does not identify the meter for each historical row,
so the integration does not associate old readings with the current meter or
calculate consumption from their differences across replacements.

History loads when the card opens or the year changes. Results are cached in
memory for up to six hours, with at most 16 account/year combinations per
connection. **Refresh history** requests a replacement result, including revised
past months; it is separate from the device's **Refresh all accounts** button.
Repeated history fetches for the same account/year are limited to once per
60 seconds. A DTEK rate-limit response pauses history requests for five minutes.
After a failed refresh, any retained result is explicitly labeled with its
original fetch time. Reloading the connection clears the cache.

History is not stored as sensor attributes or imported into Energy statistics.
An empty year is shown explicitly. More than 1,000 returned rows or 20 API pages,
inconsistent pagination, or malformed data produces an error instead of a
silently truncated history. Older years are available only when DTEK returns them.

### Compare the same periods

Choose a year and press **Compare with previous year**. The card compares monthly,
yearly and seasonal official consumption using only months that are closed and
published in **both** years. A partial yearly/seasonal total explicitly lists its
included months. Missing periods are not zero; negative DTEK corrections are retained.
Winter is explicitly grouped as January, February and December of the same calendar
year, not a continuous December–February season. Both fetch dates are shown.

These are dated **consumption** figures from DTEK, not cumulative meter readings and
not estimates from the bound HA source. The comparison fetches the preceding year's
history on demand and uses the same cache and rate limits as other history reads.

<a id="section-11"></a>
## Show or hide the account number

The history and submission cards include an eye button next to **Account number**.
Numbers start masked. Choose **Show account number** to request the full number
using your HA session; choose **Hide account number** before taking a screenshot.
This works for users with permission to read all sensors of that selected account,
without requiring administrator rights. Submission still requires an administrator.

This is a display convenience, not password protection. The full number is not
added to sensor states, attributes, device names or browser storage. Hiding it
clears the displayed value; rebuilding/closing the card masks it again. Toggling
the eye does not reset reading inputs, selection of the year or pagination.
The eye controls the account number only; an address or meter serial shown on
the same card is still visible.

For a dashboard using standard cards, add this compact card alongside them:

```yaml
type: custom:dtek-account-number-card
entity: sensor.example_account_data_updated
```

The integration loads this card automatically. Existing entity IDs and masked
device labels are unchanged.

<a id="section-12"></a>
## Dashboard card

Add a manual card to a private dashboard. Replace every example entity ID below
with the IDs from your account device. This uses only built-in Home Assistant
cards. Duplicate the card for additional accounts; add reading/date rows for
each tariff scale when needed.

```yaml
type: entities
title: DTEK personal account
show_header_toggle: false
entities:
  - entity: sensor.example_recorded_reading
    name: Recorded reading
  - entity: sensor.example_reading_date
    name: Reading date
  - entity: sensor.example_latest_closed_month_consumption
    name: Monthly consumption
  - type: attribute
    entity: sensor.example_latest_closed_month_consumption
    attribute: period
    name: Consumption month
  - entity: sensor.example_account_data_updated
    name: Data fetched
  - entity: sensor.example_meter_model
    name: Meter model
  - entity: sensor.example_next_verification_year
    name: Next verification year
  - entity: button.example_refresh_all_accounts
    name: Refresh all accounts
```

<a id="section-13"></a>
## Building monitoring and the Telegram bot

Common address abbreviations, such as `вул.`/`вулиця`, `пров.`/`провулок` and
`с.`/`село`, are matched against the operator's directory. Similar street names,
different settlement types, district qualifiers and building sections are not
interchangeable. If the address cannot be matched uniquely, select the building
in **Settings → Building and outage group**.

Building monitoring connects automatically after an unambiguous match in the
operator's directory. If it needs confirmation, open **My DTEK → Settings →
Building and outage group → Choose another building from the directory**.
Choose the city, street and house. Existing building connections are reused;
apartment numbers and cabinet credentials never enter the public address entry.

The building is independent: removing or reauthorizing a cabinet does not remove
its address monitoring. Several apartments can share one building while keeping
separate personal group choices. Changing an apartment's group never removes
other building groups. [Group selection and schedule display](SCHEDULES.md).

Configure [DTEK Telegram Bot](https://github.com/groove-max/ha-dtek-telegram-bot) separately for a building or personal account. Building mode supports channels, groups and private chats and retains all building groups.

**Monitor 2.0.0-rc2 or newer and bot 0.5.0-rc2 or newer** support personal mode: cabinet API groups, reminders, reading history, confirmed submissions and an all-groups PNG table. It works only in the explicitly assigned user’s private chat. DTEK credentials stay in the integration; the HA administrator configures profiles and permissions. Calibration and detailed settings stay in My DTEK. [Personal bot setup](https://github.com/groove-max/ha-dtek-telegram-bot/blob/main/docs/PERSONAL.md).

Installing the integration does not create Telegram profiles or change existing recipients or physical sensors. Older Monitor 2.0.0b1 and bot 0.4.1 do not include personal Telegram mode: update both projects to use it.

<a id="section-14"></a>
## If DTEK changes its API

The cabinet currently combines `/api/billing/joint` for linked accounts and
`/api/billing-service/api` for meter information. The official website still uses
both; `joint` is not known to have an announced retirement date. The integration
does not use the old account-number conversion API.

If a known service route disappears (404), DTEK explicitly retires a supported
route (410), or the account-list response no longer matches its expected format,
HA creates a persistent **Settings → System → Repairs** notice. It identifies the
affected interface and links to [integration releases](https://github.com/groove-max/ha-dtek-monitor/releases)
and [Issues](https://github.com/groove-max/ha-dtek-monitor/issues). Update the
integration; if the latest version is affected, report the interface and reason
shown there, without passwords, tokens or full account numbers.

A timeout, rate limit, failed login or missing account is not labelled as API
retirement. The notice says the interface may have changed: an HTTP response alone
cannot prove DTEK's intention. Repeated failures reuse the same notice, and a
successful request to the affected operation clears it. Other working operations
do not hide it. Detection occurs when HA uses that operation; it does not send
extra account changes or meter readings to probe availability.

<a id="section-15"></a>
## Current limits

- Personal cabinets: household accounts in all four regions. Kyiv oblast and Dnipropetrovsk oblast are experimental, including apartment-group lookup. Public address schedules still support all four listed operators.
- One consumption meter per account; submission supports one zone or Day/Night. Live reading and form checks cover Odesa single-zone and Kyiv city Day/Night accounts. Only Odesa single-zone submission was performed live; Day/Night submission has automated tests.
- No automatic reading submissions, payments, applications, profile editing or photo uploads. Use the official cabinet for unsupported meter schemes, replacements and corrections.
- Billing history does not populate HA's Energy dashboard. Monthly consumption and cumulative readings are different values.
- Automatic building matching happens for newly monitored accounts. Existing manual links are preserved; changed cabinet addresses do not silently move your building connection.
- HA cabinet reminders and optional personal Telegram reminders have separate settings; enabling one does not enable the other.

## If something does not work

| Situation | What to do |
| --- | --- |
| My DTEK is missing from the card picker | Restart HA after installation, then reload the page. Add the card through dashboard editing; a separate sidebar dashboard is not created automatically. |
| Cabinet connected but no accounts appear | Select accounts to monitor in integration settings, or first add an account to the DTEK cabinet. |
| A card still refers to a removed account | Choose the intended account in the card editor. It never silently switches to another apartment. |
| The address appears but there is no schedule | Check building-link status; confirm the building and group in Settings if requested. An unpublished schedule is different from a request error. |
| HA requests sign-in again | Reauthenticate the same cabinet. Do not remove the connection for a temporary outage. |
| I cannot submit readings | An HA administrator, a supported available meter and unblocked input are required. Read the reason shown in the form. |
| I do not know whether readings were accepted | Check submission status and the DTEK cabinet. Do not blindly repeat the send. |
| My sensor is available but there is no suggestion | Check the apartment, tariff, units, freshness and possible counter reset; see the sensor guide. Do not extend the age limit just to hide connection loss. |

Reading requires access to the account's entities. Submission, sensor bindings
and settings changes require an administrator. Hiding a card or masking a number
is a display choice, not access control. HA reminders are visible to users of
this HA installation; they are not private chat messages.
