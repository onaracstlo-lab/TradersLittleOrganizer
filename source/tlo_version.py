"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v512"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 512
DISPLAY_VERSION = "v1.7 Build 512"
VERSION_SUMMARY = "Build 512 renames the main GUI, aligns automatic Max Workers with Performance Mode, and adds persisted trailing-asterisk Copy Request folder expansion."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
