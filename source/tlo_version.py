"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v347"
__version__ = VERSION
BUNDLE_BUILD = 347
DISPLAY_VERSION = f"v1.2 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Uses one main-window Dry run setting inherited live by Tag and Add Shows.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
