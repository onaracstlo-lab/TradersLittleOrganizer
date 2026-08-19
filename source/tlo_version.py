"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v378"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
BUNDLE_BUILD = 378
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Defer short artist abbreviations until stronger artist evidence is exhausted and use them only as a last resort.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
