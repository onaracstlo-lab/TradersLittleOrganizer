"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v440"
__version__ = VERSION
PUBLIC_VERSION = "1.5"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 440
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 440 hardens group identity/date consensus, dotted setlist metadata parsing, bootlist conflict safety, and Copy/Delete hard-case recovery."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
