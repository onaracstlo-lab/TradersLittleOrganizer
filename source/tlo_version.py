"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v318"
__version__ = VERSION
BUNDLE_BUILD = 318
DISPLAY_VERSION = f"v1.0 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
