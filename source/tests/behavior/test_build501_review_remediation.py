"""Build 501 regressions for the Build 500 requirements/code review remediation."""

__version__ = "v503"

import importlib.util
import multiprocessing
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

import inventory_parser_lib as IPL
import tlo_inventory_update as IU
import tlo_options as O
import tlo_postprocess as PP
import tlo_setlistfm_lookup as SFM
import tlo_tag_lib as TL
import tlo_phase23_v2 as P
from tlo_artist_db import ArtistMatcher
from tlo_models import ShowMetadata

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_hyphen_module(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _rate_wait_worker(home: str, sleeping, result_queue):
    original_sleep = SFM.time.sleep

    def signaled_sleep(seconds):
        sleeping.set()
        original_sleep(seconds)

    SFM.time.sleep = signaled_sleep
    # Reset the timestamp inside the spawned process so process-start latency
    # cannot consume the intended wait interval before the regression begins.
    SFM._write_rate_state(
        SFM._rate_limit_state_file(home),
        {"last_request": time.time(), "counts": {}, "daily": {}},
    )
    try:
        value = SFM.wait_for_rate_limit(
            0.80,
            max_calls=0,
            max_calls_per_day=0,
            run_id="waiter",
            tlo_home=home,
            lock_timeout_seconds=3.0,
        )
        result_queue.put(("waiter", value, ""))
    except Exception as exc:  # pragma: no cover - diagnostic path
        result_queue.put(("waiter-error", 0, str(exc)))


def _rate_holder_worker(home: str, ready, result_queue):
    lock_dir = SFM._rate_limit_lock_dir(home)
    try:
        SFM._acquire_rate_limit_lock(lock_dir, stale_after=30.0, timeout_seconds=2.0)
        ready.set()
        time.sleep(1.20)
        result_queue.put(("holder-lock-exists", os.path.isdir(lock_dir), ""))
    finally:
        try:
            os.rmdir(lock_dir)
        except OSError:
            pass


def test_build501_duplicate_text_review_reads_file_through_real_gui_callback(tmp_path):
    tk = pytest.importorskip("tkinter")
    gui = _load_hyphen_module("tlo-ggi.py", "tlo_ggi_build501_review")
    root = tk.Tk()
    root.withdraw()
    try:
        sample = tmp_path / "sample.txt"
        sample.write_text("hello from review\nsecond line", encoding="utf-8")
        obj = gui.DuplicateHandlerWindow.__new__(gui.DuplicateHandlerWindow)
        obj.window = root
        obj._open_text_review_window(str(sample))
        root.update_idletasks()
        reviews = [child for child in root.winfo_children() if isinstance(child, tk.Toplevel)]
        assert reviews
        container = reviews[-1].grid_slaves(row=1, column=0)[0]
        viewer = next(child for child in container.winfo_children() if child.winfo_class() == "Text")
        text = viewer.get("1.0", "end-1c")
        assert "hello from review" in text
        assert "Unable to read file" not in text
    finally:
        root.destroy()


def test_build501_rate_limit_waiter_does_not_remove_another_workers_lock(tmp_path):
    state_file = SFM._rate_limit_state_file(str(tmp_path))
    SFM._write_rate_state(state_file, {"last_request": time.time(), "counts": {}, "daily": {}})
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    sleeping = ctx.Event()
    holder_ready = ctx.Event()
    waiter = ctx.Process(target=_rate_wait_worker, args=(str(tmp_path), sleeping, q))
    waiter.start()

    # The worker signals from the actual wait_for_rate_limit sleep call. At this
    # point that function has already released its own lock, so the second worker
    # can deterministically acquire the lock during the wait interval.
    assert sleeping.wait(5.0)
    holder = ctx.Process(target=_rate_holder_worker, args=(str(tmp_path), holder_ready, q))
    holder.start()
    assert holder_ready.wait(5.0)

    waiter.join(8.0)
    holder.join(8.0)
    assert waiter.exitcode == 0
    assert holder.exitcode == 0
    rows = [q.get(timeout=2.0), q.get(timeout=2.0)]
    assert ("holder-lock-exists", True, "") in rows
    assert any(row[0] == "waiter" for row in rows)


def test_build501_proper_grammar_is_exposed_by_real_inventory_gui_and_tagger_parsers(tmp_path):
    args = IPL.build_inventory_parser().parse_args(["--search-path", str(tmp_path), "--proper-grammar"])
    assert args.proper_grammar is True

    tag = _load_hyphen_module("tlo-tag.py", "tlo_tag_build501_parse")
    tag_args = tag._parse_args([str(tmp_path), "--proper-grammar"])
    assert tag_args.proper_grammar is True

    gui = _load_hyphen_module("tlo-ggi.py", "tlo_ggi_build501_parse")
    gui_args = gui._parse_gui_command_line(["--proper-grammar"])
    assert gui_args.proper_grammar is True


def test_build501_tlo_tag_main_passes_proper_grammar_to_shared_tagger(tmp_path, monkeypatch):
    tag = _load_hyphen_module("tlo-tag.py", "tlo_tag_build501_main")
    captured = {}

    def fake_build(**kwargs):
        captured["build"] = dict(kwargs)
        values = dict(kwargs)
        values["TLOHome"] = values.get("tlo_home", "")
        return SimpleNamespace(**values)

    def fake_run(**kwargs):
        captured["run"] = dict(kwargs)
        return {"groups": 0}

    monkeypatch.setattr(tag, "build_tagger_config", fake_build)
    monkeypatch.setattr(tag, "resolve_tagging_path", lambda _home, path: str(path))
    monkeypatch.setattr(tag, "operation_review_lines", lambda *a, **k: [])
    monkeypatch.setattr(tag, "append_run_settings", lambda *a, **k: None)
    monkeypatch.setattr(tag, "run_tagger", fake_run)
    assert tag.main([str(tmp_path), "--proper-grammar"]) == 0
    assert captured["build"]["proper_grammar"] is True
    assert captured["run"]["proper_grammar"] is True


def test_build501_delete_script_translates_wsl_and_windows_paths_and_uses_crlf(tmp_path, monkeypatch):
    bat = tmp_path / "deleteReplacedFolders.bat"
    assert IU._append_delete_command(str(bat), "/mnt/e/Artist/Show") is True
    raw = bat.read_bytes()
    assert b'E:\\Artist\\Show' in raw
    assert b"\r\n" in raw
    assert b"\n" not in raw.replace(b"\r\n", b"")

    sh = tmp_path / "deleteBackupFolders.sh"
    monkeypatch.setattr(IU, "_running_under_wsl", lambda: True)
    assert IU._append_delete_command(str(sh), r"E:\Artist\Show") is True
    assert "/mnt/e/Artist/Show" in sh.read_text(encoding="utf-8")


def test_build501_untranslatable_delete_path_fails_closed(tmp_path, monkeypatch):
    sh = tmp_path / "deleteBackupFolders.sh"
    monkeypatch.setattr(IU, "_running_under_wsl", lambda: False)
    assert IU._append_delete_command(str(sh), r"E:\Artist\Show") is False
    assert not sh.exists()


def test_build501_backup_alert_uses_actual_script_name():
    gui = _load_hyphen_module("tlo-ggi.py", "tlo_ggi_build501_backup")
    assert gui._backup_alert_message("/tmp/deleteBackupFolders.sh") == "TLOHome/deleteBackupFolders.sh already exists. Continue or abort?"
    assert gui._backup_alert_message(r"C:\\.tlo\\deleteReplacedFolders.bat").endswith("deleteReplacedFolders.bat already exists. Continue or abort?")


def test_build501_missing_corruption_fields_fail_closed_but_valid_zero_threshold_is_preserved():
    assert O.defensive_corruption_policy_values(SimpleNamespace()) == ("keep", "never", 100)
    assert O.defensive_corruption_policy_values({"corrupt_files": "delete", "corrupt_folders": "threshold", "corrupt_folder_threshold": 0}) == ("delete", "threshold", 0)
    assert O.defensive_corruption_policy_values({"corrupt_files": "bogus", "corrupt_folders": "bogus", "corrupt_folder_threshold": None}) == ("keep", "never", 100)


def test_build501_destination_reservation_retries_without_overwriting_racing_directory(tmp_path, monkeypatch):
    parent = tmp_path / "dest"
    parent.mkdir()
    first = parent / "Show"
    second = parent / "Show (alt1)"
    calls = {"n": 0}

    def racing_unique(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            first.mkdir()
            return str(first)
        return str(second)

    monkeypatch.setattr(TL, "_unique_destination_path", racing_unique)
    reserved = TL._reserve_unique_destination_directory(str(parent), "Show", "")
    assert Path(reserved) == second
    assert first.is_dir()
    assert second.is_dir()


def test_build501_copy_delete_cleanup_failure_retains_verified_destination_and_reports_recovery(tmp_path, monkeypatch):
    source = tmp_path / "source" / "Show"
    source.mkdir(parents=True)
    (source / "track.flac").write_bytes(b"abc")
    destination_parent = tmp_path / "dest"
    destination_parent.mkdir()
    config = SimpleNamespace(tag_copy_and_delete_path=str(destination_parent), rename_compliantly=False)
    group = {"main_dir_path": str(source), "music_dirs": [str(source)], "music_files": [str(source / "track.flac")]}
    record = SimpleNamespace(main_dir_name="Show", main_dir_path=str(source), show_name="Show", parentheticals="", setlist_file="", music_dirs=[str(source)], setlist_files=[])
    monkeypatch.setattr(TL, "_paths_on_same_filesystem", lambda *_: False)
    real_rmtree = TL.shutil.rmtree

    def fail_source_cleanup(path, *args, **kwargs):
        if os.path.normpath(str(path)) == os.path.normpath(str(source)):
            raise OSError("simulated cleanup failure")
        return real_rmtree(path, *args, **kwargs)

    monkeypatch.setattr(TL.shutil, "rmtree", fail_source_cleanup)
    with pytest.raises(TL.TaggerError, match="Destination verified; source may be partially removed"):
        TL.prepare_inventory_copy_delete_target(config, group, record)
    copied = [p for p in destination_parent.iterdir() if p.is_dir()]
    assert len(copied) == 1
    assert (copied[0] / "track.flac").read_bytes() == b"abc"


def test_build501_setlist_collision_requires_content_identity_not_same_size(tmp_path):
    setlists = tmp_path / "setlists"
    setlists.mkdir()
    exact = setlists / "Artist 2000-01-01.txt"
    exact.write_text("AAAA\n", encoding="utf-8")
    used = {exact.name}
    name, should_write = PP._resolve_setlist_filename_for_text("Artist 2000-01-01", str(setlists), "BBBB", used)
    assert name == "Artist 2000-01-01(alt1).txt"
    assert should_write is True
    name2, should_write2 = PP._resolve_setlist_filename_for_text("Artist 2000-01-01", str(setlists), "AAAA", {exact.name})
    assert name2 == exact.name
    assert should_write2 is False


def test_build501_known_artist_with_unknown_word_is_not_blankened_before_db_resolution():
    matcher = ArtistMatcher(db_path="test")
    matcher.master_aliases = {"Unknown Mortal Orchestra": ["Unknown Mortal Orchestra"]}
    matcher.exact_map = {"unknown mortal orchestra": {"Unknown Mortal Orchestra"}}
    matcher.master_norms = {"Unknown Mortal Orchestra": {"unknownmortalorchestra"}}
    record = ShowMetadata(
        group_number=1,
        main_dir_name="show",
        main_dir_path="/music/show",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "Unknown Mortal Orchestra", "albumartist": "", "date": ""}],
    )
    P._blank_unusable_artist_tags_for_noncompliant(record, [], matcher)
    assert record.flac_tag_samples[0]["artist"] == "Unknown Mortal Orchestra"


