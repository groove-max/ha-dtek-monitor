# Contributing to DTEK Monitor

**English** · [Українська](CONTRIBUTING.uk.md) · [User guide](README.md)

Bug reports, fixes and documentation improvements are welcome in English or Ukrainian.

## Choose the right repository

DTEK website parsing, regional address lookup and HA entities belong to [DTEK Monitor](https://github.com/groove-max/ha-dtek-monitor). Telegram delivery, message templates and local-sensor power detection belong to [DTEK Telegram Bot](https://github.com/groove-max/ha-dtek-telegram-bot).

Before opening an issue, search existing issues and include versions, reproduction steps, expected/actual behavior and a short sanitized log. Do not publish bot tokens, HA tokens, exact private addresses or raw production journals. For vulnerabilities, use [Security](SECURITY.md).

## Run the checks

From the repository root, with the indicated Python version installed:

```bash
python3.13 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -c "import json, subprocess, sys; subprocess.check_call([sys.executable, '-m', 'pip', 'install', *json.load(open('custom_components/dtek_monitor/manifest.json'))['requirements']])"
python -m unittest discover -s tests -v
python -m compileall custom_components tests
```

The lightweight suite skips HA-dependent tests when Home Assistant is absent. For complete verification, use a separate Python 3.14 environment, install `homeassistant==2026.3.0` plus the manifest requirements, and rerun the suite. Match `.github/workflows/tests.yml`; do not describe skipped runtime tests as passed.

Provider changes need fixtures for published, unpublished, empty, malformed and multi-group data. Keep provider/address identity and publication coverage intact. New regions must use the provider interface and explicit rollout settings, not hardcoded regional branching in HA entities.

## Regional personal accounts

Public outage support (`providers.py`) and personal-cabinet support (`account_providers.py`) have separate rollout gates. Public schedules already support all four operators below. Odesa and Kyiv city cabinets are enabled; Kyiv oblast and Dnipropetrovsk oblast are enabled experimentally and await real-account validation.

| Operator | Cabinet domain | Modern household number | Cabinet rollout |
| --- | --- | --- | --- |
| Odesa oblast (`dtek_oem`) | `my.dtek-oem.com.ua` | 12 digits, prefix `572` | Enabled |
| Kyiv city (`dtek_kem`) | `my.dtek-kem.com.ua` | 12 digits, prefix `452` | Enabled; read-only live validation |
| Kyiv oblast (`dtek_krem`) | `my.dtek-krem.com.ua` | 12 digits, prefix `842` | Experimental; pending live validation |
| Dnipropetrovsk oblast (`dtek_dnem`) | `my.dtek-dnem.com.ua` | 12 digits, prefix `12` | Experimental; pending live validation |

`AccountProvider` in `account.py` is the cabinet interface. `DTEKAccountClient` implements the shared API; `AccountProviderSpec` supplies trusted domains, OAuth settings, number rules and the rollout flag. The factory rejects disabled operators before opening a session. Each client owns its cookies and tokens and keeps one immutable regional specification. SMS registration/recovery uses the same specification in a separate transient session. If a backend needs different behavior, implement the interface and select that implementation in the factory; do not add regional conditions to entities or cards.

The public frontend bundles checked on 2026-10-19 use the same OAuth client ID and API routes: `/main-page/488.js` describes OAuth, `/main-page/602.js` describes modern account prefixes. These resources are available from the [Odesa](https://my.dtek-oem.com.ua/main-page/488.js), [Kyiv city](https://my.dtek-kem.com.ua/main-page/488.js), [Kyiv oblast](https://my.dtek-krem.com.ua/main-page/488.js) and [Dnipropetrovsk](https://my.dtek-dnem.com.ua/main-page/488.js) cabinets. Identical frontend code does not establish that authenticated data or submission behavior is identical. Kyiv city legacy household numbers can be resolved to their modern account number. Other legacy-number formats and commercial accounts remain unverified.

Before enabling a cabinet, validate login or registration/recovery, lookup/linking, account selection, meter details, accepted readings, history and building matching with an authorized household account. An existing regional login is optional: the account owner can authorize attaching a test account to a newly registered cabinet. Verify that the account can be selected without changing its upstream link and that its public building uses the same operator. Confirm any real reading submission separately using actual meter values; do not submit synthetic test readings. Include multi-tariff fixtures and document which tariff types were actually tested live.

`test_account_regions.py` and `test_account_regions_runtime.py` exercise contracts with synthetic transports and temporarily enabled test specifications. They verify origin/callback isolation, number validation, SMS lifecycle, HA identity, repair notices and unlink protection. Tests must not silently mark experimental regions as validated. Personal-account data stays separate from the building data consumed by the Telegram bot.

Unauthenticated checks on 2026-10-19 confirmed that login/signup/recovery pages respond for all four regions and that account APIs require authentication. Public address directories were also read for Kyiv city, Kyiv oblast and Dnipropetrovsk oblast. This is not an authenticated account test. Treat repeated street names, district annotations and building sections as ambiguous instead of removing meaningful address parts to force a match. Navigation uses the local permission-checked `account_identity` response (`provider_id`, `cabinet_url`); unknown operators have no default cabinet link.

## Test against a live installation

Use a separate HA/test destination and keep production notification delivery disabled during experiments. Never toggle electrical equipment as an incidental software test. Document which scenarios used fixtures and which were actually observed.

## Documentation and pull requests

- Keep `README.md` and `README.uk.md` aligned; detailed guides also have `.uk.md` counterparts.
- Keep the README focused on installing and using the project. Put contracts and implementation detail in the reference/contributor guides.
- Validate relative links and YAML examples. Use fictional addresses and placeholder entity IDs.
- Update the changelog for user-visible behavior changes; historical release entries stay in their original language.
- Explain the problem, resulting behavior and meaningful checks. Preserve existing user settings and identifiers unless a documented migration is necessary.
- Do not commit credentials, private diagnostics, caches, virtual environments or `graphify-out/` artifacts.

Contributions must be your own work or compatible with this project’s [license](LICENSE). Submit contributions under PolyForm Noncommercial 1.0.0 and preserve third-party notices.

## Release validation

Run the HA runtime suite on both `2026.3.0` and `2026.10.2`, as in CI. Run the browser suite separately with Playwright 1.58.0 and Chromium:

```sh
python -m unittest discover -s tests -p 'test_*card.py' -v
```

`python scripts/release.py v2.0.0-rc2` checks the version, dated notes and publication channel. Set the exact version and boolean `prerelease` in `.github/release-channel.json`; a mismatch stops publication. RC2 explicitly uses `false`, so GitHub publishes a regular release and marks it Latest. The RC suffix does not override that choice. CI publishes only after all checks pass. Without a channel file, alpha/beta/RC suffixes default to prereleases.

The local UI demo is `examples/account-workspace/index.html`, served from the repository root with `python -m http.server 8974 --bind 127.0.0.1`. It uses fictional data; its connection screens are a mockup and never send SMS or readings.

When changing Ukrainian translations, run `python scripts/sync_translations.py`. The `ru.json` file intentionally contains the same Ukrainian text for Russian HA language preferences; a test prevents these files from drifting apart.

## Documentation website

User guides are published in [Ukrainian and English](https://groove-max.github.io/ha-dtek-monitor/).
Edit the existing Markdown guides, then run `python scripts/build_docs.py` and
`python scripts/check_docs.py` after installing `website/requirements.txt`.
The site publishes automatically from `main`; generated HTML is not committed
or included in integration archives.
