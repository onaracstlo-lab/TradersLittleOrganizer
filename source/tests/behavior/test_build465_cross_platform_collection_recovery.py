import json
import os
from pathlib import Path

import pytest

import tlo_sibling_collections as SC

pytestmark = pytest.mark.behavior


def _write_windows_journal(container: Path, original_parent: str, names):
    payload = {
        "schema": 1,
        "temporary_path": rf"E:\\boots\\.tlo-collection-interrupted",
        "final_path": original_parent + "\\" + names[0],
        "generated_info": "info.txt",
        "members": [
            {"original": original_parent + "\\" + name, "child_name": name}
            for name in names
        ],
    }
    (container / SC.JOURNAL_NAME).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )
    return payload


def test_build465_windows_journal_paths_translate_to_wsl_mount(tmp_path, monkeypatch):
    mount_root = tmp_path / "mnt"
    monkeypatch.setattr(SC, "_WSL_MOUNT_ROOT", str(mount_root))
    assert SC._runtime_recovery_path(r"E:\boots\Pink Floyd - Early Flights") == os.path.normpath(
        str(mount_root / "e" / "boots" / "Pink Floyd - Early Flights")
    )


def test_build465_wsl_journal_paths_translate_to_native_windows_form():
    assert SC._runtime_recovery_path(
        "/mnt/e/boots/Pink Floyd - Early Flights", platform_name="nt"
    ) == r"E:\boots\Pink Floyd - Early Flights"


def test_build465_recovers_windows_written_collision_journal_under_wsl(tmp_path, monkeypatch):
    # Reproduce the user's interrupted state, except the WSL mount root is
    # redirected into pytest's temporary directory so the test is portable.
    mount_root = tmp_path / "mnt"
    monkeypatch.setattr(SC, "_WSL_MOUNT_ROOT", str(mount_root))

    parent = mount_root / "e" / "boots" / "Pink Floyd - Early Flights"
    container = parent / "Pink Floyd - Early Flights"
    container.mkdir(parents=True)

    names = ["Pink Floyd - Early Flights"] + [
        f"Pink Floyd - Early Flights (alt{i})" for i in range(1, 9)
    ]
    for name in names:
        child = container / name
        child.mkdir()
        (child / "marker.txt").write_text(name, encoding="utf-8")

    _write_windows_journal(
        container,
        r"E:\boots\Pink Floyd - Early Flights",
        names,
    )

    emitted = []
    recovered = SC.recover_interrupted_sibling_consolidations(
        str(mount_root / "e" / "boots"), emit=emitted.append
    )

    assert recovered == 1
    assert any("SIBLING_COLLECTION_RECOVERED:" in line for line in emitted)
    assert not container.exists() or (container / "marker.txt").exists()
    for name in names:
        restored = parent / name
        assert restored.is_dir()
        assert (restored / "marker.txt").read_text(encoding="utf-8") == name
        assert not (restored / SC.JOURNAL_NAME).exists()


def test_build465_cross_platform_diagnostic_shows_runtime_and_journal_forms(tmp_path, monkeypatch):
    mount_root = tmp_path / "mnt"
    monkeypatch.setattr(SC, "_WSL_MOUNT_ROOT", str(mount_root))
    container = mount_root / "e" / "boots" / "Pink Floyd - Early Flights" / "Pink Floyd - Early Flights"
    container.mkdir(parents=True)
    names = ["Pink Floyd - Early Flights"]
    payload = _write_windows_journal(
        container,
        r"E:\boots\Pink Floyd - Early Flights",
        names,
    )
    message = SC._format_recovery_error(str(container), payload, "test")
    assert f"Planned final folder: {container}" in message
    assert r"Journal path form: E:\boots\Pink Floyd - Early Flights\Pink Floyd - Early Flights" in message
    assert f"original: {container}" in message
