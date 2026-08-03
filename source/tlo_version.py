"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v354"
__version__ = VERSION
BUNDLE_BUILD = 354
DISPLAY_VERSION = f"v1.2 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Prevents broad collection roots from being aggregated or renamed and preserves Artist in Album during full-inventory tagging.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
