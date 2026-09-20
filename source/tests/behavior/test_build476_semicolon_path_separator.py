"""Build 476: Path(s) uses semicolons; commas are ordinary path characters."""

from pathlib import Path

import pytest

import inventory_list_lib as IL
import tlo_dragdrop as DD

pytestmark = pytest.mark.behavior


def _music_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "01.flac").write_bytes(b"x")
    return path


def test_build476_semicolon_separates_direct_entries(tmp_path):
    one = _music_dir(tmp_path / "one")
    two = _music_dir(tmp_path / "two")
    parsed = IL.parse_search_path_input(f"{one};{two}")
    assert [item[1] for item in parsed] == [str(one), str(two)]


def test_build476_unquoted_comma_is_literal_path_text(tmp_path):
    folder = _music_dir(tmp_path / "Dudek, Les")
    parsed = IL.parse_search_path_input(str(folder))
    assert len(parsed) == 1
    assert parsed[0][1] == str(folder)


def test_build476_quotes_remain_optional_for_comma_path(tmp_path):
    folder = _music_dir(tmp_path / "Artist, City, ST")
    plain = IL.parse_search_path_input(str(folder))
    quoted = IL.parse_search_path_input(f'"{folder}"')
    assert plain[0][1] == quoted[0][1] == str(folder)


def test_build476_dragdrop_joiner_is_semicolon_and_does_not_quote_commas():
    assert DD._append_search_path_drop_values("A", ["B", "C,D"]) == "A;B;C,D"
