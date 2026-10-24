# DTEK Monitor reference

**English** · [Українська](REFERENCE.uk.md) · [Start here](../README.md)

<a id="entities"></a>
## Find the correct entity IDs

Open **Settings → Devices & services → DTEK Monitor → your device**. Copy entity IDs from there; a display name and an entity ID are different.

New regional entries use a stable prefix such as `dtek_krem_<address_hash>`. Odesa and older entries may retain IDs derived from their original names. Do not rename all entities just to match an example. The Telegram companion discovers supported prefixes automatically.

| Purpose | Typical ID suffix; older IDs can differ |
| --- | --- |
| Reported power state | `binary_sensor.<prefix>_power` |
| Outage classification | `sensor.<prefix>_outage_status` |
| Description, start, end | `sensor.<prefix>_outage_description`, `_outage_start`, `_outage_end` |
| Primary/all groups | `sensor.<prefix>_primary_schedule_group`, `_all_schedule_groups` |
| Source timestamps | `sensor.<prefix>_dtek_last_update`, `_schedule_changed` |
| Connection diagnostics | `sensor.<prefix>_dtek_connection` |
| Planned/possible calendars | `calendar.<prefix>_outage_schedule`, `_possible_outage_schedule` |

Find **Last known schedule (view only)** by its display name. Use live calendars for automation and the saved one for reference.

The reported power sensor uses `on`/`off`; a failed address request makes it unavailable. Outage types are `ok`, `emergency`, `planned` and `stabilization`. If DTEK lists several active outages, the primary status uses the most severe one. Additional `outage_N_*` attributes preserve individual descriptions and times.

