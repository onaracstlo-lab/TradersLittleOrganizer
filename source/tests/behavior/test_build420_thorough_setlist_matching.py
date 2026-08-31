"""Build 420 regressions for Thorough Setlist Matching."""

__version__ = "v423"

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _track(title, source="test"):
    return {
        "original_number": 1,
        "normalized_number": 1,
        "title": title,
        "source_line": title,
        "source": source,
    }


def _tracks(*titles, source="test"):
    return [dict(_track(title, source=source), original_number=i, normalized_number=i) for i, title in enumerate(titles, 1)]


def test_thorough_option_defaults_off_and_is_exposed_to_cli_and_gui():
    import argparse
    from tlo_options import OPTIONS_BY_FIELD, GUI_CHECKBOX_OPTIONS, add_options_to_parser

    option = OPTIONS_BY_FIELD["thorough_setlist_matching"]
    assert option.flag == "--thorough-setlist-matching"
    assert option.default is False
    assert option.gui_label == "Thorough Setlist Matching"
    assert option in GUI_CHECKBOX_OPTIONS
    assert "normal setlist.fm" in option.help
    assert "setlist.fm upgrade" in option.help

    parser = argparse.ArgumentParser()
    add_options_to_parser(parser, fields=("thorough_setlist_matching",))
    assert parser.parse_args([]).thorough_setlist_matching is False
    assert parser.parse_args(["--thorough-setlist-matching"]).thorough_setlist_matching is True


def test_main_window_review_includes_thorough_checkbox():
    from tlo_ux import main_window_checkbox_review_lines

    lines = main_window_checkbox_review_lines({"thorough_setlist_matching": True})
    assert any(line.strip() == "Thorough Setlist Matching: Yes" for line in lines)


def test_thorough_queries_setlistfm_even_after_usable_etree(monkeypatch):
    import tlo_phase23_v2 as phase

    calls = []
    monkeypatch.setattr(phase, "_apply_setlistfm_lookup_to_record", lambda *_args, **_kwargs: calls.append("setlistfm") or True)
    config = SimpleNamespace(thorough_setlist_matching=True, setlistfm_lookup=True, etree_lookup=True)
    record = SimpleNamespace(artist="Pink Floyd", date="1971-09-18")
    success, key = phase._apply_setlistfm_only_after_etree_fallback(
        config, record, {}, [], True, ("pink floyd", "1971-09-18")
    )
    assert success is True
    assert calls == ["setlistfm"]


def test_normal_mode_still_short_circuits_setlistfm_after_usable_etree(monkeypatch):
    import tlo_phase23_v2 as phase

    calls = []
    monkeypatch.setattr(phase, "_apply_setlistfm_lookup_to_record", lambda *_args, **_kwargs: calls.append("setlistfm") or True)
    config = SimpleNamespace(thorough_setlist_matching=False, setlistfm_lookup=True, etree_lookup=True)
    record = SimpleNamespace(artist="Pink Floyd", date="1971-09-18")
    success, key = phase._apply_setlistfm_only_after_etree_fallback(
        config, record, {}, [], True, ("pink floyd", "1971-09-18")
    )
    assert success is True
    assert calls == []


def test_setlistfm_thorough_search_follows_additional_pages(monkeypatch):
    import tlo_setlistfm_lookup as sfm

    calls = []

    def fake_api_get(_path, params, *_args, **_kwargs):
        page = int(params["p"])
        calls.append(page)
        item = {
            "artist": {"name": "Pink Floyd"},
            "eventDate": "18-09-1971",
            "url": f"https://example/{page}",
            "venue": {
                "name": f"Venue {page}",
                "city": {"name": "Montreux", "state": "", "stateCode": "", "country": {"name": "Switzerland", "code": "CH"}},
            },
            "sets": {"set": [{"song": [{"name": f"Song {page}"}]}]},
        }
        return {"total": 2, "itemsPerPage": 1, "page": page, "setlist": [item]}

    monkeypatch.setattr(sfm, "api_get", fake_api_get)
    results = sfm.search_setlists("Pink Floyd", "1971-09-18", api_key="x", thorough=True)
    assert calls == [1, 2]
    assert [result.venue for result in results] == ["Venue 1", "Venue 2"]


