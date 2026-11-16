"""Build 667: ensure the shipped Requirements DOCX remains readable and self-contained."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree
from docx import Document
import tlo_version as V
import pytest

pytestmark = pytest.mark.contract

ROOT = Path(__file__).resolve().parents[2]

def test_requirements_docx_opc_package_and_every_xml_part():
    path=ROOT/f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx"
    with ZipFile(path) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert len(set(names))==len(names)
        assert all(x in names for x in ("[Content_Types].xml","_rels/.rels","word/document.xml","word/styles.xml"))
        for name in names:
            if name.endswith((".xml",".rels")):
                etree.fromstring(z.read(name))
        relationships = etree.fromstring(z.read("_rels/.rels"))
        relationship_types = [r.get("Type") for r in relationships]
        assert "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" in relationship_types

def test_requirements_contains_entire_consolidated_specification():
    d=Document(ROOT/f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx")
    assert d.core_properties.title == f"TLO Inventory Requirements - {V.DISPLAY_VERSION}"
    assert len(d.paragraphs)>=1200
    assert len(d.tables)==13
    text="\n".join(p.text for p in d.paragraphs)
    assert f"Current document version: {V.VERSION}" in text
    assert f"TLO_Requirements_Catalog_{V.VERSION}.csv" in text
    assert "21. Revision Index" not in text
    assert "Appendix K - Supplemental Current Operational Requirements" in text

def test_manual_rtf_format_and_version():
    rtf=(ROOT/f"TLO_Inventory_User_Manual_{V.VERSION}.rtf").read_text(encoding="latin-1")
    assert rtf.startswith("{\\rtf1")
    assert "update_downloads = msi" in rtf
    assert "update_downloads = zip" in rtf
