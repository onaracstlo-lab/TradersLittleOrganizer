"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v411"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 411
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Track-list candidate selection now uses audio-count agreement first and positive-only filename/title-tag corroboration to distinguish numbered notes from real song lists."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
