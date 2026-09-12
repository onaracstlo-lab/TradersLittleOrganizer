from __future__ import annotations

import os
from pathlib import Path

import pytest

import tlo_reverse_folders as R

pytestmark = pytest.mark.behavior


def _home(tmp_path: Path) -> Path:
    home = tmp_path / "TLOHome"
    (home / "logs").mkdir(parents=True)
    return home


def _write_log(home: Path, name: str, lines: list[str]) -> Path:
    p = home / "logs" / name
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def _touch_tree(root: Path, names=("01.flac", "info.txt")):
    root.mkdir(parents=True, exist_ok=True)
    for name in names:
        (root / name).write_text(name, encoding="utf-8")


def test_rename_only_is_inferred_and_reversed(tmp_path, monkeypatch):
    home = _home(tmp_path)
    original = tmp_path / "music" / "old name"
    current = tmp_path / "music" / "Artist 2020-01-01 Venue City, ST"
    _touch_tree(current)
    _write_log(home, "tags1.txt", [f"RENAME_COMPLIANTLY: {original} -> {current}"])
    monkeypatch.setenv("TLOHome", str(home))

    plan = R.prepare_reverse_plan(str(current))
    assert [op.operation for op in plan.operations] == ["rename"]
    result = R.reverse_folder_operations(plan)
    assert result.reversed == 1
    assert original.is_dir() and not current.exists()


def test_copy_delete_without_rename_restores_original(tmp_path, monkeypatch):
    home = _home(tmp_path)
    original = tmp_path / "source" / "show"
    current = tmp_path / "moved" / "show"
    _touch_tree(current)
    _write_log(home, "tags2.txt", [
        "TAG_DURING_INVENTORY: mode=copy-and-delete | convert shn=no | rename compliantly=no | copy destination=" + str(current.parent),
        f"TAG_COPY_DELETE_MOVE: {original} -> {current}",
    ])
    monkeypatch.setenv("TLOHome", str(home))

    plan = R.prepare_reverse_plan(str(current))
    assert plan.operations[0].operation == "copy-delete"
    result = R.reverse_folder_operations(plan)
    assert result.reversed == 1
    assert original.is_dir() and not current.exists()


def test_copy_delete_with_compliant_rename_is_one_mapping(tmp_path, monkeypatch):
    home = _home(tmp_path)
    original = tmp_path / "source" / "messy folder"
    current = tmp_path / "moved" / "Artist 2021-02-03 Venue City, ST"
    _touch_tree(current)
    _write_log(home, "tags3.txt", [
        "TAG_DURING_INVENTORY: mode=copy-and-delete | convert shn=no | rename compliantly=yes | copy destination=" + str(current.parent),
        f"TAG_COPY_DELETE_COPY: {original} -> {current}",
    ])
    monkeypatch.setenv("TLOHome", str(home))

    plan = R.prepare_reverse_plan(str(current))
    assert len(plan.operations) == 1
    assert plan.operations[0].source == os.path.normpath(str(original))
    result = R.reverse_folder_operations(plan)
    assert result.reversed == 1
    assert original.is_dir()


def test_tag_copy_reverse_removes_copy_but_keeps_original(tmp_path, monkeypatch):
    home = _home(tmp_path)
    original = tmp_path / "source" / "show"
    copied = tmp_path / "copies" / "show"
    _touch_tree(original)
    _touch_tree(copied)
    _write_log(home, "tags4.txt", [f"TAG_COPY: {original} -> {copied}"])
    monkeypatch.setenv("TLOHome", str(home))

    plan = R.prepare_reverse_plan(str(copied))
    assert plan.operations[0].operation == "copy"
    result = R.reverse_folder_operations(plan)
    assert result.reversed == 1
    assert original.is_dir()
    assert not copied.exists()


def test_tag_copy_changed_file_set_is_not_deleted(tmp_path, monkeypatch):
    home = _home(tmp_path)
    original = tmp_path / "source" / "show"
    copied = tmp_path / "copies" / "show"
    _touch_tree(original)
    _touch_tree(copied)
    (copied / "extra.txt").write_text("new", encoding="utf-8")
    _write_log(home, "tags5.txt", [f"TAG_COPY: {original} -> {copied}"])
    monkeypatch.setenv("TLOHome", str(home))

    result = R.reverse_folder_operations(R.prepare_reverse_plan(str(copied)))
    assert result.conflicts == 1
    assert copied.is_dir()


def test_multiple_active_runs_require_narrower_path_or_log(tmp_path, monkeypatch):
    home = _home(tmp_path)
    broad = tmp_path / "music"
    a_src, a_dst = broad / "a-old", broad / "a-new"
    b_src, b_dst = broad / "b-old", broad / "b-new"
    _touch_tree(a_dst)
    _touch_tree(b_dst)
    _write_log(home, "tags6.txt", [f"RENAME_COMPLIANTLY: {a_src} -> {a_dst}"])
    _write_log(home, "tags7.txt", [f"RENAME_COMPLIANTLY: {b_src} -> {b_dst}"])
    monkeypatch.setenv("TLOHome", str(home))

    with pytest.raises(R.ReverseFoldersError, match="More than one logged run"):
        R.prepare_reverse_plan(str(broad))

    plan = R.prepare_reverse_plan(str(a_dst))
    assert len(plan.operations) == 1
    assert plan.operations[0].destination == os.path.normpath(str(a_dst))


def test_dry_run_changes_no_folders(tmp_path, monkeypatch):
    home = _home(tmp_path)
    original = tmp_path / "old"
    current = tmp_path / "new"
    _touch_tree(current)
    _write_log(home, "tags8.txt", [f"RENAME_COMPLIANTLY: {original} -> {current}"])
    monkeypatch.setenv("TLOHome", str(home))

    result = R.reverse_folder_operations(R.prepare_reverse_plan(str(current)), dry_run=True)
    assert result.reversed == 1
    assert current.is_dir() and not original.exists()
    assert any("WOULD_RESTORE_RENAME" in m for m in result.messages)
