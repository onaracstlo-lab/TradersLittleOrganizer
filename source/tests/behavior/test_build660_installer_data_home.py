"""Build 660: per-user TLOHome setup, safe user-data boundaries, MSI-managed DBs."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

import tlo_msi_install_mode as mode

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tlo_build660_wix", ROOT / "msi" / "generate_wix.py")
WIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIX)
NS = {"w": WIX.NS, "ui": WIX.UI_NS}


def _generate(tmp_path, version="1.7.660"):
    stage = tmp_path / "signed"
    stage.mkdir()
    (stage / "tlo-main.exe").write_bytes(b"signed exe")
    (stage / "TLO_DBs").mkdir()
    (stage / "TLO_DBs" / "cities.sqlite").write_bytes(b"sample")
    wxs = tmp_path / "result.wxs"
    WIX.generate(stage, wxs, version)
    return ET.parse(wxs).getroot()


def test_msi_prompts_for_tlo_data_not_install_root_and_pins_ui_version(tmp_path):
    root = _generate(tmp_path)
    pkg = root.find("w:Package", NS)
    assert pkg.get("Scope") == "perUser"
    assert pkg.get("UpgradeCode") == WIX.UPGRADE_CODE
    ui = root.find(".//ui:WixUI", NS)
    assert ui is not None
    assert ui.get("InstallDirectory") == "TLODATAFOLDER"
    assert root.find(".//w:Directory[@Id='TLODATAFOLDER']", NS) is not None
    assert root.find(".//w:Directory[@Id='INSTALLFOLDER']", NS) is not None
    defaults = root.findall(".//w:SetDirectory", NS)
    assert {node.get("Action") for node in defaults} == {
        "SetTLODataInstalled", "SetTLODataExisting", "SetTLODataLegacy", "SetTLODataDefault",
    }
    assert all(node.get("Sequence") == "first" for node in defaults)
    assert next(x for x in defaults if x.get("Action") == "SetTLODataDefault").get("Value") == r"C:\.tlo"
    searches = root.findall(".//w:RegistrySearch", NS)
    assert {x.get("Name") for x in searches} == {"TLOHome", "DataHome"}
    assert all(x.get("Root") == "HKCU" for x in searches)


def test_msi_sets_persistent_user_environment_and_does_not_remove_tlohome(tmp_path):
    root = _generate(tmp_path)
    component = root.find(".//w:Component[@Id='TLOUserDataHomeConfiguration']", NS)
    assert component is not None
    assert component.get("Permanent") == "yes"
    assert component.get("Guid") == WIX.stable_guid("user-data/home-configuration")
    environment = component.find("w:Environment", NS)
    assert environment is not None
    assert environment.attrib == {
        "Id": "TLOHomeUserEnvironment", "Name": "TLOHome", "Action": "set",
        "Part": "all", "Permanent": "yes", "System": "no", "Value": "[TLODATAFOLDER]",
    }
    registry = component.find("w:RegistryValue", NS)
    assert registry.get("Key") == mode.MSI_USER_SETTINGS_KEY
    assert registry.get("Name") == "DataHome"
    assert registry.get("Value") == "[TLODATAFOLDER]"
    assert registry.get("Root") == "HKCU"
    assert registry.get("KeyPath") == "yes"
    removed = {node.get("Directory") for node in root.findall(".//w:RemoveFolder", NS)}
    assert "TLODATAFOLDER" not in removed
    assert "TLOUserDataHomeConfiguration" in {
        node.get("Id") for node in root.findall(".//w:ComponentRef", NS)}


def test_msi_ui_extension_is_pinned_and_localization_explains_editable_files():
    build = (ROOT / "msi" / "Build-TLO-MSI.ps1").read_text(encoding="utf-8")
    localization = (ROOT / "msi" / "TLO.en-us.wxl").read_text(encoding="utf-8")
    assert "WixToolset.UI.wixext/6.0.2" in build
    assert "-ext WixToolset.UI.wixext" in build
    assert "-loc" in build
    assert "Choose TLOHome" in localization
    assert "Application files install separately" in localization






def test_gui_open_tlo_folder_is_accessible_in_both_applications():
    main = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    search = (ROOT / "tlo-search.py").read_text(encoding="utf-8")
    for app in (main, search):
        assert 'label="Open TLO Folder"' in app
        assert "open_tlo_home_folder" in app






def test_open_folder_uses_arg_list_not_shell(tmp_path, monkeypatch):
    import subprocess
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))
    if mode.sys.platform == "win32":
        monkeypatch.setattr(mode.os, "startfile", lambda path: calls.append(([path], {"win32_startfile": True})))
    mode.open_tlo_home_folder(tmp_path)
    assert len(calls) == 1
    args, opts = calls[0]
    assert args[-1] == str(tmp_path.resolve())
    if mode.sys.platform == "win32":
        assert opts == {"win32_startfile": True}
    else:
        assert opts["close_fds"]
        assert args[0] in {"open", "xdg-open"}
