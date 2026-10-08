from __future__ import annotations
from tests import _release_artifacts as RA

import ast
import errno
import importlib.util
import logging
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import logging_lib as LL
import tlo_copy_requests as CR
import tlo_github_updates as GU
import tlo_inventory_update as IU
import tlo_reverse_folders as RF
import tlo_runtime_control as RC
import tlo_tag_lib as TL

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_delete_dupes():
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_build529", ROOT / "tlo-deleteDupes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request(tmp_path: Path) -> tuple[Path, str]:
    home = tmp_path / "home"
    home.mkdir()
    destination = tmp_path / "destination"
    destination.mkdir()
    request_file = tmp_path / "request.txt"
    request_file.write_text("Grateful Dead\n", encoding="utf-8")
    state = CR.create_or_open_request(str(home), str(request_file), str(destination))
    return home, str(state["request_id"])


def _reverse_log(home: Path, line: str) -> Path:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / "tags1.txt"
    path.write_text(line + "\n", encoding="utf-8")
    return path


def test_build529_flac_partial_backup_fault_cannot_replace_keeper(tmp_path, monkeypatch):
    module = _load_delete_dupes()
    source = tmp_path / "healthy.flac"
    keeper = tmp_path / "keeper.flac"
    source.write_bytes(b"HEALTHY" * 8192)
    keeper.write_bytes(b"KEEPER" * 8192)
    original = keeper.read_bytes()
    real_copy2 = module.shutil.copy2
    calls = 0

    def fail_second_copy(src, dst, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            Path(dst).write_bytes(original[:13])
            raise OSError(errno.ENOSPC, "injected full disk")
        return real_copy2(src, dst, *args, **kwargs)

    monkeypatch.setattr(module.shutil, "copy2", fail_second_copy)
    with pytest.raises(OSError, match="full disk"):
        module._replace_file_from_copy(str(source), str(keeper))

    assert keeper.read_bytes() == original
    assert not list(tmp_path.glob(".tlo-deleteDupes-backup-*.flac"))


def test_build529_unexpected_flac_validator_failure_is_logged_and_unverifiable(tmp_path, caplog):
    module = _load_delete_dupes()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")

    def boom(*_args, **_kwargs):
        raise RuntimeError("validator infrastructure exploded")

    caplog.set_level(logging.DEBUG, logger="tlo.suppressed")
    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=boom) is None
    assert "flac_file_is_healthy validator" in caplog.text
    assert "validator infrastructure exploded" in caplog.text


def test_build529_copy_request_delete_faults_fail_closed(tmp_path):
    home, request_id = _request(tmp_path)
    root = Path(CR.copy_requests_root(str(home)))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")

    for bad in ("", ".", "..", "../outside", str(outside), "nested/name"):
        with pytest.raises(CR.CopyRequestError):
            CR.delete_request(str(home), bad)
        assert root.is_dir()
        assert (root / request_id).is_dir()
        assert (outside / "keep.txt").is_file()


