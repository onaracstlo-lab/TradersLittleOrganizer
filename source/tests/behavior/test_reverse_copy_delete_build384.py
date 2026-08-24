from pathlib import Path
import os

import pytest

import tlo_reverse_copy_delete as R


def _write_log(tlo_home: Path, name: str, *, search_path: Path, old_destination: Path, mappings):
    logs = tlo_home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    body = [
        f"# tagSuccessLog for search path: [OLDLABEL] {search_path}\n",
        f"SEARCH_PATH: [OLDLABEL] {search_path}\n",
        "TAG_DURING_INVENTORY: mode=copy-and-delete | convert shn=no | rename compliantly=yes | "
        f"copy destination={old_destination}\n",
        f"TAG_COPY_AND_DELETE: enabled | destination={old_destination}\n",
    ]
    for source, destination in mappings:
        body.append(f"TAG_COPY_DELETE_MOVE: {source} -> {destination}\n")
    path = logs / name
    path.write_text("".join(body), encoding="utf-8")
    return path


def test_full_original_path_can_replace_old_drive_and_volume_label(tmp_path):
    tlo_home = tmp_path / "home"
    old_search = tmp_path / "old-drive" / "somePath"
    current_search = tmp_path / "new-drive" / "somePath"
    old_destination = tmp_path / "old-destination"
    current_destination = tmp_path / "current-destination"
    current_search.mkdir(parents=True)
    current_destination.mkdir()

    logged_source = old_search / "F" / "Friedman, Kinky" / "Kinky Friedman 1980s Lone Star Cafe NYC"
    logged_destination = old_destination / "Kinky Friedman xxxx-xx-xx Lone Star Cafe New York, NY"
    actual_destination = current_destination / logged_destination.name
    actual_destination.mkdir()
    (actual_destination / "song.flac").write_bytes(b"tagged")
    _write_log(
        tlo_home,
        "tagsA.txt",
        search_path=old_search,
        old_destination=old_destination,
        mappings=[(logged_source, logged_destination)],
    )

    selection = R.prepare_reverse_selection(
        tlo_home=str(tlo_home),
        original_partition=str(current_search),
        moved_to=str(current_destination),
    )

    expected = current_search / "F" / "Friedman, Kinky" / "Kinky Friedman 1980s Lone Star Cafe NYC"
    assert selection.log_path.endswith("tagsA.txt")
    assert selection.records[0].original_path == os.path.normpath(str(expected))
    assert selection.records[0].current_path == os.path.normpath(str(actual_destination))


def test_changed_current_volume_label_does_not_need_to_match_historical_log_label(tmp_path, monkeypatch):
    tlo_home = tmp_path / "home"
    old_volume = tmp_path / "old-volume"
    current_volume = tmp_path / "current-volume"
    old_destination = tmp_path / "old-destination"
    moved = tmp_path / "moved"
    current_volume.mkdir()
    moved.mkdir()

    logged_source = old_volume / "Music" / "Artist" / "Artist 1987-01-17 Old Venue"
    logged_destination = old_destination / "Artist 1987-01-17 New Venue City ST"
    actual = moved / logged_destination.name
    actual.mkdir()
    _write_log(
        tlo_home,
        "tagsB.txt",
        search_path=old_volume / "Music",
        old_destination=old_destination,
        mappings=[(logged_source, logged_destination)],
    )

    monkeypatch.setattr(
        R,
        "_mounted_roots_for_label",
        lambda label: [str(current_volume)] if str(label).casefold() == "newlabel" else [],
    )
    monkeypatch.setattr(R, "_logged_volume_root", lambda path: str(old_volume) if str(path).startswith(str(old_volume)) else "")

    selection = R.prepare_reverse_selection(
        tlo_home=str(tlo_home), original_partition="NEWLABEL", moved_to=str(moved)
    )
    assert selection.log_path.endswith("tagsB.txt")
    assert selection.records[0].original_path == os.path.normpath(
        str(current_volume / "Music" / "Artist" / "Artist 1987-01-17 Old Venue")
    )


