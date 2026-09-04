"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v433"
__version__ = VERSION
PUBLIC_VERSION = "1.5"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 433
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 433 extracts corruption decisions into directly testable fail-closed assessment and mutation stages and consolidates current requirements."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
