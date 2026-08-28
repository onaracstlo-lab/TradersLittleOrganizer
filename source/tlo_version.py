"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v414"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 414
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = "Structured collaboration headers can resolve component artists safely, location tails no longer become weak path artists, and exact-count bare track-number blocks write Unknown titles."
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
