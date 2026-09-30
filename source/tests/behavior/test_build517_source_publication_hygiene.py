"""Build 517: source publication must not contain scratch requirements documents."""
from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def test_build517_has_exactly_one_current_requirements_document():
    docs = sorted(ROOT.glob("TLO_Inventory_Requirements_Working_v*.docx"))
    assert [p.name for p in docs] == ["TLO_Inventory_Requirements_Working_v517.docx"]


def test_build517_rejects_requirements_work_files_at_source_root():
    names = [p.name for p in ROOT.iterdir() if p.is_file()]
    offenders = [
        name for name in names
        if name.lower().endswith(".docx") and (
            name.lower().endswith(".tmp.docx")
            or re.match(r"^req\d+.*\.docx$", name, flags=re.IGNORECASE)
            or ("requirements" in name.lower() and name != "TLO_Inventory_Requirements_Working_v517.docx")
        )
    ]
    assert offenders == []
