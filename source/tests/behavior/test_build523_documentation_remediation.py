from tests._release_artifacts import release_history
from tests import _release_artifacts as RA

import pytest

pytestmark = pytest.mark.behavior

"""Current documentation/history/metadata contracts (carried forward through Build 531)."""

from pathlib import Path
import re

from docx import Document

ROOT = Path(__file__).resolve().parents[2]


def _manual_text() -> str:
    return (ROOT / RA.MANUAL_FILENAME).read_text(encoding="utf-8", errors="ignore")


def test_build523_current_version_and_document_metadata():
    import tlo_version as version


    doc = Document(ROOT / RA.REQUIREMENTS_FILENAME)
    assert doc.core_properties.title == f"TLO Inventory Requirements - {version.DISPLAY_VERSION}"
    assert doc.core_properties.subject == f"Consolidated current specification for TLO {version.DISPLAY_VERSION}"

    rtf = _manual_text()
    assert rf"\title TLO Inventory User Manual {version.VERSION}" in rtf
    assert rf"\subject TLO {version.DISPLAY_VERSION} end-user manual" in rtf
    assert "Build 535 - " in release_history()
    assert "Native build supply-chain baseline" in release_history()
    assert "FFmpeg 9.0.2" in release_history() and "PyInstaller 6.22.3" in release_history()


def test_build523_manual_section_and_cli_contracts():
    rtf = _manual_text()
    # One TOC occurrence plus one actual heading; Build 522 had a third duplicated heading.
    assert rtf.count("8. Search paths, visible and unique volume names, and mount paths") == 2
    assert "SETLISTFMUPGRADE_API_KEY or SETLISTFM_UPGRADE_API_KEY" in rtf
    assert "Applies to executable(s)" in rtf
    assert "Required. Positional or named fully qualified search folder for every standalone tlo-tag run" in rtf
    assert "--tag-copy-delete-original" in rtf and "tlo-main" in rtf
    assert "tlo-main/tlo-gi default to all" in rtf
    assert "standalone tlo-tag defaults to never" in rtf


def test_build523_requirements_revision_index_is_descending_and_clean():
    doc = Document(ROOT / RA.REQUIREMENTS_FILENAME)
    ps = [p.text.strip() for p in doc.paragraphs]
    start = next(i for i, t in enumerate(ps) if t.startswith("21. Revision Index"))
    end = next(i for i, t in enumerate(ps[start + 1 :], start + 1) if t.startswith("Appendix A"))
    entries = [t for t in ps[start + 1 : end] if re.match(r"Build \d+:", t)]
    nums = [int(re.match(r"Build (\d+):", t).group(1)) for t in entries]
    assert nums == sorted(nums, reverse=True)
    assert 535 in nums and 533 in nums and 532 in nums and 531 in nums and 530 in nums and 529 in nums and 528 in nums and 527 in nums and 526 in nums and 523 in nums and 517 in nums
    assert not any(t.startswith("Build 469:") and "change summary ->" in t for t in entries)
    assert ps[end - 1].startswith("This index is navigational rather than normative.")
    assert not any(re.match(r"Build 51[5-7]:", t) for t in ps[end + 1 :])


def test_build523_current_terminology_faq_changes_and_carried_history():
    doc = Document(ROOT / RA.REQUIREMENTS_FILENAME)
    for p in doc.paragraphs:
        text = p.text.strip()
        if text.startswith("Build "):
            continue
        assert "Inventory GUI" not in text

    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Sections 4 through 7 of the User Manual" in faq
    assert "Inventory GUI" not in faq

    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "TLO v1.7 Build 528" in changes
    assert "TLO v1.7 Build 517" in changes

    root_test = (ROOT / "test_tlo_requirements.py").read_text(encoding="utf-8")
    assert "authoritative release regression suite" in root_test
    assert "compatibility subset" in root_test.lower()
    assert "must not be used as the sole official release gate" in root_test
