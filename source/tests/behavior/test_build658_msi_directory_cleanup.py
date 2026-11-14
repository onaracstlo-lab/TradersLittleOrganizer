"""Build 658: ICE64 requires uninstall entries for all per-user MSI directories."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tlo_build658_wix", ROOT / "msi" / "generate_wix.py")
WIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIX)
NS = {"w": WIX.NS}


def _render(stage: Path, version: str, files: tuple[str, ...]) -> ET.Element:
    for relative in files:
        destination = stage / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"signed placeholder")
    output = stage.parent / f"test-{version}.wxs"
    WIX.generate(stage, output, version)
    return ET.parse(output).getroot()


def _cleanup(root: ET.Element) -> ET.Element:
    component = root.find(".//w:Component[@Id='TLOInstallDirectoryCleanup']", NS)
    assert component is not None
    assert component.get("Guid") == WIX.stable_guid("directory-cleanup/install-root")
    values = component.findall("w:RegistryValue", NS)
    assert len(values) == 1
    assert values[0].get("Root") == "HKCU"
    assert values[0].get("KeyPath") == "yes"
    assert values[0].get("Name") == "DirectoryCleanup"
    refs = [node.get("Id") for node in root.findall(".//w:ComponentRef", NS)]
    assert refs.count("TLOInstallDirectoryCleanup") == 1
    return component


def test_wix_ice64_all_created_profile_directories_have_remove_entries(tmp_path):
    """Mimic hosted 657: intermediate THIRD_PARTY folders have no direct files."""
    root = _render(tmp_path / "stage", "1.7.658", (
        "tlo-main.exe",
        "THIRD_PARTY/vendor/runtime.dll",
        "THIRD_PARTY/vendor/architecture/native.dll",
        "THIRD_PARTY/other/license.txt",
        "tlo-main_runtime/package/data/fixture.dat",
        "isolated/child/level/only.txt",
    ))
    component = _cleanup(root)
    created = {node.get("Id") for node in root.findall(".//w:Directory", NS)
               if node.get("Id") not in {"TLOProgramsMenu", "TARGETDIR", "TLODATAFOLDER"}}
    # Only cleanup our own %LOCALAPPDATA%\\Programs\\TLO tree, not a shared
    # parent profile directory (or TLOHome).
    created.update(("TLOLocalProgramsDir", "INSTALLFOLDER"))
    remove = component.findall("w:RemoveFolder", NS)
    removed = [node.get("Directory") for node in remove]
    assert len(removed) == len(set(removed))
    assert set(removed) == created
    assert all(node.get("On") == "uninstall" for node in remove)
    assert "LocalAppDataFolder" not in removed
    assert "TLOHome" not in removed
    assert "TLODATAFOLDER" not in removed
    # ICE64 would have flagged these directories with no direct file child.
    for path in ("THIRD_PARTY", "THIRD_PARTY/vendor", "tlo-main_runtime", "isolated/child"):
        assert WIX.stable_id("Dir", path) in removed


def test_wix_ice64_root_cleanup_without_root_level_files(tmp_path):
    """Installation root must still be removable when main.exe lives nested."""
    root = _render(tmp_path / "stage", "1.7.658", (
        "bin/tlo-main.exe", "bin/tlo-search.exe", "THIRD_PARTY/vendor/native.dll",
    ))
    component = _cleanup(root)
    removed = {node.get("Directory") for node in component.findall("w:RemoveFolder", NS)}
    assert "INSTALLFOLDER" in removed
    assert "TLOLocalProgramsDir" in removed
    assert WIX.stable_id("Dir", "bin") in removed


def test_wix_directory_cleanup_component_stable_across_upgrades(tmp_path):
    files = ("tlo-main.exe", "THIRD_PARTY/vendor/a.dll", "THIRD_PARTY/vendor/deep/b.dll")
    roots = [_render(tmp_path / f"stage-{build}", f"1.7.{build}", files) for build in (657, 658)]
    components = [_cleanup(root) for root in roots]
    assert components[0].get("Guid") == components[1].get("Guid")
    assert [{node.get("Id") for node in comp.findall("w:RemoveFolder", NS)}
            for comp in components][0] == {
                node.get("Id") for node in components[1].findall("w:RemoveFolder", NS)
            }
    assert roots[0].find("w:Package", NS).get("UpgradeCode") == roots[1].find("w:Package", NS).get("UpgradeCode")


def test_wix_cleanup_not_owned_by_file_component(tmp_path):
    root = _render(tmp_path / "stage", "1.7.658", (
        "tlo-main.exe", "THIRD_PARTY/vendor/runtime.dll",
    ))
    cleanup = _cleanup(root)
    files = root.findall(".//w:File", NS)
    assert len(files) == 2
    assert cleanup.findall("w:File", NS) == []
    assert all(not node.findall("w:RemoveFolder", NS)
               for node in root.findall(".//w:Component", NS) if node is not cleanup
               and node.get("Id") != "TLOStartMenuComponent")