def test_online_consensus_can_beat_uncorroborated_local_candidate(tmp_path):
    import tlo_tag_lib as taglib

    audio = []
    for idx, title in enumerate(("Song A", "Song B", "Song C"), 1):
        path = tmp_path / f"{idx:02d} - {title}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    candidates = [
        {"source": "setlist", "family": "local", "label": "local-numbered", "tracks": _tracks("Wrong 1", "Wrong 2", "Wrong 3"), "venue": "", "location": "", "distance": 0},
        {"source": "etreedb", "family": "etreedb", "label": "eTreeDB", "tracks": _tracks("Song A", "Song B", "Song C"), "venue": "", "location": "", "distance": 0},
        {"source": "setlist.fm", "family": "setlist.fm", "label": "setlist.fm", "tracks": _tracks("Song A", "Song B", "Song C"), "venue": "", "location": "", "distance": 0},
    ]
    taglib._score_thorough_track_candidates(candidates, audio, SimpleNamespace(venue="", location=""))
    scores = {candidate["source"]: candidate["score"] for candidate in candidates}
    assert scores["etreedb"] > scores["setlist"]
    assert scores["setlist.fm"] > scores["setlist"]


def test_strong_audio_corroboration_can_keep_local_candidate_ahead_of_online_consensus(tmp_path):
    import tlo_tag_lib as taglib

    audio = []
    for idx, title in enumerate(("Local A", "Local B", "Local C"), 1):
        path = tmp_path / f"{idx:02d} - {title}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    candidates = [
        {"source": "setlist", "family": "local", "label": "local-numbered", "tracks": _tracks("Local A", "Local B", "Local C"), "venue": "", "location": "", "distance": 0},
        {"source": "etreedb", "family": "etreedb", "label": "eTreeDB", "tracks": _tracks("Online A", "Online B", "Online C"), "venue": "", "location": "", "distance": 0},
        {"source": "setlist.fm", "family": "setlist.fm", "label": "setlist.fm", "tracks": _tracks("Online A", "Online B", "Online C"), "venue": "", "location": "", "distance": 0},
    ]
    taglib._score_thorough_track_candidates(candidates, audio, SimpleNamespace(venue="", location=""))
    winner = max(candidates, key=lambda candidate: candidate["score"])
    assert winner["source"] == "setlist"


def test_near_count_alignment_places_recording_only_intro_at_correct_position(tmp_path):
    import tlo_tag_lib as taglib

    audio = []
    for idx, title in enumerate(("Intro", "Song A", "Song B", "Song C"), 1):
        path = tmp_path / f"{idx:02d} - {title}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    mapping, corroborated, coverage, gaps = taglib._candidate_audio_alignment(_tracks("Song A", "Song B", "Song C"), audio)
    assert mapping[0] is None
    assert [row["title"] if row else None for row in mapping[1:]] == ["Song A", "Song B", "Song C"]
    assert corroborated >= 3
    assert coverage >= 0.75
    assert gaps >= 1

    materialized = taglib._materialize_aligned_candidate_tracks(mapping, audio, "setlist.fm")
    assert [row["title"] for row in materialized] == ["Intro", "Song A", "Song B", "Song C"]


def test_thorough_selector_can_use_near_count_cached_setlistfm_with_audio_alignment(tmp_path):
    import tlo_tag_lib as taglib

    audio = []
    for idx, title in enumerate(("Intro", "Song A", "Song B", "Song C"), 1):
        path = tmp_path / f"{idx:02d} - {title}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    config = SimpleNamespace(thorough_setlist_matching=True, etree_lookup=False, debug=False)
    record = SimpleNamespace(
        artist="Pink Floyd",
        date="1971-09-18",
        venue="",
        location="",
        setlistfm_setlist_candidates=[{
            "url": "https://example/setlist",
            "venue": "Casino",
            "city": "Montreux",
            "state_code": "",
            "country": "Switzerland",
            "setlists": ["01 Song A\n02 Song B\n03 Song C"],
        }],
    )
    tracks, source, error = taglib._select_tracks_for_tagging(
        config, {"main_dir_path": str(tmp_path), "setlist_file": ""}, audio, record=record
    )
    assert error is None
    assert source == "setlist.fm"
    assert [row["title"] for row in tracks] == ["Intro", "Song A", "Song B", "Song C"]



