"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v621"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 621
DISPLAY_VERSION = "v1.7 Build 621"
VERSION_SUMMARY = "Resolve comma-delimited city-only show folders and corroborate ambiguous dates"
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
