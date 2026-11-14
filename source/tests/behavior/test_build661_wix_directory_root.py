"""Build 661: keep WiX 6 TARGETDIR virtual and release docs unique."""
from pathlib import Path
import importlib.util
import xml.etree.ElementTree as ET

import pytest

from tlo_version import BUNDLE_BUILD

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
MODULE_SPEC = importlib.util.spec_from_file_location("tlo_wix_generator_661", ROOT / "msi" / "generate_wix.py")
WIX = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(WIX)
NS = {"w": WIX.NS, "ui": WIX.UI_NS}


def _generated(tmp_path):
    stage = tmp_path / "signed"
    stage.mkdir()
    (stage / "tlo-main.exe").write_bytes(b"test")
    (stage / "THIRD_PARTY" / "vendor").mkdir(parents=True)
    (stage / "THIRD_PARTY" / "vendor" / "lib.dll").write_bytes(b"lib")
    wxs = tmp_path / "generated.wxs"
    WIX.generate(stage, wxs, f"1.7.{BUNDLE_BUILD}")
    return ET.parse(wxs).getroot()


def test_wix6_uses_virtual_targetdir_reference_not_conflicting_definition(tmp_path):
    root = _generated(tmp_path)
    assert root.findall(".//w:Directory[@Id='TARGETDIR']", NS) == []
    refs = root.findall(".//w:StandardDirectory[@Id='TARGETDIR']", NS)
    assert len(refs) == 1
    data_dir = refs[0].find("w:Directory[@Id='TLODATAFOLDER']", NS)
    assert data_dir is not None
    assert data_dir.get("Name") == ".tlo"
    assert root.find(".//w:Directory[@Id='INSTALLFOLDER']", NS) is not None
    ui = root.find(".//ui:WixUI", NS)
    assert ui is not None and ui.get("InstallDirectory") == "TLODATAFOLDER"
    assert root.find(".//w:SetDirectory[@Action='SetTLODataDefault']", NS).get("Value") == r"C:\.tlo"
    assert root.find(".//w:Component[@Id='TLOUserDataHomeConfiguration']", NS) is not None


def test_661_source_does_not_ship_old_release_verification_or_results():
    for base in ("BUILD_VERIFICATION", "REGRESSION_RESULTS", "SHA256SUMS"):
        names = sorted(p.name for p in ROOT.glob(f"{base}_v*.txt"))
        if base == "SHA256SUMS" and not names:  # Added at package creation.
            continue
        assert names == [f"{base}_v{BUNDLE_BUILD}.txt"]


def test_wix_build_uses_pinned_ui_extension_and_keeps_ice_gate():
    script = (ROOT / "msi" / "Build-TLO-MSI.ps1").read_text(encoding="utf-8")
    assert "WixToolset.UI.wixext/6.0.2" in script
    assert "wix -- msi validate" in script
    assert "WiX MSI build failed" in script
