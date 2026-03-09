"""Unit tests for DTEK client parsing helpers."""

from __future__ import annotations

import unittest

from component_loader import load_component_module

dtek_client = load_component_module("dtek_client")


class ParseHouseDataTests(unittest.TestCase):
    """Regression tests for normalized outage payloads."""

    def test_parse_house_data_keeps_all_groups_and_primary_group(self) -> None:
        """Multiple outages should preserve all groups and pick the severe outage."""
        api_response = {
            "updateTimestamp": "09.03.2026 08:05",
            "data": {
                "56В": [
                    {
                        "sub_type": "Планове відключення",
                        "start_date": "08:00 09.03.2026",
                        "end_date": "10:00 09.03.2026",
                        "sub_type_reason": ["GPV5.1", "GPV5.2"],
                        "type": "1",
                    },
                    {
                        "sub_type": "Екстрене відключення",
                        "start_date": "09:00 09.03.2026",
                        "end_date": "11:00 09.03.2026",
                        "sub_type_reason": ["GPV5.3"],
                        "type": "2",
                    },
                ]
            },
        }

        parsed = dtek_client.DTEKClient.parse_house_data(api_response, "56в")

        self.assertFalse(parsed["power_on"])
        self.assertEqual(parsed["outage_type"], "emergency")
        self.assertEqual(parsed["outage_description"], "Екстрене відключення")
        self.assertEqual(parsed["schedule_groups"], ["GPV5.1", "GPV5.2", "GPV5.3"])
        self.assertEqual(parsed["primary_schedule_group"], "GPV5.1")
        self.assertEqual(parsed["outage_count"], 2)

    def test_parse_schedule_from_html_handles_nested_objects(self) -> None:
        """HTML parser should extract both schedule objects without greedy overmatch."""
        html = """
        <script>
        DisconSchedule.fact = {"update":"09.03.2026 08:00","data":{"1741471200":{"GPV5.1":{"9":"no"}}}};
        const ignored = {"outer":{"inner":"value"}};
        DisconSchedule.preset = {"updateFact":"09.03.2026 08:00","data":{"GPV5.1":{"1":{"9":"maybe","10":"msecond"}}}};
        </script>
        """

        parsed = dtek_client._parse_schedule_from_html(html)

        self.assertIsNotNone(parsed)
        self.assertEqual(
            parsed["fact"]["data"]["1741471200"]["GPV5.1"]["9"],
            "no",
        )
        self.assertEqual(
            parsed["preset"]["data"]["GPV5.1"]["1"]["10"],
            "msecond",
        )


if __name__ == "__main__":
    unittest.main()
