"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v743"
__version__ = VERSION
PUBLIC_VERSION = "1.7"
OFFICIAL_GITHUB_OWNER = "onaracstlo-lab"
OFFICIAL_GITHUB_REPO = "TradersLittleOrganizer"
BUNDLE_BUILD = 743
DISPLAY_VERSION = "v1.7 Build 743"
VERSION_SUMMARY = 'Bound generic ancestor artist evidence to the selected root and prevent explicit dated artist text or existing tags from being replaced by container names; fold accent queries against the Artist DB; report non-Latin unrepresentable artists as unidentified; use the actual rename guard in Dry Run; lock mutating CLI Tag, GUI Tag and duplicate cleanup. Exclude TLO work/held-original directories from Tag Copy and Copy Requests; refuse Copy/Delete when held data is nested; retain duplicate-repair originals with source-relative provenance and log repairs; warn to re-inventory after moves; align home options, safe confirmation defaults, auxiliary search and CLI preview.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
