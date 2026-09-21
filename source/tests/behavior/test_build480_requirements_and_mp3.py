"""Build 480 requirements consolidation and MP3 inventory-tag evidence regressions."""

from pathlib import Path
import importlib.util
from types import SimpleNamespace

import pytest

import tlo_audio_tags as AT
import tlo_phase23_v2 as P

pytestmark = pytest.mark.behavior


def _load_gui():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("tlo_ggi_build480", root / "tlo-ggi.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build480_gui_launcher_rejects_dead_tag_path_option():
    gui = _load_gui()
    with pytest.raises(SystemExit):
        gui._parse_gui_command_line(["--tag-path", "/tmp/tags"])


def test_build480_mp3_tags_are_inventory_metadata_evidence(tmp_path, monkeypatch):
    wav = tmp_path / "00.wav"
    mp3 = tmp_path / "01.mp3"
    flac = tmp_path / "02.flac"
    for path in (wav, mp3, flac):
        path.write_bytes(b"x")

    class FakeAudio:
        def __init__(self, tags):
            self.tags = tags

    def fake_mutagen(path, easy=True):
        assert easy is True
        if str(path).endswith(".mp3"):
            return FakeAudio({
                "artist": ["MP3 Artist"],
                "albumartist": ["MP3 Album Artist"],
                "album": ["MP3 Album"],
                "date": ["1977-05-08"],
            })
        return FakeAudio({"artist": ["FLAC Artist"]})

    monkeypatch.setattr(AT, "MutagenFile", fake_mutagen)
    AT._FILE_TAG_CACHE.clear()
    info = AT.collect_group_flac_tag_info([str(wav), str(mp3), str(flac)], max_files=2)
    assert [Path(row["file"]).suffix.lower() for row in info["flac_tag_samples"]] == [".mp3", ".flac"]
    assert info["flac_tag_albumartist_values"] == ["MP3 Album Artist"]
    assert info["flac_tag_artist_values"] == ["MP3 Artist", "FLAC Artist"]
    assert info["flac_tag_album_values"] == ["MP3 Album"]
    assert info["flac_tag_date_values"] == ["1977-05-08"]


def test_build480_group_sampler_includes_mp3_candidates(tmp_path):
    music = tmp_path / "show"
    music.mkdir()
    (music / "01.mp3").write_bytes(b"x")
    group = {"music_dirs": [str(music)], "music_files": [str(music / "01.mp3")]}
    assert P._flac_tag_sample_files_for_group(group) == [str(music / "01.mp3")]


def test_build480_trailing_state_code_requires_uppercase_and_valid_left_side():
    assert P._parse_string2("The Fillmore San Francisco CA SBD") == (
        "The Fillmore", "San Francisco", "CA", "", "SBD"
    )
    assert P._parse_string2("Boca Raton Florida - Schoeps") == (
        "", "Boca Raton", "FL", "", "Schoeps"
    )
    # Ordinary title/prose word "In" must not become Indiana merely because
    # additional text follows it.
    assert P._parse_string2("Two Gentlemen In, NY source info") == ("", "", "", "", "")
