"""Central release-version constants for the TLO Inventory bundle."""

VERSION = "v394"
__version__ = VERSION
PUBLIC_VERSION = "1.4"
BUNDLE_BUILD = 394
DISPLAY_VERSION = f"v{PUBLIC_VERSION} Build {BUNDLE_BUILD}"
VERSION_SUMMARY = 'Harden Linux CI regression tests so synthetic FLAC fixtures explicitly opt out of corruption removal; runtime behavior is unchanged.'
def versioned_title(base_title: str) -> str:
    """Return a GUI title containing the public version/build string."""
    base = str(base_title or "").strip()
    return f"{base} {DISPLAY_VERSION}".strip()
