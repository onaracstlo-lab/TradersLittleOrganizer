"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v518"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 517
DISPLAY_VERSION = "v1.7 Build 518"
VERSION_SUMMARY = "Build 518 replaces the packaged inventory-app icon artwork with the supplied TLO Main icon and regenerates the packaged inventory icon resources."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
