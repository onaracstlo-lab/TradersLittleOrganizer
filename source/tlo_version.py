"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v370"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 370
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Compares duplicate copies with each other using content-equivalence clusters and preferred keepers.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
