"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v319"
__version__ = VERSION
BUNDLE_BUILD = 319
DISPLAY_VERSION = f"v1.0 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
