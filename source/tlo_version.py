"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v406"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 406
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "CI regression fixtures for non-corruption inventory behavior explicitly neutralize corruption classification, eliminating Trash-backend-dependent false failures while preserving Build 405 application behavior."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
