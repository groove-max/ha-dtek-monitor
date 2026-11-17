"""Synthetic history, corrections, pagination and bounded on-demand fetching."""

import asyncio
from copy import deepcopy
from datetime import date, datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from component_loader import load_component_module

history = load_component_module("account_history")
account = load_component_module("account")
client_module = load_component_module("account_client")
TODAY = date(2026, 10, 18)


def row(identity="one", value=120, stamp="2026-09-30T23:59:00", **changes):
    return {
        "id": identity,
        "dateTime": stamp,
        "value": value,
        "deviceEnergyType": "ACTIVE",
        "deviceScaleType": "GENERAL",
        "kind": "Synthetic source",
        "isInactive": False,
        "isBlocked": False,
        **changes,
    }


def page(*rows, number=1, total=1):
    return {"page": number, "totalPages": total, "data": list(rows)}


def months(*items):
    return {"items": list(items)}


def month(period="2026-09", value=-12, zones=None):
    return {"date": period, "consumption": value, "zones": zones or []}


class HistoryParsingTests(unittest.TestCase):
    def test_photo_and_controller_metadata_are_optional_and_bounded(self):
        rows = [row(hasPhoto=True, controllerNote="Photo checked"),
                row("bad", hasPhoto="true", controllerNote={"unexpected": "data"}),
                row("long", controllerNote="x" * 1001), row("absent")]
        parsed = [item for _, item in history.parse_history_page(page(*rows), 2026, TODAY)[2]]
        self.assertTrue(parsed[0]["has_photo"])
        self.assertEqual(parsed[0]["controller_note"], "Photo checked")
        for item in parsed[1:]:
            self.assertFalse(item["has_photo"])
            self.assertIsNone(item["controller_note"])

    def test_display_filter_preserves_warnings_and_distinct_periods_without_mutation(self):
        rows = [{"energy": "ACTIVE", "status": "inactive", "value": "120"} for _ in range(8)]
        # The same value in different periods or tariff zones is not a duplicate.
        rows += [{"energy": "ACTIVE", "status": "active", "value": "120", "date_time": str(i), "zone": "DAY" if i == 1 else "GENERAL"} for i in range(7)]
        rows += [{"energy": "ACTIVE", "status": s, "value": "121"} for s in ("blocked", "unknown")]
        rows += [{"energy": "REACTIVE", "status": "active", "value": "9"}]
        original = deepcopy(rows)
        first = history.reading_history_page(rows)
        self.assertEqual(len(first["latest"]), 6)
        self.assertEqual(first["history_view"]["visible"], 9)
        self.assertEqual(first["history_view"]["inactive_count"], 8)
        last = history.reading_history_page(rows, offset=1000)
        self.assertEqual([r["status"] for r in last["latest"]], ["active", "blocked", "unknown"])
        self.assertEqual(last["history_view"]["previous_offset"], 0)
        full = history.reading_history_page(rows, include_inactive=True)
        self.assertEqual(full["history_view"]["visible"], 17)
        self.assertTrue(all(r["status"] == "inactive" for r in full["latest"]))
        self.assertEqual(rows, original)

    def test_all_inactive_is_distinct_from_empty_history(self):
        page = history.reading_history_page([{"energy": "ACTIVE", "status": "inactive"}], offset=999)
        self.assertEqual(page["latest"], [])
        self.assertEqual(page["history_view"]["total"], 1)
        self.assertEqual(page["history_view"]["offset"], 0)
        self.assertEqual(history.reading_history_page([])["history_view"]["total"], 0)

    def test_explicit_statuses_and_kyiv_dates(self):
        values = [
            row(),
            row("inactive", isInactive=True),
            row("blocked", isBlocked=True),
            row("unknown", isBlocked=None),
        ]
        _, _, result = history.parse_history_page(page(*values), 2026, TODAY)
        self.assertEqual(
            [r["status"] for _, r in result],
            ["active", "inactive", "blocked", "unknown"],
        )
        self.assertTrue(result[0][1]["date_time"].endswith("+03:00"))
        self.assertNotIn("id", result[0][1])
        self.assertNotIn("serial_number", result[0][1])
        utc = row(stamp="2025-12-31T23:15:00+00:00")
        self.assertTrue(
            history.parse_history_page(page(utc), 2026, TODAY)[2][0][1][
                "date_time"
            ].startswith("2026-01-01T01:15")
        )

    def test_bad_history_never_becomes_empty(self):
        cases = [
            {},
            [],
            page(row(value="NaN")),
            page(row(value="1e1000")),
            page(row(value="1e1000000")),
            page(row(value=True)),
            page(row(value=-2)),
            page(row(isInactive="false")),
            page(row(id=None)),
            page(row(stamp="broken")),
            page(row(stamp="2027-01-01T00:00:00")),
            page(row(deviceScaleType="../../wrong")),
            page(row(kind={})),
            page(row(), total=0),
            page(row(), total=21),
        ]
        for payload in cases:
            with self.subTest(payload=payload), self.assertRaises(account.AccountError):
                history.parse_history_page(payload, 2026, TODAY)
        self.assertEqual(history.parse_history_page(page(total=0), 2026, TODAY)[2], [])

    def test_mixed_years_are_filtered_with_or_without_optional_metadata(self):
        payload = page(
            row("older", stamp="2023-12-31T12:00:00"),
            row("previous", stamp="2025-09-30T12:00:00"),
            row("day", deviceScaleType="DAY", isInactive=True),
            row("night", deviceScaleType="NIGHT", isBlocked=True),
        )
        for metadata in (None, {"years": ["2026", "2025", "2024", "2023"],
                                "deviceCombinedTypes": ["ACTIVE:GENERAL"],
                                "source": ["FROM_CLIENT", "CONTROL_READING"]}):
            with self.subTest(metadata=metadata):
                candidate = deepcopy(payload)
                if metadata is not None:
                    candidate["metadata"] = metadata
                original = deepcopy(candidate)
                for year, expected in ((2026, ["day", "night"]), (2025, ["previous"]),
                                       (2024, []), (2023, ["older"])):
                    returned_page, pages, rows = history.parse_history_page(candidate, year, TODAY)
                    self.assertEqual((returned_page, pages), (1, 1))
                    self.assertEqual([identity for identity, _ in rows], expected)
                    if year == 2026:
                        self.assertEqual([(r["zone"], r["status"]) for _, r in rows],
                                         [("DAY", "inactive"), ("NIGHT", "blocked")])
                self.assertEqual(candidate, original)

    def test_year_filter_uses_kyiv_date_on_both_sides_of_new_year(self):
        payload = page(row("current", stamp="2025-12-31T23:15:00+00:00"),
                       row("previous", stamp="2026-01-01T00:30:00+03:00"))
        self.assertEqual([identity for identity, _ in history.parse_history_page(payload, 2026, TODAY)[2]], ["current"])
        self.assertEqual([identity for identity, _ in history.parse_history_page(payload, 2025, TODAY)[2]], ["previous"])

    def test_filter_never_hides_future_or_invalid_dates_in_other_years(self):
        for stamp in ("2026-10-19T12:00:00", "2027-01-01T00:00:00", "not-a-date"):
            with self.subTest(stamp=stamp), self.assertRaises(account.AccountError):
                history.parse_history_page(page(row(stamp=stamp)), 2025, TODAY)

    def test_months_keep_signed_zones_and_mark_gaps_open_future(self):
        payload = months(
            month(
                value=-12,
                zones=[
                    {"zone": "DAY", "consumption": -15},
                    {"zone": "NIGHT", "consumption": 3},
                ],
            ),
            month("2026-10", 20),
            month("2026-11", 0),
        )
        result = history.parse_months(payload, 2026, TODAY)
        self.assertEqual(len(result), 12)
        self.assertEqual(result[0]["status"], "missing")
        self.assertIsNone(result[0]["value"])
        self.assertEqual(result[8]["value"], "-12")
        self.assertEqual(result[8]["zones"], {"DAY": "-15", "NIGHT": "3"})
        self.assertEqual(result[9]["status"], "open")
        self.assertEqual(result[9]["value"], "20")
        self.assertEqual(result[10]["status"], "future")
        self.assertIsNone(result[10]["value"])
        self.assertEqual(
            history.parse_months(months(month(value=0)), 2026, TODAY)[8]["value"], "0"
        )

    def test_invalid_months_and_duplicate_zones_fail(self):
        for payload in [
            months(month(), month()),
            months(month("2025-01")),
            months(month("2026-13")),
            months(month(value="Infinity")),
            months(month(value=None)),
            months(
                month(
                    zones=[
                        {"zone": "DAY", "consumption": 1},
                        {"zone": "DAY", "consumption": 2},
                    ]
                )
            ),
            months({"date": "2026-01", "consumption": 1, "zones": None}),
        ]:
            with self.subTest(payload=payload), self.assertRaises(account.AccountError):
                history.parse_months(payload, 2026, TODAY)

    def test_year_validation(self):
        for year in [True, 2026.5, "2026", 1999, 2027]:
            with self.assertRaises(account.AccountError):
                history.validate_year(year, TODAY)
        self.assertEqual(history.validate_year(2000, TODAY), 2000)


class HistoryClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.client = client_module.DTEKAccountClient(
            SimpleNamespace(close=AsyncMock())
        )
        self.client._accounts = {"100001"}

    async def test_pagination_deduplicates_and_retains_distinct_zones_and_meter_reset(
        self,
    ):
        # A smaller later reading may follow replacement; retain both, never subtract.
        first = row("old", 9000, deviceScaleType="DAY")
        next_row = row(
            "new", 20, "2026-10-01T11:00:00", deviceScaleType="NIGHT", isInactive=True
        )
        self.client._get = AsyncMock(
            side_effect=[
                page(first, total=2),
                page(first, next_row, number=2, total=2),
                months(month()),
            ]
        )
        result = await self.client.read_history("100001", 2026)
        self.assertEqual(len(result["readings"]), 2)
        self.assertEqual([r["value"] for r in result["readings"]], ["20", "9000"])
        self.assertEqual(result["meter_scope"], "account")
        self.assertEqual(result["months"][8]["value"], "-12")
        self.assertNotIn("100001", str(result))
        self.assertEqual(self.client._get.await_count, 3)
        self.assertEqual(self.client._get.call_args_list[1].kwargs["params"]["page"], 2)

    async def test_changed_or_conflicting_pages_are_rejected(self):
        for second in [
            page(row(), number=1, total=2),
            page(row(), number=2, total=3),
            page(row(value=999), number=2, total=2),
            page(number=2, total=2),
        ]:
            self.client._get = AsyncMock(side_effect=[page(row(), total=2), second])
            with self.assertRaises(account.AccountError):
                await self.client.read_history("100001", 2026)
            self.assertEqual(self.client._get.await_count, 2)

    async def test_other_year_pages_before_and_after_requested_rows_are_not_empty(self):
        self.client._get = AsyncMock(side_effect=[
            page(row("old", stamp="2023-01-01T12:00:00"), total=3),
            page(row("current"), number=2, total=3),
            page(row("previous", stamp="2025-01-01T12:00:00"), number=3, total=3),
            months(month()),
        ])
        result = await self.client.read_history("100001", 2026)
        self.assertEqual(len(result["readings"]), 1)
        self.assertEqual(result["readings"][0]["date_time"], "2026-09-30T23:59:00+03:00")
        self.assertEqual(result["months"][8]["value"], "-12")
        requests = self.client._get.call_args_list
        self.assertEqual(len(requests), 4)
        self.assertEqual([call.kwargs["params"]["page"] for call in requests[:3]], [1, 2, 3])
        self.assertTrue(all(call.kwargs["params"]["year"] == 2026 for call in requests))

    async def test_absent_requested_year_is_empty_only_after_all_pages_are_read(self):
        self.client._get = AsyncMock(side_effect=[
            page(row("old", stamp="2023-01-01T12:00:00"), total=2),
            page(row("current"), number=2, total=2),
            months(month("2025-09", 7)),
        ])
        result = await self.client.read_history("100001", 2025)
        self.assertEqual(result["readings"], [])
        self.assertEqual(result["months"][8]["value"], "7")
        self.assertEqual(self.client._get.await_count, 3)

    async def test_raw_row_limit_also_counts_records_removed_by_year_filter(self):
        self.client._get = AsyncMock(side_effect=[
            page(row("a", stamp="2024-01-01T12:00:00"),
                 row("b", stamp="2024-01-02T12:00:00"), total=2),
            page(row("c", stamp="2025-01-01T12:00:00"),
                 row("d", stamp="2025-01-02T12:00:00"), number=2, total=2),
        ])
        with patch.object(client_module, "MAX_HISTORY_ROWS", 3):
            with self.assertRaisesRegex(account.AccountError, "excessive history"):
                await self.client.read_history("100001", 2026)
        self.assertEqual(self.client._get.await_count, 2)

    async def test_failed_or_empty_page_after_other_year_rows_is_not_success(self):
        for second in (page(number=2, total=2), account.AccountError("down")):
            with self.subTest(second=second):
                self.client._get = AsyncMock(side_effect=[
                    page(row(stamp="2025-01-01T12:00:00"), total=2), second,
                ])
                with self.assertRaises(account.AccountError):
                    await self.client.read_history("100001", 2026)
                self.assertEqual(self.client._get.await_count, 2)

    async def test_api_failure_and_excessive_history_do_not_return_partial_results(
        self,
    ):
        self.client._get = AsyncMock(
            side_effect=[page(row(), total=2), account.AccountError("down")]
        )
        with self.assertRaises(account.AccountError):
            await self.client.read_history("100001", 2026)
        self.client._get = AsyncMock(
            return_value=page(*[row(str(n)) for n in range(1001)])
        )
        with self.assertRaises(account.AccountError):
            await self.client.read_history("100001", 2026)

    async def test_unlinked_account_does_not_issue_request(self):
        self.client._get = AsyncMock()
        with self.assertRaises(account.AccountError):
            await self.client.read_history("999999", 2026)
        self.client._get.assert_not_awaited()


class HistoryCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_short_bot_cache_reuses_recent_fetch_and_refreshes_after_one_minute(self):
        client = SimpleNamespace(read_history=AsyncMock(return_value={"readings": [1]}))
        cache = history.HistoryCache(client)
        with patch.object(history, "monotonic", return_value=100):
            await cache.get("100001", 2026)
        with patch.object(history, "monotonic", return_value=159):
            self.assertEqual(await cache.get("100001", 2026, max_age=60), {"readings": [1]})
            self.assertEqual(client.read_history.await_count, 1)
        client.read_history.return_value = {"readings": [2]}
        with patch.object(history, "monotonic", return_value=160):
            self.assertEqual(await cache.get("100001", 2026, max_age=60), {"readings": [2]})
        self.assertEqual(client.read_history.await_count, 2)

    async def test_submission_invalidates_cached_and_in_flight_history(self):
        client = SimpleNamespace(read_history=AsyncMock(return_value={"months": [1]}))
        cache = history.HistoryCache(client)
        with patch.object(history, "monotonic", return_value=100):
            await cache.get("100001", 2026)
        cache.invalidate("100001")
        self.assertNotIn(("100001", 2026), cache._cache)

        async def changed(*args):
            cache.invalidate("100001")
            return {"months": ["old"]}

        client.read_history.side_effect = changed
        with patch.object(history, "monotonic", return_value=161):
            with self.assertRaises(account.AccountError):
                await cache.get("100001", 2026)
        self.assertNotIn(("100001", 2026), cache._cache)

    async def test_concurrent_reads_coalesce_and_force_corrects_previous_month(self):
        client = SimpleNamespace(read_history=AsyncMock(return_value={"months": [1]}))
        cache = history.HistoryCache(client)
        with patch.object(history, "monotonic", return_value=100):
            await asyncio.gather(cache.get("100001", 2026), cache.get("100001", 2026))
            self.assertEqual(client.read_history.await_count, 1)
            with self.assertRaises(account.AccountRateLimitError):
                await cache.get("100001", 2026, force=True)
        client.read_history.return_value = {"months": [-1]}
        with patch.object(history, "monotonic", return_value=161):
            result = await cache.get("100001", 2026, force=True)
            self.assertEqual(result["months"], [-1])
            self.assertEqual((await cache.get("100001", 2026))["months"], [-1])
        self.assertEqual(client.read_history.await_count, 2)

    async def test_failure_cooldown_and_cache_expiry(self):
        client = SimpleNamespace(read_history=AsyncMock(return_value={"year": 2026}))
        cache = history.HistoryCache(client)
        with patch.object(history, "monotonic", return_value=100):
            await cache.get("100001", 2026)
        client.read_history.side_effect = account.AccountError("down")
        with patch.object(history, "monotonic", return_value=22000):
            with self.assertRaises(account.AccountError):
                await cache.get("100001", 2026)
            with self.assertRaises(account.AccountRateLimitError):
                await cache.get("100001", 2026)
        self.assertEqual(client.read_history.await_count, 2)

    async def test_provider_429_blocks_other_years_temporarily_and_cache_is_bounded(
        self,
    ):
        client = SimpleNamespace(
            read_history=AsyncMock(side_effect=account.AccountRateLimitError("limit"))
        )
        cache = history.HistoryCache(client)
        with patch.object(history, "monotonic", return_value=100):
            with self.assertRaises(account.AccountRateLimitError):
                await cache.get("100001", 2026)
            with self.assertRaises(account.AccountRateLimitError):
                await cache.get("100001", 2025)
        self.assertEqual(client.read_history.await_count, 1)
        client.read_history.side_effect = None
        client.read_history.return_value = {}
        with patch.object(history, "monotonic", return_value=401):
            for year in range(2000, 2026):
                await cache.get("100001", year)
        self.assertEqual(len(cache._cache), 16)
