"""Build 519: Main/Search application filenames and packaging names are aligned."""
from tests import _release_artifacts as RA

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8", errors="ignore")


def test_build519_source_entry_points_replace_old_names():
    assert (ROOT / "tlo-main.py").is_file()
    assert (ROOT / "tlo-search.py").is_file()
    assert not (ROOT / "tlo-ggi.py").exists()
    assert not (ROOT / "tlo-gsi.py").exists()
    assert 'prog="tlo-main"' in _text("tlo-main.py")
    assert 'APP_FILE_NAME = "tlo-search"' in _text("tlo-search.py")


def test_build519_platform_builders_emit_new_names_only():
    linux = _text("createLinuxDist.sh")
    mac = _text("createMacOSDist.sh")
    win = _text("createWindowsDist.ps1")

    for text in (linux, mac, win):
        assert "tlo-ggi" not in text
        assert "tlo-gsi" not in text

    assert "find_script tlo-main.py" in linux
    assert "find_script tlo-search.py" in linux
    assert "find_script tlo-main.py" in mac
    assert "find_script tlo-search.py" in mac
    assert "tlo-main.app" in mac
    assert "tlo-search.app" in mac
    assert "Find-SourceScript 'tlo-main.py'" in win
    assert "Find-SourceScript 'tlo-search.py'" in win
    assert "tlo-main.exe" in win
    assert "tlo-search.exe" in win


def test_build519_user_facing_docs_use_new_application_names():
    manual = _text(RA.MANUAL_FILENAME)
    faq = _text("TLO-FAQ.txt")
    readme = _text(RA.SOURCE_README_FILENAME)
    assert "tlo-main.exe" in manual and "tlo-search.exe" in manual
    assert "Does tlo-main accept --tag-path?" in faq
    assert "tlo-main.py: Main GUI." in readme
    assert "tlo-search.py: collection search." in readme
