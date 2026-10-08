from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

import tlo_copy_requests as CR
import tlo_inventory_update as IU
import tlo_reverse_folders as RF

pytestmark = pytest.mark.behavior


def _create_request(tmp_path: Path) -> tuple[Path, str]:
    home = tmp_path / "home"
    home.mkdir()
    destination = tmp_path / "destination"
    destination.mkdir()
    request_file = tmp_path / "request.txt"
    request_file.write_text("Grateful Dead\n", encoding="utf-8")
    state = CR.create_or_open_request(str(home), str(request_file), str(destination))
    return home, str(state["request_id"])


def _touch_tree(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "01.flac").write_bytes(b"audio")
    (root / "info.txt").write_text("info", encoding="utf-8")


def _write_reverse_log(home: Path, name: str, line: str) -> Path:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / name
    path.write_text(line + "\n", encoding="utf-8")
    return path


def test_build526_copy_request_state_id_must_match_containing_directory(tmp_path):
    home, request_id = _create_request(tmp_path)
    state_file = Path(CR.state_path(str(home), request_id))
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    payload["request_id"] = ""
    state_file.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CR.CopyRequestError, match="does not match its containing directory"):
        CR.load_request(str(home), request_id)

    assert CR.list_request_entries(str(home)) == []
    assert Path(CR.copy_requests_root(str(home))).is_dir()


def test_build526_copy_request_delete_rejects_malformed_ids_without_touching_root(tmp_path):
    home, request_id = _create_request(tmp_path)
    request_root = Path(CR.copy_requests_root(str(home)))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")

    for malformed in ("", ".", "..", "../outside", "/tmp/outside", "a/b", r"a\b"):
        with pytest.raises(CR.CopyRequestError, match="Invalid Copy Request ID"):
            CR.delete_request(str(home), malformed)
        assert request_root.is_dir()
        assert Path(CR.request_dir(str(home), request_id)).is_dir()
        assert (outside / "keep.txt").is_file()


def test_build526_copy_request_delete_confines_resolved_target_to_request_root(tmp_path):
    home, _request_id = _create_request(tmp_path)
    request_root = Path(CR.copy_requests_root(str(home)))
    outside = tmp_path / "outside-tree"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep", encoding="utf-8")
    link = request_root / "escape"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlinks are unavailable on this platform")

    with pytest.raises(CR.CopyRequestError, match="outside the Copy Requests root"):
        CR.delete_request(str(home), "escape")
    assert outside.is_dir()
    assert (outside / "keep.txt").is_file()


def test_build526_copy_request_delete_valid_directory_removes_only_that_request(tmp_path):
    home, request_id = _create_request(tmp_path)
    root = Path(CR.copy_requests_root(str(home)))
    sibling = root / "sibling--123"
    sibling.mkdir()
    (sibling / "keep.txt").write_text("keep", encoding="utf-8")

    CR.delete_request(str(home), request_id)

    assert root.is_dir()
    assert not Path(root / request_id).exists()
    assert (sibling / "keep.txt").is_file()


def test_build526_posix_unlabeled_cleanup_entry_is_non_destructive(tmp_path):
    script = tmp_path / "deleteBackupFolders.sh"
    assert IU._append_delete_command(str(script), "/mnt/e/Shows/Band 1999", "") is True
    body = script.read_text(encoding="utf-8")
    active_lines = [line for line in body.splitlines() if line.strip() and not line.lstrip().startswith("#")]

    assert any("SKIPPED: unlabeled volume cannot be verified automatically" in line for line in active_lines)
    assert not any("rm -rf" in line for line in active_lines)
    assert "# rm -rf -- '/mnt/e/Shows/Band 1999'" in body


def test_build526_posix_unlabeled_cleanup_script_cannot_delete_when_run(tmp_path):
    target = tmp_path / "unlabeled-volume" / "Shows" / "Band"
    target.mkdir(parents=True)
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    script = tmp_path / "deleteBackupFolders.sh"
    assert IU._append_delete_command(str(script), str(target), "") is True

    completed = subprocess.run(["sh", str(script)], text=True, capture_output=True, check=False)

    assert completed.returncode == 0
    assert target.is_dir()
    assert (target / "keep.txt").is_file()
    assert "SKIPPED: unlabeled volume cannot be verified automatically" in completed.stdout


def test_build526_posix_labeled_cleanup_still_requires_identity_before_delete(tmp_path):
    script = tmp_path / "deleteBackupFolders.sh"
    assert IU._append_delete_command(str(script), "/mnt/e/Shows/Band", "Backup") is True
    body = script.read_text(encoding="utf-8")

    assert "TLO_EXPECTED_LABEL=Backup" in body
    assert "Wrong or unverifiable volume" in body
    assert "rm -rf -- /mnt/e/Shows/Band" in body


def test_build526_tag_copy_possible_post_copy_replacement_is_left_untouched(tmp_path):
    home = tmp_path / "home"
    original = tmp_path / "source" / "show"
    copied = tmp_path / "copies" / "show"
    _touch_tree(original)
    _touch_tree(copied)
    log = _write_reverse_log(home, "tags1.txt", f"TAG_COPY: {original} -> {copied}")

    future = log.stat().st_mtime + 10
    (copied / "01.flac").write_bytes(b"replacement")
    os.utime(copied / "01.flac", (future, future))

    result = RF.reverse_folder_operations(RF.prepare_reverse_plan(str(copied), tlo_home=str(home)))

    assert result.conflicts == 1
    assert copied.is_dir()
    assert any("possible post-copy replacement" in message for message in result.messages)


def test_build526_tag_copy_tag_byte_difference_before_log_completion_can_still_reverse(tmp_path):
    home = tmp_path / "home"
    original = tmp_path / "source" / "show"
    copied = tmp_path / "copies" / "show"
    _touch_tree(original)
    _touch_tree(copied)
    (copied / "01.flac").write_bytes(b"audio-with-different-tags")
    log = _write_reverse_log(home, "tags2.txt", f"TAG_COPY: {original} -> {copied}")
    prior = log.stat().st_mtime - 10
    os.utime(copied / "01.flac", (prior, prior))

    result = RF.reverse_folder_operations(RF.prepare_reverse_plan(str(copied), tlo_home=str(home)))

    assert result.reversed == 1
    assert original.is_dir()
    assert not copied.exists()


def test_build526_cross_filesystem_reversal_preserves_symbolic_links(tmp_path, monkeypatch):
    home = tmp_path / "home"
    original = tmp_path / "original" / "show"
    current = tmp_path / "moved" / "show"
    current.mkdir(parents=True)
    (current / "target.txt").write_text("target", encoding="utf-8")
    try:
        (current / "link.txt").symlink_to("target.txt")
    except (OSError, NotImplementedError):
        pytest.skip("symbolic links are unavailable on this platform")
    _write_reverse_log(home, "tags3.txt", f"RENAME_COMPLIANTLY: {original} -> {current}")
    monkeypatch.setattr(RF, "_same_filesystem", lambda _path, _parent: False)

    result = RF.reverse_folder_operations(RF.prepare_reverse_plan(str(current), tlo_home=str(home)))

    assert result.reversed == 1
    assert not current.exists()
    assert (original / "link.txt").is_symlink()
    assert os.readlink(original / "link.txt") == "target.txt"
    assert (original / "link.txt").read_text(encoding="utf-8") == "target"
