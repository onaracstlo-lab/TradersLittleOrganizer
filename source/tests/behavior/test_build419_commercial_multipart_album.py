"""Build 419 regressions for commercial-release ALBUM tags and Parent (N) aggregation."""

__version__ = "v421"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _build_groups_from_tree(tmp_path, root):
    import logging_lib
    import tlo_phase23_v2 as phase
    from initial_dir_walk_lib import initial_dir_walk

    config = SimpleNamespace(
        TLOHome=str(tmp_path / "home"),
        performance_mode="balanced",
        silent=True,
        compliant=False,
    )
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(root), 1, log_token="N")
    initial_dir_walk(config, str(root))
    return phase._build_groups_from_search_path(config, str(root))


def _pink_floyd_tree(tmp_path, count=9):
    root = tmp_path / "boots"
    base = "Pink Floyd - 1988 Some More Secrets - Limited Edition Box Set"
    parent = root / base
    for part in range(1, count + 1):
        folder = parent / f"{base} ({part})"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"01 - Track {part}.flac").write_bytes(b"audio")
    return root, parent, base


def test_parent_named_same_base_with_consecutive_parenthesized_parts_aggregates(tmp_path):
    root, parent, base = _pink_floyd_tree(tmp_path)

    groups = _build_groups_from_tree(tmp_path, root)

    assert len(groups) == 1
    group = groups[0]
    assert group["main_dir_path"] == os.path.normpath(str(parent))
    assert group["main_dir_name"] == base
    assert group["aggregate_album_name"] == base
    assert group["aggregate_release_base"] == base
    assert len(group["music_dirs"]) == 9
    assert [os.path.basename(path) for path in group["music_dirs"]] == [f"{base} ({n})" for n in range(1, 10)]


def test_parenthesized_parts_require_consecutive_numbers_starting_at_one(tmp_path):
    root = tmp_path / "boots"
    base = "Pink Floyd - Collection"
    parent = root / base
    for part in (1, 3):
        folder = parent / f"{base} ({part})"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "01 Track.flac").write_bytes(b"audio")

    groups = _build_groups_from_tree(tmp_path, root)

    assert len(groups) == 2
    assert all(group["main_dir_path"] != os.path.normpath(str(parent)) for group in groups)


def test_parenthesized_parts_require_parent_name_to_match_common_base(tmp_path):
    root = tmp_path / "boots"
    parent = root / "Compilation Root"
    base = "Pink Floyd - Collection"
    for part in (1, 2):
        folder = parent / f"{base} ({part})"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "01 Track.flac").write_bytes(b"audio")

    groups = _build_groups_from_tree(tmp_path, root)

    assert len(groups) == 2
    assert all(group["main_dir_path"] != os.path.normpath(str(parent)) for group in groups)


def test_parenthesized_parts_do_not_aggregate_when_parent_itself_has_music(tmp_path):
    root, parent, base = _pink_floyd_tree(tmp_path, count=2)
    (parent / "00 Parent Track.flac").write_bytes(b"audio")

    groups = _build_groups_from_tree(tmp_path, root)

    assert len(groups) == 3


def test_noncompliant_album_name_is_used_before_unknown_fallback():
    import tlo_tag_lib as taglib

    record = SimpleNamespace(
        artist="Pink Floyd",
        date="",
        venue="",
        location="",
        album_name="1988 Some More Secrets - Limited Edition Box Set",
        parentheticals="",
    )

    assert taglib._album_for_record(SimpleNamespace(compliant=False, artist_in_album=True), record) == (
        "Pink Floyd 1988 Some More Secrets - Limited Edition Box Set"
    )
    assert taglib._album_for_record(SimpleNamespace(compliant=False, artist_in_album=False), record) == (
        "1988 Some More Secrets - Limited Edition Box Set"
    )


def test_aggregated_pink_floyd_parent_resolves_one_commercial_release_record(tmp_path):
    import sqlite3
    import tlo_phase23_v2 as phase
    from tlo_artist_db import load_artist_matcher

    root, parent, base = _pink_floyd_tree(tmp_path)
    db_dir = tmp_path / "db"
    db_dir.mkdir()
    db = db_dir / "artists.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, source_row_number INTEGER NOT NULL UNIQUE, master_name TEXT NOT NULL);
        CREATE TABLE aliases (alias_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL, alias_text TEXT NOT NULL, alias_order INTEGER NOT NULL);
        CREATE TABLE terms (term_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL, term_text TEXT NOT NULL, term_type TEXT NOT NULL, term_order INTEGER NOT NULL);
        INSERT INTO artists VALUES (1, 1, 'Pink Floyd');
        INSERT INTO aliases VALUES (1, 1, 'PF', 1);
        INSERT INTO terms VALUES (1, 1, 'Pink Floyd', 'master', 0);
        INSERT INTO terms VALUES (2, 1, 'PF', 'alias', 1);
        """
    )
    conn.commit()
    conn.close()
    matcher = load_artist_matcher(SimpleNamespace(artist_sqlite_db_file=str(db)))

    groups = _build_groups_from_tree(tmp_path, root)
    groups[0]["group_number"] = 1
    config = SimpleNamespace(
        compliant=False,
        current_slam="",
        etree_lookup=False,
        setlistfm_lookup=False,
        setlistfm_upgrade=False,
        as_is_artist_name=False,
        TLOHome=str(tmp_path / "home2"),
        performance_mode="balanced",
        silent=True,
    )
    record, _dates, unresolved = phase._extract_metadata_for_group(config, groups[0], matcher)

    assert unresolved == []
    assert record.artist == "Pink Floyd"
    assert record.date == ""
    assert record.album_name == "1988 Some More Secrets - Limited Edition Box Set"
    assert record.show_name == "Pink Floyd - 1988 Some More Secrets - Limited Edition Box Set"
    assert record.main_dir_path == os.path.normpath(str(parent))
    assert len(record.music_dirs) == 9





def test_numbered_multipart_parent_is_related_for_setlist_lookup_even_above_small_parent_limit(tmp_path):
    import tlo_setlist_file_selection as selection

    base = "Pink Floyd - Large Box"
    parent = tmp_path / base
    children = []
    for number in range(1, 14):
        child = parent / f"{base} ({number})"
        child.mkdir(parents=True, exist_ok=True)
        children.append(str(child))

    assert selection._all_child_dirs_related_release_parts(children) is True

def test_build419_documentation_contract():
    from pathlib import Path
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    doc = Document(root / "TLO_Inventory_Requirements_Working_v421.docx")
    req = "\n".join(p.text for p in doc.paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v421.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v421 (v1.4 Build 421)." in req
    assert "Parent/Parent (1)" in req
    assert "use ALBUM_NAME as the base Album value" in req
    assert "Build 419 revision:" in req
    assert "Version v1.4 Build 421" in manual
    assert "Parent/Parent (1)" in manual
    assert "ALBUM_NAME" in manual
