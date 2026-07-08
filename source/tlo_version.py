"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v328"
__version__ = VERSION
BUNDLE_BUILD = 328
DISPLAY_VERSION = f"v1.1 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
