"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v746"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 746
DISPLAY_VERSION = "v1.7 Build 746"
VERSION_SUMMARY = 'Close legacy storage-identity SQLite connections explicitly on success and failure, including test setup. Use the existing read-only catalog opener. Preserve log-owned identity, migration backups and reversal safeguards. Build Process v170 and database masters unchanged.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
