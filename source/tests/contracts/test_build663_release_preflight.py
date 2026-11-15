"""Build 663: stop release packaging when versioned documentation regresses."""

from pathlib import Path
import importlib.util
import re
import xml.etree.ElementTree as ET
from docx import Document
import pytest
import tlo_version as V

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def test_normative_requirements_never_contain_historical_build_labels():
    doc = Document(ROOT / f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx")
    paragraphs = [p.text for p in doc.paragraphs]
    revision_index = next(i for i, text in enumerate(paragraphs)
                          if text.startswith("21. Revision Index"))
    assert any("20. Destructive Operations Safety" in p for p in paragraphs[:revision_index])
    misplaced = [(i, p[:120]) for i, p in enumerate(paragraphs[:revision_index])
                 if re.search(r"\bBuild\s+\d+", p)]
    assert not misplaced, f"Historical build labels outside Revision Index: {misplaced}"
    assert f"Build {V.BUNDLE_BUILD}" in "\n".join(paragraphs[revision_index:])
    assert "license-agreement dialog SHALL display" in "\n".join(paragraphs[:revision_index])
    assert "build-provenance.json" in "\n".join(paragraphs[:revision_index])
    assert V.VERSION in paragraphs[4]
    assert V.VERSION in paragraphs[6]
    assert f"CHANGES_{V.VERSION}.txt" in paragraphs[7]
    assert f"Build {V.BUNDLE_BUILD}" in doc.core_properties.title
    assert f"Build {V.BUNDLE_BUILD}" in doc.core_properties.subject
    assert doc.core_properties.revision == V.BUNDLE_BUILD
    assert f"CHANGES_{V.VERSION}.txt" in "\n".join(paragraphs[revision_index:])


def test_release_source_has_one_current_report_set_without_stale_versions():
    for prefix in ("CHANGES", "BUILD_VERIFICATION", "REGRESSION_RESULTS",
                   "SOURCE_BUNDLE_README", "SHA256SUMS"):
        candidates = sorted(ROOT.glob(prefix + "_v[0-9]*.txt"))
        assert [p.name for p in candidates] == [f"{prefix}_{V.VERSION}.txt"]
    assert (ROOT / f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx").is_file()
    assert (ROOT / f"TLO_Inventory_User_Manual_{V.VERSION}.rtf").is_file()
    assert V.VERSION == f"v{V.BUNDLE_BUILD}"
    assert V.BUNDLE_BUILD >= 663
    report = (ROOT / f"BUILD_VERIFICATION_{V.VERSION}.txt").read_text(encoding="utf-8")
    assert "lint not attested" in report
    assert "full GitHub Actions run" in report
    assert "NOT RELEASE-ATTESTED" in report
    readme = (ROOT / f"SOURCE_BUNDLE_README_{V.VERSION}.txt").read_text(encoding="utf-8")
    process_version = re.search(r"Native GitHub Build Process: (v\d+)", readme)
    assert process_version, "Current build-process version missing from source README"
    assert process_version.group(1) in report


def test_msi_wix_generator_license_and_layout_preflight(tmp_path):
    spec = importlib.util.spec_from_file_location("tlo_msi_build663", ROOT / "msi" / "generate_wix.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    staged = tmp_path / "signed"
    nested = staged / "tlo-main_runtime" / "THIRD_PARTY"
    nested.mkdir(parents=True)
    (staged / "tlo-main.exe").write_bytes(b"exe")
    (nested / "payload.dll").write_bytes(b"dll")
    wxs = tmp_path / "installer.wxs"
    result = mod.generate(staged, wxs, f"1.7.{V.BUNDLE_BUILD}")
    assert result["file_count"] == 2
    xml = ET.parse(wxs).getroot()
    ns = {"w": mod.NS, "ui": mod.UI_NS}
    roots = xml.findall('.//w:StandardDirectory[@Id="TARGETDIR"]', ns)
    assert len(roots) == 1
    assert not xml.findall('.//w:Directory[@Id="TARGETDIR"]', ns)
    licenses = xml.findall('.//w:WixVariable[@Id="WixUILicenseRtf"]', ns)
    assert len(licenses) == 1
    assert Path(licenses[0].get('Value')).is_file()
    assert xml.find('.//ui:WixUI[@Id="WixUI_InstallDir"]', ns) is not None
