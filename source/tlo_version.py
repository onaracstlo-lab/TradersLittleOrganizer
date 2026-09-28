"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v511"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 511
DISPLAY_VERSION = "v1.7 Build 511"
VERSION_SUMMARY = "Build 511 expands Copy Request Path(s) input to mix direct items and .txt lists, appends repeated drops, and persists the expanded request snapshot for later passes."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
