# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

- Integrate FastivProService's compact daily timeline from PR #12 as a built-in dashboard card. Add automatic loading, a permission-aware building picker, English/Ukrainian UI, shared grid validation/time helpers and browser regressions. Keep demos/YAML in examples; no manual JS resource installation is required.

## [2.0.0-rc4] - 2026-10-23

**Regular GitHub release**, without the Pre-release flag. Available through the standard HACS update channel. Requires HA 2026.3.0+.

- Attach optional meter photos in My DTEK or Telegram Bot 0.5.0-rc4, review the optimized images and explicitly confirm readings with their photos. For multi-zone meters, attach a photo for every tariff or submit numerical readings only. Short-lived drafts and the single-attempt submission barrier prevent old confirmations from resending readings; image bytes are not stored in the submission journal.
- Show photo requests, attachment indicators and controller comments in reading history. A real single-zone Odesa submission was accepted and its photo confirmed in DTEK history. Live multi-zone photo submission remains unverified.
- Add an account-specific DTEK document list, protected PDF downloads up to 2 MB, and optional HA notifications every 30 minutes. Existing documents become a silent baseline. This document feature remains experimental: real inspection-act download and publication after a photo submission are not yet verified. Documents sent only by DTEK's own bot may be absent from the cabinet API.
- Fix cabinet-group expiry callbacks running outside Home Assistant's event loop, preventing thread-safety errors and rejected updates. Test expiry and cancellation with the real HA timer scheduler.
- Update English/Ukrainian photo, document and upgrade guides; add backend, permission and browser regression tests.

**Upgrade:** update the integration, restart HA and reload the HA page. Update Telegram Bot to **0.5.0-rc4** for private photos and documents. Existing addresses, accounts, calibration and bot destinations are preserved. Document notifications are opt-in. Updating does not submit readings or sign an act.

[Photo and document guide](docs/ENERGY_AND_READINGS.md) · [Фото та документи](docs/ENERGY_AND_READINGS.uk.md) · [Upgrade guide](docs/UPGRADING.md) · [Оновлення](docs/UPGRADING.uk.md)

## [2.0.0-rc3] - 2026-10-21

**Regular GitHub release**, without the Pre-release flag. Available through the standard HACS update channel. Requires HA 2026.3.0+.

- Restore meter details, reading history and reading preparation after DTEK changed its meter API authorization format. Existing accounts and passwords can be kept; no new login is needed.
- Automatically recognize the two known authorization formats on read-only requests, with bounded retries. If neither works, distinguish a service incompatibility from an expired login and show update/support guidance in HA and Telegram Bot 0.5.0-rc3. Meter submissions are never replayed automatically.
- Keep meter details, readings, consumption and personal schedules independent during partial service failures. Unavailable data is labeled explicitly; valid history remains accessible when consumption is unavailable. Partial updates retry every five minutes.
- Keep personal schedules and private bot alerts on cabinet groups confirmed by fresh building data when the cabinet also reports extra, unconfirmed groups. If none are confirmed, pause schedule alerts. My DTEK explains the discrepancy; building schedules and valid manual selections remain independent.
- Update English/Ukrainian help and add regression coverage for authorization changes, partial outages, recovery, diagnostics and account cards.

**Upgrade:** update the integration, restart HA and reload the HA page. Update Telegram Bot to 0.5.0-rc3 for the new error guidance. Existing addresses, accounts, calibration, sensors and bot destinations are preserved. No readings are sent during the update.

[Upgrade guide](docs/UPGRADING.md) · [Оновлення](docs/UPGRADING.uk.md)

## [2.0.0-rc2] - 2026-10-20

**Published in the regular release channel**, with no GitHub Pre-release flag. HACS offers this version without enabling prereleases; the version name retains RC2. Kyiv oblast and Dnipropetrovsk oblast cabinets remain experimental.

Version 2 adds My DTEK: household cabinet access, account management, meter details, reading history, consumption, sensor-calibrated suggestions and explicitly confirmed readings. Public address schedules and building bots remain independent. Requires HA 2026.3.0+.

