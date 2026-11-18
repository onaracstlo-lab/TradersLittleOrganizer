"""Build 677: executable local release gate accepts current requirements schema."""
from pathlib import Path
import os
import sys
import importlib.util
from types import SimpleNamespace
import pytest
from tests import _release_artifacts as RA

ROOT=Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.contract


def _gate():
    spec=importlib.util.spec_from_file_location("tlo_gate677", ROOT/"tools"/"verify_release_gates.py")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_gate_uses_current_requirements_and_absolutepath_interpreter(monkeypatch):
    m=_gate()
    seen=[]
    monkeypatch.setattr(m.subprocess,"run",lambda argv,**kw: seen.append((argv,kw)) or SimpleNamespace(returncode=0))
    assert m.main()==0
    assert len(seen)==2
    assert all(os.path.isabs(argv[0]) and argv[0] == sys.executable for argv,_ in seen)
    assert all(kw["env"]["PYTHONDONTWRITEBYTECODE"]=="1" for _,kw in seen)


def test_gate_refuses_failed_tool_without_false_pass(monkeypatch):
    m=_gate()
    seen=[]
    monkeypatch.setattr(m.subprocess,"run",lambda argv,**kw: seen.append(argv) or SimpleNamespace(returncode=13))
    assert m.main()==1 and len(seen)==1


def test_versioned_requirements_core_metadata_matches_runtime():
    from docx import Document
    import tlo_version as V
    doc=Document(ROOT/RA.REQUIREMENTS_FILENAME)
    assert doc.core_properties.title==f"TLO Inventory Requirements - {V.DISPLAY_VERSION}"
    assert doc.core_properties.subject==f"Current testable technical and functional requirements, TLO {V.DISPLAY_VERSION}"
