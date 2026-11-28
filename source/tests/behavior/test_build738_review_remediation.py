"""Behavioral regressions for review 732 safety and reference-catalog findings."""
import importlib.util
import os
from pathlib import Path, PureWindowsPath
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

from tlo_catalog_io import catalog_readonly_uri, open_catalog_readonly
from tlo_locking import acquire_owned_lock, release_owned_lock
from tlo_media_rules import COUNTED_AUDIO, DISCOVERY, TAG_WRITABLE, VIDEO_EXTENSIONS
from tlo_security import trusted_windows_tool

ROOT = Path(__file__).resolve().parents[2]


def test_trusted_windows_paths(monkeypatch):
    import tlo_security
    from tlo_msi_install_mode import _trusted_system32_executable
    monkeypatch.setattr(tlo_security, "windows_directory_from_api", lambda: r"C:\Windows")
    assert _trusted_system32_executable("powershell.exe") == r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    assert trusted_windows_tool("whoami.exe") == r"C:\Windows\System32\whoami.exe"
    assert trusted_windows_tool("icacls.exe") == r"C:\Windows\System32\icacls.exe"
    with pytest.raises(ValueError):
        trusted_windows_tool("unknown.exe")


@pytest.mark.skipif(os.name == "nt", reason="POSIX link creation test; native Windows reparse acceptance pending")
@pytest.mark.parametrize("kind", ["symlink", "hardlink", "fifo"])
def test_lock_refuses_link_and_preserves_victim(tmp_path, kind):
    victim = tmp_path / "victim"
    victim.write_bytes(b"do not overwrite")
    lock = tmp_path / "operation.lock"
    if kind == "symlink":
        lock.symlink_to(victim)
    elif kind == "hardlink":
        os.link(victim, lock)
    else:
        os.mkfifo(lock)
    with pytest.raises(OSError):
        acquire_owned_lock(str(lock), {"pid": os.getpid()})
    assert victim.read_bytes() == b"do not overwrite"
    lock.unlink()
    assert acquire_owned_lock(str(lock), {"pid": os.getpid()})
    assert release_owned_lock(str(lock))


def test_private_recovery_directory(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("reverse738", ROOT / "tlo-reverse.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod.os.path, "expanduser", lambda _: str(tmp_path))
    home = Path(mod._private_recovery_lock_home(str(tmp_path / "destination")))
    assert home.is_relative_to(tmp_path)
    assert (home / "logs").is_dir()
    if os.name != "nt":
        assert home.stat().st_mode & 0o077 == 0
        home.chmod(0o777)
        with pytest.raises(OSError, match="Unsafe"):
            mod._private_recovery_lock_home(str(tmp_path / "destination"))


def test_media_roles_and_artifacts(tmp_path):
    from initial_dir_walk_lib import _phase1_is_real_music_file
    from tlo_corruption import group_audio_snapshot
    from tlo_tag_lib import _is_audio_file, _is_taggable_audio_file
    from tlo_media_rules import is_media_file
    from tlo_inventory_update import _collect_folder_paths
    from tlo_phase23_v2 import _is_music_file
    filenames = ["track.flac", "track2.flac", "._track.flac", "._track2.flac",
                 ".tlo-deleteDupes-backup-123.flac", ".tlo-convert-1.flac", "other.wma",
                 "other.tta", "vid.mp4"]
    for name in filenames:
        (tmp_path / name).write_bytes(b"fixture")
    audio = {"track.flac", "track2.flac", "other.wma", "other.tta"}
    discovered = audio | {"vid.mp4"}
    assert TAG_WRITABLE < COUNTED_AUDIO < DISCOVERY
    assert not VIDEO_EXTENSIONS.intersection(COUNTED_AUDIO)
    for predicate in (_phase1_is_real_music_file, is_media_file, _is_music_file):
        assert {p.name for p in tmp_path.iterdir() if predicate(str(p))} == discovered
    assert {p.name for p in tmp_path.iterdir() if _is_audio_file(str(p))} == audio
    assert {p.name for p in tmp_path.iterdir() if _is_taggable_audio_file(str(p))} == {"track.flac", "track2.flac"}
    paths, errors = group_audio_snapshot({"music_dirs": [str(tmp_path)]})
    assert not errors and {Path(p).name for p in paths} == audio
    assert {Path(p).name for p in _collect_folder_paths(str(tmp_path))[1]} == discovered


def test_catalog_uri_and_readonly(tmp_path):
    unc = PureWindowsPath(r"\\nas\music\TLO DBs\cities#1.sqlite")
    assert catalog_readonly_uri(unc) == "file:////nas/music/TLO%20DBs/cities%231.sqlite?mode=ro"
    file = tmp_path / "catalog #1.sqlite"
    with sqlite3.connect(file) as db:
        db.execute("CREATE TABLE sample (value TEXT)")
    db = open_catalog_readonly(file)
    try:
        with pytest.raises(sqlite3.Error, match="readonly"):
            db.execute("INSERT INTO sample VALUES ('x')")
    finally:
        db.close()
    missing = tmp_path / "not there.sqlite"
    with pytest.raises(sqlite3.Error):
        open_catalog_readonly(missing)
    assert not missing.exists()


def test_valid_venue_sqlite_does_not_require_legacy_text():
    from tlo_db_validation import validate_required_databases
    db = ROOT / "TLO_DBs"
    config = SimpleNamespace(tlo_dbs_dir=str(db), artist_sqlite_db_file=str(db / "artists.sqlite"),
                             venue_reference_db_file=str(db / "not-present.txt"))
    artist, venue = validate_required_databases(config)
    assert Path(artist).name == "artists.sqlite"
    assert Path(venue).name == "venues.sqlite"


def test_batch_zero_rejected():
    run = subprocess.run([sys.executable, str(ROOT / "tlo-reverse.py"), "--manual-updates", "--batch", "0"],
                         capture_output=True, text=True)
    assert run.returncode == 2
    assert "--batch must be between 1 and 100" in run.stderr


def test_cleanup_doc_contract():
    from docx import Document
    from tlo_version import VERSION
    source = (ROOT / "tlo_inventory_update.py").read_text()
    assert "rmdir /s /q" in source
    req = Document(ROOT / f"TLO_Inventory_Requirements_Working_{VERSION}.docx")
    for p in req.paragraphs:
        t = p.text.casefold()
        if "deletereplacedfolders" in t or "deferred old-folder windows" in t:
            assert "recycle-only" not in t
    assert any("permanently destructive rmdir /s /q" in p.text for p in req.paragraphs)



def test_appledouble_does_not_trigger_folder_threshold(tmp_path, monkeypatch):
    import tlo_corruption as corruption
    for name in ("01.flac", "02.flac", "._01.flac", "._02.flac"):
        (tmp_path / name).write_bytes(b"fixture")
    def tag_probe(path):
        if Path(path).name.startswith("._"):
            raise ValueError("not audio")
    monkeypatch.setattr(corruption, "_validate_tag_write_round_trip", tag_probe)
    result = corruption.assess_group_corruption({"music_dirs": [str(tmp_path)]},
        corrupt_files="keep", corrupt_folders="threshold", folder_threshold=50, check_tag_write=True)
    assert len(result.audio_files) == 2
    assert not result.corrupt_files and result.corruption_percent == 0
    assert result.action == "none"
