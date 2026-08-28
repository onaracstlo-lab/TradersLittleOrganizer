"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v415"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 415
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Copy/Delete destination parents are append containers, not broad re-inventory scopes; only exact current destination rows may be replaced."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
