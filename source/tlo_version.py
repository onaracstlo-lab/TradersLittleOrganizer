"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v663"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 663
DISPLAY_VERSION = "v1.7 Build 663"
VERSION_SUMMARY = "Build 662 Linux documentation-release regression correction"
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