def test_log_selection_uses_artist_date_with_last_first_normalization(tmp_path):
    tlo_home = tmp_path / "home"
    current_original = tmp_path / "current" / "unknown-root"
    current_original.mkdir(parents=True)
    moved = tmp_path / "moved"
    moved.mkdir()
    old_dest = tmp_path / "old-dest"

    source_a = tmp_path / "old-a" / "archive" / "Friedman, Kinky 1987-01-17 Old"
    dest_a = old_dest / "Kinky Friedman 1987-01-17 Lone Star Cafe New York, NY"
    _write_log(tlo_home, "tagsA.txt", search_path=tmp_path / "old-a" / "archive", old_destination=old_dest, mappings=[(source_a, dest_a)])

    source_b = tmp_path / "old-b" / "other" / "Other Artist 1987-01-17 Old"
    dest_b = old_dest / "Other Artist 1987-01-17 Other Venue"
    _write_log(tlo_home, "tagsB.txt", search_path=tmp_path / "old-b" / "other", old_destination=old_dest, mappings=[(source_b, dest_b)])

    # The folder was manually renamed after TLO processing, so there is no exact
    # destination match. Artist/date evidence may identify the log, but must not
    # later be used to guess that this is the folder to move.
    manually_changed = moved / "Friedman, Kinky 1987-01-17 Lone Star Cafe New York, NY"
    manually_changed.mkdir()

    selection = R.prepare_reverse_selection(
        tlo_home=str(tlo_home), original_partition=str(current_original), moved_to=str(moved)
    )
    assert selection.log_path.endswith("tagsA.txt")
    assert "artist_date_matches=1" in selection.evidence

    result = R.reverse_copy_delete_and_rename(selection=selection)
    assert result.restored == 0
    assert result.skipped_unmatched == 1
    assert manually_changed.is_dir()


def test_log_selection_treats_the_suffix_as_same_artist(tmp_path):
    tlo_home = tmp_path / "home"
    current_original = tmp_path / "current" / "unknown-root"
    current_original.mkdir(parents=True)
    moved = tmp_path / "moved"
    moved.mkdir()
    old_dest = tmp_path / "old-dest"

    source = tmp_path / "old" / "shows" / "Doors, The 1970-01-17 Old"
    destination = old_dest / "The Doors 1970-01-17 Felt Forum New York, NY"
    _write_log(tlo_home, "tagsDoors.txt", search_path=tmp_path / "old" / "shows", old_destination=old_dest, mappings=[(source, destination)])
    (moved / "Doors, The 1970-01-17 Felt Forum New York, NY").mkdir()

    selection = R.prepare_reverse_selection(
        tlo_home=str(tlo_home), original_partition=str(current_original), moved_to=str(moved)
    )
    assert selection.log_path.endswith("tagsDoors.txt")
    assert "artist_date_matches=1" in selection.evidence


def test_original_path_evidence_selects_one_log_and_all_records_from_only_that_log(tmp_path):
    tlo_home = tmp_path / "home"
    moved = tmp_path / "moved"
    moved.mkdir()
    current_a = tmp_path / "new-drive" / "A"
    current_a.mkdir(parents=True)
    old_dest = tmp_path / "old-dest"

    old_a = tmp_path / "old-drive" / "A"
    a1 = old_a / "Artist One 1980-01-01 Old"
    a2 = old_a / "Artist Two 1981-01-01 Old"
    da1 = old_dest / "Artist One 1980-01-01 Venue"
    da2 = old_dest / "Artist Two 1981-01-01 Venue"
    _write_log(tlo_home, "tagsA.txt", search_path=old_a, old_destination=old_dest, mappings=[(a1, da1), (a2, da2)])

    old_b = tmp_path / "old-drive" / "B"
    b1 = old_b / "Artist Three 1982-01-01 Old"
    db1 = old_dest / "Artist Three 1982-01-01 Venue"
    _write_log(tlo_home, "tagsB.txt", search_path=old_b, old_destination=old_dest, mappings=[(b1, db1)])

    # Put all three destination folders in one holding directory. The supplied
    # original full path must select tagsA once; tagsB is not revisited.
    for path in (da1, da2, db1):
        (moved / path.name).mkdir()

    selection = R.prepare_reverse_selection(
        tlo_home=str(tlo_home), original_partition=str(current_a), moved_to=str(moved)
    )
    assert selection.log_path.endswith("tagsA.txt")
    assert len(selection.records) == 2
    assert all(record.log_path.endswith("tagsA.txt") for record in selection.records)


def test_execution_with_prepared_selection_does_not_search_logs_again(tmp_path, monkeypatch):
    tlo_home = tmp_path / "home"
    original = tmp_path / "original"
    moved = tmp_path / "moved"
    original.mkdir()
    moved.mkdir()
    old_dest = tmp_path / "old-dest"
    source = original / "Old Name"
    logged_destination = old_dest / "Artist 1987-01-17 Venue"
    current = moved / logged_destination.name
    current.mkdir()
    (current / "song.flac").write_bytes(b"abc")
    _write_log(tlo_home, "tags1.txt", search_path=original, old_destination=old_dest, mappings=[(source, logged_destination)])

    selection = R.prepare_reverse_selection(
        tlo_home=str(tlo_home), original_partition=str(original), moved_to=str(moved)
    )
    monkeypatch.setattr(R, "_candidate_logs", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("searched twice")))

    result = R.reverse_copy_delete_and_rename(selection=selection)
    assert result.restored == 1
    assert (source / "song.flac").read_bytes() == b"abc"
