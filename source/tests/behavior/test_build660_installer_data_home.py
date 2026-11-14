"""Build 660: per-user TLOHome setup, safe user-data boundaries, MSI-managed DBs."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

import tlo_msi_install_mode as mode
from tlo_version import BUNDLE_BUILD

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
    (stage / "TLO_DBs" / "cities.csv").write_bytes(b"sample")
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
        "SetTLODataExisting", "SetTLODataLegacy", "SetTLODataDefault",
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


def test_managed_db_master_replaced_on_new_msi_build_only(tmp_path, monkeypatch):
    install = tmp_path / "app"
    masters = install / "TLO_DBs"
    masters.mkdir(parents=True)
    for db in mode.MSI_MANAGED_DATABASES:
        (masters / db).write_bytes(b"new " + db.encode())
    home = tmp_path / "data"
    (home / "TLO_DBs").mkdir(parents=True)
    for db in mode.MSI_MANAGED_DATABASES:
        (home / "TLO_DBs" / db).write_bytes(b"user edit")
    (home / "bootlist.csv").write_bytes(b"inventory")
    (home / "tlo-preferences.ini").write_bytes(b"preferences")
    marker = home / "TLO_DBs" / mode.MSI_DATABASE_BUILD_MARKER
    marker.write_text("659\n", encoding="utf-8")
    monkeypatch.setattr(mode, "msi_install_root", lambda: install)
    mode.seed_msi_data_home(home)
    for db in mode.MSI_MANAGED_DATABASES:
        assert (home / "TLO_DBs" / db).read_bytes() == b"new " + db.encode()
    assert (home / "bootlist.csv").read_bytes() == b"inventory"
    assert (home / "tlo-preferences.ini").read_bytes() == b"preferences"
    assert marker.read_text().strip() == str(BUNDLE_BUILD)
    (home / "TLO_DBs" / "cities.csv").write_bytes(b"edited after upgrade")
    mode.seed_msi_data_home(home)
    assert (home / "TLO_DBs" / "cities.csv").read_bytes() == b"edited after upgrade"
    marker.write_text("659\n")
    mode.seed_msi_data_home(home)
    assert (home / "TLO_DBs" / "cities.csv").read_bytes() == b"new cities.csv"


def test_validation_rejects_program_directory_and_writes_probe(tmp_path):
    install = tmp_path / "app"
    install.mkdir()
    child = install / "user-data"
    with pytest.raises(ValueError, match="outside"):
        mode._validated_msi_home(child, install)
    valid = mode._validated_msi_home(tmp_path / "data", install)
    assert valid.is_dir()
    assert not list(valid.iterdir())  # probe cleaned up


def test_gui_open_tlo_folder_is_accessible_in_both_applications():
    main = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    search = (ROOT / "tlo-search.py").read_text(encoding="utf-8")
    for app in (main, search):
        assert 'label="Open TLO Folder"' in app
        assert "open_tlo_home_folder" in app


def test_failed_db_replacement_does_not_advance_build_marker(tmp_path, monkeypatch):
    program = tmp_path / "program"
    master = program / "TLO_DBs"
    master.mkdir(parents=True)
    for name in mode.MSI_MANAGED_DATABASES:
        (master / name).write_bytes(name.encode())
    home = tmp_path / "user-home"
    managed = home / "TLO_DBs"
    managed.mkdir(parents=True)
    marker = managed / mode.MSI_DATABASE_BUILD_MARKER
    marker.write_text("659\n")
    monkeypatch.setattr(mode, "msi_install_root", lambda: program)
    def fail_replace(_source, _dest):
        raise PermissionError("locked db")
    monkeypatch.setattr(mode, "_write_atomic_from_file", fail_replace)
    with pytest.raises(PermissionError, match="locked db"):
        mode.seed_msi_data_home(home)
    assert marker.read_text() == "659\n"


def test_saved_user_environment_preferred_and_synced_without_admin(tmp_path, monkeypatch):
    import sys
    from types import SimpleNamespace

    program = tmp_path / "program"
    program.mkdir()
    home = tmp_path / "prior-environment-home"
    home.mkdir()
    other = tmp_path / "stale-saved-home"
    other.mkdir()
    values = {
        ("Environment", "TLOHome"): str(home),
        (mode.MSI_USER_SETTINGS_KEY, "DataHome"): str(other),
    }

    class FakeKey:
        def __init__(self, path):
            self.path = path
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
    fake = SimpleNamespace(HKEY_CURRENT_USER=object(), REG_SZ=1)
    def get_key(_root, path):
        if not any(k[0] == path for k in values):
            raise FileNotFoundError(path)
        return FakeKey(path)
    fake.OpenKey = get_key
    fake.CreateKey = lambda _root, key: FakeKey(key)
    fake.QueryValueEx = lambda key, name: (values[(key.path, name)], 1)
    fake.SetValueEx = lambda key, name, _unused, _type, value: values.__setitem__((key.path, name), value)
    monkeypatch.setitem(sys.modules, "winreg", fake)
    monkeypatch.setattr(mode, "msi_install_root", lambda: program)
    monkeypatch.setenv("TLOHome", str(home))
    calls = []
    monkeypatch.setattr(mode, "seed_msi_data_home", lambda selected: calls.append(selected))
    assert mode.ensure_msi_tlo_home()
    assert values[("Environment", "TLOHome")] == str(home)
    assert values[(mode.MSI_USER_SETTINGS_KEY, "DataHome")] == str(home)
    assert calls == [home.resolve()]


def test_open_folder_uses_arg_list_not_shell(tmp_path, monkeypatch):
    import subprocess
    calls = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))
    mode.open_tlo_home_folder(tmp_path)
    assert len(calls) == 1
    args, opts = calls[0]
    assert opts["close_fds"]
    assert args[-1] == str(tmp_path.resolve())
    assert args[0] in {"open", "xdg-open"}
