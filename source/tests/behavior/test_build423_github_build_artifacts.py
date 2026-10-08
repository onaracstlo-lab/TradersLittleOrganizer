"""Build 423 regression coverage for GitHub Build Process separation."""
from __future__ import annotations
from tests import _release_artifacts as RA

from pathlib import Path

from docx import Document
import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _doc_text(path: Path) -> str:
    d = Document(path)
    chunks = [p.text for p in d.paragraphs]
    for table in d.tables:
        for row in table.rows:
            chunks.extend(cell.text for cell in row.cells)
    return "\n".join(chunks)


def test_build423_public_version_and_current_documents():
    import tlo_version as V

    assert V.PUBLIC_VERSION == "1.7"
    assert (ROOT / RA.REQUIREMENTS_FILENAME).is_file()
    assert (ROOT / RA.MANUAL_FILENAME).is_file()


def test_build423_source_bundle_contains_no_github_build_process_artifacts():
    forbidden = [
        ROOT / "Run-TLO-GitHub-Build.ps1",
        ROOT / "Create-TLOArtifactSigningMetadata.ps1",
    ]
    assert not any(path.exists() for path in forbidden)
    assert not list(ROOT.glob("TLO_GitHub_Build_Process_Requirements_v*.docx"))
    assert not list(ROOT.glob("TLO_GitHub_Build_Process_v*.zip"))


def test_build423_tlo_requirements_record_strict_separation_rule():
    req = ROOT / RA.REQUIREMENTS_FILENAME
    text = _doc_text(req)
    assert "source bundle and the independently versioned GitHub Build Process are separate artifacts" in text
    assert "shall contain no GitHub Build Process files" in text
    assert "Run-TLO-GitHub-Build.ps1" in text
    assert "Create-TLOArtifactSigningMetadata.ps1" in text
    assert "distributed only as its own independently versioned package" in text
