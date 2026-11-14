"""Build 657: MSI major-upgrade path is isolated from portable ZIP updates."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

import tlo_github_updates as U
import tlo_msi_install_mode as mode
from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("tlo_generate_wix", ROOT / "msi" / "generate_wix.py")
WIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIX)


def test_official_msi_identity_and_unrecognized_assets():
    assert U._asset_release_identity("TLO_V1.7Build657_Windows_x64.msi") == (657, "msi", "windows_msi")
    assert U._asset_release_identity("TLO_V1.7Build654_Windows_x64.msi") == (654, "msi", "windows_msi")
    assert U._asset_release_identity("random_installer.msi") is None


def release():
    return {"assets": [
        {"name": "TLO_V1.7Build657_update_Windows_onedir.zip"},
        {"name": "TLO_V1.7Build657_Windows_x64.msi"},
    ]}


def test_msi_selects_only_installer(monkeypatch):
    monkeypatch.setattr(U, "is_msi_install", lambda: True)
    result = U._choose_asset(release(), 657)
    assert result[1:] == ("msi", "windows_msi")
    assert result[0]["name"].endswith(".msi")


def test_msi_cannot_fall_back_to_zip(monkeypatch):
    monkeypatch.setattr(U, "is_msi_install", lambda: True)
    only_zip = {"assets": [release()["assets"][0]]}
    assert U._choose_asset(only_zip, 657) == (None, "", "windows_msi")


def test_portable_cannot_select_msi(monkeypatch):
    monkeypatch.setattr(U, "is_msi_install", lambda: False)
    monkeypatch.setattr(U, "_detect_installed_platform_key", lambda _: "windows_onedir")
    selected = U._choose_asset(release(), 657)
    assert selected[1:] == ("update", "windows_onedir")


def test_verified_msi_header_required(tmp_path):
    fake = tmp_path / ".temporary.pending"
    fake.write_bytes(b"not_msi")
    with pytest.raises(ValueError, match="database header"):
        U._inspect_verified_release_asset(fake, package_kind="msi", platform_key="windows_msi", latest_build=657)
    fake.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"data")
    assert U._inspect_verified_release_asset(fake, package_kind="msi", platform_key="windows_msi", latest_build=657)["packaging_mode"] == "msi-per-user"


def test_msi_launch_requires_signed_download_result(tmp_path, monkeypatch):
    monkeypatch.setattr(U, "is_msi_install", lambda: True)
    with pytest.raises(ValueError, match="Only a downloaded MSI"):
        U.install_downloaded_msi(U.UpdateCheckResult("available", "", "", package_kind="msi"))
    file = tmp_path / "test.msi"
    file.write_bytes(b"test")
    with pytest.raises(ValueError, match="no longer matches"):
        U.install_downloaded_msi(U.UpdateCheckResult("downloaded", "", "", package_kind="msi", path=str(file), asset_digest="a" * 64))


def test_wix_payload_stable_and_data_seed_not_source_modified(tmp_path):
    source = tmp_path / "source"; source.mkdir()
    (source / "tlo-main.exe").write_bytes(b"main")
    (source / "tlo-search.exe").write_bytes(b"search")
    db = tmp_path / "database"; db.mkdir()
    for name in ("artists.sqlite", "venues.txt", "cities.csv"):
        (db / name).write_bytes(b"base")
    prepared = tmp_path / "prepared"
    WIX.prepare_stage(source, prepared, ROOT / "msi" / "TLO-MSI-Update-Worker.ps1", db)
    assert (prepared / "TLO_DBs" / "cities.csv").read_bytes() == b"base"
    assert not (source / "TLO_DBs").exists()
    wxs = tmp_path / "out.wxs"
    data = WIX.generate(prepared, wxs, "1.7.657")
    assert data["version"] == "1.7.657"
    tree = ET.parse(wxs)
    assert tree.find("w:Package", {"w": WIX.NS}).get("Scope") == "perUser"
    assert tree.find(".//w:MajorUpgrade", {"w": WIX.NS}) is not None
    assert any(p.get("Source", "").endswith("cities.csv") for p in tree.findall(".//w:File", {"w": WIX.NS}))


def test_msi_mode_not_detected_on_non_windows():
    assert mode.msi_install_root() is None


def test_msi_build_script_requires_trusted_signing_and_data_masters():
    text = (ROOT / "msi" / "Build-TLO-MSI.ps1").read_text()
    for key in ("TLO_ARTIFACT_SIGNING_METADATA", "TLO_ARTIFACT_SIGNING_DLIB", "verify /pa /all /v", "--data-source"):
        assert key in text


def test_msi_updates_managed_database_masters_and_seeds_user_files_only_once(tmp_path, monkeypatch):
    program = tmp_path / "program"
    home = tmp_path / "TLOHome"
    (program / "TLO_DBs").mkdir(parents=True)
    for filename, content in {
        "artists.sqlite": b"new master", "venues.txt": b"new venues", "cities.csv": b"new cities",
    }.items():
        (program / "TLO_DBs" / filename).write_bytes(content)
    (program / "TLO-FAQ.txt").write_bytes(b"new FAQ")
    (program / "tlo-preferences.ini").write_bytes(b"template only")
    (home / "TLO_DBs").mkdir(parents=True)
    (home / "TLO_DBs" / "artists.sqlite").write_bytes(b"USER DATABASE")
    (home / "tlo-preferences.ini").write_bytes(b"USER PREFERENCES")
    monkeypatch.setattr(mode, "msi_install_root", lambda *_args, **_kw: program)
    mode.seed_msi_data_home(home)
    assert (home / "TLO_DBs" / "artists.sqlite").read_bytes() == b"new master"
    assert (home / "tlo-preferences.ini").read_bytes() == b"USER PREFERENCES"
    assert (home / "TLO_DBs" / "cities.csv").read_bytes() == b"new cities"
    assert (home / "TLO_DBs" / "venues.txt").read_bytes() == b"new venues"
    assert (home / "TLO-FAQ.txt").read_bytes() == b"new FAQ"
    (home / "TLO_DBs" / "artists.sqlite").write_bytes(b"edited same-build master")
    mode.seed_msi_data_home(home)  # no re-copy within the same installed build
    assert (home / "TLO_DBs" / "artists.sqlite").read_bytes() == b"edited same-build master"
    assert (home / "TLO_DBs" / mode.MSI_DATABASE_BUILD_MARKER).read_text().strip() == str(__import__("tlo_version").BUNDLE_BUILD)


def test_wix_preparation_seeds_docs_but_not_source_tree(tmp_path):
    original = tmp_path / "source"; original.mkdir()
    (original / "tlo-main.exe").write_bytes(b"signed exe placeholder")
    docs = tmp_path / "documents"; docs.mkdir()
    for name in ("TLO-FAQ.txt", "tlo-preferences.ini",
                 RA.MANUAL_FILENAME, RA.REQUIREMENTS_FILENAME):
        (docs / name).write_bytes(b"documentation")
    stage = tmp_path / "prepared"
    WIX.prepare_stage(original, stage, ROOT / "msi" / "TLO-MSI-Update-Worker.ps1",
                      document_source=docs)
    assert (stage / "TLO-FAQ.txt").read_bytes() == b"documentation"
    assert (stage / RA.MANUAL_FILENAME).is_file()
    assert not (original / "TLO-FAQ.txt").exists()


def test_wix_generator_creates_all_ancestor_directories(tmp_path):
    """Build 656 CI failure: THIRD_PARTY had only files in subdirectories."""
    stage = tmp_path / "signed-onedir"
    paths = (
        "tlo-main.exe",
        "THIRD_PARTY/vendor/runtime.dll",
        "THIRD_PARTY/vendor/submodule/native.dll",
        "THIRD_PARTY/other/license.txt",
        "tlo-main_runtime/package/data/fixture.dat",
    )
    for relative in paths:
        file_path = stage / relative
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(b"signed-placeholder")

    wxs = tmp_path / "generated.wxs"
    result = WIX.generate(stage, wxs, "1.7.657")
    assert result["file_count"] == len(paths)
    tree = ET.parse(wxs)
    ns = {"w": WIX.NS}
    install = tree.find(".//w:Directory[@Id='INSTALLFOLDER']", ns)
    assert install is not None

    def find_child(parent, name):
        matches = [child for child in parent.findall("w:Directory", ns)
                   if child.get("Name") == name]
        assert len(matches) == 1, (name, len(matches))
        return matches[0]

    third_party = find_child(install, "THIRD_PARTY")
    vendor = find_child(third_party, "vendor")
    find_child(vendor, "submodule")
    find_child(third_party, "other")
    runtime = find_child(install, "tlo-main_runtime")
    find_child(find_child(runtime, "package"), "data")
    assert len(tree.findall(".//w:File", ns)) == len(paths)


def test_wix_generator_stable_when_file_creation_order_differs(tmp_path):
    """MSI Component identities must remain stable across major upgrades."""
    names = ["tlo-main.exe", "THIRD_PARTY/vendor/submodule/a.dll", "THIRD_PARTY/other/b.dll"]
    outputs = []
    for index, ordered in enumerate((names, list(reversed(names)))):
        stage = tmp_path / f"release-{index}"
        for relative in ordered:
            file_path = stage / relative
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_bytes(b"payload")
        wxs = tmp_path / f"release-{index}.wxs"
        WIX.generate(stage, wxs, f"1.7.{657 + index}")
        tree = ET.parse(wxs)
        outputs.append({component.get("Id"): component.get("Guid")
                        for component in tree.findall(".//w:Component", {"w": WIX.NS})})
    assert outputs[0] == outputs[1]
