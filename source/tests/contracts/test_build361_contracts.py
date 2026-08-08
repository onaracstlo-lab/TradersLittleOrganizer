"""Build 361 documentation and release contracts."""

__version__ = "v361"

from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def _docx_text(name):
    doc = Document(ROOT / name)
    return "\n".join(p.text for p in doc.paragraphs)


def test_build361_requirements_define_commercial_release_year_and_no_duplicate_artist():
    text = _docx_text("TLO_Inventory_Requirements_Working_v361.docx")
    assert "(1991) - Rod Stewart - Vagabond Heart" in text
    assert "The release year is classification evidence only" in text
    assert "do not assign it to DATE and do not include it in SHOW_NAME" in text
    assert "remove that one redundant Artist component" in text
    assert "String2 Rod Stewart - Camouflage produces ALBUM_NAME Camouflage" in text
    assert "SHOW_NAME Rod Stewart - Camouflage" in text


def test_build361_requirements_define_complete_recursive_transfer_tree():
    text = _docx_text("TLO_Inventory_Requirements_Working_v361.docx")
    assert "complete identified source folder tree rooted at MAIN_DIR_PATH" in text
    assert "including non-music files and empty directories" in text
    assert "descendant directory structure" in text


def test_build361_manual_documents_commercial_release_and_complete_tree_copy():
    text = (ROOT / "TLO_Inventory_User_Manual_v361.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "Commercial releases may use (YYYY) - Artist - Album or YYYY - Artist - Album" in text
    assert "does not write the year to DATE or include it in the Show Name" in text
    assert "Rod Stewart - Rod Stewart - Camouflage becomes Rod Stewart - Camouflage" in text
    assert "complete identified folder tree" in text
    assert "non-music files and empty subfolders" in text


def test_build361_archives_prior_change_log():
    with ZipFile(ROOT / "old-change-logs.zip") as zf:
        assert "CHANGES_v360.txt" in zf.namelist()
