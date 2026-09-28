"""Shared filesystem exclusions and temporary-tree policy for TLO."""

from __future__ import annotations

__version__ = "v511"

# Operating-system maintained directories that are not part of a music
# collection.  Callers decide whether exclusions are root-only or recursive.
OS_MANAGED_DIR_NAMES = frozenset({
    "$recycle.bin",
    "system volume information",
    ".spotlight-v100",
    ".fseventsd",
    ".trashes",
    ".temporaryitems",
})

# TLO-owned work trees must never be inventoried as shows.  Prefix matching is
# case-insensitive and recursive in Phase 1.
TLO_TEMP_DIR_PREFIXES = (
    ".tlo-collection-",
    ".tlo-copy-",
    ".tlo-partial-",
    ".tlo-restore-",
    ".tlo-convert-",
)


def is_phase1_pruned_directory(name: str) -> bool:
    lowered = str(name or "").strip().casefold()
    return (
        lowered in OS_MANAGED_DIR_NAMES
        or any(lowered.startswith(prefix) for prefix in TLO_TEMP_DIR_PREFIXES)
    )
