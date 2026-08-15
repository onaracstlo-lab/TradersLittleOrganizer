"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v363"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 363
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Adds tlo-deleteDupes for safe recursive cleanup of copy-suffixed duplicate folders via the platform Trash/Recycle Bin.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
