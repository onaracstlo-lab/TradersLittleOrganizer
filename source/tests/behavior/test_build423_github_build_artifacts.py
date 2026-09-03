"""Build 423 regression coverage for source-bundled GitHub build artifacts."""
from __future__ import annotations

from pathlib import Path

from docx import Document
import pytest

pytestmark = pytest.mark.behavior
__version__ = "v426"

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "Run-TLO-GitHub-Build.ps1"
BUILD_REQ = ROOT / "TLO_GitHub_Build_Process_Requirements_v075.docx"


def _doc_text(path: Path) -> str:
    d = Document(path)
    chunks = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            chunks.extend(cell.text for cell in row.cells)
    return "\n".join(chunks)


def test_build423_public_version_and_current_documents():
    import tlo_version as V

    assert V.VERSION == "v426"
    assert V.PUBLIC_VERSION == "1.5"
    assert V.BUNDLE_BUILD == 426
    assert V.DISPLAY_VERSION == "v1.5 Build 426"
    assert (ROOT / "TLO_Inventory_Requirements_Working_v426.docx").is_file()
    assert (ROOT / "TLO_Inventory_User_Manual_v426.rtf").is_file()


def test_build423_source_bundle_carries_runner_and_matching_requirements_not_process_zip():
    assert RUNNER.is_file()
    assert BUILD_REQ.is_file()
    assert not list(ROOT.glob("TLO_GitHub_Build_Process_v*.zip"))
    runner_text = RUNNER.read_text(encoding="utf-8-sig")
    assert "$ProcessVersion = 'v075'" in runner_text


def test_build423_build_requirements_focus_on_runner_and_setup_assumptions():
    text = _doc_text(BUILD_REQ)
    assert "Process v075" in text
    assert "Run-TLO-GitHub-Build.ps1" in text
    assert "3. Operating Assumptions" in text
    assert "setup-script behavior is intentionally outside this requirements baseline" in text
    assert "01-Install-Prerequisites.ps1" not in text
    assert "02-Create-Build-Repository.ps1" not in text
    assert "05-Create-Release-Repository.ps1" not in text


def test_build423_tlo_requirements_record_direct_artifact_rule():
    req = ROOT / "TLO_Inventory_Requirements_Working_v426.docx"
    text = _doc_text(req)
    assert "Current document version: v426 (v1.5 Build 426)." in text
    assert "Beginning with Build 423" in text
    assert "Run-TLO-GitHub-Build.ps1" in text
    assert "TLO_GitHub_Build_Process_Requirements_v<PROCESS>.docx" in text
    assert "complete GitHub Build Process ZIP is no longer embedded" in text
