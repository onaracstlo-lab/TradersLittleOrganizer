"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v487"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 487
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 487 adds ordered redundancy groups so Copy Requests can use equivalent backup volumes by declared precedence."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
