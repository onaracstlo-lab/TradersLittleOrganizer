__version__ = "v467"

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior
from mutagen import MutagenError
from mutagen.id3 import APIC, COMM, TALB, TIT2, TPE1, TRCK

import tlo_corruption as corruption
import tlo_options as options
import tlo_tag_lib as taglib
import tlo_ux as ux


class _FakeEasyAudio(dict):
    def __init__(self, values):
        super().__init__(values)
        self.tags = self
        self.save_count = 0

    def add_tags(self):
        self.tags = self

    def save(self):
        self.save_count += 1


class _FakeID3:
    def __init__(self, frames):
        self.frames = list(frames)
        self.saved_to = None

    def values(self):
        return list(self.frames)

    def getall(self, frame_id):
        target = str(frame_id).upper()
        return [frame for frame in self.frames if str(getattr(frame, "FrameID", "")).upper() == target]

    def clear(self):
        self.frames.clear()

    def add(self, frame):
        self.frames.append(frame)

    def save(self, path):
        self.saved_to = str(path)


def test_build467_delete_extra_tags_option_is_far_right_two_line_checkbox_contract():
    option = options.OPTIONS_BY_FIELD["delete_extra_tags"]
    assert option.flag == "--delete-extra-tags"
    assert option.gui == "checkbox"
    assert (option.gui_row, option.gui_col) == (3, 3)
    assert option.default is False
    assert ux.MAIN_WINDOW_CHECKBOX_SPECS[-2:] == (
        ("delete_extra_tags", "Delete extra tags"),
        ("dry_run", "Dry run"),
    )


def test_build467_main_window_review_includes_delete_extra_tags_before_dry_run():
    values = ux.main_window_checkbox_values({"delete_extra_tags": True}, dry_run=False)
    assert values["delete_extra_tags"] is True
    lines = ux.main_window_checkbox_review_lines(values, dry_run=False)
    delete_index = next(i for i, line in enumerate(lines) if "Delete extra tags:" in line)
    dry_index = next(i for i, line in enumerate(lines) if "Dry run:" in line)
    assert delete_index < dry_index


def test_build467_tagger_config_propagates_delete_extra_tags(tmp_path):
    (tmp_path / "TLO_DBs").mkdir()
    config = taglib.build_tagger_config(tlo_home=str(tmp_path), delete_extra_tags=True)
    assert config.delete_extra_tags is True


