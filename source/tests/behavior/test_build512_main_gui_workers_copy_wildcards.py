"""Build 514 main-GUI naming, mode worker ceilings, and Copy Request wildcard paths."""

__version__ = "v514"

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

import tlo_copy_requests as CR


def _load_gui_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tlo_ggi_build512", Path("tlo-ggi.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_build512_main_window_uses_main_naming():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'WINDOW_TITLE = versioned_title("TLO Main GUI")' in source
    assert 'text="Traders Little Organizer™ Main"' in source
    assert 'WINDOW_TITLE = versioned_title("TLO Inventory GUI")' not in source
    assert 'text="Traders Little Organizer™ Inventory App"' not in source


def test_build512_max_workers_automatic_value_matches_selected_mode(monkeypatch):
    gui = _load_gui_module()
    monkeypatch.setattr(gui.os, "cpu_count", lambda: 8)
    assert gui._default_max_workers_for_mode("gentle") == 1
    assert gui._default_max_workers_for_mode("balanced") == 2
    assert gui._default_max_workers_for_mode("fast") == 8
    assert gui._default_max_workers_for_mode("extreme") == 32

    monkeypatch.setattr(gui.os, "cpu_count", lambda: 32)
    assert gui._default_max_workers_for_mode("extreme") == 64

    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'self.performance_combo.bind("<<ComboboxSelected>>", self._sync_max_workers_to_performance_mode)' in source


def test_build512_prefix_wildcard_expands_matching_top_level_folders_only(tmp_path):
    wanted1 = tmp_path / "TLO"
    wanted2 = tmp_path / "TLO-Backup"
    ignored = tmp_path / "Other"
    wanted_file = tmp_path / "TLO-not-a-folder.txt"
    for path in (wanted1, wanted2, ignored):
        path.mkdir()
    wanted_file.write_text("x", encoding="utf-8")

    text, sources = CR.aggregate_request_paths_input(str(tmp_path / "TLO*"))
    assert CR.request_lines_from_text(text) == [str(wanted1), str(wanted2)]
    assert sources[0]["kind"] == "wildcard"
    assert sources[0]["expanded_items"] == [str(wanted1), str(wanted2)]


def test_build512_child_wildcard_copies_child_folders_not_container(tmp_path):
    container = tmp_path / "TLO"
    child1 = container / "A"
    child2 = container / "B"
    child1.mkdir(parents=True)
    child2.mkdir()
    (container / "not-a-folder.txt").write_text("x", encoding="utf-8")

    text, sources = CR.aggregate_request_paths_input(str(container) + os.sep + "*")
    assert CR.request_lines_from_text(text) == [str(child1), str(child2)]
    assert str(container) not in CR.request_lines_from_text(text)
    assert sources[0]["expanded_items"] == [str(child1), str(child2)]


def test_build512_wildcards_inside_txt_are_expanded_and_persisted(tmp_path):
    home = tmp_path / "home"; home.mkdir()
    destination = tmp_path / "dest"; destination.mkdir()
    source_parent = tmp_path / "sources"; source_parent.mkdir()
    one = source_parent / "TLO1"; one.mkdir()
    two = source_parent / "TLO2"; two.mkdir()
    request_file = tmp_path / "request.txt"
    request_file.write_text(str(source_parent / "TLO*") + "\nAllman Brothers Band\n", encoding="utf-8")

    request_input = str(request_file)
    state = CR.create_or_open_request_paths(str(home), request_input, str(destination))
    rid = str(state["request_id"])
    assert CR.request_lines_from_text(CR.saved_request_text(str(home), rid)) == [str(one), str(two), "Allman Brothers Band"]

    # Request identity is resolved before source re-expansion. Neither the list
    # file nor the wildcard source tree is required for later continuation.
    request_file.unlink()
    one.rmdir(); two.rmdir(); source_parent.rmdir()
    reopened = CR.create_or_open_request_paths(str(home), request_input, str(destination))
    assert reopened["request_id"] == rid
    assert CR.request_lines_from_text(CR.saved_request_text(str(home), rid)) == [str(one), str(two), "Allman Brothers Band"]


def test_build512_wildcard_requires_accessible_parent_and_at_least_one_folder(tmp_path):
    with pytest.raises(CR.CopyRequestError, match="matched no folders"):
        CR.aggregate_request_paths_input(str(tmp_path / "NoMatch*"))
    with pytest.raises(CR.CopyRequestError, match="not an accessible folder"):
        CR.aggregate_request_paths_input(str(tmp_path / "missing" / "TLO*"))


def test_build512_documentation_contracts():
    from docx import Document

    req = "\n".join(p.text for p in Document("TLO_Inventory_Requirements_Working_v514.docx").paragraphs)
    manual = Path("TLO_Inventory_User_Manual_v514.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = Path("TLO-FAQ.txt").read_text(encoding="utf-8")

    assert "TLO Main GUI followed by the current tlo_version.DISPLAY_VERSION" in req
    assert "Traders Little Organizer™ Main" in req
    assert "gentle = 1; balanced = min(2, CPU count); fast = CPU count; extreme = min(4 × CPU count, 64)" in req
    assert "C:\\TLO* selects every immediate directory" in req
    assert "C:\\TLO\\* selects every immediate child directory" in req
    assert "Build 512 - Main GUI naming, mode-aware Max Workers, and Copy Request wildcards" in manual
    assert r"c:\\TLO* selects each immediate folder" in manual
    assert r"c:\\TLO\\* selects the immediate folders inside" in manual
    assert "Q: What does Max Workers mean?" in faq
    assert "c:\\TLO* selects each immediate folder" in faq
    assert "c:\\TLO\\* selects the immediate folders inside" in faq
