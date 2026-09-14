"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v465"
__version__ = VERSION
PUBLIC_VERSION = "1.6"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 465
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 465 recovers interrupted sibling-collection journals across native Windows and WSL path forms, including the colliding collection-container case, without weakening recovery validation."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