def test_build529_unlabeled_posix_cleanup_script_is_executable_but_non_destructive(tmp_path):
    target = tmp_path / "volume" / "Band 1999"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    script = tmp_path / "deleteBackupFolders.sh"

    assert IU._append_delete_command(str(script), str(target), "") is True
    completed = subprocess.run(["sh", str(script)], capture_output=True, text=True, check=False)

    assert completed.returncode == 0
    assert target.is_dir()
    assert (target / "keep.txt").is_file()
    assert "SKIPPED: unlabeled volume cannot be verified automatically" in completed.stdout
    active = [line for line in script.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert not any("rm -rf" in line for line in active)


def test_build529_tag_copy_post_run_replacement_is_not_deleted(tmp_path):
    home = tmp_path / "home"
    source = tmp_path / "source" / "show"
    copied = tmp_path / "copy" / "show"
    source.mkdir(parents=True)
    copied.mkdir(parents=True)
    (source / "01.flac").write_bytes(b"original")
    (copied / "01.flac").write_bytes(b"original")
    log = _reverse_log(home, f"TAG_COPY: {source} -> {copied}")
    future = log.stat().st_mtime + 5
    (copied / "01.flac").write_bytes(b"user replacement")
    os.utime(copied / "01.flac", (future, future))

    result = RF.reverse_folder_operations(RF.prepare_reverse_plan(str(copied), tlo_home=str(home)))

    assert result.conflicts == 1
    assert copied.is_dir()
    assert (copied / "01.flac").read_bytes() == b"user replacement"


def test_build529_cross_filesystem_reverse_failure_never_deletes_logged_destination(tmp_path, monkeypatch):
    home = tmp_path / "home"
    original = tmp_path / "original" / "show"
    current = tmp_path / "current" / "show"
    current.mkdir(parents=True)
    (current / "01.flac").write_bytes(b"audio")
    _reverse_log(home, f"RENAME_COMPLIANTLY: {original} -> {current}")
    monkeypatch.setattr(RF, "_same_filesystem", lambda *_args: False)
    monkeypatch.setattr(RF, "_trees_exactly_match_preserving_symlinks", lambda *_args: False)

    result = RF.reverse_folder_operations(RF.prepare_reverse_plan(str(current), tlo_home=str(home)))

    assert result.errors == 1
    assert current.is_dir()
    assert not original.exists()
    assert not Path(RF._reverse_partial_path(str(original))).exists()


def test_build529_inventory_mutation_lock_fail_closed_and_releases(tmp_path):
    first = RC.acquire_inventory_lock(str(tmp_path))
    try:
        with pytest.raises(RuntimeError, match="Another inventory-mutating TLO run"):
            RC.acquire_inventory_lock(str(tmp_path))
    finally:
        RC.release_inventory_lock(first)
    second = RC.acquire_inventory_lock(str(tmp_path))
    RC.release_inventory_lock(second)


def test_build529_shn_target_race_preserves_user_file_and_source(tmp_path, monkeypatch):
    source = tmp_path / "track.shn"
    target = tmp_path / "track.flac"
    source.write_bytes(b"source-shn")
    monkeypatch.setattr(TL, "_bundled_ffmpeg_executable", lambda: "/app/ffmpeg")

    def fake_run(command, **_kwargs):
        Path(command[-1]).write_bytes(b"converted")
        target.write_bytes(b"user-created")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(TL.subprocess, "run", fake_run)
    with pytest.raises(TL.TaggerError, match="appeared during conversion"):
        TL.convert_shn_to_flac(str(source))

    assert source.read_bytes() == b"source-shn"
    assert target.read_bytes() == b"user-created"


def test_build529_atomic_persistence_faults_leave_prior_bytes_unchanged(tmp_path, monkeypatch):
    settings = tmp_path / GU.SETTINGS_FILE_NAME
    settings.write_text('{"auto_update": true}\n', encoding="utf-8")
    settings_before = settings.read_bytes()
    log = tmp_path / "dead0.log"
    root = tmp_path / "shows"
    root.mkdir()
    log.write_bytes(b"NOTE: keep\nPATH: " + str(root / "remove").encode() + b"\n")
    log_before = log.read_bytes()

    real_replace = os.replace

    def fail_replace(src, dst):
        if Path(dst) in {settings, log}:
            raise OSError("injected atomic commit failure")
        return real_replace(src, dst)

    monkeypatch.setattr(GU.os, "replace", fail_replace)
    monkeypatch.setattr(LL.os, "replace", fail_replace)

    with pytest.raises(OSError, match="atomic commit failure"):
        GU.save_update_settings(tmp_path, {"auto_update": False})
    with pytest.raises(OSError, match="atomic commit failure"):
        LL._prune_line_log(str(log), [str(root)])

    assert settings.read_bytes() == settings_before
    assert log.read_bytes() == log_before


def test_build529_targeted_destructive_modules_reduce_broad_exception_surface():
    # Build 528 baseline across these six destructive/persistence modules was
    # 51 broad Exception handlers, 30 of them silent. Build 531 deliberately
    # narrows only the remediation-touched paths rather than attempting a risky
    # codebase-wide cleanup.
    modules = [
        "tlo-deleteDupes.py",
        "tlo_copy_requests.py",
        "tlo_inventory_update.py",
        "tlo_github_updates.py",
        "tlo_reverse_folders.py",
    ]
    broad = 0
    silent = 0
    for name in modules:
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            is_broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id == "Exception")
            if not is_broad:
                continue
            broad += 1
            if all(isinstance(stmt, (ast.Pass, ast.Continue, ast.Return)) for stmt in node.body):
                silent += 1
    assert broad <= 31
    assert silent <= 21


def test_build529_documentation_closes_log_location_and_safety_coverage_contracts():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / RA.REQUIREMENTS_FILENAME).paragraphs)
    manual = (ROOT / RA.MANUAL_FILENAME).read_text(encoding="utf-8", errors="replace")

    assert "REQ-SAFETY-001" in req and "suppressed-exception diagnostic logger" in req
    assert "REQ-SAFETY-002" in req and "Builds 525-528" in req
    assert "reinventoryDelta.log" in manual
    assert "Append-only path-scoped re-inventory reconciliation audit" in manual
    assert "TLOHome/CorruptFlacs.txt is an append-only diagnostic file stored in the TLOHome root (not in TLOHome/logs)" in manual
