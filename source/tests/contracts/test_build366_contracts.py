"""Build 367 alphabetical-master duplicate-cleanup contracts."""

__version__ = "v367"

from pathlib import Path
from zipfile import ZipFile

import pytest
from docx import Document

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def _docx_text(name: str) -> str:
    doc = Document(ROOT / name)
    chunks = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                chunks.extend(p.text for p in cell.paragraphs)
    return "\n".join(chunks)


def test_build366_source_discovers_unsuffixed_same_artist_date_groups_alphabetically():
    source = (ROOT / "tlo-deleteDupes.py").read_text(encoding="utf-8")
    assert "_matching_unsuffixed_duplicate_groups" in source
    assert "_alphabetical_name_key" in source
    assert "first folder is the master" in source
    assert 'source_kind="alphabetical"' in source
    assert "directory_trees_match_for_duplicate_deletion(master, later_path)" in source


def test_build366_requirements_define_unsuffixed_alphabetical_master_rule():
    text = _docx_text("TLO_Inventory_Requirements_Working_v367.docx")
    assert "18.2 Candidate Discovery and Alphabetical Master Selection" in text
    assert "sort those unsuffixed directory names alphabetically without regard to case" in text
    assert "The alphabetically first directory is the master and shall be protected from relocation" in text
    assert "Each later unsuffixed directory is treated as a copy candidate" in text
    assert "A later unsuffixed folder that does not match the alphabetically first master remains in place" in text


def test_build366_manual_documents_unsuffixed_alphabetical_master_rule():
    text = (ROOT / "TLO_Inventory_User_Manual_v367.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "folders that have no (copyN) suffix" in text
    assert "sorted alphabetically without regard to case" in text
    assert "The first folder alphabetically is the master and is always kept" in text
    assert "Every later folder is treated as a copy candidate" in text
    assert "later folder that differs from the first master is left alone" in text


def test_build366_faq_mentions_unsuffixed_alphabetical_master_cleanup():
    text = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "same-parent folders with no copy suffix" in text
    assert "analyzed alphabetically" in text
    assert "the first folder is kept as the master" in text


def test_build366_archives_build365_change_log():
    with ZipFile(ROOT / "old-change-logs.zip") as zf:
        assert "CHANGES_v365.txt" in zf.namelist()
