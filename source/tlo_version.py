"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v361"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 361
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Fixes commercial-release naming and guarantees complete recursive folder-tree transfer and verification for copy operations.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
