"""Unit tests for migration helpers."""

from __future__ import annotations

import unittest

from component_loader import load_component_module

migration = load_component_module("migration")


class MigrationHelperTests(unittest.TestCase):
    """Regression tests for config-entry registry migration helpers."""

    def test_migrate_entity_unique_id_rewrites_old_prefix(self) -> None:
        """Old entry_id-based unique IDs should migrate to address-based IDs."""
        migrated = migration.migrate_entity_unique_id(
            "01ABC_power",
            "01ABC",
            "м. Одеса_дорога Люстдорфська_56В",
        )

        self.assertEqual(
            migrated,
            "м. Одеса_дорога Люстдорфська_56В_power",
        )

    def test_migrate_entity_unique_id_ignores_other_entries(self) -> None:
        """Unique IDs that are already migrated should be left untouched."""
        migrated = migration.migrate_entity_unique_id(
            "м. Одеса_дорога Люстдорфська_56В_power",
            "01ABC",
            "м. Одеса_дорога Люстдорфська_56В",
        )

        self.assertIsNone(migrated)

    def test_migrate_device_identifiers_swaps_only_integration_identifier(self) -> None:
        """Device identifier migration should preserve unrelated identifiers."""
        migrated = migration.migrate_device_identifiers(
            {("dtek_monitor", "01ABC"), ("other", "value")},
            "dtek_monitor",
            "01ABC",
            "м. Одеса_дорога Люстдорфська_56В",
        )

        self.assertEqual(
            migrated,
            {
                ("dtek_monitor", "м. Одеса_дорога Люстдорфська_56В"),
                ("other", "value"),
            },
        )


if __name__ == "__main__":
    unittest.main()
