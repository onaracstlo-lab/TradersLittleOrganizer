"""Build 636: prevent ZIP members that Windows Expand-Archive cannot extract."""
from __future__ import annotations

from pathlib import Path
from tlo_version import BUNDLE_BUILD
import re
import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
_FORBIDDEN = set('<>:"/\\|?*')
_RESERVED = re.compile(r"(?i)^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?$")


def test_release_source_members_use_windows_compatible_names():
    for item in ROOT.rglob('*'):
        relative = item.relative_to(ROOT)
        for component in relative.parts:
            assert not (_FORBIDDEN & set(component)), f"invalid Windows ZIP member: {relative}"
            assert component == component.rstrip(' .'), f"trailing dot/space: {relative}"
            assert not _RESERVED.fullmatch(component), f"Windows device name: {relative}"


def test_current_checksum_manifest_never_lists_protocol_pipes():
    manifest = ROOT / f'SHA256SUMS_v{BUNDLE_BUILD}.txt'
    if manifest.exists():
        assert all('pipe:1' not in line for line in manifest.read_text(encoding='utf-8').splitlines())
