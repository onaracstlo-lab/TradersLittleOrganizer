"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v517"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 517
DISPLAY_VERSION = "v1.7 Build 517"
VERSION_SUMMARY = "Build 517 removes stray requirements-document work files from the source publication and adds source-bundle hygiene regression coverage."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
