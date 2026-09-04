"""Build 375 Research application and GUI contracts."""

__version__ = "v433"

from pathlib import Path

import pytest

pytestmark = pytest.mark.contract
from docx import Document

ROOT = Path(__file__).resolve().parents[2]


def _docx_text(name: str) -> str:
    doc = Document(ROOT / name)
    return "\n".join(p.text for p in doc.paragraphs)


def test_research_sources_are_present_and_gui_is_wired():
    cli = (ROOT / "tlo-research.py").read_text(encoding="utf-8")
    lib = (ROOT / "tlo_research_lib.py").read_text(encoding="utf-8")
    gui = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'prog="tlo-research"' in cli
    assert '"--TLOHome"' in cli
    assert '"--myTLO"' in cli
    assert "resolve_tlo_home" in cli
    assert "meta*.log" in lib
    assert "comp*.log" in lib
    assert 'text="Research\\n "' in gui
    assert "command=self._open_research" in gui
    assert "research_logs" in gui


def test_research_is_built_on_all_platforms():
    windows = (ROOT / "createWindowsDist.ps1").read_text(encoding="utf-8")
    linux = (ROOT / "createLinuxDist.sh").read_text(encoding="utf-8")
    mac = (ROOT / "createMacOSDist.sh").read_text(encoding="utf-8")
    assert "tlo-research.py" in windows
    assert "tlo-research.exe" in windows
    assert "tlo-research.py" in linux
    assert "tlo-research.py" in mac
    assert "tlo-research" in mac


def test_research_documentation_is_present():
    requirements = _docx_text("TLO_Inventory_Requirements_Working_v433.docx")
    manual = (ROOT / "TLO_Inventory_User_Manual_v433.rtf").read_text(encoding="utf-8", errors="ignore")
    for text in (requirements, manual):
        assert "tlo-research" in text
        assert "artist followed by a date" in text.lower()
        assert "meta*.log" in text
        assert "comp*.log" in text
        assert "Research" in text
        assert "ALL RELATED RAW LOG LINES" in text
        assert "line number" in text.lower()
