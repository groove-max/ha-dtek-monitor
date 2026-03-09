# Changelog

All notable changes to this project will be documented in this file.

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
