"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v456"
__version__ = VERSION
PUBLIC_VERSION = "1.6"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 456
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 456 moves folder reversal out of the Inventory GUI into the standalone tlo-reverse CLI, which infers logged rename/copy/copy-delete operations and never changes tags."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
