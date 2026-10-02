"""Build 511 Copy Request Path(s) mixed-input and snapshot persistence."""

__version__ = "v518"

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

import inventory_list_lib as INV
import tlo_copy_requests as CR


def test_build511_copy_request_paths_uses_main_gui_semicolon_rules():
    value = r'c:\tmpBoots; "c:\folder;with-semicolon\copyMe.txt"; Allman Brothers Band'
    assert INV.split_search_path_entries(value) == [
        r"c:\tmpBoots",
        r'"c:\folder;with-semicolon\copyMe.txt"',
        "Allman Brothers Band",
    ]


def test_build511_mixed_paths_text_files_and_plain_text_are_aggregated_and_persisted(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    destination = tmp_path / "dest"
    destination.mkdir()
    direct = tmp_path / "tmpBoots"
    direct.mkdir()
    request_file = tmp_path / "copyMe.txt"
    request_file.write_text(
        "# ignored\nREM ignored too\n\nGrateful Dead\nMiles Davis 1970-04-10\n",
        encoding="utf-8",
    )

    request_input = f'{direct}; "{request_file}"; Allman Brothers Band'
    state = CR.create_or_open_request_paths(str(home), request_input, str(destination))
    rid = str(state["request_id"])

    assert state["input_mode"] == "paths"
    assert state["request_input"] == request_input
    assert [row["kind"] for row in state["request_sources"]] == ["item", "file", "item"]
    assert CR.request_lines_from_text(CR.saved_request_text(str(home), rid)) == [
        str(direct),
        "Grateful Dead",
        "Miles Davis 1970-04-10",
        "Allman Brothers Band",
    ]

    # The contributing .txt file is an input source only at creation time. Once
    # expanded, the saved aggregate is sufficient to reopen/continue the request.
    request_file.unlink()
    reopened = CR.create_or_open_request_paths(str(home), request_input, str(destination))
    assert reopened["request_id"] == rid
    assert CR.source_request_change_state(str(home), reopened) == "snapshot-only"
    assert CR.request_lines_from_text(CR.saved_request_text(str(home), rid))[-1] == "Allman Brothers Band"


def test_build511_new_paths_request_requires_txt_source_only_when_first_created(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    destination = tmp_path / "dest"
    destination.mkdir()
    missing = tmp_path / "gone.txt"

    with pytest.raises(CR.CopyRequestError, match="does not exist"):
        CR.create_or_open_request_paths(str(home), str(missing), str(destination))


def test_build511_txt_comments_match_tobeinventoried_convention(tmp_path):
    request_file = tmp_path / "request.txt"
    request_file.write_text(
        "\ufeff# comment\n rem\nREM another comment\nArtist One\n  Artist Two  \n",
        encoding="utf-8",
    )
    text, sources = CR.aggregate_request_paths_input(str(request_file))
    assert CR.request_lines_from_text(text) == ["Artist One", "Artist Two"]
    assert sources[0]["expanded_items"] == ["Artist One", "Artist Two"]


def test_build511_gui_labels_field_paths_and_uses_append_drop_and_snapshot_creation():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("    def _new_request(self):")
    end = source.index("    def _prepare_request_for_continue", start)
    block = source[start:end]
    assert 'text="Path(s)"' in block
    assert "enable_search_path_folder_drop(" in block
    assert "append_search_path_values(request_var.get(), list(selected))" in block
    assert "create_or_open_request_paths(self.tlo_home, request_paths, destination)" in block
    assert "enable_single_txt_file_drop(" not in block
    assert "Request File" not in block


def test_build511_documentation_contracts():
    from docx import Document

    req = "\n".join(p.text for p in Document("TLO_Inventory_Requirements_Working_v518.docx").paragraphs)
    manual = Path("TLO_Inventory_User_Manual_v518.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = Path("TLO-FAQ.txt").read_text(encoding="utf-8")

    assert "REQ-COPY-006" in req
    assert "Path(s) may mix plain request text, direct filesystem path/volume items, and .txt request files" in req
    assert "must be sufficient for all later Preview, Continue, Process All, report, and resume operations without rereading the source .txt files" in req
    assert "The first input is Path(s)" in manual
    assert "the source .txt file does not need to remain present or unchanged" in manual
    assert "Q: What can I put in Copy Request Path(s)?" in faq
    assert "c:\\tmpBoots; c:\\tlo\\copyMe.txt; Allman Brothers Band" in faq
