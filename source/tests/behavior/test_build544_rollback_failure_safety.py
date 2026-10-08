"""Build 544 rollback-failure safety regressions."""

from __future__ import annotations
from tests._release_artifacts import release_history
from tests import _release_artifacts as RA

import ast
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_folder_rename as FR
import tlo_manual_updates as MU
import tlo_sibling_collections as SC

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _diag_spy(monkeypatch, module):
    calls: list[tuple[str, BaseException]] = []
    monkeypatch.setattr(module, "debug_suppressed_exception", lambda context, exc: calls.append((context, exc)))
    return calls


def test_build544_case_only_rename_reports_failed_rollback_location(monkeypatch, tmp_path):
    source = tmp_path / "old name"
    destination = tmp_path / "Old Name"
    temporary = tmp_path / ".old name.tlo-case-rename-test"
    source.mkdir()
    diagnostics = _diag_spy(monkeypatch, FR)
    real_rename = os.rename
    calls = 0

    monkeypatch.setattr(FR, "same_existing_entry", lambda _left, _right: True)
    monkeypatch.setattr(FR, "_temporary_case_rename_path", lambda _source: str(temporary))

    def faulted_rename(left, right):
        nonlocal calls
        calls += 1
        if calls == 1:
            return real_rename(left, right)
        if calls == 2:
            raise OSError("final hop blocked")
        if calls == 3:
            raise OSError("rollback blocked")
        raise AssertionError("unexpected rename call")

    monkeypatch.setattr(FR.os, "rename", faulted_rename)

    with pytest.raises(OSError) as caught:
        FR.rename_folder_exact_case(str(source), str(destination))

    message = str(caught.value)
    assert "could not be undone" in message
    assert str(temporary) in message
    assert "final hop blocked" in message
    assert "rollback blocked" in message
    assert temporary.is_dir() and not source.exists() and not destination.exists()
    assert diagnostics and diagnostics[0][0] == "case-only folder rename rollback"
    assert "rollback blocked" in str(diagnostics[0][1])


def test_build544_manual_update_reports_folder_rollback_failure(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    original = tmp_path / "library" / "Old Folder"
    original.mkdir(parents=True)
    target = original.parent / "New Folder"
    rows = [{"Show": "Old Folder", "VolumePath": str(original)}]
    diagnostics = _diag_spy(monkeypatch, MU)
    real_rename = MU.rename_folder_exact_case
    rename_calls = 0

    monkeypatch.setattr(MU, "_matching_bootlist_rows", lambda _home, _path: list(rows))
    monkeypatch.setattr(MU, "read_bootlist", lambda _home: list(rows))
    monkeypatch.setattr(MU, "infer_setlist_paths_for_show", lambda _home, _show: [])
    monkeypatch.setattr(MU, "_snapshot_setlists", lambda _paths: [])
    monkeypatch.setattr(MU, "write_bootlist", lambda _home, _rows: None)
    monkeypatch.setattr(MU, "identify_folder_dict", lambda _config, _path: (_ for _ in ()).throw(RuntimeError("metadata failed")))

    def faulted_exact_rename(left, right):
        nonlocal rename_calls
        rename_calls += 1
        if rename_calls == 1:
            return real_rename(left, right)
        raise OSError("rollback rename blocked")

    monkeypatch.setattr(MU, "rename_folder_exact_case", faulted_exact_rename)

    with pytest.raises(MU.ManualUpdateError) as caught:
        MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(home)), str(original), "New Folder")

    message = str(caught.value)
    assert "metadata failed" in message
    assert "Automatic rollback was incomplete" in message
    assert "folder rename could not be undone" in message
    assert f"current folder location: {target}" in message
    assert "rollback rename blocked" in message
    assert target.is_dir() and not original.exists()
    assert any(context == "Manual Updates folder rollback" for context, _exc in diagnostics)


def test_build544_manual_update_reports_bootlist_restore_failure(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    original = tmp_path / "library" / "Old Folder"
    original.mkdir(parents=True)
    rows = [{"Show": "Old Folder", "VolumePath": str(original)}]
    diagnostics = _diag_spy(monkeypatch, MU)
    writes = 0

    monkeypatch.setattr(MU, "_matching_bootlist_rows", lambda _home, _path: list(rows))
    monkeypatch.setattr(MU, "read_bootlist", lambda _home: list(rows))
    monkeypatch.setattr(MU, "infer_setlist_paths_for_show", lambda _home, _show: [])
    monkeypatch.setattr(MU, "_snapshot_setlists", lambda _paths: [])
    monkeypatch.setattr(MU, "identify_folder_dict", lambda _config, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda _home, _record: "")

    def faulted_write(_home, _rows):
        nonlocal writes
        writes += 1
        if writes == 1:
            raise OSError("commit write failed")
        raise OSError("restore write blocked")

    monkeypatch.setattr(MU, "write_bootlist", faulted_write)

    with pytest.raises(MU.ManualUpdateError) as caught:
        MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(home)), str(original), "New Folder")

    message = str(caught.value)
    assert "commit write failed" in message
    assert "bootlist.csv could not be restored" in message
    assert "restore write blocked" in message
    assert str(home / "bootlist.csv") in message
    assert original.is_dir() and not (original.parent / "New Folder").exists()
    assert any(context == "Manual Updates bootlist rollback" for context, _exc in diagnostics)


