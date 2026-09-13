"""Build 458 regressions for exact release-package/update handling."""
__version__ = "v458"

import json
import zipfile
from pathlib import Path

import pytest

import tlo_github_updates as U
from tlo_version import BUNDLE_BUILD

pytestmark = pytest.mark.behavior


def _asset(name: str) -> dict[str, object]:
    return {
        "name": name,
        "browser_download_url": f"https://github.com/onaracstlo-lab/TradersLittleOrganizer/releases/download/test/{name}",
        "size": 123,
        "digest": "sha256:" + "0" * 64,
    }


def _release(*names: str) -> dict[str, object]:
    return {"assets": [_asset(name) for name in names]}


def _write_package(path: Path, *, kind: str, platform_key: str, build: int, databases: bool, packaging_mode: str = "native") -> None:
    manifest_name = "UPDATE_MANIFEST.json" if kind == "update" else "manifest.json"
    manifest = {
        "kind": kind,
        "platform_key": platform_key,
        "packaging_mode": packaging_mode,
        "databases_included": databases,
        "database_files": ["artists.sqlite", "venues.txt"] if databases else [],
    }
    if kind == "update":
        manifest["build"] = build
    else:
        manifest["build_number"] = build
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(manifest_name, json.dumps(manifest))
        if databases:
            archive.writestr("TLO_DBs/artists.sqlite", b"db")
            archive.writestr("TLO_DBs/venues.txt", "venues")


def test_build458_update_only_release_is_selected(monkeypatch):
    monkeypatch.setattr(U.sys, "platform", "linux")
    release = _release("TLO_V1.6Build459_update_Linux.zip")
    asset, kind, platform = U._choose_asset(release, 459)
    assert asset and asset["name"] == "TLO_V1.6Build459_update_Linux.zip"
    assert (kind, platform) == ("update", "linux")


def test_build458_complete_only_release_is_valid_fallback(monkeypatch):
    monkeypatch.setattr(U.sys, "platform", "linux")
    release = _release("TLO_V1.6Build459_complete_Linux.zip")
    asset, kind, platform = U._choose_asset(release, 459)
    assert asset and asset["name"] == "TLO_V1.6Build459_complete_Linux.zip"
    assert (kind, platform) == ("complete", "linux")


def test_build458_generic_or_source_zip_is_never_update_fallback(monkeypatch):
    monkeypatch.setattr(U.sys, "platform", "linux")
    release = _release(
        "music_inventory_flat_bundle_v459.zip",
        "TLO_V1.6Build459_complete_Windows.zip",
    )
    asset, kind, platform = U._choose_asset(release, 459)
    assert asset is None
    assert kind == ""
    assert platform == "linux"


def test_build458_windows_onedir_selects_only_onedir(monkeypatch, tmp_path):
    monkeypatch.setattr(U.sys, "platform", "win32")
    (tmp_path / "apps" / "Windows" / "_internal").mkdir(parents=True)
    release = _release(
        "TLO_V1.6Build459_update_Windows.zip",
        "TLO_V1.6Build459_update_Windows_onedir.zip",
    )
    asset, kind, platform = U._choose_asset(release, 459, tmp_path)
    assert asset and asset["name"].endswith("_update_Windows_onedir.zip")
    assert (kind, platform) == ("update", "windows_onedir")


def test_build458_windows_hybrid_does_not_cross_fallback_to_onedir(monkeypatch, tmp_path):
    monkeypatch.setattr(U.sys, "platform", "win32")
    (tmp_path / "apps" / "Windows").mkdir(parents=True)
    release = _release("TLO_V1.6Build459_complete_Windows_onedir.zip")
    asset, kind, platform = U._choose_asset(release, 459, tmp_path)
    assert asset is None
    assert kind == ""
    assert platform == "windows"


@pytest.mark.parametrize("databases", [False, True])
def test_build458_update_manifest_database_modes_validate(tmp_path, databases):
    package = tmp_path / "update.zip"
    _write_package(package, kind="update", platform_key="linux", build=459, databases=databases)
    info = U._inspect_downloaded_package(
        package,
        expected_kind="update",
        expected_platform_key="linux",
        expected_build=459,
    )
    assert info["databases_included"] is databases


def test_build458_partial_or_extra_database_payload_is_rejected(tmp_path):
    package = tmp_path / "bad-update.zip"
    manifest = {
        "kind": "update", "build": 459, "platform_key": "linux", "packaging_mode": "native",
        "databases_included": False, "database_files": [],
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("UPDATE_MANIFEST.json", json.dumps(manifest))
        archive.writestr("TLO_DBs/artists.sqlite", b"unexpected")
    with pytest.raises(ValueError, match="database manifest"):
        U._inspect_downloaded_package(package, expected_kind="update", expected_platform_key="linux", expected_build=459)


def test_build458_manifest_platform_mismatch_is_rejected(tmp_path):
    package = tmp_path / "wrong-platform.zip"
    _write_package(package, kind="update", platform_key="windows", build=459, databases=False)
    with pytest.raises(ValueError, match="targets windows"):
        U._inspect_downloaded_package(package, expected_kind="update", expected_platform_key="linux", expected_build=459)


def test_build458_check_for_updates_reports_database_refresh(monkeypatch, tmp_path):
    available_build = BUNDLE_BUILD + 1
    name = f"TLO_V1.6Build{available_build}_update_Linux.zip"
    release = {
        "tag_name": f"v1.6-build{available_build}",
        "name": f"TLO v1.6 Build {available_build}",
        "assets": [_asset(name)],
    }
    monkeypatch.setattr(U.sys, "platform", "linux")
    monkeypatch.setattr(U, "_fetch_latest_release", lambda owner, repo: release)
    monkeypatch.setattr(U, "_downloads_dir", lambda: tmp_path)

    def fake_download(_asset_value, destination):
        _write_package(destination, kind="update", platform_key="linux", build=available_build, databases=True)
        return True

    monkeypatch.setattr(U, "_download_asset", fake_download)
    result = U.check_for_updates(tmp_path / "TLOHome")
    assert result.status == "downloaded"
    assert result.package_kind == "update"
    assert result.platform_key == "linux"
    assert result.databases_included is True
    assert "includes refreshed TLO_DBs/artists.sqlite and venues.txt" in result.message


def test_build458_current_documentation_describes_package_matrix():
    root = Path(__file__).resolve().parents[2]
    from docx import Document
    req_text = "\n".join(p.text for p in Document(root / "TLO_Inventory_Requirements_Working_v458.docx").paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v458.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (root / "TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Current document version: v458 (v1.6 Build 458)." in req_text
    assert "exact matching complete ZIP" in req_text
    assert "databases_included" in req_text
    assert "only the four complete ZIPs" in manual
    assert "Can an update ZIP include the TLO databases?" in faq
