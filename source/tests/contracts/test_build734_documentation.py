"""Keep the current specification, catalog, and user guidance in agreement."""
import csv
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from tlo_version import BUNDLE_BUILD
from tests import _release_artifacts as A

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _norm(text):
    return " ".join(text.split())


def _paragraph_text(paragraph):
    return "".join(
        node.text or "" if node.tag.endswith("}t") else " "
        for node in paragraph.iter()
        if node.tag.rsplit("}", 1)[-1] in {"t", "tab", "br", "cr"}
    )


def test_current_requirements_catalog_locators_and_text():
    with zipfile.ZipFile(ROOT / f"TLO_Inventory_Requirements_Working_v{BUNDLE_BUILD}.docx") as archive:
        body = ET.fromstring(archive.read("word/document.xml")).find("w:body", NS)
    paragraphs = body.findall("w:p", NS)
    tables = body.findall("w:tbl", NS)
    with (ROOT / f"TLO_Requirements_Catalog_v{BUNDLE_BUILD}.csv").open(
        encoding="utf-8-sig", newline=""
    ) as catalog:
        rows = list(csv.DictReader(catalog))
    assert len({row["Requirement_ID"] for row in rows}) == len(rows)
    counts = {"paragraph": 0, "table": 0}
    for row in rows:
        locator = row["Source_Locator"]
        match = re.fullmatch(r"paragraph (\d+)", locator)
        if match:
            index = int(match[1])
            expected = _paragraph_text(paragraphs[index])
            counts["paragraph"] += 1
        else:
            match = re.fullmatch(r"table (\d+), row (\d+)", locator)
            if not match:
                continue  # supplemental requirements retain separate provenance
            table, number = map(int, match.groups())
            cells = tables[table - 1].findall("w:tr", NS)[number - 1].findall("w:tc", NS)
            # Match Word's merged-cell expansion when a cell spans columns.
            values = []
            for cell in cells:
                value = " ".join(_paragraph_text(p) for p in cell.findall("w:p", NS))
                span = cell.find("w:tcPr/w:gridSpan", NS)
                values.extend([value] * (int(span.attrib[f"{{{NS['w']}}}val"]) if span is not None else 1))
            expected = " | ".join(values)
            counts["table"] += 1
        assert _norm(expected) == _norm(row["Requirement_Text"]), (row["Requirement_ID"], locator)
    assert counts["paragraph"] >= 732
    assert counts["table"] >= 293


def test_current_manual_faq_and_readme_explain_reverse_and_cleanup():
    manual = (ROOT / f"TLO_Inventory_User_Manual_v{BUNDLE_BUILD}.rtf").read_text(encoding="utf-8")
    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8")
    readme = (ROOT / f"SOURCE_BUNDLE_README_v{BUNDLE_BUILD}.txt").read_text(encoding="utf-8")
    report = (ROOT / A.BUILD_VERIFICATION_FILENAME).read_text(encoding="utf-8")
    for document in (manual, faq, readme):
        folded = document.casefold()
        assert "reverse" in folded
        assert "confirmation" in folded or "confirm" in folded
        assert "reversefolders.log" in folded
        assert "rmdir /s /q" in folded
    assert f"NOT ATTESTED for Build {BUNDLE_BUILD}" in report
