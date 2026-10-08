"""Build 547: retire the obsolete Reverse Copy/Delete implementation safely."""

from __future__ import annotations
from tests._release_artifacts import release_history
from tests import _release_artifacts as RA

from pathlib import Path

import pytest

import tlo_reverse_folders as RF

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _write_log(home: Path, line: str) -> Path:
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    path = logs / "tags547.txt"
    path.write_text(line.rstrip() + "\n", encoding="utf-8")
    return path


def test_build547_obsolete_reverse_copy_delete_module_and_dedicated_tests_are_absent():
    assert not (ROOT / "tlo_reverse_copy_delete.py").exists()
    assert not (ROOT / "tests" / "behavior" / "test_reverse_copy_delete_build383.py").exists()
    assert not (ROOT / "tests" / "behavior" / "test_reverse_copy_delete_build384.py").exists()


def test_build547_no_python_source_imports_deleted_module():
    offenders = []
    needle = "tlo_reverse_copy_delete"
    for path in ROOT.rglob("*.py"):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if needle in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_build547_live_reverse_refuses_to_overwrite_existing_original(tmp_path):
    home = tmp_path / "home"
    original = tmp_path / "original" / "Old Name"
    current = tmp_path / "moved" / "New Name"
    original.mkdir(parents=True)
    current.mkdir(parents=True)
    (original / "keep.txt").write_text("original", encoding="utf-8")
    (current / "keep.txt").write_text("moved", encoding="utf-8")
    log = _write_log(home, f"TAG_COPY_DELETE_MOVE: {original} -> {current}")

    result = RF.reverse_folder_operations(
        RF.prepare_reverse_plan(str(current), tlo_home=str(home), log_path=str(log))
    )

    assert result.reversed == 0
    assert result.conflicts == 1
    assert (original / "keep.txt").read_text(encoding="utf-8") == "original"
    assert (current / "keep.txt").read_text(encoding="utf-8") == "moved"


def test_build547_live_cross_filesystem_reverse_verifies_bytes_before_delete(tmp_path, monkeypatch):
    home = tmp_path / "home"
    original = tmp_path / "original" / "Original Folder"
    current = tmp_path / "moved" / "Compliant Folder"
    (current / "notes").mkdir(parents=True)
    (current / "song.flac").write_bytes(b"abc123")
    (current / "notes" / "setlist.txt").write_text("song", encoding="utf-8")
    _write_log(home, f"TAG_COPY_DELETE_COPY: {original} -> {current}")
    monkeypatch.setattr(RF, "_same_filesystem", lambda *_args: False)

    result = RF.reverse_folder_operations(
        RF.prepare_reverse_plan(str(current), tlo_home=str(home))
    )

    assert result.reversed == 1
    assert not current.exists()
    assert (original / "song.flac").read_bytes() == b"abc123"
    assert (original / "notes" / "setlist.txt").read_text(encoding="utf-8") == "song"


def test_build547_live_cross_filesystem_hash_mismatch_keeps_destination(tmp_path, monkeypatch):
    home = tmp_path / "home"
    original = tmp_path / "original" / "show"
    current = tmp_path / "moved" / "show"
    current.mkdir(parents=True)
    (current / "01.flac").write_bytes(b"audio")
    _write_log(home, f"RENAME_COMPLIANTLY: {original} -> {current}")
    monkeypatch.setattr(RF, "_same_filesystem", lambda *_args: False)
    monkeypatch.setattr(RF, "_trees_exactly_match_preserving_symlinks", lambda *_args: False)

    result = RF.reverse_folder_operations(
        RF.prepare_reverse_plan(str(current), tlo_home=str(home))
    )

    assert result.errors == 1
    assert current.is_dir()
    assert not original.exists()
    assert not Path(RF._reverse_partial_path(str(original))).exists()


def test_build547_version_and_documentation_contract():
    from docx import Document


    req_path = ROOT / RA.REQUIREMENTS_FILENAME
    manual_path = ROOT / RA.MANUAL_FILENAME
    assert req_path.is_file() and manual_path.is_file()
    req = "\n".join(p.text for p in Document(req_path).paragraphs)
    assert "Build 547: M-03->§14.6." in req
    assert "The obsolete tlo_reverse_copy_delete implementation is not shipped." in req

    assert "Build 547 - " in release_history()
    assert 'removes the obsolete tlo_reverse_copy_delete module' in release_history()

    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "Obsolete reverse implementation removal (M-03)" in changes
    assert "GitHub Build Process remains v108 unchanged" in changes.split("TLO v1.7 Build 546", 1)[0]
