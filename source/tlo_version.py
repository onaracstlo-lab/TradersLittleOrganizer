"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v351"
__version__ = VERSION
BUNDLE_BUILD = 351
DISPLAY_VERSION = f"v1.2 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Uses normal dark text for donation details and corrects the About contact wording.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
