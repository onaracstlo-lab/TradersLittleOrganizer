import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
import tlo_sibling_collections as sibling
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior


def _audio(folder: Path, names=("01 - Song One.flac", "02 - Song Two.flac")):
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"not-real-audio")


def _setlist(folder: Path, titles):
    lines = [f"{index:02d}. {title}" for index, title in enumerate(titles, start=1)]
    (folder / "setlist.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _complete_log(root: Path) -> Path:
    log = root / "comp.log"
    rows = [f"# completePathLog for search path: {root}", f"SEARCH_PATH: {root}"]
    rows.extend(str(audio) for audio in sorted(root.rglob("*.flac")))
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return log


def _phase_config(log: Path):
    return SimpleNamespace(
        compliant=False,
        logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))),
        performance_mode="balanced",
    )


def test_disc_siblings_are_moved_under_common_parent_and_inventoried_once(tmp_path):
    root = tmp_path / "boots"
    disc1 = root / "Frankie Valli - Greatest D1"
    disc2 = root / "Frankie Valli - Greatest D2"
    unrelated = root / "Other Artist - Other Album"
    _audio(disc1, ("01 - First.flac", "02 - Second.flac"))
    _audio(disc2, ("01 - Third.flac", "02 - Fourth.flac"))
    _audio(unrelated, ("01 - Elsewhere.flac",))
    _setlist(disc1, ("First", "Second"))
    _setlist(disc2, ("Third", "Fourth"))
    log = _complete_log(root)

    results = sibling.consolidate_sibling_collections(str(root), str(log))
    parent = root / "Frankie Valli - Greatest"

    assert len(results) == 1
    assert (parent / disc1.name).is_dir() and (parent / disc2.name).is_dir()
    assert unrelated.is_dir() and not disc1.exists() and not disc2.exists()
    info = (parent / "info.txt").read_text(encoding="utf-8")
    assert info.index("Disc 1") < info.index("First") < info.index("Disc 2") < info.index("Third")
    groups = phase._build_groups_from_search_path(_phase_config(log), str(root))
    collection = [group for group in groups if group["main_dir_path"] == str(parent)]
    assert len(collection) == 1 and collection[0]["music_file_count"] == 4
    assert collection[0]["setlist_file"] == str(parent / "info.txt")


def test_collection_track_order_finishes_each_disc_before_the_next(tmp_path):
    root = tmp_path / "boots"
    disc1 = root / "Frankie Valli - Greatest D1"
    disc2 = root / "Frankie Valli - Greatest D2"
    _audio(disc1, ("01.flac", "02.flac")); _audio(disc2, ("01.flac", "02.flac"))
    _setlist(disc1, ("One", "Two")); _setlist(disc2, ("Three", "Four"))
    log = _complete_log(root)
    sibling.consolidate_sibling_collections(str(root), str(log))
    group = phase._build_groups_from_search_path(_phase_config(log), str(root))[0]
    ordered = [os.path.relpath(path, group["main_dir_path"]) for path in taglib._rescan_group_audio_files(group)]
    assert ordered == [
        os.path.join(disc1.name, "01.flac"), os.path.join(disc1.name, "02.flac"),
        os.path.join(disc2.name, "01.flac"), os.path.join(disc2.name, "02.flac"),
    ]
    assert [taglib.format_tag_track_number(number, 100) for number in (1, 99, 100)] == ["001", "099", "100"]


def test_concatenated_parent_setlist_tags_one_continuous_sequence(tmp_path, monkeypatch):
    root = tmp_path / "boots"
    disc1 = root / "Artist - Anthology CD1"; disc2 = root / "Artist - Anthology CD2"
    _audio(disc1, ("01.flac", "02.flac")); _audio(disc2, ("01.flac", "02.flac"))
    _setlist(disc1, ("First", "Second")); _setlist(disc2, ("Third", "Fourth"))
    log = _complete_log(root)
    sibling.consolidate_sibling_collections(str(root), str(log))
    group = phase._build_groups_from_search_path(_phase_config(log), str(root))[0]
    writes = []
    monkeypatch.setattr(taglib, "write_audio_tags", lambda path, artist, album, track, title, total_tracks=0: writes.append((track, title, total_tracks)))
    config = SimpleNamespace(compliant=False, artist_in_album=False, convert_shn=False, thorough_setlist_matching=False, etree_db=False, setlist_fm=False)
    record = SimpleNamespace(artist="Artist", album_name="Anthology", date="", venue="", location="", parentheticals="", show_name="Artist - Anthology", setlist_file=group["setlist_file"])
    stats = taglib.tag_group_with_record(config, group, record, allow_unknown_metadata=False, fallback_to_filenames_on_track_problem=True)
    assert stats["tagged"] == 4
    assert [row[0] for row in writes] == ["01", "02", "03", "04"]
    assert [row[1] for row in writes] == ["First", "Second", "Third", "Fourth"]
    assert all(row[2] == 4 for row in writes)


