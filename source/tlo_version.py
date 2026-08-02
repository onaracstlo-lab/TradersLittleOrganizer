"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v352"
__version__ = VERSION
BUNDLE_BUILD = 352
DISPLAY_VERSION = f"v1.2 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Slows the GUI activity indicator animation to one-tenth of its previous speed.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
