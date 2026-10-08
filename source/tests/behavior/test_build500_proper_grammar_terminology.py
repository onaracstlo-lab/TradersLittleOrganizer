"""Build 500 regressions for Proper Grammar terminology and unreleased CLI cleanup."""
from tests import _release_artifacts as RA


import argparse
from pathlib import Path

import pytest

from tlo_options import OPTIONS_BY_FIELD, add_options_to_parser
from tlo_ux import MAIN_WINDOW_CHECKBOX_SPECS

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build500_gui_and_config_use_proper_grammar_name_only():
    assert "proper_grammar" in OPTIONS_BY_FIELD
    assert "old_grammar" not in OPTIONS_BY_FIELD
    option = OPTIONS_BY_FIELD["proper_grammar"]
    assert option.gui_label == "Proper Grammar"
    assert option.flag == "--proper-grammar"
    assert (option.gui_row, option.gui_col) == (3, 1)
    assert ("proper_grammar", "Proper Grammar") in MAIN_WINDOW_CHECKBOX_SPECS


def test_build500_cli_accepts_only_proper_grammar_spelling():
    parser = argparse.ArgumentParser(add_help=False)
    add_options_to_parser(parser, ["proper_grammar"])
    assert parser.parse_args(["--proper-grammar"]).proper_grammar is True
    with pytest.raises(SystemExit):
        parser.parse_args(["--old-grammar"])


def test_build500_source_has_no_old_grammar_identifiers_or_label():
    targets = [
        "tlo_options.py", "tlo_ux.py", "tlo-main.py", "tlo_phase23_v2.py",
        "tlo_tag_lib.py", "tlo_artist_db.py", "inventory_parser_lib.py", "walk_trees_lib.py",
    ]
    combined = "\n".join((ROOT / name).read_text(encoding="utf-8") for name in targets)
    assert "old_grammar" not in combined
    assert "Old Grammar" not in combined
    assert "--old-grammar" not in combined
    assert "proper_grammar" in combined
    assert "Proper Grammar" in combined


def test_build500_current_docs_use_proper_grammar_and_current_version():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / RA.REQUIREMENTS_FILENAME).paragraphs)
    manual = (ROOT / RA.MANUAL_FILENAME).read_text(encoding="utf-8", errors="ignore")
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "Build 498: Proper Grammar artist naming" in req
    assert "Build 500: Proper Grammar terminology" in req
    assert "Proper Grammar" in manual
    assert "--proper-grammar" in changes
