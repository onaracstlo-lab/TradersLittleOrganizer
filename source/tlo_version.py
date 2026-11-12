"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v653"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 653
DISPLAY_VERSION = "v1.7 Build 653"
VERSION_SUMMARY = "Approved GitHub releases only; pre-releases excluded from updates"
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
