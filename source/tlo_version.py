"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v369"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 369
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Adds Research log lookup by artist/date, venue, or date in the CLI and Inventory GUI.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
