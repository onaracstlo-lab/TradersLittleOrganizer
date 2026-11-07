"""Build 615: dated show siblings labelled 'CD1 final'/'CD2 final'."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior

SHOW = "Bill Wyman & The Rhythm Kings 2004-07-11 Mirande, France, Festival De Country Music [Previously Uncirculated]"


def _fixture(tmp_path: Path, names=("CD1 final", "CD2 final"), counts=(16, 6), with_setlist=True):
    root = tmp_path / "archive"
    show = root / SHOW
    music = []
    for disc, (name, count) in enumerate(zip(names, counts)):
        folder = show / name
        folder.mkdir(parents=True)
        for track_number in range(1, count + 1):
            track = folder / f"{track_number:02d} - disc {disc + 1} track.flac"
            track.write_bytes(f"audio-{disc + 1}-{track_number}".encode())
            music.append(track)
    notes = show / "textfile.txt"
    if with_setlist:
        notes.write_text("Bill Wyman's Rhythm Kings\nMirande, France\n2004-07-11\n", encoding="utf-8")
    return root, show, music, notes


def _groups(tmp_path, root, music, *, compliant=False, extra_paths=()):
    log = tmp_path / "complete_paths.log"
    log.write_text("SEARCH_PATH: " + str(root) + "\n" + "\n".join(str(f) for f in (*music, *extra_paths)) + "\n", encoding="utf-8")
    config = SimpleNamespace(compliant=compliant, performance_mode="balanced", logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))))
    return phase._build_groups_from_search_path(config, str(root))


def test_bill_wyman_cd_final_pair_aggregates_and_finds_shared_setlist(tmp_path):
    root, show, music, notes = _fixture(tmp_path)
    groups = _groups(tmp_path, root, music, extra_paths=(notes,))
    assert len(groups) == 1
    group = groups[0]
    assert group["main_dir_path"] == str(show)
    assert group["main_dir_name"] == SHOW
    assert group["aggregation_reason"] == "dated_final_disc_siblings"
    assert group["music_file_count"] == 22
    assert group["music_dirs"] == [str(show / "CD1 final"), str(show / "CD2 final")]
    assert group["setlist_file"] == str(notes)
    assert phase._group_trailing_parentheticals(group) == ""


def test_copy_delete_final_disc_pair_preserves_file_structure_and_transfers_once(tmp_path):
    root, show, music, notes = _fixture(tmp_path)
    group = _groups(tmp_path, root, music, extra_paths=(notes,))[0]
    destination = tmp_path / "dest"
    destination.mkdir()
    record = SimpleNamespace(
        show_name="Bill Wyman's Rhythm Kings 2004-07-11 Music Festival Grounds Mirande, France",
        parentheticals="", main_dir_name=SHOW, main_dir_path=str(show),
        setlist_file=str(notes), music_dirs=group["music_dirs"], setlist_files=group["setlist_files"],
        original_main_dir_path="",
    )
    config = SimpleNamespace(tag_copy_and_delete_path=str(destination), rename_compliantly=True)
    updated_group, updated_record = taglib.prepare_inventory_copy_delete_target(config, group, record)
    published = destination / record.show_name
    assert published.is_dir() and not show.exists()
    assert updated_record.main_dir_path == str(published)
    assert updated_group["main_dir_path"] == str(published)
    assert (published / "textfile.txt").is_file()
    assert len(list(published.rglob("*.flac"))) == 22
    assert sorted(p.name for p in published.iterdir()) == ["CD1 final", "CD2 final", "textfile.txt"]
    assert len(list(destination.iterdir())) == 1


@pytest.mark.parametrize("names", [
    ("CD 1 final", "CD 2 final"),
    ("Disc 1 FINAL", "Disc 2 final"),
    ("CD1-final", "CD2-final"),
    ("Set one final", "Set two final"),
])
def test_conservative_disc_final_spelling_variants(tmp_path, names):
    root, show, music, _notes = _fixture(tmp_path, names=names, counts=(2, 2))
    assert [g["main_dir_path"] for g in _groups(tmp_path, root, music)] == [str(show)]


@pytest.mark.parametrize("names", [
    ("CD1 final",),
    ("CD2 final",),
    ("CD1 final", "CD1 final copy"),
    ("CD1 final", "CD3 final"),
    ("CD1 final", "Opening Artist"),
    ("CD1 final", "Other Band 2004-07-12 Venue City, ST"),
])
def test_lone_incomplete_or_unrelated_siblings_remain_separate(tmp_path, names):
    root, show, music, _notes = _fixture(tmp_path, names=names, counts=tuple(2 for _ in names))
    groups = _groups(tmp_path, root, music)
    assert all(group["main_dir_path"] != str(show) for group in groups)


def test_undated_collection_preserves_individual_disc_final_names(tmp_path):
    root, show, music, _notes = _fixture(tmp_path, counts=(2, 2))
    undated = root / "Country Music CD Collection"
    show.rename(undated)
    migrated = [undated / name / path.name for path in music for name in (path.parent.name,)]
    assert len(_groups(tmp_path, root, migrated)) == 2


def test_direct_audio_below_show_must_not_overlap_final_disc_pair(tmp_path):
    root, show, music, _notes = _fixture(tmp_path, counts=(2, 2))
    direct = show / "01 direct.flac"
    direct.write_bytes(b"audio")
    groups = _groups(tmp_path, root, music + [direct])
    assert all(group["aggregation_reason"] != "dated_final_disc_siblings" for group in groups)


def test_compliant_mode_keeps_two_disc_final_folders(tmp_path):
    root, show, music, _notes = _fixture(tmp_path, counts=(2, 2))
    groups = _groups(tmp_path, root, music, compliant=True)
    assert len(groups) == 2
    assert {group["main_dir_path"] for group in groups} == {str(show / "CD1 final"), str(show / "CD2 final")}


def test_grouping_must_not_consult_flac_tags(tmp_path, monkeypatch):
    root, show, music, _notes = _fixture(tmp_path, counts=(2, 2))
    monkeypatch.setattr(phase, "collect_group_flac_tag_info", lambda *_args, **_kwargs: {
        "flac_tag_artist_values": ["Unrelated Artist"], "flac_tag_album_values": ["Other Show"]
    })
    groups = _groups(tmp_path, root, music)
    assert len(groups) == 1 and groups[0]["main_dir_path"] == str(show)


def test_initial_directory_walk_discovers_and_aggregates_final_disc_tree(tmp_path):
    """Use the real Phase 1 directory walker, not only synthetic complete logs."""
    import logging_lib
    from initial_dir_walk_lib import initial_dir_walk

    root, show, music, notes = _fixture(tmp_path)
    config = SimpleNamespace(
        TLOHome=str(tmp_path / "home"), performance_mode="balanced",
        silent=True, compliant=False,
    )
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(root), 1, log_token="W")
    initial_dir_walk(config, str(root))
    groups = phase._build_groups_from_search_path(config, str(root))
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(show)
    assert groups[0]["music_file_count"] == len(music) == 22
    assert groups[0]["setlist_file"] == str(notes)