def test_build467_normal_mp3_tagging_preserves_unrelated_easy_metadata(tmp_path, monkeypatch):
    path = tmp_path / "track01.mp3"
    path.write_bytes(b"placeholder")
    fake = _FakeEasyAudio({
        "artist": ["Old Artist"],
        "album": ["Old Album"],
        "title": ["Old Title"],
        "tracknumber": ["9"],
        "genre": ["Rock"],
    })
    monkeypatch.setattr(taglib, "MutagenFile", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(taglib, "_id3_tags_match_target", lambda *_args, **_kwargs: False)

    changed = taglib.write_audio_tags(str(path), "Artist", "Album", "01", "Song")

    assert changed is True
    assert fake["genre"] == ["Rock"]
    assert fake["artist"] == ["Artist"]
    assert fake["album"] == ["Album"]
    assert fake["title"] == ["Song"]
    assert fake["tracknumber"] == ["01"]


def test_build467_delete_extra_tags_mp3_keeps_only_four_id3_fields(tmp_path, monkeypatch):
    path = tmp_path / "track01.mp3"
    path.write_bytes(b"placeholder")
    tags = _FakeID3([
        TPE1(encoding=3, text=["Artist"]),
        TALB(encoding=3, text=["Album"]),
        TIT2(encoding=3, text=["Song"]),
        TRCK(encoding=3, text=["01"]),
        COMM(encoding=3, lang="eng", desc="note", text=["remove me"]),
        APIC(encoding=3, mime="image/jpeg", type=3, desc="cover", data=b"jpeg"),
    ])
    monkeypatch.setattr(taglib, "ID3", lambda *_args, **_kwargs: tags)

    changed = taglib.write_audio_tags(
        str(path), "Artist", "Album", "01", "Song", delete_extra_tags=True
    )

    assert changed is True
    assert tags.saved_to == str(path)
    assert [frame.FrameID for frame in tags.frames] == ["TPE1", "TALB", "TIT2", "TRCK"]


def test_build467_delete_extra_tags_noop_when_mp3_already_has_exact_four_fields(tmp_path, monkeypatch):
    path = tmp_path / "track01.mp3"
    path.write_bytes(b"placeholder")
    tags = _FakeID3([
        TPE1(encoding=3, text=["Artist"]),
        TALB(encoding=3, text=["Album"]),
        TIT2(encoding=3, text=["Song"]),
        TRCK(encoding=3, text=["01"]),
    ])
    monkeypatch.setattr(taglib, "ID3", lambda *_args, **_kwargs: tags)
    monkeypatch.setattr(taglib, "MutagenFile", lambda *_args, **_kwargs: None)

    changed = taglib.write_audio_tags(
        str(path), "Artist", "Album", "01", "Song", delete_extra_tags=True
    )

    assert changed is False
    assert tags.saved_to is None


def test_build467_mp3_corruption_uses_explicit_mp3_validator(tmp_path, monkeypatch):
    path = tmp_path / "broken.mp3"
    path.write_bytes(b"not-an-mp3")
    calls = []

    def fail_mp3(candidate):
        calls.append(str(candidate))
        raise MutagenError("invalid MPEG stream")

    monkeypatch.setattr(corruption, "MP3", fail_mp3)
    monkeypatch.setattr(corruption, "MutagenFile", lambda *_args, **_kwargs: pytest.fail("generic validator should not be used for MP3"))

    bad, unverifiable = corruption.classify_audio_paths([str(path)])

    assert bad == [str(path)]
    assert unverifiable == []
    assert calls == [str(path)]


def test_build467_mp3_counts_in_same_folder_corruption_percentage_as_flac(tmp_path, monkeypatch):
    folder = tmp_path / "show"
    folder.mkdir()
    flac = folder / "01.flac"
    mp3 = folder / "02.mp3"
    flac.write_bytes(b"flac")
    mp3.write_bytes(b"mp3")
    group = {"main_dir_path": str(folder), "music_dirs": [str(folder)]}

    monkeypatch.setattr(
        corruption,
        "classify_audio_paths",
        lambda paths: ([str(mp3)], []),
    )

    assessment = corruption.assess_group_corruption(
        group, corrupt_files="delete", corrupt_folders="threshold", folder_threshold=50
    )

    assert set(assessment.audio_files) == {str(flac), str(mp3)}
    assert assessment.corrupt_files == [str(mp3)]
    assert assessment.corruption_percent == 50.0
    assert assessment.action == "trash_folder_threshold"


def test_build467_tag_group_passes_cleanup_only_when_selected(tmp_path, monkeypatch):
    path = tmp_path / "01.mp3"
    path.write_bytes(b"audio")
    calls = []
    monkeypatch.setattr(taglib, "_rescan_group_audio_files", lambda _group: [str(path)])
    monkeypatch.setattr(taglib, "_prepare_audio_files_for_tagging", lambda _config, _group, files, emit=None: (files, 0))
    monkeypatch.setattr(taglib, "_select_tracks_for_tagging", lambda *_args, **_kwargs: ([{"normalized_number": 1, "title": "Song"}], "filename", ""))
    monkeypatch.setattr(taglib, "write_audio_tags", lambda *args, **kwargs: calls.append((args, kwargs)) or True)
    config = SimpleNamespace(delete_extra_tags=True, convert_shn=False, artist_in_album=False, debug=False, TLOHome=str(tmp_path))
    record = SimpleNamespace(artist="Artist", show_name="Artist 2000-01-01", album_name="Album", parentheticals="")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": tmp_path.name, "music_dirs": [str(tmp_path)]}

    stats = taglib.tag_group_with_record(config, group, record, allow_unknown_metadata=True)

    assert stats["tagged"] == 1
    assert calls[0][1]["delete_extra_tags"] is True


def test_build467_delete_extra_tags_flac_with_picture_is_not_a_noop(tmp_path, monkeypatch):
    path = tmp_path / "track01.flac"
    path.write_bytes(b"placeholder")

    class FakeFlac(dict):
        def __init__(self):
            super().__init__({
                "artist": ["Artist"],
                "album": ["Album"],
                "title": ["Song"],
                "tracknumber": ["01"],
            })
            self.pictures = [object()]
            self.saved = False

        def clear_pictures(self):
            self.pictures.clear()

        def save(self):
            self.saved = True

    audio = FakeFlac()
    monkeypatch.setattr(taglib, "FLAC", lambda *_args, **_kwargs: audio)

    changed = taglib.write_audio_tags(
        str(path), "Artist", "Album", "01", "Song", delete_extra_tags=True
    )

    assert changed is True
    assert audio.pictures == []
    assert set(audio.keys()) == {"artist", "album", "title", "tracknumber"}
    assert audio.saved is True
