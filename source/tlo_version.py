"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v681"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 681
DISPLAY_VERSION = "v1.7 Build 681"
VERSION_SUMMARY = 'Fix macOS path-length and Trash test contracts and Windows bootlist path verification'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
