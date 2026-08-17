"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v372"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
BUNDLE_BUILD = 372
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Research accepts the full canonical TLO date grammar, and the public application version advances to 1.4.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
