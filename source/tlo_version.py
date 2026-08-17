"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v375"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
BUNDLE_BUILD = 375
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Correct weak path venue/location parsing and allow stronger selected-setlist metadata to replace it.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
