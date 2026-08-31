"""Build 399 cross-partition potential-duplicate behavior."""

__version__ = "v421"

from types import SimpleNamespace

import pytest

import tlo_inventory_update as U

pytestmark = pytest.mark.unit


def test_partition_relation_uses_drive_identity_before_volume_label():
    assert U._same_partition_relation("[NewLabel]E:\\Music", "[OldLabel] E:\\Archive\\Show") is True
    assert U._same_partition_relation("[Backup]E:\\Music", "[Other] F:\\Archive\\Show") is False
    assert U._same_partition_relation("[Backup]/mnt/e/Music", "[Other] E:\\Archive\\Show") is True


def test_partition_relation_falls_back_to_volume_labels_for_legacy_relative_rows():
    assert U._same_partition_relation("Backup-A", "[Backup-A] Artist 2001-02-03 Venue") is True
    assert U._same_partition_relation("Backup-A", "[Backup-B] Artist 2001-02-03 Venue") is False
    assert U._same_partition_relation("Backup-A", "Artist 2001-02-03 Venue") is None


def test_remote_only_requires_every_match_to_be_definitively_other_partition():
    remote = {"Show": "Artist 2001-02-03 Venue", "VolumePath": "[B] F:\\Archive\\Show"}
    local = {"Show": "Artist 2001-02-03 Venue", "VolumePath": "[A] E:\\Archive\\Show"}
    unknown = {"Show": "Artist 2001-02-03 Venue", "VolumePath": "Show"}

    assert U.potential_duplicate_matches_are_remote_only([remote], "[A]E:\\Music") is True
    assert U.potential_duplicate_matches_are_remote_only([remote, local], "[A]E:\\Music") is False
    assert U.potential_duplicate_matches_are_remote_only([remote, unknown], "[A]E:\\Music") is False


def test_pdup_number_starts_at_01_and_advances_past_highest_existing_marker():
    matches = [
        {"Show": "Artist 2001-02-03 Venue", "VolumePath": "[B] F:\\Show"},
        {"Show": "Artist 2001-02-03 Venue (pdup01)", "VolumePath": "[C] G:\\Show"},
        {"Show": "Artist 2001-02-03 Venue (pdup03)", "VolumePath": "[D] H:\\Show"},
    ]
    assert U._next_pdup_number([matches[0]]) == 1
    assert U._next_pdup_number(matches) == 4

    record = {"show_name": "Artist 2001-02-03 Venue", "parentheticals": "(set 2)"}
    marker = U._apply_pdup_marker(record, 4)
    assert marker == "(pdup04)"
    assert record["show_name"] == "Artist 2001-02-03 Venue (set 2) (pdup04)"
    assert record["parentheticals"] == "(set 2) (pdup04)"


def test_exact_compliant_show_match_recognizes_existing_pdup_suffix(tmp_path):
    U.write_bootlist(
        str(tmp_path),
        [{"Show": "Artist - Album (pdup01)", "VolumePath": "[B] F:\\Artist - Album"}],
    )
    rows = U._bootlist_show_name_matches(str(tmp_path), "Artist - Album")
    assert [row["Show"] for row in rows] == ["Artist - Album (pdup01)"]


def _fake_record():
    return SimpleNamespace(
        artist="Artist",
        date="2001-02-03",
        venue="Venue",
        location="City, ST",
        parentheticals="",
        show_name="Artist 2001-02-03 Venue City, ST",
    )


def _fake_record_dict(folder):
    return {
        "artist": "Artist",
        "date": "2001-02-03",
        "venue": "Venue",
        "location": "City, ST",
        "parentheticals": "",
        "show_name": "Artist 2001-02-03 Venue City, ST",
        "main_dir_path": str(folder),
        "music_dirs_json": "[]",
        "setlist_files_json": "[]",
    }


