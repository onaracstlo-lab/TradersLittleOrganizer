"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v510"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 510
DISPLAY_VERSION = "v1.7 Build 510"
VERSION_SUMMARY = "Build 510 fixes the Ruff F541 lint error in the cross-platform collection-recovery regression test; application behavior is unchanged from Build 509."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
