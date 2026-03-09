"""Unit tests for pure schedule-domain helpers."""

from __future__ import annotations

import datetime as dt
import unittest

from component_loader import load_component_module

schedule = load_component_module("schedule")


class ScheduleDomainTests(unittest.TestCase):
    """Regression tests for schedule merging and next-event lookup."""

    def test_fact_slots_trim_overlapping_preset_slots(self) -> None:
        """Preset windows should be cut around overlapping fact windows."""
        date = dt.date(2026, 3, 9)
        day_timestamp = str(
            int(dt.datetime(2026, 3, 9, 0, 0, tzinfo=schedule.KYIV_TZ).timestamp())
        )
        fact = {
            day_timestamp: {
                "GPV5.1": {
                    "9": "first",
                }
            }
        }
        preset = {
            "GPV5.1": {
                "1": {
                    "9": "maybe",
                }
            }
        }

        windows = schedule.get_schedule_windows_for_date(
            date,
            ["GPV5.1"],
            fact,
            preset,
            event_type="possible",
        )

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0].start.hour, 8)
        self.assertEqual(windows[0].start.minute, 30)
        self.assertEqual(windows[0].end.hour, 9)
        self.assertEqual(windows[0].end.minute, 0)

    def test_next_event_search_scans_entire_week(self) -> None:
        """Calendar helper should find the next event beyond a 48-hour horizon."""
        now = dt.datetime(2026, 3, 9, 12, 0, tzinfo=schedule.KYIV_TZ)
        preset = {
            "GPV5.1": {
                "5": {
                    "10": "maybe",
                }
            }
        }

        window = schedule.find_current_or_next_window(
            now,
            ["GPV5.1"],
            {},
            preset,
            event_type="possible",
        )

        self.assertIsNotNone(window)
        self.assertEqual(window.start.date(), dt.date(2026, 3, 13))
        self.assertEqual(window.start.hour, 9)
        self.assertEqual(window.end.hour, 10)


if __name__ == "__main__":
    unittest.main()
