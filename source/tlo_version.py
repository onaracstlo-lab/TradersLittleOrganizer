"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v324"
__version__ = VERSION
BUNDLE_BUILD = 324
DISPLAY_VERSION = f"v1.1 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