def test_build544_unidentified_update_reports_state_restore_failure(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    unidentified = home / "unidentifiedShows.txt"
    unidentified.write_text("/old/Unknown Show\n", encoding="utf-8")
    destination = tmp_path / "destination"
    final = destination / "Known Show"
    final.mkdir(parents=True)
    diagnostics = _diag_spy(monkeypatch, MU)

    monkeypatch.setattr(MU, "find_unidentified_show_path", lambda _home, _original: "/old/Unknown Show")
    monkeypatch.setattr(MU, "read_bootlist", lambda _home: [])
    monkeypatch.setattr(MU, "identify_folder_dict", lambda _config, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda _home, _record: "")
    monkeypatch.setattr(MU, "write_bootlist", lambda _home, _rows: None)
    monkeypatch.setattr(MU, "_remove_unidentified_show_path", lambda _home, _path: (_ for _ in ()).throw(OSError("commit removal failed")))
    monkeypatch.setattr(MU, "_atomic_write_bytes", lambda _path, _payload: (_ for _ in ()).throw(OSError("restore unidentified blocked")))

    with pytest.raises(MU.ManualUpdateError) as caught:
        MU.apply_unidentified_manual_update(
            SimpleNamespace(TLOHome=str(home)),
            "/old/Unknown Show",
            "Known Show",
            str(destination),
        )

    message = str(caught.value)
    assert "commit removal failed" in message
    assert "unidentifiedShows.txt could not be restored" in message
    assert str(unidentified) in message
    assert "current state: present" in message
    assert "restore unidentified blocked" in message
    assert any(context == "Manual Updates unidentifiedShows rollback" for context, _exc in diagnostics)


def test_build544_sibling_consolidation_reports_log_and_folder_rollback_failures(monkeypatch, tmp_path):
    parent = tmp_path / "library"
    member_path = parent / "Artist Collection CD1"
    member_path.mkdir(parents=True)
    log_path = tmp_path / "complete-path.log"
    log_path.write_bytes(b"before\n")
    plan = SC.CollectionPlan(
        parent_dir=str(parent),
        base_name="Artist Collection",
        kind="multipart",
        members=[SC.CollectionMember(path=str(member_path), index=1)],
    )
    diagnostics = _diag_spy(monkeypatch, SC)
    real_unlink = os.unlink

    monkeypatch.setattr(SC, "_rewrite_complete_path_log", lambda _path, _rewrites: None)
    monkeypatch.setattr(
        SC,
        "_restore_complete_path_log",
        lambda _path, _payload: (_ for _ in ()).throw(OSError("log restore blocked")),
    )

    def faulted_rollback(container, _payload):
        raise SC._SiblingCollectionRollbackFailure(container, "member restore blocked")

    monkeypatch.setattr(SC, "_rollback_container", faulted_rollback)

    def faulted_unlink(path):
        if str(path).endswith(SC.JOURNAL_NAME):
            raise OSError("journal cleanup failed")
        return real_unlink(path)

    monkeypatch.setattr(SC.os, "unlink", faulted_unlink)

    with pytest.raises(RuntimeError) as caught:
        SC._execute_plan(plan, str(log_path), tlo_home="")

    final_path = parent / "Artist Collection"
    message = str(caught.value)
    assert "journal cleanup failed" in message
    assert "complete-path log could not be restored" in message
    assert "log restore blocked" in message
    assert "folder rollback failed" in message
    assert "member restore blocked" in message
    assert f"Current recovery container: {final_path}" in message
    assert final_path.is_dir()
    contexts = {context for context, _exc in diagnostics}
    assert "sibling collection complete-path log rollback" in contexts
    assert "sibling collection folder rollback" in contexts


def test_build544_destructive_modules_do_not_silently_pass_broad_exceptions():
    for name in (
        "tlo_folder_rename.py",
        "tlo_manual_updates.py",
        "tlo_sibling_collections.py",
        "tlo_corruption.py",
    ):
        source = (ROOT / name).read_text(encoding="utf-8")
        tree = ast.parse(source)
        silent = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not (isinstance(node.type, ast.Name) and node.type.id == "Exception"):
                continue
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                silent.append(node.lineno)
        assert not silent, f"{name} silently passes broad exceptions at lines {silent}"
        assert "debug_suppressed_exception" in source


def test_build544_version_and_documentation_contract():
    from docx import Document

    requirements_path = ROOT / RA.REQUIREMENTS_FILENAME
    manual_path = ROOT / RA.MANUAL_FILENAME
    assert requirements_path.is_file() and manual_path.is_file()
    req = "\n".join(p.text for p in Document(requirements_path).paragraphs)
    assert "Build 544: P2-M1 -> §16.4" in req
    assert "the user-facing failure must state that rollback was incomplete" in req
    manual = manual_path.read_text(encoding="utf-8", errors="ignore")
    assert "Build 544 - " in release_history()
    assert "reports the rollback failure" in manual
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    first = changes.split("TLO v1.7 Build 543", 1)[0]
    assert "P2-M1 only" in first
    assert "GitHub Build Process remains v108 unchanged" in first
