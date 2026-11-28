"""Reproduce review W1/W2/W5/W6/W10 against real catalogs and public entry points."""
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from tlo_artist_db import load_artist_matcher, lookup_artist_masters
from tlo_phase23_v2 import _eligible_artist_path_parts, _resolve_artist_from_subdirs
from tlo_postprocess import _adjust_show_name_for_output, _record_has_blank_show
from tlo_runtime_control import inventory_operation_lock

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.behavior


@pytest.fixture(scope="module")
def matcher():
    return load_artist_matcher(SimpleNamespace(artist_sqlite_db_file=str(ROOT / "TLO_DBs" / "artists.sqlite")))


@pytest.mark.parametrize("term,master", [("Björk", "Bjork"), ("Beyoncé", "Beyonce"),
    ("Motörhead", "Motorhead"), ("Sigur Rós", "Sigur Ros"), ("Mötley Crüe", "Motley Crue"), ("Maná", "Mana")])
def test_real_catalog_accent_query(matcher, term, master):
    assert lookup_artist_masters(term, matcher) == [master]


@pytest.mark.parametrize("container", ["Dropbox", "Elements", "Work", "Public"])
def test_unknown_artist_not_inferred_from_storage(tmp_path, matcher, container):
    root = tmp_path / container
    show = root / "Zzyzx Quartet 2023-01-01 Cambridge, MA"
    group = {"search_root": str(root), "main_dir_path": str(show), "music_dirs": [str(show)]}
    assert container not in [name for name, _ in _eligible_artist_path_parts(group)]
    assert _resolve_artist_from_subdirs(group, matcher, {}, []) == ""


def test_artist_folder_with_date_only_child_remains_usable(tmp_path, matcher):
    root = tmp_path / "Music"
    show = root / "Phish" / "1997-11-29"
    group = {"search_root": str(root), "main_dir_path": str(show), "music_dirs": [str(show)]}
    assert _resolve_artist_from_subdirs(group, matcher, {}, []) == "Phish"


def test_nonlatin_artist_not_output_as_bare_date():
    record = {"artist": "Кино", "show_name": "Кино 1990-06-24", "date": "1990-06-24"}
    assert _record_has_blank_show(record)
    assert not _adjust_show_name_for_output(record)


@pytest.mark.parametrize("script", ["tlo-tag.py", "tlo-deleteDupes.py"])
def test_cli_media_mutation_refuses_held_lock(tmp_path, script):
    home = tmp_path / "home"
    home.mkdir()
    collection = tmp_path / "shows"
    collection.mkdir()
    with inventory_operation_lock(str(home)):
        result = subprocess.run([sys.executable, str(ROOT / script), "--TLOHome", str(home), str(collection)],
                                capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert "Another inventory-mutating TLO run" in result.stderr + result.stdout


def test_real_inventory_ancestor_and_accent(tmp_path):
    """Use public CLI with real DBs and actual FLAC tags, not just helpers."""
    import shutil
    from mutagen.flac import FLAC
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("FFmpeg fixture encoder unavailable")
    home = tmp_path / "home"
    shutil.copytree(ROOT / "TLO_DBs", home / "TLO_DBs")
    root = tmp_path / "Dropbox"
    show = root / "Björk 2007-08-20 Paris, France"
    show.mkdir(parents=True)
    unknown = root / "Zzyzx Quartet 2023-01-01 Cambridge, MA"
    unknown.mkdir()
    audio = show / "01.flac"
    subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=duration=0.1", str(audio)],
                   check=True, capture_output=True)
    tags = FLAC(audio)
    tags["ARTIST"] = "Björk"
    tags["TITLE"] = "Jóga"
    tags.save()
    shutil.copy2(audio, unknown / "01.flac")
    tags = FLAC(unknown / "01.flac"); tags.clear(); tags.save()
    cmd = [sys.executable, str(ROOT / "tlo-gi.py"), "--TLOHome", str(home), "--search-path", str(root)]
    result = subprocess.run(cmd, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    bootlist = (home / "bootlist.csv").read_text(encoding="utf-8-sig")
    assert "Bjork 2007-08-20" in bootlist
    assert "Dropbox 2007-08-20" not in bootlist and "Dropbox 2023-01-01" not in bootlist
    assert "Zzyzx Quartet" in (home / "unidentifiedShows.txt").read_text(encoding="utf-8-sig")
    assert FLAC(audio)["ARTIST"] == ["Björk"]


def test_preview_uses_actual_rename_guard(tmp_path):
    import shutil
    home = tmp_path / "home"
    shutil.copytree(ROOT / "TLO_DBs", home / "TLO_DBs")
    show = tmp_path / "shows" / "Phish 1997-11-29 Worcester Centrum, Worcester, MA"
    show.mkdir(parents=True)
    (show / "01.flac").write_bytes(b"fixture only")
    result = subprocess.run([sys.executable, str(ROOT / "tlo-gi.py"),
                             "--TLOHome", str(home), "--search-path", str(show.parent),
                             "--dry-run", "--rename-compliantly", "--tag-during-inventory"],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "rename skipped:" in result.stdout or "no rename needed" in result.stdout
    assert "rename to resolved compliant show name" not in result.stdout
