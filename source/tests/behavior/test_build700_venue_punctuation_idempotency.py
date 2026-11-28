"""Build 700: parser preserves internal venue punctuation on every inventory pass."""
from __future__ import annotations

import os
import shutil
import sqlite3
from contextlib import closing
import subprocess
import sys
from pathlib import Path

import pytest
from mutagen.flac import FLAC

from tlo_phase23_v2 import _parse_string2

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
FLAC_FIXTURE = ROOT / "tests" / "fixtures" / "build543_silence.flac"


def _prepare_db(home: Path) -> None:
    db = home / "TLO_DBs"
    db.mkdir()
    with closing(sqlite3.connect(db / "artists.sqlite")) as conn, conn:
        conn.executescript("""
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, source_row_number INTEGER NOT NULL UNIQUE, master_name TEXT NOT NULL);
        CREATE TABLE aliases (alias_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL, alias_text TEXT NOT NULL, alias_order INTEGER NOT NULL);
        CREATE TABLE terms (term_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL, term_text TEXT NOT NULL, term_type TEXT NOT NULL, term_order INTEGER NOT NULL);
        INSERT INTO artists VALUES (1,1,'Grateful Dead');
        INSERT INTO aliases VALUES (1,1,'Grateful Dead',1);
        INSERT INTO terms VALUES (1,1,'Grateful Dead','master',0);
        """)
    (db / "venues.txt").write_text("Barton Hall, Cornell University\nBarton Hall\n", encoding="utf-8")


def test_path_venue_parser_keeps_internal_comma_not_boundary_comma():
    venue, city, region, country, extra = _parse_string2("Barton Hall, Cornell University Ithaca, NY")
    assert (venue, city, region, country, extra) == ("Barton Hall, Cornell University", "Ithaca", "NY", "", "")
    assert _parse_string2("The Metro, Chicago, IL")[:3] == ("The Metro", "Chicago", "IL")


def test_four_inventory_passes_keep_folder_album_and_bootlist_identical(tmp_path: Path):
    assert FLAC_FIXTURE.is_file()
    home = tmp_path / "home"
    home.mkdir()
    music = tmp_path / "music"
    music.mkdir()
    folder = music / "Grateful Dead 1977-05-08 Barton Hall, Ithaca, NY"
    folder.mkdir()
    (folder / "info.txt").write_text("Grateful Dead\nBarton Hall, Cornell University\nIthaca, NY\n1977-05-08\n\n01. Scarlet Begonias\n", encoding="utf-8")
    shutil.copy2(FLAC_FIXTURE, folder / "01.flac")
    _prepare_db(home)
    expected = "Grateful Dead 1977-05-08 Barton Hall, Cornell University Ithaca, NY"
    options = [
        ("--rename-compliantly", "--tag-during-inventory"),
        ("--rename-compliantly", "--tag-during-inventory"),
        ("--tag-during-inventory",),
        (),
    ]
    # The CI scratch volume may have a real label (e.g. cloudimg-rootfs).
    # Use that label rather than an invented [Disk]. A truly unlabeled volume
    # may use a stable explicit fixture label; TLO allows this only if the OS
    # cannot determine a label.
    from tlo_volume_label import resolve_volume_label
    actual_label = resolve_volume_label(str(music)).label
    search_path = f"[{actual_label or 'TLO_TEST_VOLUME'}] {music}"
    for extra in options:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run([
            sys.executable, str(ROOT / "tlo-gi.py"), "--TLOHome", str(home),
            "--search-path", search_path, *extra,
        ], cwd=str(ROOT), env=env, text=True, capture_output=True, timeout=80, check=False)
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
        files = list(music.rglob("01.flac"))
        assert len(files) == 1
        assert files[0].parent.name == expected
        assert FLAC(files[0])["album"] == [expected]
        boot = (home / "bootlist.csv").read_text(encoding="utf-8")
        assert boot.splitlines()[2].startswith(expected + "^")
        assert len(boot.splitlines()) == 3
        from tlo_storage_identities import load_registry, IDENTITY_PREFIX, JOURNAL, REGISTRY, LEGACY_OPERATIONS
        records = load_registry(str(home))
        assert len(records) == 1 and next(iter(records.values()))["path"] == str(music)
        assert any(IDENTITY_PREFIX in p.read_text(encoding="utf-8")
                   for p in (home / "logs").glob("groups*.log"))
        assert (home / "logs" / JOURNAL).is_file()
        assert not (home / REGISTRY).exists()
        assert not (home / "logs" / LEGACY_OPERATIONS).exists()


def test_unlabeled_search_path_uses_os_identity_and_wrong_explicit_label_rejected(tmp_path: Path, monkeypatch):
    from types import SimpleNamespace
    import inventory_list_lib as inventory
    from tlo_bootlist_volume_policy import normalize_volume_label
    from tlo_volume_label import resolve_volume_label

    music = tmp_path / "music"
    music.mkdir()
    info = resolve_volume_label(str(music))
    assigned = inventory._assign_volume_labels([(str(music), str(music), "", "")])
    assert assigned[0][3] == normalize_volume_label(info.label)

    # A deterministic OS-provided label exercises the fail-closed rule on every host,
    # including CI systems whose temporary partition has no label.
    monkeypatch.setattr(inventory, "resolve_volume_label", lambda path: SimpleNamespace(
        volume_key=info.volume_key, label="REAL_VOLUME", label_source="fixture"
    ))
    with pytest.raises(ValueError, match="Search path volume mismatch"):
        inventory._assign_volume_labels([(f"[Disk] {music}", str(music), "", "Disk")])
