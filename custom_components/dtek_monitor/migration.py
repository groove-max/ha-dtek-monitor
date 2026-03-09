"""Migration helpers for DTEK Monitor."""

from __future__ import annotations

from collections.abc import Iterable


def migrate_entity_unique_id(
    unique_id: str,
    old_entry_id: str,
    new_entry_identifier: str,
) -> str | None:
    """Return a migrated entity unique ID if it still uses the old entry ID."""
    old_prefix = f"{old_entry_id}_"
    if not unique_id.startswith(old_prefix):
        return None

    suffix = unique_id[len(old_prefix) :]
    return f"{new_entry_identifier}_{suffix}"


def migrate_device_identifiers(
    identifiers: Iterable[tuple[str, str]],
    domain: str,
    old_entry_id: str,
    new_entry_identifier: str,
) -> set[tuple[str, str]] | None:
    """Return migrated device identifiers if the old integration identifier is present."""
    identifiers_set = set(identifiers)
    old_identifier = (domain, old_entry_id)
    if old_identifier not in identifiers_set:
        return None

    identifiers_set.discard(old_identifier)
    identifiers_set.add((domain, new_entry_identifier))
    return identifiers_set
