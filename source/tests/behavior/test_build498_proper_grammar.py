"""Build 498 regressions for the main-GUI Proper Grammar artist-name preference."""

__version__ = "v499"

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher, proper_grammar_artist_name
from tlo_models import ShowMetadata
from tlo_options import OPTIONS_BY_FIELD
import tlo_phase23_v2 as phase
from tlo_tag_lib import build_tagger_config
from tlo_ux import main_window_checkbox_values

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _matcher():
    matcher = ArtistMatcher(db_path="test")
    matcher.master_aliases = {
        "John Smith": ["John Smith", "Smith, John"],
        "The Kinks": ["The Kinks", "Kinks", "Kinks, The"],
        "Emerson, Lake & Palmer": ["Emerson, Lake & Palmer", "ELP"],
        "Bob Dylan": ["Bob Dylan", "Dylan, Bob"],
    }
    return matcher


def _record(artist="John Smith"):
    return ShowMetadata(
        group_number=1,
        main_dir_name="show",
        main_dir_path="/music/show",
        setlist_file="",
        music_file_count=1,
        artist=artist,
        date="2000-01-01",
        venue="Club",
        location="Boston, MA",
    )


def test_build498_gui_option_is_under_as_is_and_defaults_unchecked():
    option = OPTIONS_BY_FIELD["proper_grammar"]
    assert option.gui_label == "Proper Grammar"
    assert (option.gui_row, option.gui_col) == (3, 1)
    assert option.default is False
    assert OPTIONS_BY_FIELD["as_is_artist_name"].gui_row == 2
    assert OPTIONS_BY_FIELD["as_is_artist_name"].gui_col == 1


def test_build498_person_and_article_aliases_are_selected_conservatively():
    matcher = _matcher()
    assert proper_grammar_artist_name("John Smith", matcher) == "Smith, John"
    assert proper_grammar_artist_name("The Kinks", matcher) == "Kinks, The"
    assert proper_grammar_artist_name("Kinks", matcher) == "Kinks, The"


def test_build498_comma_band_name_is_not_mistaken_for_last_first():
    matcher = _matcher()
    assert proper_grammar_artist_name("Emerson, Lake & Palmer", matcher) == "Emerson, Lake & Palmer"


def test_build498_collaborations_apply_preference_per_known_artist():
    matcher = _matcher()
    assert proper_grammar_artist_name("John Smith & Bob Dylan", matcher) == "Smith, John & Dylan, Bob"


def test_build498_proper_grammar_changes_artist_before_show_name_construction():
    record = _record()
    observations = []
    config = SimpleNamespace(proper_grammar=True, as_is_artist_name=False, compliant_artist_mode="master")
    phase._apply_proper_grammar_artist_output(config, record, _matcher(), observations)
    record.show_name = phase._build_show_name(record)
    assert record.artist == "Smith, John"
    assert record.show_name.startswith("Smith, John 2000-01-01")
    assert any("Proper Grammar artist output selected" in line for line in observations)


def test_build498_as_is_artist_name_overrides_proper_grammar():
    record = _record("John Smith")
    observations = []
    config = SimpleNamespace(proper_grammar=True, as_is_artist_name=True, compliant_artist_mode="as-is")
    phase._apply_proper_grammar_artist_output(config, record, _matcher(), observations)
    assert record.artist == "John Smith"
    assert observations == []


def test_build498_proper_grammar_falls_back_to_current_name_when_no_matching_alias_exists():
    record = _record("Emerson, Lake & Palmer")
    observations = []
    config = SimpleNamespace(proper_grammar=True, as_is_artist_name=False, compliant_artist_mode="master")
    phase._apply_proper_grammar_artist_output(config, record, _matcher(), observations)
    assert record.artist == "Emerson, Lake & Palmer"
    assert observations == []


def test_build498_main_gui_and_active_tag_path_carry_proper_grammar_state(tmp_path):
    values = main_window_checkbox_values({"proper_grammar": True, "as_is_artist_name": False})
    assert values["proper_grammar"] is True
    config = build_tagger_config(tlo_home=str(tmp_path), proper_grammar=True)
    assert config.proper_grammar is True
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'proper_grammar=bool(getattr(self.bool_vars.get("proper_grammar"), "get", lambda: False)())' in source
    assert "class TaggerWindow" not in source
    start = source.index("    def _start_tagging_from_main(self):")
    end = source.index("    def _open_manual_updates(self):", start)
    tag_source = source[start:end]
    assert "config = self._build_config()" in tag_source
    assert "run_tagger_jobs(config, jobs, emit=self.queue.put)" in tag_source
    assert 'self.config.proper_grammar = bool(values.get("proper_grammar", False))' in source


def test_build498_documentation_records_proper_grammar_contract():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v510.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v510.rtf").read_text(encoding="utf-8", errors="ignore")
    changes = (ROOT / "CHANGES_v510.txt").read_text(encoding="utf-8")

    assert "Current document version: v510 (TLO v1.7)." in req
    assert "Build 498: Proper Grammar artist naming" in req
    assert "As-Is Artist Name always overrides and suppresses Proper Grammar output conversion" in req
    assert "Kinks, The" in req and "Smith, John" in req
    assert "Version v1.7 Build 510" in manual
    assert "Proper Grammar is directly beneath As-Is Artist Name and defaults unchecked" in manual
    assert "Carries forward all Build 499 and earlier behavior" in changes
