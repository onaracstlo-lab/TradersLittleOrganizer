"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v325"
__version__ = VERSION
BUNDLE_BUILD = 325
DISPLAY_VERSION = f"v1.1 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Removes the editable TLOHome fields from the Inventory and Search GUIs while preserving myTLO/TLOHome/environment precedence.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