def test_process_new_shows_stages_remote_match_as_pdup_instead_of_dups(tmp_path, monkeypatch):
    ready = tmp_path / "readyForXfer"
    staged = tmp_path / "staged"
    dups = tmp_path / "dups"
    folder = ready / "Incoming"
    folder.mkdir(parents=True)
    staged.mkdir(); dups.mkdir()
    U.write_bootlist(
        str(tmp_path),
        [{"Show": "Artist 2001-02-03 Venue City ST", "VolumePath": "[Remote] F:\\Archive\\Old"}],
    )
    config = SimpleNamespace(TLOHome=str(tmp_path), compliant=False, rename_compliantly=False)

    monkeypatch.setattr(U, "prepare_updater_config", lambda config: config)
    monkeypatch.setattr(U, "ensure_updater_directories", lambda _home: {"ready": str(ready), "staged": str(staged), "dups": str(dups)})
    monkeypatch.setattr(U, "load_artist_matcher", lambda _config: object())
    monkeypatch.setattr(U, "_iter_top_level_dirs", lambda _root: [str(folder)])
    monkeypatch.setattr(U, "identify_folder", lambda *_args, **_kwargs: _fake_record())
    monkeypatch.setattr(U, "find_potential_duplicate_rows_for_folder", lambda *_args, **_kwargs: U.read_bootlist(str(tmp_path)))
    monkeypatch.setattr(U, "_record_dict_for_new_folder", lambda *_args, **_kwargs: _fake_record_dict(folder))
    monkeypatch.setattr(U, "create_or_replace_generated_setlist", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(U, "_tag_add_shows_folder_in_place", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(U, "_log_add_shows_metadata", lambda *_args, **_kwargs: None)

    result = U.process_new_shows(config, "[Current]E:\\Music", check_duplicates=True)

    assert result["duplicates"] == 0
    assert result["potential_duplicates_unavailable"] == 1
    assert result["staged"] == 1
    rows = U.read_bootlist(str(tmp_path))
    assert any(row["Show"].endswith("(pdup01)") and "E:\\Music" in row["VolumePath"] for row in rows)
    assert not any(dups.iterdir())


def test_process_new_shows_keeps_same_partition_match_in_existing_dups_workflow(tmp_path, monkeypatch):
    ready = tmp_path / "readyForXfer"
    staged = tmp_path / "staged"
    dups = tmp_path / "dups"
    folder = ready / "Incoming"
    folder.mkdir(parents=True)
    staged.mkdir(); dups.mkdir()
    existing = {"Show": "Artist 2001-02-03 Venue City ST", "VolumePath": "[OldLabel] E:\\Archive\\Old"}
    U.write_bootlist(str(tmp_path), [existing])
    config = SimpleNamespace(TLOHome=str(tmp_path), compliant=False, rename_compliantly=False)

    monkeypatch.setattr(U, "prepare_updater_config", lambda config: config)
    monkeypatch.setattr(U, "ensure_updater_directories", lambda _home: {"ready": str(ready), "staged": str(staged), "dups": str(dups)})
    monkeypatch.setattr(U, "load_artist_matcher", lambda _config: object())
    monkeypatch.setattr(U, "_iter_top_level_dirs", lambda _root: [str(folder)])
    monkeypatch.setattr(U, "identify_folder", lambda *_args, **_kwargs: _fake_record())
    monkeypatch.setattr(U, "find_potential_duplicate_rows_for_folder", lambda *_args, **_kwargs: [existing])
    monkeypatch.setattr(U, "_record_dict_for_new_folder", lambda *_args, **_kwargs: _fake_record_dict(folder))
    monkeypatch.setattr(U, "_log_add_shows_metadata", lambda *_args, **_kwargs: None)

    result = U.process_new_shows(config, "[Current]E:\\Music", check_duplicates=True)

    assert result["duplicates"] == 1
    assert result["potential_duplicates_unavailable"] == 0
    assert result["staged"] == 0
    assert any(dups.iterdir())
    assert U.read_bootlist(str(tmp_path)) == [existing]
