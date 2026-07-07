"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v320"
__version__ = VERSION
BUNDLE_BUILD = 320
DISPLAY_VERSION = f"v1.0 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Adds prebuilt Windows ICO and macOS ICNS icon assets and uses packaged icon files during native builds.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
