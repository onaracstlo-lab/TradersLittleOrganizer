"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v362"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 362
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Classifies name collisions as copy only after exact recursive tree/content comparison; non-identical collisions are labeled alt.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