**Upgrade:** update in place, restart HA and reload its page. From 1.7.0, back up configuration and code first: version 2 migrates entries and rollback requires that backup. Existing addresses, accounts, calibration, entities and bot destinations are preserved. Use Telegram Bot 0.5.0-rc2 for calibration from the private reading form.

- Enable Kyiv oblast and Dnipropetrovsk oblast household cabinets and apartment-group lookup experimentally, with a setup notice. Real linked-account validation is pending; optional group failures remain isolated from meter data.
- Keep verified private cabinet groups usable when public group labels are hidden. Require fresh building membership, preserve all public building groups, and recheck manual choices before saving.

- Resolve old 11-digit Kyiv city account numbers through DTEK, review the current number/address, and choose explicitly when several accounts match. Cabinet writes still use only verified modern account numbers.
- Offer optional calibration from reading review in HA and the private bot bridge. Require fresh per-zone samples and separate confirmation of simultaneous physical readings; preserve captured samples and keep calibration separate from submission.
- Enable Kyiv city household cabinets after live read-only validation of login, renewal, linked accounts, meter profile, history, submission context, automatic building matching and account-group lookup. Kyiv oblast and Dnipropetrovsk oblast are enabled experimentally (see above).
- Use Kyiv's independently verified legacy group handoff; accept numeric group identifiers above six and retain the fresh building-membership check.
- Support the modern Day/Night tariff codes throughout reading forms, source calibration, stored bindings, sensors, reminders and history. Keep exact upstream codes in submissions and identities; localize their display names.
- Actual Kyiv reading submission and account mutations were not performed during validation. Regression tests use fictional accounts and readings.

[Install and upgrade](docs/UPGRADING.md) · [Встановлення й оновлення](docs/UPGRADING.uk.md)

[Personal accounts](docs/PERSONAL_ACCOUNT.md) · [Особисті рахунки](docs/PERSONAL_ACCOUNT.uk.md)

## [2.0.0-rc1] - 2026-10-20

**Release candidate — for testing before the final 2.0 release.** Requires Home Assistant 2026.3.0+. Public address schedules support Odesa oblast, Kyiv oblast, Dnipropetrovsk oblast and Kyiv city; personal cabinets remain **Odesa household accounts only**.

### Start here

- New to 2.0? Add an address for schedules, or sign in to the cabinet for **My DTEK**: account details, meter readings, monthly consumption, schedules and sensor-calibrated reading suggestions.
- Pair with **DTEK Telegram Bot 0.5.0-rc1** for a private account menu, notifications, history, reminders and explicitly confirmed submissions. Existing building bots remain independent and compatible.
- Update in place and reload the HA page. Existing addresses, account selections and sensor calibration are preserved. Before leaving 1.7.0, back up configuration and code; reverting to 1.7.0 requires restoring that backup.
- No unattended reading submissions or new regional cabinets are enabled by this release.

[English: installation and upgrade](docs/UPGRADING.md) · [Українська: встановлення та оновлення](docs/UPGRADING.uk.md)

[English user guide](README.md) · [Український посібник](README.uk.md)

### Changes since 2.0.0b1

- Add a permission-checked local WebSocket bridge for explicitly configured personal Telegram profiles. Supply cabinet-only groups, verified calendars, grid images' source data, reminder eligibility and existing reading submission/energy/readback operations. Bind confirmation drafts to HA principal, bot, Telegram user and profile; never export cabinet credentials or silently fall back to a building/manual group.
- Document the companion bot's private profile setup and preserve independent building monitoring, cabinet UI and HA reminder settings.

- Notify in HA when verified building or apartment groups change, without creating a Repair. Follow automatic assignments and replace a disappeared manual selection only when a single verified replacement is available; retain all building/bot groups and never guess during ambiguity or API failures. Persist comparison baselines across restarts.
- Add a building refresh button and make the grid's refresh action query DTEK with shared cooldown and permission checks. Preserve date/filter choices and ignore replies for a previously selected account.
- Emit `dtek_monitor_schedule_changed` for meaningful verified future daily schedule changes and `dtek_monitor_groups_changed` for building assignments. Ignore timestamp-only changes, expired intervals, missing coverage and weekly forecasts; comparison caches never supply live alerts.

