"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v367"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 367
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Moves qualifying duplicate folders into a partition-root duplicates holding folder instead of Trash/Recycle Bin.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
