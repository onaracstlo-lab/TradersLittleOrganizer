"""Build 397 contracts for the v396 technical-review remediation."""
__version__ = "v426"

import ast
import re
import zipfile
from pathlib import Path

import pytest
from docx import Document

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
CATEGORY_MARKERS = {"unit", "behavior", "contract", "integration"}


def _pytestmark_names(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names=set()
    for node in tree.body:
        if not isinstance(node, ast.Assign): continue
        if not any(isinstance(t, ast.Name) and t.id=="pytestmark" for t in node.targets): continue
        for child in ast.walk(node.value):
            if isinstance(child, ast.Attribute) and isinstance(child.value, ast.Attribute):
                if isinstance(child.value.value, ast.Name) and child.value.value.id=="pytest" and child.value.attr=="mark":
                    names.add(child.attr)
    return names


def test_every_test_module_has_exactly_one_category_marker_and_traits_are_used():
    all_marks=set()
    for path in sorted((ROOT/"tests").rglob("test_*.py")):
        marks=_pytestmark_names(path); all_marks |= marks
        assert len(marks & CATEGORY_MARKERS) == 1, f"{path.name}: {sorted(marks)}"
    assert "gui" in all_marks
    assert "slow" in all_marks


def test_requirements_authoritative_range_has_no_numbered_heading_above_20():
    doc=Document(ROOT/"TLO_Inventory_Requirements_Working_v426.docx")
    numbered=[]
    for p in doc.paragraphs:
        if p.style.name == "Heading 1":
            m=re.match(r"^(\d+)\.", p.text.strip())
            if m: numbered.append(int(m.group(1)))
    assert numbered and max(numbered) == 20


def test_no_stale_per_module_version_summary_metadata_remains():
    for path in ROOT.glob("*.py"):
        text=path.read_text(encoding="utf-8", errors="ignore")
        assert "__version_summary__" not in text, path.name
        assert "TLO-GI package version:" not in text, path.name
        assert "TLO-GI version summary:" not in text, path.name


def test_manual_keywords_and_version_are_current():
    text=(ROOT/"TLO_Inventory_User_Manual_v426.rtf").read_text(encoding="utf-8", errors="ignore")
    import tlo_version as V
    assert "Build,, ,373" not in text
    assert f"Version {V.DISPLAY_VERSION}" in text


def test_updater_has_no_environment_repository_redirect():
    text=(ROOT/"tlo_github_updates.py").read_text(encoding="utf-8")
    assert "TLO_GITHUB_OWNER" not in text
    assert "TLO_GITHUB_REPO" not in text
    assert "MAX_UPDATE_ASSET_BYTES" in text


def test_setlist_metadata_read_is_bounded():
    text=(ROOT/"tlo_setlist_metadata_lookup.py").read_text(encoding="utf-8")
    assert "Path(path).read_bytes()" not in text
    assert "MAX_TEXT_SAMPLE_BYTES" in text and "MAX_TEXT_FULL_BYTES" in text


def test_setlistfm_utility_delegates_to_production_lookup():
    text=(ROOT/"setlistFM.py").read_text(encoding="utf-8")
    assert "from tlo_setlistfm_lookup import" in text
    assert "urllib.request" not in text


def test_legacy_monolith_no_longer_contains_v395_v396_regressions():
    text=(ROOT/"tests/_legacy_suite.py").read_text(encoding="utf-8")
    assert "# v395 - structured double-dash" not in text
    assert "# v396 - setlist filename artist" not in text