Repair reports have a separate **Address repair works** calendar and **Repair report availability** sensor. Find their actual IDs on the building device; new regional entries use `_address_works` and `_address_works_status`. These reports use address freshness, not GPV publication coverage. [Setup and status meanings](SCHEDULES.md#address-works).

<a id="freshness"></a>
## Freshness and calendar automations

A recent HA state change is not enough to establish that a schedule is current. On the group sensor, inspect:

| Attribute | Meaning |
| --- | --- |
| `schedule_groups` | Complete list of address groups; do not assume the scalar primary group is exhaustive. |
| `group_labels_visible` | Whether DTEK shows group labels on its public website (`showUserGroup`). Source metadata only: `false` does not hide returned IDs or block a published schedule in HA. |
| `provider_id`, `address_id` | Source identity; prevents mixing different operators/addresses. |
| `schedule_notifications_ready` | Whether the schedule passed the current address/group verification. |
| `schedule_snapshot_id` | Identity of the verified schedule snapshot. |
| `schedule_coverage` | Published date ranges for each group and interval kind. |

Live calendars and the diagnostic sensor also expose `data_status` (`current`, `stale`, `missing`), `last_verified_at`, `source_updated_at`, `schedule_state` and `schedule_reason`.

For custom schedule notifications:

1. Require `schedule_notifications_ready == true`.
2. Read groups, source identity and snapshot ID, then fetch calendar events.
3. Check that those values still match before sending.
4. Preserve each event's group from its description, such as `Planned; group=GPV3.1`.
5. Treat an empty result as “no planned outages” only when the relevant dates are fully covered for the selected groups.
6. Never use a calendar/event marked `usage=display_only` as fresh notification input.

[DTEK Telegram Bot](https://github.com/groove-max/ha-dtek-telegram-bot) performs these checks for its schedule notifications. Using it avoids having to reproduce this coordination in your own automation.

A calendar can be available while some future dates remain unpublished. `coverage_start`/`coverage_end` bound the stored snapshot; **they do not mean every date inside is published**. Use `schedule_coverage` for publication coverage. A query wholly outside published coverage fails instead of returning an all-clear result.

All schedule calculations use the Kyiv timezone; HA accepts timezone-aware query boundaries, including UTC. Possible windows are shown only when applicable published data exists. Old weekly presets are not projected indefinitely.

### Publication status is different from a request error

**DTEK connection = OK** means the requests and response validation succeeded.
The **Schedule availability** sensor describes today's planned schedule separately:

| State | Meaning |
| --- | --- |
| `current` | A complete verified schedule contains planned outages today. |
| `empty` | Every group has complete dated coverage and no planned outages today. |
| `forecast` | Only a forecast is available; it does not confirm planned outages. |
| `partial` | Coverage is incomplete; missing intervals are not an all-clear. |
| `missing` | No complete applicable schedule was verified. |
| `unpublished` | DTEK explicitly disabled publication. |
| `unsupported` | The address belongs to an unsupported operator. |
| `error` | An address/schedule request failed or returned invalid data. |

`status_date` and `status_timezone` scope the description to a day in Europe/Kyiv.
This describes a schedule, not actual power presence. Publication gaps do not
increase the network failure count or trigger error backoff. Actual failures do.
Live calendar entities still use HA's `unavailable` state when there is no usable
calendar; the separate status explains why. Previously saved events remain for
reference only and never establish an outage-free day.

<a id="scheduled-times"></a>
### Scheduled times and tomorrow's status

Building timestamp suffixes are `_next_planned_outage`, `_next_possible_outage`
and `_scheduled_outage_end`. Find their actual IDs on the device; account devices
have corresponding personal entities. These use HA's `timestamp` device class,
so HA displays them in the viewer's timezone. [Meanings and setup](SCHEDULES.md#upcoming-times).

`event_status` explains a missing timestamp:

| Value | HA state and meaning |
| --- | --- |
| `scheduled` | A timestamp within continuously verified coverage. |
| `no_event_in_coverage` | `unknown`: no future event before `verified_until`; no claim beyond that boundary. |
| `end_unconfirmed` | `unknown`: the candidate end meets a publication boundary or another continuing outage. |
| `missing_coverage` | `unavailable`: at least one selected group lacks coverage at the current time. |
| `unavailable` | `unavailable`: a failed request or unusable schedule; no saved values reused. |
| `no_groups` / `group_selection_unavailable` | `unavailable`: no verified groups or unresolved personal selection. |

`event_groups` identifies the groups for the displayed start/end, `schedule_sources`
distinguishes `daily` and `weekly`, and `ongoing_scheduled_outage` indicates whether
the end belongs to an ongoing event. `basis` is always `schedule`. A building end
is the earliest end among ongoing outages, or among the next outages starting
together. It is not a prediction for every group or a measurement of actual power.
The search stops at the first coverage gap in any selected group.

`_schedule_tomorrow_status` uses the same states as today's availability sensor,
with `status_date` set to tomorrow in Europe/Kyiv. The personal version also
retains group-selection statuses and prefixes publication states with `schedule_`.
These entities update at event/coverage boundaries and Kyiv midnight without
marking network data as freshly fetched. Existing calendar entity IDs, event
types and `group=…` descriptions remain compatible with the Telegram bot.

### Schedule card

The integration loads its cards automatically. Reload the HA page after setup and add a manual card; no separate JavaScript resource registration is needed:

```yaml
type: custom:dtek-schedule-card
title: Building — all groups
status_entity: sensor.example_schedule_availability
entities:
  - calendar.example_outage_schedule
  - calendar.example_possible_outage_schedule
```

Use your device's actual entity IDs. For an apartment, use its **My schedule
status** sensor and its personal calendars in a second card. The building card
retains all groups for the bot. This card uses English/Ukrainian UI text and the
built-in HA calendar; it does not change your automations or personal selection.

### Saved schedules

A successful, complete verification stores concrete events in Home Assistant storage for an eight-day horizon. An unchanged successful result refreshes the verification time; a failed request does not. Restoring this snapshot after a restart never makes the live sensors/calendars current. There is no “45-minute fresh data” exception.

<a id="diagnostics"></a>
## Diagnose unavailable data

To attach a diagnostic file to an issue, open **Settings → Devices & services → DTEK Monitor**, find the affected connection, and choose **Download diagnostics** from its three-dot menu. This works for both address and personal-account connections, including connections that could not finish setup.

The DTEK section contains refresh status, timestamps, retry/protection counters, schedule publication flags and counts. For a personal account it shows how many accounts are selected, whether cached data is present and whether building links are configured. Cached data does not imply a successful current refresh: check `last_update_success` too. Credentials, addresses, account numbers (including suffixes and hashes), EIC codes, readings, raw responses and error text are omitted. Home Assistant also adds system and integration information. Review the complete file before publishing it.

Open **DTEK connection** on the device page, including its attributes:

- `address_last_success`, `address_error`: address/status requests.
- `schedule_last_success`, `schedule_error`: schedule requests.
- `last_success`, `last_error`, `consecutive_failures`: combined polling health.
- `retry_interval_seconds`: current retry interval in seconds, not a remaining-time countdown.
- `snapshot_storage_error`: problems saving/loading the reference copy.

Repeated failures remain visible in diagnostics even while other entities are unavailable. Failed refreshes back off to roughly 1, 2, 4, 8 and 10 minutes, with small timing variation. Success restores the configured polling interval.

Public website requests also share one queue and failure pause per operator across all addresses, setup dialogs and reloads. Completed operations are spaced by at least one second; the existing bounded page/CSRF handshake stays inside an operation. After a failed operation, no other address retries that operator for 1, 2, 4, 8 or at most 10 minutes. A server `Retry-After` can extend this to at most one hour. Suppressed calls do not extend the pause; a successful operation resets it. Other operators and personal-cabinet requests remain independent. Reloading an address does not bypass the pause.

The connection attributes `public_retry_in_seconds` and `public_consecutive_failures` describe this shared state at the last entity update. They are also included in diagnostic downloads; the remaining time is not a live countdown.

Check the same address on the operator's website. If it also fails, wait for the source to recover. If it works there, inspect HA logs under the integration name for transport, website-protection or parsing errors. Do not reduce the polling interval as a workaround for website protection.

When reporting a problem, include versions, operator, timestamps with timezone and sanitized error text. Logs/screenshots can contain your exact address; remove anything you do not want public.

<a id="updates"></a>
## Updates, backup and removal

1. Make a Home Assistant backup before an upgrade.
2. Read the [changelog](../CHANGELOG.md), update via HACS or replace the integration folder, then restart HA.
3. Verify the connection, address and calendars after the restart. Update the companion bot when its release requires newer integration attributes.

Existing entries migrate automatically; version 2.0 uses config-entry schema version 4. Address-based identity is designed to preserve entity IDs across upgrades. Manual renames still take precedence. Do not delete and re-add entries as a normal upgrade step.

A full HA backup preserves configuration entries, entity registries and saved snapshots. Do not edit files under `.storage` manually. Removing an integration entry removes its active entities from use; update dependent dashboards, automations and bot addresses accordingly.

<a id="architecture"></a>
## Where the data comes from

The integration reads the selected operator's public shutdowns website. It is not built on a guaranteed public DTEK API contract; website changes can require an update.

| Module | Responsibility |
| --- | --- |
| `providers.py` | Supported operators and their endpoints. |
| `provider.py` | Provider interface and normalized address/schedule types. |
| `dtek_provider.py`, `dtek_client.py` | DTEK website transport and response normalization. |
| `config_flow.py` | Operator/address setup and polling options. |
| `coordinator.py` | Refreshes, verification, retries and diagnostics. |
| `schedule.py`, `snapshot.py` | Interval rules, publication coverage and saved data. |
| `sensor.py`, `binary_sensor.py`, `calendar.py` | HA entities. |

For development and verification, see [Contributing](../CONTRIBUTING.md).

## Cabinet, readings and upgrading to 2.0

[Cabinet and dashboard](PERSONAL_ACCOUNT.md) · [Readings and sensors](ENERGY_AND_READINGS.md) · [Grid and groups](SCHEDULES.md).

[Back up before updating to the beta](UPGRADING.md). Returning from 2.0 to 1.7.0 requires restoring the earlier configuration and code, not just reinstalling the old release.

<a id="schedule-change-events"></a>
## Schedule change events

`dtek_monitor_schedule_changed` contains `entry_id`, `provider_id`, `groups`,
`changed_groups`, `revision` (content fingerprint) and `source_updated_at`.
It concerns the public building's verified future daily schedule; filter
`changed_groups` if your automation is for one apartment. The existing schedule
publication timestamp sensor keeps its meaning and the bot's contract is unchanged.

`dtek_monitor_groups_changed` contains `entry_id`, `provider_id`,
`previous_groups` and `groups`. It concerns the building, not a private account.
Neither event contains credentials, account numbers or meter readings.

Listen for these events in **Developer tools → Events** to find your building's
`entry_id`, then use it to limit an automation:

```yaml
alias: DTEK schedule changed
triggers:
  - trigger: event
    event_type: dtek_monitor_schedule_changed
    event_data:
      entry_id: YOUR_BUILDING_ENTRY_ID
conditions: []
actions:
  - action: persistent_notification.create
    data:
      title: DTEK schedule
      message: "Updated groups: {{ trigger.event.data.changed_groups | join(', ') }}"
mode: queued
```

The first verified schedule is a baseline, not an update notification. Events do
not fire for source timestamp changes, routine expiry, midnight rollover, missing
coverage or weekly forecasts alone. Newly verified dates can trigger a change,
including a published empty day. [User-facing behavior](SCHEDULES.md#changes).

The building's **Refresh schedule** button (`schedule_refresh` unique-ID suffix)
queries the public provider. The grid uses `dtek_monitor/schedule_refresh` with its
status `entity_id`, requiring control permission on that entity and read access to
both associated calendars. All manual requests for a building share a one-minute
limit and respect operator-wide cooldowns. A successful request without a published
schedule stays distinguishable from a request failure or a verified empty day.