def test_distinct_alt_content_is_consolidated_and_ordered(tmp_path):
    root = tmp_path / "boots"
    base = root / "Pink Floyd - Early Flights"
    alt1 = root / "Pink Floyd - Early Flights (alt1)"
    alt2 = root / "Pink Floyd - Early Flights (alt2)"
    for folder, songs in ((base, ("Astronomy", "Lucifer")), (alt1, ("Embryo", "Green")), (alt2, ("Cymbaline", "Echoes"))):
        _audio(folder, tuple(f"{i:02d} - {song}.flac" for i, song in enumerate(songs, 1))); _setlist(folder, songs)
    log = _complete_log(root)
    assert len(sibling.consolidate_sibling_collections(str(root), str(log))) == 1
    assert (base / base.name).is_dir() and (base / alt1.name).is_dir() and (base / alt2.name).is_dir()
    groups = phase._build_groups_from_search_path(_phase_config(log), str(root))
    assert len(groups) == 1 and groups[0]["aggregation_reason"] == "consolidated_sibling_collection"
    ordered = [os.path.relpath(path, base) for path in taglib._rescan_group_audio_files(groups[0])]
    assert ordered[0].startswith(base.name + os.sep) and ordered[2].startswith(alt1.name + os.sep) and ordered[4].startswith(alt2.name + os.sep)


def test_same_or_shifted_alt_song_lists_remain_separate(tmp_path):
    root = tmp_path / "boots"; base = root / "Pink Floyd - Echoes Compilation"; alt1 = root / "Pink Floyd - Echoes Compilation (alt1)"
    _audio(base, ("01 - Intro.flac", "02 - Echoes.flac", "03 - Time.flac", "04 - Money.flac"))
    _audio(alt1, ("01 - Echoes.flac", "02 - Time.flac", "03 - Money.flac", "04 - Encore.flac"))
    _setlist(base, ("Intro", "Echoes", "Time", "Money")); _setlist(alt1, ("Echoes", "Time", "Money", "Encore"))
    log = _complete_log(root)
    assert sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log))) == []
    assert sibling.consolidate_sibling_collections(str(root), str(log)) == []


def test_alt_without_enough_title_evidence_fails_closed(tmp_path):
    root = tmp_path / "boots"; base = root / "Pink Floyd - Mystery"; alt1 = root / "Pink Floyd - Mystery (alt1)"
    _audio(base, ("01.flac",)); _audio(alt1, ("01.flac",)); log = _complete_log(root)
    assert sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log))) == []


@pytest.mark.parametrize("base_name", ["Artist - 1980's Collection", "Artist - 1978-1982 Collection", "Artist - Undated Collection"])
def test_year_span_decade_and_undated_collection_names_are_eligible(tmp_path, base_name):
    root = tmp_path / "boots"; _audio(root / f"{base_name} D1", ("01 - First.flac",)); _audio(root / f"{base_name} D2", ("01 - Second.flac",))
    log = _complete_log(root); plans = sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log)))
    assert len(plans) == 1 and plans[0].base_name == base_name


def test_specific_date_release_parts_are_not_physically_consolidated(tmp_path):
    root = tmp_path / "boots"; _audio(root / "Artist - 1990-07-10 Venue D1", ("01 - First.flac",)); _audio(root / "Artist - 1990-07-10 Venue D2", ("01 - Second.flac",)); log = _complete_log(root)
    assert sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log))) == []


def test_cross_partition_family_is_rejected(tmp_path, monkeypatch):
    root = tmp_path / "boots"; _audio(root / "Artist - Collection D1", ("01 - First.flac",)); _audio(root / "Artist - Collection D2", ("01 - Second.flac",)); log = _complete_log(root)
    monkeypatch.setattr(sibling, "_same_filesystem", lambda _paths: False)
    assert sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log))) == []


def test_existing_unrelated_destination_blocks_collection(tmp_path):
    root = tmp_path / "boots"; _audio(root / "Artist - Greatest D1", ("01 - First.flac",)); _audio(root / "Artist - Greatest D2", ("01 - Second.flac",)); (root / "Artist - Greatest").mkdir(parents=True); log = _complete_log(root)
    assert sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log))) == []


