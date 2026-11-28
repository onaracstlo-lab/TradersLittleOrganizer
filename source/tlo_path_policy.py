"""Shared filesystem exclusions and temporary-tree policy for TLO."""

from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

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
    ".tlo-case-rename-",
    ".tlo-copy-",
    ".tlo-partial-",
    ".tlo-restore-",
    ".tlo-convert-",
    ".tlo-shn-originals",
    ".tlo-deletedupes-originals-",
)


def is_tlo_work_directory(name: str) -> bool:
    return str(name or "").strip().casefold().startswith(TLO_TEMP_DIR_PREFIXES)


def is_phase1_pruned_directory(name: str) -> bool:
    lowered = str(name or "").strip().casefold()
    return (
        lowered in OS_MANAGED_DIR_NAMES
        or any(lowered.startswith(prefix) for prefix in TLO_TEMP_DIR_PREFIXES)
    )


def is_ignorable_filesystem_artifact(name: str) -> bool:
    """Exclude OS sidecars and TLO-generated scratch files, not ordinary dotfiles."""
    import os
    leaf = os.path.basename(str(name or "").replace("\\", "/")).casefold()
    return (leaf.startswith(("._", ".tlo-"))
            or leaf in {".ds_store", "thumbs.db", "desktop.ini"})
