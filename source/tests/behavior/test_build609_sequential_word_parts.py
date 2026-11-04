"""Build 609: one/two under one dated concert must not publish a copy1."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
import tlo_tag_lib as tagging

pytestmark = pytest.mark.behavior


def _recording(tmp_path: Path, *, track_numbers=((1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)),
               parent_name="RTF Paris 7 March 76 flac16", shared_info=True,
               child_names=("one", "two")):
    root = tmp_path / "x" / "R" / "Return to Forever" / "1976" / parent_name
    tracks = []
    for child, numbers in zip(child_names, track_numbers):
        part = root / child
        part.mkdir(parents=True)
        for number in numbers:
            filename = f"{number:02d} " + (
                "the romantic warrior" if number == 1 else "band introductions" if number == 7 else f"song {number}"
            ) + ".flac"
            f = part / filename
            f.write_bytes(f"fixture-data-{number}".encode("ascii"))
            tracks.append(f)
    if shared_info:
        (root / "info.txt").write_text(
            "Return to Forever\nOlympia\nParis, France\n7 March 1976\n"
            + "\n".join(f"{number:02d}. Song {number}" for number in range(1, 13)) + "\n",
            encoding="utf-8",
        )
    return root, tracks


def _groups(start: Path, tracks: list[Path], config=None):
    log = start.parent / "complete.txt"
    log.write_text("# complete paths\nSEARCH_PATH: " + str(start) + "\n" +
                   "\n".join(str(track) for track in tracks) + "\n", encoding="utf-8")
    if config is None:
        config = SimpleNamespace(compliant=False)
    config.logs = SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log)))
    config.performance_mode = "balanced"
    return phase._build_groups_from_search_path(config, str(start))


def test_real_world_return_to_forever_parts_form_one_group(tmp_path):
    show, files = _recording(tmp_path)
    # Run against the ancestor search root as in the supplied inventory log.
    groups = _groups(tmp_path / "x", files)
    assert len(groups) == 1
    group = groups[0]
    assert group["aggregation_reason"] == "sequential_word_numbered_parts"
    assert group["main_dir_path"] == str(show)
    assert group["setlist_file"] == str(show / "info.txt")
    assert group["music_file_count"] == 12
    assert group["music_dirs"] == [str(show / "one"), str(show / "two")]
    ordered = tagging._rescan_group_audio_files(group)
    assert [Path(path).name for path in ordered] == [Path(path).name for path in files]


def test_aggregated_show_metadata_matches_two_individual_log_records(tmp_path):
    from tlo_artist_db import ArtistMatcher

    show, files = _recording(tmp_path)
    group = _groups(tmp_path / "x", files)[0]
    group["group_number"] = 3
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"return to forever": {"Return to Forever"}, "rtf": {"Return to Forever"}}
    matcher.master_aliases = {"Return to Forever": ["Return to Forever", "RTF"]}
    matcher.master_norms = {"Return to Forever": {"returntoforever", "rtf"}}
    config = SimpleNamespace(
        compliant=False, current_volume_label="", current_slam="", as_is_artist_name=False,
        compliant_artist_mode="master", etree_lookup=False, setlistfm_lookup=False,
        thorough_setlist_matching=False, tlo_dbs_dir=str(tmp_path),
        venue_reference_db_file=str(tmp_path / "venues.txt"), debug=False,
    )
    record, _dates, unresolved = phase._extract_metadata_for_group(config, group, matcher)
    assert not unresolved and not record.conflicts
    assert record.artist == "Return to Forever"
    assert record.date == "1976-03-07"
    assert record.venue == "Olympia"
    assert record.location == "Paris, France"
    assert record.show_name == "Return to Forever 1976-03-07 Olympia Paris, France"
    assert record.music_file_count == 12


def test_starting_at_exact_dated_show_root_also_merges(tmp_path):
    show, files = _recording(tmp_path)
    groups = _groups(show, files)
    assert len(groups) == 1 and groups[0]["main_dir_path"] == str(show)


def test_merged_recording_moves_once_with_all_files_and_no_copy_suffix(tmp_path):
    show, files = _recording(tmp_path)
    group = _groups(tmp_path / "x", files)[0]
    destination = tmp_path / "update"
    destination.mkdir()
    name = "Return to Forever 1976-03-07 Olympia Paris, France"
    config = SimpleNamespace(tag_copy_and_delete_path=str(destination), rename_compliantly=True)
    record = SimpleNamespace(
        show_name=name, parentheticals="", main_dir_name=show.name,
        main_dir_path=str(show), setlist_file=group["setlist_file"],
        music_dirs=group["music_dirs"], setlist_files=group["setlist_files"],
        original_main_dir_path="",
    )
    updated_group, updated_record = tagging.prepare_inventory_copy_delete_target(config, group, record)
    published = destination / name
    assert published.is_dir() and not show.exists()
    assert updated_group["main_dir_path"] == str(published)
    assert updated_record.main_dir_path == str(published)
    assert updated_record.original_main_dir_path == str(show)
    assert (published / "info.txt").exists()
    assert len(list(published.rglob("*.flac"))) == 12
    assert not any("(copy" in item.name or "(alt" in item.name for item in destination.iterdir())
    for file in files:
        copied = published / file.relative_to(show)
        assert copied.read_bytes() == f"fixture-data-{int(file.name[:2])}".encode("ascii")


@pytest.mark.parametrize("numbers", [
    ((1, 2), (1, 2)),        # alternative takes, repeated tracks
    ((1, 2), (4, 5)),        # discontinuous track sequence
    ((2, 3), (4, 5)),        # not the beginning of the performance
    ((1,), (2,)),           # insufficient evidence
])
def test_unknown_or_duplicate_sequences_remain_separate(tmp_path, numbers):
    _show, files = _recording(tmp_path, track_numbers=numbers)
    groups = _groups(tmp_path / "x", files)
    assert len(groups) == 2


def test_shared_setlist_and_date_are_required(tmp_path):
    _show, files = _recording(tmp_path, shared_info=False)
    assert len(_groups(tmp_path / "x", files)) == 2
    other_show, other_files = _recording(tmp_path / "undated", parent_name="Recording without date")
    assert len(_groups(tmp_path / "undated" / "x", other_files)) == 2
    assert other_show.exists()


def test_different_artist_sibling_and_third_nonpart_keep_shows_separate(tmp_path, monkeypatch):
    show, files = _recording(tmp_path)
    monkeypatch.setattr(phase, "collect_group_flac_tag_info", lambda samples, max_files=2: {
        "flac_tag_artist_values": ["Return to Forever" if "one" in samples[0] else "Opening Act"],
        "flac_tag_albumartist_values": [],
    })
    assert len(_groups(tmp_path / "x", files)) == 2
    monkeypatch.undo()
    extra = show / "Opening Artist"
    extra.mkdir()
    extra_file = extra / "01 Another Song.flac"
    extra_file.write_bytes(b"other")
    assert len(_groups(tmp_path / "x", files + [extra_file])) == 3


def test_compliant_mode_still_keeps_individual_music_directories(tmp_path):
    _show, files = _recording(tmp_path)
    config = SimpleNamespace(compliant=True)
    groups = _groups(tmp_path / "x", files, config)
    assert len(groups) == 2


def test_missing_unreadable_parent_directories_do_not_crash(tmp_path, monkeypatch):
    show, files = _recording(tmp_path)
    real_listdir = phase.os.listdir

    def denied(path):
        if os.fspath(path) == str(show / "two"):
            raise PermissionError("access denied")
        return real_listdir(path)

    monkeypatch.setattr(phase.os, "listdir", denied)
    groups = _groups(tmp_path / "x", files)
    assert len(groups) == 2
