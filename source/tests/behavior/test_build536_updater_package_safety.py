"""Build 536: downloaded update ZIPs enforce their safety manifest contract."""


import json
import zipfile
from pathlib import Path

import pytest

import tlo_github_updates as U

pytestmark = pytest.mark.behavior


def _protected_paths(*, databases: bool) -> list[str]:
    paths = list(U.UPDATE_PROTECTED_PATHS)
    if not databases:
        paths.append("TLO_DBs/")
    return paths


def _manifest(*, databases: bool = False) -> dict[str, object]:
    return {
        "kind": "update",
        "build": 536,
        "platform_key": "linux",
        "packaging_mode": "native",
        "safe_update": True,
        "requires_complete_install": False,
        "protected_paths": _protected_paths(databases=databases),
        "databases_included": databases,
        "database_files": ["artists.sqlite", "venues.txt"] if databases else [],
    }


def _write_update(
    path: Path,
    *,
    manifest: dict[str, object] | None = None,
    members: tuple[str, ...] = (),
) -> None:
    data = manifest or _manifest()
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("UPDATE_MANIFEST.json", json.dumps(data))
        if data.get("databases_included") is True:
            archive.writestr("TLO_DBs/artists.sqlite", b"db")
            archive.writestr("TLO_DBs/venues.txt", "venues")
        for member in members:
            archive.writestr(member, b"x")


def _inspect(path: Path) -> dict[str, object]:
    return U._inspect_downloaded_package(
        path,
        expected_kind="update",
        expected_platform_key="linux",
        expected_build=536,
    )


def test_build536_valid_update_safety_manifest_is_accepted(tmp_path):
    package = tmp_path / "update.zip"
    _write_update(package, members=("apps/Linux/tlo-main", "TLO-FAQ.txt"))
    assert _inspect(package)["kind"] == "update"


@pytest.mark.parametrize("value", [None, False, 1, "true"])
def test_build536_safe_update_must_be_boolean_true(tmp_path, value):
    package = tmp_path / "update.zip"
    manifest = _manifest()
    if value is None:
        manifest.pop("safe_update")
    else:
        manifest["safe_update"] = value
    _write_update(package, manifest=manifest)
    with pytest.raises(ValueError, match="safe_update=true"):
        _inspect(package)


@pytest.mark.parametrize("value", [None, True, 0, "false"])
def test_build536_requires_complete_install_must_be_boolean_false(tmp_path, value):
    package = tmp_path / "update.zip"
    manifest = _manifest()
    if value is None:
        manifest.pop("requires_complete_install")
    else:
        manifest["requires_complete_install"] = value
    _write_update(package, manifest=manifest)
    with pytest.raises(ValueError, match="requires_complete_install=false"):
        _inspect(package)


def test_build536_manifest_must_declare_the_complete_required_protected_set(tmp_path):
    package = tmp_path / "update.zip"
    manifest = _manifest()
    manifest["protected_paths"] = [
        item for item in manifest["protected_paths"] if item.casefold() != "logs/"
    ]
    _write_update(package, manifest=manifest)
    with pytest.raises(ValueError, match="protected_paths manifest"):
        _inspect(package)


@pytest.mark.parametrize(
    "member",
    [
        "bootlist.csv",
        "BOOTLIST.CSV",
        "toBeInventoried.txt",
        "setlists/show.txt",
        "LOGS/meta1.log",
        "debug/item.txt",
        "dups/show/file.flac",
        "readyForXfer/show/file.flac",
        "staged/show/file.flac",
        "unidentifiedShows.txt",
    ],
)
def test_build536_update_rejects_protected_user_data_members_case_insensitively(tmp_path, member):
    package = tmp_path / "update.zip"
    _write_update(package, members=(member,))
    with pytest.raises(ValueError, match="protected user-data path"):
        _inspect(package)


def test_build536_database_refresh_remains_allowed_only_when_declared(tmp_path):
    package = tmp_path / "update.zip"
    _write_update(package, manifest=_manifest(databases=True))
    info = _inspect(package)
    assert info["databases_included"] is True


def test_build536_casefold_colliding_zip_members_are_rejected(tmp_path):
    package = tmp_path / "update.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("UPDATE_MANIFEST.json", json.dumps(_manifest()))
        archive.writestr("apps/Linux/TLO-Main", b"one")
        archive.writestr("apps/linux/tlo-main", b"two")
    with pytest.raises(ValueError, match="duplicate ZIP member"):
        _inspect(package)


def test_build536_complete_package_contract_is_unchanged(tmp_path):
    package = tmp_path / "complete.zip"
    manifest = {
        "kind": "complete",
        "build_number": 536,
        "platform_key": "linux",
        "packaging_mode": "native",
        "databases_included": True,
        "database_files": ["artists.sqlite", "venues.txt"],
    }
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr("TLO_DBs/artists.sqlite", b"db")
        archive.writestr("TLO_DBs/venues.txt", "venues")
    assert U._inspect_downloaded_package(
        package,
        expected_kind="complete",
        expected_platform_key="linux",
        expected_build=536,
    )["kind"] == "complete"
