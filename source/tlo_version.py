"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v455"
__version__ = VERSION
PUBLIC_VERSION = "1.6"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 455
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 455 reconciles resolved entries out of unidentifiedShows.txt, preserves encounter order in unidentified show/artist review files, and trims the Corrupt files dropdown width."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