- Join verified adjacent calendar intervals across midnight without mixing groups, event types or sources. Localize live and saved calendar titles to HA's system language while preserving machine-readable event descriptions.
- Add building and personal timestamp sensors for the next planned/possible outage and scheduled outage end, plus tomorrow's publication status. Keep missing coverage, empty schedules and errors distinct; never infer restoration at an unverified publication boundary. Update derived states at event boundaries and Kyiv midnight without additional API requests.
- Coordinate public requests across addresses, setup flows and reloads with an operator-wide queue and bounded failure cooldown. Respect Retry-After, preserve independent cabinet/other-operator access, and expose shared retry health in diagnostics.
- Add an independent address repair calendar and availability sensor. Keep all reported repairs, distinguish incomplete times from no reports and failed requests, and never invent end times or reuse old repairs as current.

- Add optional Odesa account-group lookup using a separate legacy cabinet session. A single fresh group can select the private schedule when verified against the building; multiple groups require a choice. Manual choices take priority, all building/bot groups remain, and lookup can be disabled per account.
- Refresh optional groups independently every 15 minutes and after account updates; distinguish empty, unavailable, expired and conflicting assignments. Retired/incompatible legacy routes produce a scoped HA Repair without blocking meter data or submissions. Show the group source on the dashboard and safe metadata health in diagnostics.
- Recognize planned repair records with dates even when DTEK omits their description. Empty records still mean no reported outage; malformed repair dates remain unavailable instead of confirming power.
- Add Home Assistant diagnostic downloads for address and personal-account connections, including failed setup. Exports contain technical health, freshness and counts, without credentials, addresses, account identifiers, meter readings or raw responses/errors.
- Prepare a shared regional personal-account client with separate cabinet/auth domains, OAuth settings and modern household account-number rules. Only Odesa cabinets remain enabled; Kyiv city, Kyiv oblast and Dnipropetrovsk oblast await authenticated live validation.
- Keep SMS challenges, account-link confirmations, API repair notices and unlink protection scoped to the selected operator. Changing the region clears unfinished cabinet setup.
- Show the selected operator's account-number format and registration/recovery links in setup. Existing Odesa account and building identities are unchanged.
- Use the selected regional cabinet for device and reading-form links; distinguish new cabinet connections by operator and masked phone number. Loading a link never replaces edited readings.
- Match explicit street and settlement abbreviations when connecting a cabinet address to a public building. Ambiguous names, district qualifiers and building sections still require manual confirmation.

- Hide inactive history records by default while keeping blocked/unknown warnings visible. A show-all switch restores every source record; preserve dates, tariff zones, calculations and readback matching. The personal bot gets filtered pagination.
- Use Ukrainian when Home Assistant's language is Russian; maintain English and Ukrainian source translations and version all frontend assets together.
- Refresh English/Ukrainian user guides, compatibility, first setup, data meanings, sensor calibration and upgrade/rollback instructions.

## [2.0.0b1] - 2026-10-18

First public beta of DTEK Monitor 2.0. This is a testing release, not a release candidate or a stable update. Address monitoring remains available without a personal cabinet.

### New in 2.0

- Optional Odesa household cabinet: phone login, SMS registration/recovery, account linking/unlinking, and independent selection of the accounts monitored by HA.
- My DTEK dashboard in English and Ukrainian: address, account visibility control, EIC/meter details, readings, monthly consumption and per-card apartment selection.
- Automatic verified building matching with manual confirmation when needed. All building groups remain available; a personal group can be selected separately, or chosen automatically when the building has one group.
- Half-hour schedule grid for all published operator groups, building/apartment highlights, list view and PNG export. Unpublished data stays distinct from empty schedules and connection errors.
- Explicitly confirmed meter-reading submissions with a durable attempt journal, ambiguous-result protection and read-back checks. No automatic submissions.
- Optional generic cumulative energy sensor: direct official-meter readings or estimates from paired references, calibration corrections, continuity checks and separate tariff zones.
- Optional HA reading reminders, meter verification/replacement notices and scheduled checks without submission.
- Account-scoped permissions, input preservation during HA updates, API-change repair notices and automatic recovery from directory failures.

### Installation and limits