def test_build501_unmatched_generic_unknown_tag_is_still_blankened():
    matcher = ArtistMatcher(db_path="test")
    record = ShowMetadata(
        group_number=1,
        main_dir_name="show",
        main_dir_path="/music/show",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "Unknown", "albumartist": "", "date": ""}],
    )
    P._blank_unusable_artist_tags_for_noncompliant(record, [], matcher)
    assert record.flac_tag_samples[0]["artist"] == ""

def test_build501_requirements_reconcile_review_findings_and_remove_stale_label():
    from docx import Document
    root = Path(__file__).resolve().parents[2]
    text = "\n".join(p.text for p in Document(root / "TLO_Inventory_Requirements_Working_v512.docx").paragraphs)
    assert "Current document version: v512 (TLO v1.7)." in text
    assert "Old Grammar" not in text
    assert "14.8 Collection Search GUI (tlo-gsi)" in text
    assert "14.9 Artist Database Search GUI (search-artist-db)" in text
    assert "REQ-CORR-000" in text and "fail closed" in text
    assert "SHA-256" in text
    assert "deleteBackupFolders.txt" not in text


def test_build501_current_manual_and_changes_are_versioned():
    root = Path(__file__).resolve().parents[2]
    manual = (root / "TLO_Inventory_User_Manual_v512.rtf").read_text(encoding="utf-8", errors="ignore")
    changes = (root / "CHANGES_v512.txt").read_text(encoding="utf-8")
    assert "Version v1.7 Build 512" in manual
    assert "Build 501" in manual
    assert "Review remediation" in changes
