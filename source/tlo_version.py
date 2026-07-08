"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v327"
__version__ = VERSION
BUNDLE_BUILD = 327
DISPLAY_VERSION = f"v1.1 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Updates source version stamping and release-test compatibility for the injected GitHub release builder.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
