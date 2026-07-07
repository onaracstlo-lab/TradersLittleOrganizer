"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v322"
__version__ = VERSION
BUNDLE_BUILD = 322
DISPLAY_VERSION = f"v1.0 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
