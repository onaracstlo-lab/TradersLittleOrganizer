"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v359"
__version__ = VERSION
PUBLIC_VERSION = "1.3"
BUNDLE_BUILD = 359
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Refines copy verification so same-partition Copy/Delete uses a size-free directory move while every real copy is verified by file size.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
