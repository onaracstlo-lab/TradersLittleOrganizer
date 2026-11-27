"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v735"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 735
DISPLAY_VERSION = "v1.7 Build 735"
VERSION_SUMMARY = 'Resolve the PowerShell case-insensitive HOME automatic-variable collision in the Windows MSI installation smoke test and opt-in acceptance diagnostics. Keep all signing, native install/uninstall and database/shortcut acceptance gates.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
