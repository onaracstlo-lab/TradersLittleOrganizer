import pytest

pytestmark = pytest.mark.behavior

import os
from types import SimpleNamespace

import tlo_folder_rename as folder_rename
import tlo_inventory_update as update
import tlo_tag_lib as tag


def test_folder_name_write_needed_detects_capitalization_only_change(tmp_path):
    source = tmp_path / "dave van ronk 1978-02-17 Main Point Bryn Mawr, PA"
    source.mkdir()

    assert folder_rename.folder_name_write_needed(
        str(source), "Dave Van Ronk 1978-02-17 Main Point Bryn Mawr, PA"
    ) is True
    assert folder_rename.folder_name_write_needed(str(source), source.name) is False


def test_exact_case_rename_uses_temporary_hop_when_two_spellings_are_same_entry(tmp_path, monkeypatch):
    source = tmp_path / "dave van ronk 1978-02-17 Main Point Bryn Mawr, PA"
    source.mkdir()
    destination = tmp_path / "Dave Van Ronk 1978-02-17 Main Point Bryn Mawr, PA"
    real_same_entry = folder_rename.same_existing_entry
    real_rename = folder_rename.os.rename
    calls = []

    monkeypatch.setattr(folder_rename, "same_existing_entry", lambda left, right: True)

    def recording_rename(left, right):
        calls.append((os.path.normpath(left), os.path.normpath(right)))
        real_rename(left, right)

    monkeypatch.setattr(folder_rename.os, "rename", recording_rename)

    result = folder_rename.rename_folder_exact_case(str(source), str(destination))

    assert result == os.path.normpath(str(destination))
    assert destination.is_dir()
    assert not source.exists()
    assert len(calls) == 2
    assert ".tlo-case-rename-" in os.path.basename(calls[0][1])
    assert calls[1][1] == os.path.normpath(str(destination))
    monkeypatch.setattr(folder_rename, "same_existing_entry", real_same_entry)


def test_inventory_tag_rename_applies_canonical_artist_capitalization(tmp_path):
    source = tmp_path / "dave van ronk 1978-02-17 Main Point Bryn Mawr, PA"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"fake")
    setlist = source / "info.txt"
    setlist.write_text("01 Song\n", encoding="utf-8")

    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "setlist_file": str(setlist),
        "setlist_files": [str(setlist)],
    }
    record = SimpleNamespace(
        show_name="Dave Van Ronk 1978-02-17 Main Point Bryn Mawr, PA",
        parentheticals="",
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file=str(setlist),
        music_dirs=[str(source)],
        setlist_files=[str(setlist)],
        original_main_dir_path="",
    )
    config = SimpleNamespace(rename_compliantly=True, tag_copy_during_inventory=False)
    messages = []

    new_group, new_record = tag.prepare_inventory_tagging_target(config, group, record, emit=messages.append)
    expected = tmp_path / "Dave Van Ronk 1978-02-17 Main Point Bryn Mawr, PA"

    assert expected.is_dir()
    assert not source.exists()
    assert new_group["main_dir_path"] == os.path.normpath(str(expected))
    assert new_record.main_dir_path == os.path.normpath(str(expected))
    assert any(message.startswith("RENAME_COMPLIANTLY:") for message in messages)
    assert not any(message.startswith("RENAME_COMPLIANTLY_UNCHANGED:") for message in messages)


def test_add_shows_rename_applies_canonical_artist_capitalization(tmp_path):
    source = tmp_path / "dave van ronk 1978-02-17 Main Point Bryn Mawr, PA"
    source.mkdir()
    info = source / "info.txt"
    info.write_text("01 Song\n", encoding="utf-8")
    record = {
        "show_name": "Dave Van Ronk 1978-02-17 Main Point Bryn Mawr, PA",
        "parentheticals": "",
        "main_dir_path": str(source),
        "setlist_file": str(info),
        "setlist_files_json": f'["{str(info).replace(os.sep, os.sep + os.sep) if os.sep == chr(92) else str(info)}"]',
        "music_dirs_json": f'["{str(source).replace(os.sep, os.sep + os.sep) if os.sep == chr(92) else str(source)}"]',
    }

    result = update._rename_add_shows_folder_compliantly(
        SimpleNamespace(rename_compliantly=True), str(source), record
    )
    expected = tmp_path / "Dave Van Ronk 1978-02-17 Main Point Bryn Mawr, PA"

    assert result == os.path.normpath(str(expected))
    assert expected.is_dir()
    assert not source.exists()
    assert record["main_dir_path"] == os.path.normpath(str(expected))
