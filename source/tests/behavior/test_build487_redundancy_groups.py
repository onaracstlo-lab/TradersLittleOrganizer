"""Build 487 ordered redundancy groups and Copy Request source substitution."""

__version__ = "v490"

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

import tlo_copy_requests as CR
import tlo_redundancy as RG
from tlo_bootlist_volume_policy import format_volume_path, write_bootlist_rows


def _music(root: Path, rel: str, payload=b"music") -> Path:
    path = root / Path(rel)
    path.mkdir(parents=True, exist_ok=True)
    (path / "track01.flac").write_bytes(payload)
    return path


def test_build487_declaration_order_is_precedence():
    groups = RG.parse_redundancy_text("Juke3 = Back-up3 = Back-up3a\n")
    assert [g.members for g in groups] == [("Juke3", "Back-up3", "Back-up3a")]
    assert RG.ordered_equivalents("Back-up3a", groups) == ("Juke3", "Back-up3", "Back-up3a")
    assert RG.group_display_for_volume("Back-up3", groups) == "Juke3 = Back-up3 = Back-up3a"


def test_build487_path_members_need_no_quotes_and_save_as_labels(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    a = tmp_path / "Juke Three Root"
    b = tmp_path / "Backup Three Root"
    a.mkdir(); b.mkdir()
    labels = {os.path.normpath(str(a)): "Juke3", os.path.normpath(str(b)): "Back-up3"}

    monkeypatch.setattr(
        RG,
        "resolve_volume_label",
        lambda path: SimpleNamespace(label=labels[os.path.normpath(str(path))]),
    )
    groups = RG.save_redundancy_text(str(home), f"{a} = {b}\n")
    assert groups[0].members == ("Juke3", "Back-up3")
    assert RG.redundancy_path(str(home)) == str(home / "redundancyGroups.txt")
    assert (home / "redundancyGroups.txt").read_text(encoding="utf-8") == "Juke3 = Back-up3\n"


def test_build487_rejects_member_in_multiple_groups():
    with pytest.raises(RG.RedundancyError, match="already appears"):
        RG.parse_redundancy_text("Juke3 = Back-up3\nBack-up3 = Archive3\n")


def test_build487_copy_request_uses_leftmost_connected_equivalent(tmp_path):
    rel = "Music/Show"
    juke = tmp_path / "juke"
    backup = tmp_path / "backup"
    backupa = tmp_path / "backupa"
    _music(juke, rel, b"juke")
    _music(backup, rel, b"backup")
    _music(backupa, rel, b"backupa")
    groups = RG.parse_redundancy_text("Juke3 = Back-up3 = Back-up3a\n")
    rows = [{"Show": "Artist 1977-01-01 Venue City, ST", "VolumePath": format_volume_path("Back-up3a", "/" + rel)}]
    roots = {
        "juke3": [str(juke)],
        "back-up3": [str(backup)],
        "back-up3a": [str(backupa)],
    }
    source, waiting, stale = CR.source_status_for_show(rows[0]["Show"], rows, roots, groups)
    assert source is not None
    assert source.volume == "Juke3"
    assert source.inventory_volume == "Back-up3a"
    assert source.source_path == str(juke / Path(rel))
    assert waiting == []
    assert stale == []


def test_build487_copy_request_falls_through_precedence_when_higher_member_missing_show(tmp_path):
    rel = "Music/Show"
    juke = tmp_path / "juke"; juke.mkdir()
    backup = tmp_path / "backup"
    backupa = tmp_path / "backupa"
    _music(backup, rel, b"backup")
    _music(backupa, rel, b"backupa")
    groups = RG.parse_redundancy_text("Juke3 = Back-up3 = Back-up3a\n")
    rows = [{"Show": "Artist 1977-01-01 Venue City, ST", "VolumePath": format_volume_path("Juke3", "/" + rel)}]
    roots = {
        "juke3": [str(juke)],
        "back-up3": [str(backup)],
        "back-up3a": [str(backupa)],
    }
    source, _waiting, stale = CR.source_status_for_show(rows[0]["Show"], rows, roots, groups)
    assert source is not None
    assert source.volume == "Back-up3"
    assert source.source_path == str(backup / Path(rel))
    # Higher-precedence Juke3 was connected but missing the expected replica.
    assert stale == []  # successful lower-precedence replica satisfies this row


def test_build487_evaluation_groups_waiting_opportunity_once(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    dest = tmp_path / "dest"; dest.mkdir()
    request = tmp_path / "request.txt"; request.write_text("Artist\n", encoding="utf-8")
    show = "Artist 1977-01-01 Venue City, ST"
    write_bootlist_rows(str(home), [{"Show": show, "VolumePath": format_volume_path("Juke3", "/Music/Show")}])
    RG.save_redundancy_text(str(home), "Juke3 = Back-up3 = Back-up3a\n")
    state = CR.create_or_open_request(str(home), str(request), str(dest))
    monkeypatch.setattr(CR, "_load_matcher", lambda _home: None)
    evaluation = CR.evaluate_request(str(home), state["request_id"], roots={})
    assert evaluation.waiting[show] == ["[Juke3 = Back-up3 = Back-up3a] /Music/Show"]
    assert evaluation.volume_opportunities == {"Juke3 = Back-up3 = Back-up3a": 1}


def test_build487_hamburger_has_redundancy_groups_and_no_main_button():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'label="Redundancy Groups"' in source
    assert '_open_redundancy_groups' in source
    assert 'text="Redundancy Groups"' not in source
    assert "A = B = C uses A first, then B, then C" in source
    assert "Paths with spaces do not require quotes" in source


def test_build487_documentation_covers_ordered_redundancy_and_unquoted_paths():
    from docx import Document
    req = "\n".join(p.text for p in Document("TLO_Inventory_Requirements_Working_v490.docx").paragraphs)
    manual = Path("TLO_Inventory_User_Manual_v490.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = Path("TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Build 487 - ordered redundancy groups for equivalent source volumes" in req
    assert "Declaration order is authoritative source precedence" in req
    assert "Paths with spaces do not require quotes" in req
    assert "Juke3 = Back-up3 = Back-up3a" in manual
    assert "leftmost member always has the highest precedence" in manual
    assert "Paths with spaces do not require quotes" in manual
    assert "Redundancy Groups" in faq and "Only one copy needs to be inventoried" in faq


def test_build487_copy_pass_records_inventory_and_actual_equivalent_volume(tmp_path, monkeypatch):
    home = tmp_path / "home"; home.mkdir()
    dest = tmp_path / "dest"; dest.mkdir()
    request = tmp_path / "request.txt"; request.write_text("Artist\n", encoding="utf-8")
    rel = "Music/Show"
    juke = tmp_path / "juke"
    backup = tmp_path / "backup"
    _music(juke, rel, b"preferred")
    _music(backup, rel, b"lower")
    show = "Artist 1977-01-01 Venue City, ST"
    write_bootlist_rows(str(home), [{"Show": show, "VolumePath": format_volume_path("Back-up3", "/" + rel)}])
    RG.save_redundancy_text(str(home), "Juke3 = Back-up3\n")
    state = CR.create_or_open_request(str(home), str(request), str(dest))
    monkeypatch.setattr(CR, "_load_matcher", lambda _home: None)
    roots = {"juke3": [str(juke)], "back-up3": [str(backup)]}
    result = CR.copy_available(str(home), state["request_id"], roots=roots)
    assert [item[0] for item in result.copied] == [show]
    saved = CR.load_request(str(home), state["request_id"])
    completed = saved["completed"][CR._normalize_show(show)]
    assert completed["inventory_volume"] == "Back-up3"
    assert completed["source_volume"] == "Juke3"
    report = Path(result.report_path).read_text(encoding="utf-8")
    assert "Inventoried volume: Back-up3" in report
    assert "Actual source volume: Juke3" in report
