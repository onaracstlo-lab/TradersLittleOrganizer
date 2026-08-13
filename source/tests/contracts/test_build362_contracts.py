"""Build 362 documentation and release contracts."""

__version__ = "v362"

from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def _docx_text(name):
    doc = Document(ROOT / name)
    return "\n".join(p.text for p in doc.paragraphs)


def test_build362_requirements_define_commercial_release_year_and_no_duplicate_artist():
    text = _docx_text("TLO_Inventory_Requirements_Working_v362.docx")
    assert "(1991) - Rod Stewart - Vagabond Heart" in text
    assert "The release year is classification evidence only" in text
    assert "do not assign it to DATE and do not include it in SHOW_NAME" in text
    assert "remove that one redundant Artist component" in text
    assert "String2 Rod Stewart - Camouflage produces ALBUM_NAME Camouflage" in text
    assert "SHOW_NAME Rod Stewart - Camouflage" in text


def test_build362_requirements_define_complete_recursive_transfer_tree():
    text = _docx_text("TLO_Inventory_Requirements_Working_v362.docx")
    assert "complete identified source folder tree rooted at MAIN_DIR_PATH" in text
    assert "including non-music files and empty directories" in text
    assert "descendant directory structure" in text


def test_build362_manual_documents_commercial_release_and_complete_tree_copy():
    text = (ROOT / "TLO_Inventory_User_Manual_v362.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "Commercial releases may use (YYYY) - Artist - Album or YYYY - Artist - Album" in text
    assert "does not write the year to DATE or include it in the Show Name" in text
    assert "Rod Stewart - Rod Stewart - Camouflage becomes Rod Stewart - Camouflage" in text
    assert "complete identified folder tree" in text
    assert "non-music files and empty subfolders" in text


def test_build362_archives_prior_change_log():
    with ZipFile(ROOT / "old-change-logs.zip") as zf:
        assert "CHANGES_v361.txt" in zf.namelist()


def test_build362_requirements_define_exact_copy_vs_alt_classification():
    text = _docx_text("TLO_Inventory_Requirements_Working_v362.docx")
    assert "Copy-versus-alternate naming is determined by exact recursive tree identity" in text
    assert "relative descendant directory set (including empty directories)" in text
    assert "byte contents of every corresponding file are all identical" in text
    assert "use (altN), never (copyN)" in text
    assert "input folder already ending in (copyN) must be revalidated" in text


def test_build362_manual_documents_copy_vs_alt_classification():
    text = (ROOT / "TLO_Inventory_User_Manual_v362.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "does not call the new folder a copy merely because the name is already present" in text
    assert "A (copyN) suffix is used only when" in text
    assert "make the new item an (altN) instead" in text
    assert "existing folder already named with (copyN) is also rechecked" in text
