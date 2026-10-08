"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v570"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 570
DISPLAY_VERSION = "v1.7 Build 570"
VERSION_SUMMARY = "Build 570 aligns SignTool security contract with GitHub CI generated Windows builder."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
