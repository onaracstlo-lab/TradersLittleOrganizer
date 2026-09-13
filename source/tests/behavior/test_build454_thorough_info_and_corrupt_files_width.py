"""Build 454: Thorough status appears only for slow normal setlist.fm access."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v458"

ROOT = Path(__file__).resolve().parents[2]


def _source() -> str:
    return (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")


def _load_gui_module():
    from tests import _legacy_suite as legacy
    return legacy._load_local_module("tlo-ggi.py", "tlo_ggi_build454")


@pytest.mark.parametrize(
    "thorough,etree,setlistfm,upgrade",
    [
        (False, False, False, False),
        (False, True, True, False),
        (True, False, False, False),
        (True, True, False, False),
        (True, False, True, True),
        (True, True, True, True),
    ],
)
def test_build454_no_thorough_info_except_slow_normal_setlistfm(thorough, etree, setlistfm, upgrade):
    gui = _load_gui_module()
    assert gui._thorough_setlist_info_message(
        thorough=thorough,
        etree_enabled=etree,
        setlistfm_enabled=setlistfm,
        setlistfm_upgrade=upgrade,
    ) == ""


def test_build454_thorough_normal_setlistfm_warns_that_it_will_be_slow():
    gui = _load_gui_module()
    message = gui._thorough_setlist_info_message(
        thorough=True,
        etree_enabled=True,
        setlistfm_enabled=True,
        setlistfm_upgrade=False,
    )
    assert "will be slow" in message
    assert "600-ms / 1,400-call limits" in message
    assert "etreeDB" not in message


def test_build454_corrupt_files_dropdown_fits_longest_label():
    source = _source()
    block = source[source.index('self.corrupt_files_combo = ttk.Combobox'):source.index('self.corrupt_files_combo.grid')]
    assert 'width=18' in block  # Build 456 trims the Build 454 widening
    assert '"delete": "Delete corrupt files"' in source
