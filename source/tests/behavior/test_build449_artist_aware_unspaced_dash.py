"""Build 449 regressions for artist-aware Artist/Album dash parsing."""

__version__ = "v468"

import os
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


VAN_MORRISON_FOLDERS = [
    "Van Morrison-A Sense of Wonder Live",
    "Van Morrison-Astral Weeks Live",
    "Van Morrison-Avalon Sunset Live",
    "Van Morrison-Back On Top Live",
    "Van Morrison-Beautiful Vision Live",
    "Van Morrison-Common One Live",
    "Van Morrison-Days Like This Live",
    "Van Morrison-Enlightenment Live",
    "Van Morrison-His Band and the Street Choir-Tupelo Honey Live",
    "Van Morrison-HLHTBGO Live",
    "Van Morrison-Hymns To The Silence Live",
    "Van Morrison-Inarticulate Speech of the Heart Live",
    "Van Morrison-Into The Music Live",
    "Van Morrison-Irish Heartbeat Live",
    "Van Morrison-Moondance Live",
    "Van Morrison-Poetic Champions Compose Live",
    "Van Morrison-Saint Dominic's Preview-Hard Nose The Highway Live",
    "Van Morrison-The 90s Workshops",
    "Van Morrison-The Healing Game Live",
]


def _matcher():
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "van morrison": {"Van Morrison"},
        "morrison, van": {"Van Morrison"},
        "x-ray spex": {"X-Ray Spex"},
    }
    matcher.master_aliases = {
        "Van Morrison": ["Van Morrison", "Morrison, Van"],
        "X-Ray Spex": ["X-Ray Spex"],
    }
    matcher.master_norms = {
        "Van Morrison": {"vanmorrison", "morrisonvan"},
        "X-Ray Spex": {"xrayspex"},
    }
    return matcher


def _config(compliant=False):
    return SimpleNamespace(
        compliant=compliant,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        setlistfm_upgrade=False,
        TLOHome=os.path.join(os.sep, "tmp", "tlo-build449"),
    )


def _group(folder_name):
    path = os.path.join(os.sep, "music", "M", "Morrison, Van", folder_name)
    return {
        "group_number": 1,
        "main_dir_name": folder_name,
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 1,
        "setlist_files": [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


@pytest.mark.parametrize("folder_name", VAN_MORRISON_FOLDERS)
def test_van_morrison_unspaced_artist_album_folders_become_distinct_album_records(folder_name):
    import tlo_phase23_v2 as phase

    record, _dates, unresolved = phase._extract_metadata_for_group(
        _config(), _group(folder_name), _matcher()
    )

    expected_album = folder_name[len("Van Morrison-"):]
    assert unresolved == []
    assert record.artist == "Van Morrison"
    assert record.date == ""
    assert record.album_name == expected_album
    assert record.show_name == f"Van Morrison - {expected_album}"
    assert "xxxx-xx-xx" not in record.show_name


def test_only_the_artist_delimiting_dash_is_split_and_later_album_dashes_are_preserved():
    import tlo_phase23_v2 as phase

    folder_name = "Van Morrison-Saint Dominic's Preview-Hard Nose The Highway Live"
    row = phase._artist_aware_unspaced_dash_row(folder_name, _matcher())

    assert row is not None
    assert row["string1"] == "Van Morrison"
    assert row["string2"] == "Saint Dominic's Preview-Hard Nose The Highway Live"


@pytest.mark.parametrize(
    "folder_name",
    [
        "Van Morrison - A Sense of Wonder Live",
        "Van Morrison- A Sense of Wonder Live",
        "Van Morrison -A Sense of Wonder Live",
        "Van Morrison-A Sense of Wonder Live",
    ],
)
def test_all_spacing_forms_around_artist_album_dash_are_accepted(folder_name):
    import tlo_phase23_v2 as phase

    record, _dates, unresolved = phase._extract_metadata_for_group(
        _config(), _group(folder_name), _matcher()
    )

    assert unresolved == []
    assert record.artist == "Van Morrison"
    assert record.album_name == "A Sense of Wonder Live"
    assert record.show_name == "Van Morrison - A Sense of Wonder Live"


def test_relaxed_unspaced_dash_is_not_used_when_left_side_is_not_a_unique_artist_db_match():
    import tlo_phase23_v2 as phase

    assert phase._artist_aware_unspaced_dash_row(
        "Definitely Not An Artist-A Sense of Wonder Live", _matcher()
    ) is None


def test_hyphen_inside_artist_name_is_not_mistaken_for_the_album_separator():
    import tlo_phase23_v2 as phase

    row = phase._artist_aware_unspaced_dash_row("X-Ray Spex-Germfree Adolescents", _matcher())

    assert row is not None
    assert row["string1"] == "X-Ray Spex"
    assert row["string2"] == "Germfree Adolescents"


def test_compliant_mode_also_accepts_db_confirmed_unspaced_artist_album_separator():
    import tlo_phase23_v2 as phase

    record, _dates, unresolved = phase._extract_metadata_for_group(
        _config(compliant=True), _group("Van Morrison-Astral Weeks Live"), _matcher()
    )

    assert unresolved == []
    assert record.artist == "Van Morrison"
    assert record.date == ""
    assert record.album_name == "Astral Weeks Live"
    assert record.show_name == "Van Morrison - Astral Weeks Live"


def test_build449_documentation_describes_artist_aware_dash_spacing():
    from pathlib import Path
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = "\n".join(p.text for p in Document(root / "TLO_Inventory_Requirements_Working_v471.docx").paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v471.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Artist - Album, Artist- Album, Artist -Album, and Artist-Album" in req
    assert "preserve every later dash in String2" in req
    assert "Van Morrison-Saint Dominic's Preview-Hard Nose The Highway Live" in req
    assert "Artist/Album dash spacing" in manual
    assert "Missing spaces around the first Artist/Album dash" in manual
