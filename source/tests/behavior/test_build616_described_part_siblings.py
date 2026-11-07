"""Build 616: context-guarded grouping of numeric, cardinal and ordinal disc labels."""

from pathlib import Path

import pytest

from tests.behavior.test_build615_final_disc_siblings import _fixture, _groups

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize("names", [
    ("CD1 fixed", "CD two remastered"),
    ("Disc first FLAC16", "Disc 2 24bit"),
    ("Set one SBD", "Set 2 AUD"),
    ("CD1", "CD two"),
    ("Tape first corrected", "Tape second final"),
    ("CD1 final flac16", "CD2 remastered fixed"),
    ("CD one", "CD 2", "CD third v2"),
    ("CD1 SBD", "CD2 SBD"),
])
def test_mixed_label_complete_sequences_aggregate(tmp_path: Path, names):
    root, show, music, _notes = _fixture(tmp_path, names=names, counts=(2,) * len(names))
    groups = _groups(tmp_path, root, music)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(show)
    assert groups[0]["music_file_count"] == 2 * len(names)
    assert groups[0]["aggregation_reason"] == "dated_described_part_siblings"


@pytest.mark.parametrize("names", [
    ("CD one edited",),
    ("CD two remastered",),
    ("CD1 SBD", "CD one AUD"),
    ("CD1 final", "CD3 remastered"),
    ("CD first", "Other Band"),
    ("CD1 final", "CD2 2005-07-12 other performance"),
])
def test_incomplete_ambiguous_or_conflicting_sequences_do_not_aggregate(tmp_path: Path, names):
    root, show, music, _notes = _fixture(tmp_path, names=names, counts=(2,) * len(names))
    groups = _groups(tmp_path, root, music)
    assert all(g["main_dir_path"] != str(show) for g in groups)


def test_no_tag_evidence_and_compliant_mode(tmp_path: Path, monkeypatch):
    import tlo_phase23_v2 as phase
    root, show, music, _notes = _fixture(tmp_path, names=("CD1 new", "CD two 16bit"), counts=(2, 2))
    monkeypatch.setattr(phase, "collect_group_flac_tag_info", lambda *_a, **_k: {
        "flac_tag_artist_values": ["Wrong Band"]
    })
    assert len(_groups(tmp_path, root, music)) == 1
    assert len(_groups(tmp_path, root, music, compliant=True)) == 2
