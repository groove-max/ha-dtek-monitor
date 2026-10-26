"""Operator-wide grid coverage, highlights and civil-time transitions."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import unittest

from component_loader import load_component_module
from test_provider_contract import fixture, normalize

adapter = load_component_module("dtek_provider")
contract = load_component_module("provider")
grid = load_component_module("schedule_grid")


def overview_fixture():
    f = fixture()
    reading, home = normalize(f)
    raw = deepcopy(f["schedule"])
    source = next(iter(raw["fact"]["data"].values()))
    source["GPV3.1"] = {str(h): "yes" for h in range(1, 25)}
    source["GPV3.1"].update({"11": "first", "12": "msecond"})
    source["GPV4.1"] = {"1": "yes"}  # Incomplete is unknown, never clear.
    now = home.fetched_at
    start = now.astimezone(adapter.KYIV_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    overview = adapter.normalize_overview(
        reading, raw, start, start + timedelta(days=7), now
    )
    c = SimpleNamespace(
        overview=overview,
        address=reading.address,
        address_success=True,
        address_error=None,
        schedule_error=None,
        address_data={"schedule_groups": list(reading.groups)},
    )
    return c, home, reading, raw


class GridTests(unittest.TestCase):
    def test_segments_preserve_quarters_arbitrary_minutes_and_midnight(self):
        for a, b in ((735, 825), (727, 799), (1435, 1455)):
            with self.subTest(minutes=(a, b)):
                c, home, _, _ = overview_fixture()
                day = home.fetched_at.astimezone(adapter.KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
                c.overview = replace(c.overview, intervals=(contract.Interval('GPV3.1', 'outage', day+timedelta(minutes=a), day+timedelta(minutes=b), 'daily'),))
                result = grid.grid_data(c, now=home.fetched_at)['days'][0]
                row = next(r for r in result['rows'] if r['id']=='GPV3.1')
                actual = [p for p in row['segments'] if p['kind']=='outage']
                self.assertEqual(actual, [dict(start=a, end=min(b,1440), kind='outage')])
                self.assertEqual(row['segments'][0]['start'], 0)
                self.assertEqual(row['segments'][-1]['end'], 1440)
                self.assertEqual(len(row['cells']), 48)  # Old bot contract remains usable.

    def test_partial_coverage_is_split_at_exact_boundaries(self):
        c, home, _, _ = overview_fixture()
        day = home.fetched_at.astimezone(adapter.KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        c.overview = replace(c.overview, intervals=(), coverage=(contract.Coverage('GPV3.1','outage',day+timedelta(minutes=735),day+timedelta(minutes=825)),))
        row = next(r for r in grid.grid_data(c, now=home.fetched_at)['days'][0]['rows'] if r['id']=='GPV3.1')
        self.assertEqual(row['segments'], [dict(start=0,end=735,kind='unknown'), dict(start=735,end=825,kind='clear'), dict(start=825,end=1440,kind='unknown')])

    def test_daily_outage_takes_priority_over_possible_only_where_it_overlaps(self):
        c, home, _, _ = overview_fixture()
        day = home.fetched_at.astimezone(adapter.KYIV_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        c.overview = replace(c.overview, intervals=tuple(contract.Interval('GPV3.1',kind,day+timedelta(minutes=a),day+timedelta(minutes=b),'daily') for kind,a,b in [('possible',720,840),('outage',735,825)]))
        row = next(r for r in grid.grid_data(c, now=home.fetched_at)['days'][0]['rows'] if r['id']=='GPV3.1')
        self.assertEqual([(s['start'],s['end'],s['kind']) for s in row['segments'] if s['kind']!='clear'], [(720,735,'possible'),(735,825,'outage'),(825,840,'possible')])

    def test_exact_segments_use_elapsed_time_across_repeated_hour(self):
        c, _, _, _ = overview_fixture()
        day = datetime(2026,10,25,tzinfo=adapter.KYIV_TZ)
        c.overview = replace(c.overview, intervals=(contract.Interval('GPV3.1','outage',day.replace(hour=3,minute=15,fold=0),day.replace(hour=3,minute=45,fold=1),'daily'),), coverage=(contract.Coverage('GPV3.1','outage',day,day+timedelta(days=1)),))
        result = grid.grid_data(c, now=day)['days'][0]
        row = next(r for r in result['rows'] if r['id']=='GPV3.1')
        self.assertEqual(len(result['slots']),50)
        self.assertEqual([s for s in row['segments'] if s['kind']=='outage'], [dict(start=195,end=285,kind='outage')])
        self.assertEqual(row['segments'][-1]['end'],1500)

    def test_all_groups_are_returned_but_home_contract_stays_local(self):
        c, home, reading, _ = overview_fixture()
        result = grid.grid_data(c, ["GPV5.2"], now=home.fetched_at)
        rows = {r["id"]: r for r in result["days"][0]["rows"]}
        self.assertEqual(set(rows), {"GPV3.1", "GPV4.1", "GPV5.2"})
        self.assertEqual(tuple(g.id for g in home.groups), reading.groups)
        self.assertFalse(rows["GPV3.1"]["home"])
        self.assertTrue(rows["GPV5.2"]["home"] and rows["GPV5.2"]["selected"])
        self.assertEqual(
            rows["GPV3.1"]["cells"][20:24], ["outage", "clear", "clear", "possible"]
        )
        self.assertEqual(set(rows["GPV4.1"]["cells"]), {"unknown"})
        self.assertEqual(set(result["days"][1]["rows"][0]["cells"]), {"unknown"})

    def test_weekly_clear_is_forecast_not_confirmed_clear(self):
        c, home, reading, raw = overview_fixture()
        raw["fact"]["data"] = {}
        raw["preset"]["data"] = {
            "GPV5.2": {
                str(d): {str(h): "no" if h == 4 else "yes" for h in range(1, 25)}
                for d in range(1, 8)
            }
        }
        reading = replace(
            reading, publication=replace(reading.publication, weekly=True)
        )
        start = home.fetched_at.astimezone(adapter.KYIV_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        c.overview = adapter.normalize_overview(
            reading, raw, start, start + timedelta(days=7), home.fetched_at
        )
        cells = grid.grid_data(c, now=home.fetched_at)["days"][0]["rows"][0]["cells"]
        self.assertEqual(set(cells), {"forecast", "forecast_clear"})
        self.assertEqual(cells[6:8], ["forecast", "forecast"])

    def test_failures_and_disabled_publication_do_not_reuse_grid(self):
        c, home, _, _ = overview_fixture()
        c.schedule_error = "offline"
        self.assertEqual(grid.grid_data(c, now=home.fetched_at)["days"], [])
        c.schedule_error = None
        for flags in [
            replace(c.overview.publication, schedule=False),
            replace(c.overview.publication, schedule=None),
        ]:
            c.overview = replace(c.overview, publication=flags)
            self.assertEqual(
                grid.grid_data(c, now=home.fetched_at)["status"], "unpublished"
            )

    def test_website_hidden_labels_use_source_ids_without_losing_coverage(self):
        for visible in (False, None):
            c, home, _, _ = overview_fixture()
            c.overview = replace(
                c.overview,
                publication=replace(c.overview.publication, group_labels=visible),
                groups=tuple(replace(group, label=None) for group in c.overview.groups),
            )
            result = grid.grid_data(c, ["GPV5.2"], now=home.fetched_at)
            self.assertEqual(result["status"], "ready")
            rows = {r["id"]: r for r in result["days"][0]["rows"]}
            self.assertTrue(all(r["label"] == r["id"] for r in rows.values()))
            self.assertTrue(rows["GPV5.2"]["home"] and rows["GPV5.2"]["selected"])
            self.assertIn("outage", rows["GPV5.2"]["cells"])
            self.assertEqual(set(rows["GPV4.1"]["cells"]), {"unknown"})
            self.assertEqual(c.overview.publication.group_labels, visible)

    def test_bad_other_group_does_not_destroy_home_or_mark_empty(self):
        c, home, reading, raw = overview_fixture()
        next(iter(raw["fact"]["data"].values()))["GPV4.1"] = {"1": "corrupt"}
        start = home.fetched_at.astimezone(adapter.KYIV_TZ).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        c.overview = adapter.normalize_overview(
            reading, raw, start, start + timedelta(days=7), home.fetched_at
        )
        rows = {
            r["id"]: r
            for r in grid.grid_data(c, now=home.fetched_at)["days"][0]["rows"]
        }
        self.assertEqual(set(rows["GPV4.1"]["cells"]), {"unknown"})
        self.assertIn("outage", rows["GPV5.2"]["cells"])

    def test_dst_grid_retains_repeated_hour_and_skips_nonexistent_hour(self):
        c, _, _, _ = overview_fixture()
        for text, count in [
            ("2026-10-25T12:00:00+02:00", 50),
            ("2026-03-29T12:00:00+03:00", 46),
        ]:
            result = grid.grid_data(c, now=datetime.fromisoformat(text))
            slots = result["days"][0]["slots"]
            self.assertEqual(len(slots), count)
            self.assertEqual(len({s["start"] for s in slots}), count)
            threes = [s for s in slots if s["label"] == "03:00"]
            self.assertEqual(len(threes), 2 if count == 50 else 0)
            self.assertEqual(result["today"], text[:10])

    def test_midnight_selection_uses_kyiv_not_utc(self):
        c, _, _, _ = overview_fixture()
        result = grid.grid_data(c, now=datetime(2026, 10, 17, 22, tzinfo=timezone.utc))
        self.assertEqual(result["today"], "2026-10-18")
        self.assertEqual(
            result["days"][0]["slots"][0]["start"], "2026-10-17T21:00:00+00:00"
        )