def test_review_note_explains_normal_setlistfm_limits_when_thorough_without_upgrade():
    from tlo_ux import operation_review_lines

    config = SimpleNamespace(
        TLOHome="/tmp/tlo", search_path_override="", performance_mode="balanced", max_workers=0,
        acceptable_corruption_percent=100, thorough_setlist_matching=True, setlistfm_lookup=True,
        setlistfm_upgrade=False, etree_lookup=True, artist_in_album=True,
    )
    lines = operation_review_lines(config, operation="Full Inventory", dry_run=False)
    assert any("normal 600-ms / 1,400-call limits" in line for line in lines)
    assert any("setlist.fm upgrade provides broader/faster" in line for line in lines)

def test_gui_explanation_mentions_normal_setlistfm_limits():
    source = __import__("pathlib").Path(__file__).resolve().parents[2].joinpath("tlo-ggi.py").read_text(encoding="utf-8")
    assert "normal 600-ms / 1,400-call limits" in source
    assert "unless setlist.fm upgrade is enabled" in source


def test_thorough_material_cross_source_tie_reports_ambiguity(monkeypatch, tmp_path):
    import tlo_tag_lib as taglib

    audio = []
    for idx, title in enumerate(("Audio A", "Audio B", "Audio C"), 1):
        path = tmp_path / f"{idx:02d} - {title}.flac"
        path.write_bytes(b"")
        audio.append(str(path))

    local = {
        "source": "setlist", "family": "local", "label": "local-numbered",
        "tracks": _tracks("Local A", "Local B", "Local C"), "venue": "", "location": "", "distance": 0,
    }
    etree = {
        "source": "etreedb", "family": "etreedb", "label": "eTreeDB",
        "tracks": _tracks("Online X", "Online Y", "Online Z"), "venue": "", "location": "", "distance": 0,
    }
    monkeypatch.setattr(taglib, "_collect_local_track_candidates_for_thorough", lambda *_args, **_kwargs: [local])
    monkeypatch.setattr(taglib, "_collect_etreedb_track_candidates_for_thorough", lambda *_args, **_kwargs: [etree])
    monkeypatch.setattr(taglib, "_collect_setlistfm_track_candidates_for_thorough", lambda *_args, **_kwargs: [])

    def tie_scores(candidates, *_args, **_kwargs):
        for candidate in candidates:
            candidate["score"] = 100.0
            candidate["alignment"] = []
            candidate["alignment_corroborated"] = 0
            candidate["alignment_coverage"] = 0.0
            candidate["alignment_gaps"] = 0

    monkeypatch.setattr(taglib, "_score_thorough_track_candidates", tie_scores)
    tracks, source, error = taglib._select_tracks_for_tagging_thorough(
        SimpleNamespace(thorough_setlist_matching=True),
        {"main_dir_path": str(tmp_path), "setlist_file": "ignored.txt"},
        audio,
        None,
        SimpleNamespace(artist="Pink Floyd", date="1971-09-18", venue="", location=""),
    )
    assert tracks == []
    assert source == ""
    assert error and error.startswith("Thorough Setlist Matching ambiguity:")


def test_build420_documents_lock_thorough_coverage_vs_authority_contract():
    from pathlib import Path
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v423.docx")
    req_text = "\n".join(paragraph.text for paragraph in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v423.rtf").read_text(encoding="utf-8", errors="replace")

    assert "Build 420 Thorough Setlist Matching rule" in req_text
    assert "normal 600-millisecond / 1,400-call limits" in req_text
    assert "Upgrade must never increase setlist.fm source authority" in req_text
    assert "Thorough Setlist Matching" in manual_text
    assert "600 milliseconds" in manual_text
    assert "1,400 calls" in manual_text
    assert "coverage/capacity, never setlist.fm authority" in manual_text
