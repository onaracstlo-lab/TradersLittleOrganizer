"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v472"
__version__ = VERSION
PUBLIC_VERSION = "1.6"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 472
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 472 makes Auto Update ask Yes/Skip before downloading and adds a blank starter bootlist.csv to complete distributions through the GitHub Build Process."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
