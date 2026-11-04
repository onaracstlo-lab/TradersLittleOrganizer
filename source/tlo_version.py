"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v610"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 610
DISPLAY_VERSION = "v1.7 Build 610"
VERSION_SUMMARY = "Resilient SHA-256 pinned FFmpeg source acquisition and CI caching"
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