- Requires Home Assistant 2026.3.0 or newer. Public address schedules support Odesa oblast, Kyiv oblast, Dnipropetrovsk oblast and Kyiv city. Personal cabinets are Odesa household accounts only.
- Back up before upgrading: configuration migration is automatic, but returning to 1.7.0 requires restoring the earlier configuration and code. Existing building entities and bot settings are preserved.
- One consumption meter per account; manual submission supports one zone or Day/Night. Only single-zone Odesa submission has been verified live. No automatic submissions, payments, photo uploads or Energy-dashboard statistics from billing history.
- DTEK Telegram Bot 0.3.13 remains compatible and independent; private account data is not sent to the building bot.

[English installation and beta guide](https://github.com/groove-max/ha-dtek-monitor/blob/v2.0.0b1/docs/BETA.md) · [Українська: встановлення та бета](https://github.com/groove-max/ha-dtek-monitor/blob/v2.0.0b1/docs/BETA.uk.md)

[English user guide](https://github.com/groove-max/ha-dtek-monitor/blob/v2.0.0b1/README.md) · [Український посібник](https://github.com/groove-max/ha-dtek-monitor/blob/v2.0.0b1/README.uk.md) · [Report a problem](https://github.com/groove-max/ha-dtek-monitor/issues)

## [1.7.0] - 2026-10-17

- License new releases under PolyForm Noncommercial 1.0.0; earlier MIT releases keep their original terms.

- Rewrite English/Ukrainian user guides and references; add companion links and a manual GitHub publication checklist.

### Added

- Enable Kyiv city / KEM with a fixed locality and direct street selection. Its flat directory and empty-city API requests stay inside the shared adapter.
- Expose public group-label visibility on HA group sensors while preserving internal IDs for calendar provenance and freshness checks.
- KEM setup, retry, multigroup calendar and publication-visibility runtime tests.

## [1.6.0] - 2026-10-17

### Added

- Enable Dnipropetrovsk oblast / DNEM in operator selection using the shared DTEK adapter. Directory, house selection, multi-group calendars and provider-bound entity identities use the existing contract.
- DNEM setup and HA calendar tests, including revocation to an external CEK operator and mixed DTEK/CEK house records. CEK remains unsupported; its data cannot enable live schedule notifications.

## [1.5.0] - 2026-10-17

### Added

- Operator selection and Kyiv oblast / KREM support through the shared provider adapter, including multi-group addresses. Kyiv city / KEM remains a separate, disabled rollout target.
- Provider-scoped entry identity and stable entity prefixes for new regional addresses, retaining the Telegram addon's expected sensor/calendar suffixes.
- Regression tests for regional setup, directory isolation, disabled operators, retry/cleanup, legacy duplicate detection and bot discovery.

### Compatibility

- Existing Odessa entry, device and entity identifiers and polling options are unchanged. The addon continues to consume HA entities without regional API logic.

## [1.4.0] - 2026-10-17

### Added

- A provider-independent normalized address/schedule interface and a shared DTEK web adapter with per-instance transport settings.
- Offline contract fixtures for OEM, KREM, DNEM and KEM; only OEM is enabled in this first rollout stage. DEM is excluded.
- Explicit publication status, per-group/date coverage, provider/address identity and content revisions.

### Changed

- Config entry version 3 adds the OEM provider without changing existing entity/device identifiers or options. Older display snapshots remain readable.
- The coordinator consumes normalized intervals; wire-format parsing stays in the adapter. Address status remains usable during schedule failures.
- Unpublished weekly templates and incomplete days no longer generate automatic forecasts or empty-calendar claims. Complete daily schedules supersede recurring forecasts.
- Calendar queries entirely outside published coverage fail; publication/coverage changes invalidate pending schedule notifications.

## [1.3.0] - 2026-10-17

### Added

- A persistent, address/provider-bound **Last known schedule (view only)** calendar, including verification time, group provenance, coverage and content identity. It remains usable after an offline restart without enabling automated schedule notifications.
- Concrete cached intervals with an eight-day coverage horizon; cached weekly templates are never extrapolated beyond that horizon.
- Separate address/schedule diagnostics, snapshot storage errors and bounded retry backoff with jitter.
- Group-sensor freshness/revision attributes for notification consumers.

### Changed

- Address status can update while schedule requests fail. Original calendars require complete address/group/schedule verification; an unknown group mapping cannot reuse the previous group as confirmed.
- Only complete successful checks replace persistent snapshots. Successful unchanged checks advance verification time, while failures retain the previous time and events.
- Offline setup with a valid snapshot exposes the display calendar and diagnostics; live entities remain unavailable until verified.

## [1.2.2] - 2026-10-17

### Changed

- Adapted browser-compatible HTTP transport, bounded retries, connection recycling and flexible CSRF extraction from [Zerstoren/ha-dtek-krem-monitor](https://github.com/Zerstoren/ha-dtek-krem-monitor/tree/e1fb7cfd6167a37c6dfedbc385af5c02e6611a45) (MIT). Runtime dependency is pinned to `curl_cffi==0.16.3`.
- Keep cookies in memory across transport recovery; close sessions on unload and on every configuration request, including errors.

### Added

- A diagnostic connection sensor with last successful poll, last error, consecutive failure count and transport/protection counters. It continues updating through repeated failures.

### Fixed

- Treat schedule-check errors as failed polls and roll back partial schedule changes. Cached calendars cannot be queried as current data after a failed poll; no stale-data grace period is enabled.
- Reject malformed JSON and schedule responses rather than interpreting them as unchanged or empty schedules.
- Handle network errors when submitting a city, and normalize street choices.

## [1.2.1] - 2026-10-17

### Fixed

- Normalize range boundaries to Europe/Kyiv before selecting schedule days, including UTC queries across midnight and DST dates.
- Keep calendar windows separate by schedule group and include provenance in their descriptions.
- Canonicalize group lists so API array ordering does not change the compatibility primary-group sensor.
- Reject malformed house payloads as update failures instead of publishing confirmed power availability.

## [1.2.0] - 2026-03-09

### Added

- Automatic registry migration for upgrades from `1.1.x`, moving entities and devices from config-entry-based identifiers to address-based stable identifiers while preserving existing `entity_id` values.
- An options flow for changing the polling interval without removing and re-adding the integration.
- A dedicated sensor for the full list of schedule groups reported by DTEK.
- Regression tests covering HTML schedule extraction, schedule merging, and registry migration helpers.

### Changed

- Refactored schedule handling into a dedicated pure domain layer, centralizing outage merging, overlap resolution, and next-event lookup in a testable module.
- Entity and device registry identifiers are now based on the address `unique_id` instead of the transient config entry ID.
- The primary schedule group is now exposed separately from the full schedule group list.

### Fixed

- Runtime HTTP sessions are now created through Home Assistant helpers, closed correctly on setup failure, and reloaded automatically when options change.
- Preserved all schedule groups reported by DTEK instead of collapsing to the first group, so calendars and attributes no longer silently lose data.
- Corrected fact-vs-preset schedule merging: preset windows are now trimmed around overlapping fact windows rather than only skipping exact duplicates.
- Calendar entities now search the full weekly schedule horizon instead of only looking ahead 48 hours.
- HTML schedule parsing now uses brace matching instead of greedy regex extraction, making it more resilient to site markup changes.

## [1.1.0] - 2026-03-07

### Fixed

- **Stale data after long uptime** — session now automatically refreshes after 1 hour. Previously, the CSRF token and session cookies were never refreshed after the initial connection, causing the integration to serve stale schedule data indefinitely.
- **Schedule data lost after session refresh** — introduced a dirty-flag mechanism so the coordinator picks up new schedule data every time the HTTP session is refreshed, not just on the very first load.
- **Crash when schedule data has unexpected format** — added type guards in `_apply_schedule` and `_get_day_slots` to handle cases where DTEK API returns a list instead of a dict for fact/preset data, preventing `AttributeError: 'list' object has no attribute 'items'`.

## [1.0.0] - 2026-03-06

### Added

- Initial release
- Real-time outage monitoring with binary sensor and status sensors
- Outage type classification: emergency, planned, stabilization
- Two schedule calendars: confirmed outages and possible outages
- Schedule group tracking
- Automatic schedule updates via API polling and HTML parsing
- Multi-outage support with severity-based priority
- 4-step config flow with combo-box selectors
- Full Ukrainian and English translations
- Local brand icons (HA 2026.3+)