def test_failed_log_commit_rolls_back_every_moved_folder(tmp_path, monkeypatch):
    root = tmp_path / "boots"; disc1 = root / "Artist - Collection D1"; disc2 = root / "Artist - Collection D2"
    _audio(disc1, ("01 - First.flac",)); _audio(disc2, ("01 - Second.flac",)); log = _complete_log(root)
    monkeypatch.setattr(sibling, "_rewrite_complete_path_log", lambda *_args: (_ for _ in ()).throw(OSError("boom")))
    assert sibling.consolidate_sibling_collections(str(root), str(log)) == []
    assert disc1.is_dir() and disc2.is_dir() and not (root / "Artist - Collection").exists()


def test_interrupted_journal_is_recovered_before_next_walk(tmp_path):
    root = tmp_path / "boots"; original1 = root / "Artist - Collection D1"; original2 = root / "Artist - Collection D2"
    _audio(original1, ("01 - First.flac",)); _audio(original2, ("01 - Second.flac",))
    temp = root / f"{sibling.TEMP_PREFIX}interrupted"; temp.mkdir(); os.rename(original1, temp / original1.name)
    payload = {"schema": 1, "temporary_path": str(temp), "final_path": str(root / "Artist - Collection"), "generated_info": "info.txt", "members": [{"original": str(original1), "child_name": original1.name}, {"original": str(original2), "child_name": original2.name}]}
    (temp / sibling.JOURNAL_NAME).write_text(json.dumps(payload), encoding="utf-8")
    assert sibling.recover_interrupted_sibling_consolidations(str(root)) == 1
    assert original1.is_dir() and original2.is_dir() and not temp.exists()


def test_unrecoverable_tlo_temporary_folder_blocks_inventory(tmp_path):
    root = tmp_path / "boots"; temp = root / f"{sibling.TEMP_PREFIX}broken"; temp.mkdir(parents=True); (temp / sibling.JOURNAL_NAME).write_text("not json", encoding="utf-8")
    with pytest.raises(sibling.SiblingCollectionRecoveryError):
        sibling.recover_interrupted_sibling_consolidations(str(root))


def test_dry_run_guard_never_recovers_or_moves_interrupted_collection(tmp_path):
    root = tmp_path / "boots"; temp = root / f"{sibling.TEMP_PREFIX}paused"
    _audio(temp / "Artist - Collection D1", ("01 - First.flac",))
    (temp / sibling.JOURNAL_NAME).write_text("{}", encoding="utf-8")

    with pytest.raises(sibling.SiblingCollectionRecoveryError):
        sibling.assert_no_interrupted_sibling_consolidations(str(root))

    assert temp.is_dir() and (temp / "Artist - Collection D1").is_dir()


def test_nested_media_containers_stay_in_one_collection_and_disc_order(tmp_path):
    root = tmp_path / "boots"; disc1 = root / "Artist - Deep Anthology D1"; disc2 = root / "Artist - Deep Anthology D2"
    _audio(disc1 / "FLAC", ("01.flac", "02.flac")); _audio(disc2 / "FLAC", ("01.flac", "02.flac")); _setlist(disc1, ("One", "Two")); _setlist(disc2, ("Three", "Four")); log = _complete_log(root)
    sibling.consolidate_sibling_collections(str(root), str(log)); parent = root / "Artist - Deep Anthology"; groups = phase._build_groups_from_search_path(_phase_config(log), str(root))
    assert len(groups) == 1 and groups[0]["main_dir_path"] == str(parent)
    assert [os.path.relpath(path, parent) for path in taglib._rescan_group_audio_files(groups[0])] == [os.path.join(disc1.name, "FLAC", "01.flac"), os.path.join(disc1.name, "FLAC", "02.flac"), os.path.join(disc2.name, "FLAC", "01.flac"), os.path.join(disc2.name, "FLAC", "02.flac")]


def test_all_usable_child_setlists_are_concatenated_alphabetically(tmp_path):
    root = tmp_path / "boots"; disc1 = root / "Artist - Archive CD1"; disc2 = root / "Artist - Archive CD2"
    _audio(disc1, ("01 - One.flac",)); _audio(disc2, ("01 - Three.flac",)); (disc1 / "b-notes.txt").write_text("01. Two\n", encoding="utf-8"); (disc1 / "a-setlist.txt").write_text("01. One\n", encoding="utf-8"); (disc2 / "setlist.txt").write_text("01. Three\n", encoding="utf-8"); log = _complete_log(root)
    sibling.consolidate_sibling_collections(str(root), str(log)); info = (root / "Artist - Archive" / "info.txt").read_text(encoding="utf-8")
    assert info.index("/ a-setlist.txt]") < info.index("/ b-notes.txt]") < info.index("/ setlist.txt]")
