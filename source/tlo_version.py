"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v614"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 614
DISPLAY_VERSION = "v1.7 Build 614"
VERSION_SUMMARY = "Build 532 verification report headless skip-count contract restored; runtime unchanged"
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
