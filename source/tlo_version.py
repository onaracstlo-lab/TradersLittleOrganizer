"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v377"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
BUNDLE_BUILD = 377
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Add horizontal scrolling to Research results and make Search the Research dialog default Enter action.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
