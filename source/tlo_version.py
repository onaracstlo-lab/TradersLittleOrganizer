"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v335"
__version__ = VERSION
BUNDLE_BUILD = 335
DISPLAY_VERSION = f"v1.2 Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
