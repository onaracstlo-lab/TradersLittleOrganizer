"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v334"
__version__ = VERSION
BUNDLE_BUILD = 334
DISPLAY_VERSION = f"v1.2 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Rearranges the main-window checkboxes into the requested two-row, four-column layout.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
