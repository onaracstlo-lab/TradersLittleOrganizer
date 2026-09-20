"""Build 477 regressions incorporated into the complete Build 478 bundle."""

from pathlib import Path

import pytest

import inventory_list_lib as IL
import tlo_phase23_v2 as P23
from tlo_models import ShowMetadata

pytestmark = pytest.mark.behavior
__version__ = "v478"


ROOT = Path(__file__).resolve().parents[2]


def test_build477_manual_updates_new_name_drop_does_not_require_original_folder():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("    def _new_name_drop_enabled(self):")
    end = source.index("    def _original_changed", start)
    method = source[start:end]
    assert 'return not value.lower().endswith(".txt")' in method
    assert "os.path.isdir" not in method


def test_build477_apostrophe_is_ordinary_search_path_text():
    value = r"F:\boots\tito puente's golden latin jazz all stars 1994-07-24 kirjurinluoto pori, Finland"
    assert IL._split_search_path_entries(value) == [value]


def test_build477_apostrophes_do_not_break_semicolon_multiple_paths():
    first = r"F:\boots\Tito Puente's Show"
    second = r"G:\boots\Nick Vollebregt's Jazz Cafe"
    assert IL._split_search_path_entries(f"{first};{second}") == [first, second]


def test_build477_unmatched_double_quote_still_reports_malformed_explicit_quoting():
    with pytest.raises(ValueError, match="unmatched quote"):
        IL._split_search_path_entries('"F:\\boots\\one;G:\\boots\\two')


def test_build477_online_lookup_can_correct_case_but_not_replace_path_metadata():
    record = ShowMetadata(
        group_number=1,
        main_dir_name="show",
        main_dir_path="/show",
        setlist_file="",
        music_file_count=1,
        venue="kirjurinluoto",
        city="pori",
        country="Finland",
        location="pori, Finland",
    )
    evidence = {}
    observations = []
    changed = P23._apply_online_fields_fill_blanks(
        record,
        evidence,
        observations,
        "setlist.fm",
        90,
        "Kirjurinluoto",
        "Pori",
        "",
        "Finland",
        "Pori, Finland",
    )
    assert changed is True
    assert record.venue == "Kirjurinluoto"
    assert record.city == "Pori"
    assert record.location == "Pori, Finland"
    assert any("corrected capitalization" in item for item in observations)

    P23._apply_online_fields_fill_blanks(
        record,
        evidence,
        observations,
        "setlist.fm",
        90,
        "Rauma Factory",
        "Pori",
        "",
        "Finland",
        "Pori, Finland",
    )
    assert record.venue == "Kirjurinluoto"
