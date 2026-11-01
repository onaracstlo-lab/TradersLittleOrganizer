"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v603"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 603
DISPLAY_VERSION = "v1.7 Build 603"
VERSION_SUMMARY = "Editable per-TLOHome startup preferences for Main, Search, and child windows"
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
