"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v407"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 407
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Artist DB fallback now treats terminal All Star/All Stars spellings like Band, and Research results add window-level select-all plus forward/backward wrapped text search."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
