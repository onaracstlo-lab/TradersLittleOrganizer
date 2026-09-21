"""Build 479 stabilization regressions from the Build 478 review."""

from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest

import inventory_list_lib as IL
import tlo_bootlist_volume_policy as BP
import tlo_dragdrop as DD
import tlo_manual_updates as MU
import tlo_phase23_v2 as P
import tlo_setlistfm_lookup as SFM
from tlo_models import ShowMetadata

pytestmark = pytest.mark.behavior
__version__ = "v480"


def _music_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "01.flac").write_bytes(b"x")
    return path


def _record(**kwargs):
    values = dict(group_number=1, main_dir_name="x", main_dir_path="/x", setlist_file="", music_file_count=1)
    values.update(kwargs)
    return ShowMetadata(**values)


def test_build479_gui_tag_completion_calls_state_reset_without_nameerror(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("tlo_ggi_build479", root / "tlo-ggi.py")
    gui = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(gui)

    app = gui.App.__new__(gui.App)
    events = []
    app.tag_active = True
    app.active_main_operation = "Tag"
    app.worker = object()
    app.inventory_monitor = gui.RunMonitor("Tag")
    app.current_config = SimpleNamespace(TLOHome="")
    app.progress_bar = None
    app.root = object()
    app.inventory_issues = []
    app._consume_inventory_queue = lambda: events.append("consume")
    app._update_progress_display = lambda: events.append("progress")
    app._update_main_action_states = lambda: events.append("states")
    monkeypatch.setattr(gui, "is_cancel_requested", lambda: False)
    monkeypatch.setattr(gui, "collect_current_log_issues", lambda *_a, **_k: [])
    monkeypatch.setattr(gui, "merge_issues", lambda a, b: list(a) + list(b))
    monkeypatch.setattr(gui, "_show_completion_dialog", lambda *_a, **_k: events.append("dialog"))
    monkeypatch.setattr(gui, "clear_pause", lambda: None)

    app._finish_main_tagging(None, {"groups": 1, "tagged": 3, "skipped": 0, "errors": 0})
    assert app.tag_active is False
    assert events == ["consume", "progress", "states", "dialog"]


def test_build479_manual_update_matches_real_canonical_bootlist_path(tmp_path):
    home = tmp_path / "TLOHome"
    home.mkdir()
    target = "/mnt/e/boots/Old Show"
    rows = [
        {"Show": "Old Show", "VolumePath": BP.format_volume_path("Music1", target)},
        {"Show": "Other", "VolumePath": BP.format_volume_path("Backup2", "/mnt/f/archive/Other")},
    ]
    MU.write_bootlist(str(home), rows)
    matched = MU._matching_bootlist_rows(str(home), target)
    assert matched == [rows[0]]


def test_build479_manual_update_never_leaf_matches_other_volume(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    home.mkdir()
    MU.write_bootlist(str(home), [
        {"Show": "Old Show", "VolumePath": BP.format_volume_path("Backup2", "/mnt/f/archive/Old Show")}
    ])
    monkeypatch.setattr(MU, "os_volume_label_for_path", lambda _p: "Music1")
    with pytest.raises(MU.ManualUpdateError, match="not present|different volume"):
        MU._matching_bootlist_rows(str(home), "/mnt/e/boots/Old Show")


def test_build479_manual_update_preserves_shared_old_setlist_family(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    setlists = home / "setlists"
    setlists.mkdir(parents=True)
    one = _music_dir(tmp_path / "lib" / "Source One")
    two = _music_dir(tmp_path / "lib" / "Source Two")
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    base = setlists / "GratefulDead1977-05-08BartonHallIthacaNY.txt"
    alt = setlists / "GratefulDead1977-05-08BartonHallIthacaNY(alt1).txt"
    base.write_text("source one", encoding="utf-8")
    alt.write_text("source two", encoding="utf-8")
    MU.write_bootlist(str(home), [
        {"Show": show, "VolumePath": str(one)},
        {"Show": show, "VolumePath": str(two)},
    ])
    monkeypatch.setattr(MU, "identify_folder_dict", lambda _c, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda *_a, **_k: "")

    MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(home)), str(two), "Source Two Corrected")
    assert base.is_file()
    assert alt.is_file()
    rows = MU.read_bootlist(str(home))
    assert any(row["Show"] == show for row in rows)


def test_build479_unidentified_recovery_writes_canonical_volume_path(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    (home / "setlists").mkdir(parents=True)
    original = tmp_path / "old" / "Mystery"
    final = _music_dir(tmp_path / "dest" / "Named Show")
    (home / "unidentifiedShows.txt").write_text(str(original) + "\n", encoding="utf-8")
    monkeypatch.setattr(MU, "os_volume_label_for_path", lambda _p: "Music1")
    monkeypatch.setattr(MU, "identify_folder_dict", lambda _c, folder: {"show_name": "x", "main_dir_path": folder})
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda *_a, **_k: "")

    MU.apply_unidentified_manual_update(SimpleNamespace(TLOHome=str(home)), str(original), "Named Show", str(final.parent))
    assert MU.read_bootlist(str(home)) == [{
        "Show": "Named Show",
        "VolumePath": BP.format_volume_path("Music1", str(final)),
    }]


def test_build479_setlistfm_drops_same_date_wrong_artist(monkeypatch):
    def fake_api_get(*_args, **_kwargs):
        return {
            "total": 1,
            "itemsPerPage": 1,
            "setlist": [{
                "artist": {"name": "Different Artist"},
                "eventDate": "18-09-1971",
                "venue": {"name": "Wrong Venue", "city": {"name": "Paris", "country": {"name": "France", "code": "FR"}}},
            }],
        }
    monkeypatch.setattr(SFM, "api_get", fake_api_get)
    assert SFM.search_setlists("Pink Floyd", "1971-09-18", api_key="x") == []


def test_build479_case_corroboration_improves_lowercase_and_rebuilds_location():
    rec = _record(city="pori", country="Finland", location="pori, Finland")
    evidence = {}
    observations = []
    changed = P._apply_online_fields_fill_blanks(
        rec, evidence, observations, "setlist.fm", 70,
        "", "Pori", "Satakunta", "Finland", "Pori, Satakunta, Finland"
    )
    assert changed is True
    assert rec.city == "Pori"
    assert rec.location == "Pori, Finland"


def test_build479_case_corroboration_does_not_degrade_good_mixed_case():
    rec = _record(venue="Madison Square Garden")
    P._apply_online_fields_fill_blanks(rec, {}, [], "setlist.fm", 70, "MADISON SQUARE GARDEN", "", "", "", "")
    assert rec.venue == "Madison Square Garden"


def test_build479_future_dates_are_rejected_and_two_digit_year_is_past_interpretation():
    assert P._find_date_matches("Band 2031-01-01 Venue") == []
    assert [x["normalized"] for x in P._find_date_matches("Band 5/8/33 Venue", allow_slash=True)] == ["1933-05-08"]
    normalized = [x["normalized"] for x in P._find_date_matches("gd30-05-08")]
    assert "2030-05-08" not in normalized
    assert "2008-05-30" in normalized


def test_build479_semicolon_drop_round_trips_as_one_path():
    dropped = DD._append_search_path_drop_values("", [r"C:\Boots\Artist; Live 1970", r"C:\Boots\Other"])
    entries = IL._split_search_path_entries(dropped)
    assert len(entries) == 2
    assert IL._strip_optional_quotes(entries[0]) == r"C:\Boots\Artist; Live 1970"
    assert entries[1] == r"C:\Boots\Other"


def test_build479_single_quotes_are_literal_not_wrappers():
    assert IL._strip_optional_quotes("'C:/Boots/Artist'") == "'C:/Boots/Artist'"
    assert MU.strip_optional_quotes("'New Name'") == "'New Name'"


def test_build479_manual_update_tag_identity_uses_new_name_and_disables_shn(tmp_path, monkeypatch):
    folder = _music_dir(tmp_path / "Tito")
    captured = {}
    monkeypatch.setattr(MU, "_build_single_folder_group", lambda config, _folder: captured.setdefault("convert_shn", getattr(config, "convert_shn", None)) or {"music_files": []})
    monkeypatch.setattr(MU, "_record_namespace_from_dict", lambda record: SimpleNamespace(**record))
    import tlo_tag_lib
    monkeypatch.setattr(tlo_tag_lib, "tag_group_with_record", lambda config, group, record, **kwargs: captured.update(artist=record.artist, album=record.album_name) or {"errors": 0, "skipped": 0})
    record = MU._apply_manual_name_tag_identity(
        {"artist": "Wrong Artist", "album_name": "Wrong Album", "show_name": "x"},
        "Tito Puente's Golden Latin Jazz All Stars 1994-07-24 Kirjurinluoto Pori, Finland",
    )
    MU._update_manual_folder_tags(SimpleNamespace(convert_shn=True), str(folder), record)
    assert captured["convert_shn"] is False
    assert captured["artist"] == "Tito Puente's Golden Latin Jazz All Stars"
    assert captured["album"] == "1994-07-24 Kirjurinluoto Pori, Finland"
