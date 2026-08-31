"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v423"
__version__ = VERSION
PUBLIC_VERSION = "1.5"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 423
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Build 423 carries the current Run-TLO-GitHub-Build.ps1 and matching GitHub Build Process requirements document directly in the source bundle instead of embedding the full build-process ZIP."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
