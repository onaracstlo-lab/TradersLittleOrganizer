"""Build 612: extend Build 611 structural parts through ordinary disc wrappers only."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior

SHOW = "Return to Forever 1976-03-07 Olympia Paris, France"


def _make_tree(tmp_path: Path, branches=None, child_wrapper="CD1"):
    branches = branches or (f"{SHOW} (one)", f"{SHOW} (two)")
    root = tmp_path / "archive" / SHOW
    music = []
    for n, branch in enumerate(branches):
        part = root / branch
        if child_wrapper:
            part = part / child_wrapper
        part.mkdir(parents=True)
        for track in (1, 2, 3):
            file = part / f"{track + 3 * n:02d} song.flac"
            file.write_bytes(f"data-{n}-{track}".encode())
            music.append(file)
    return root, music


def _groups(tmp_path, tracks, *, compliant=False, start=None):
    root = start or (tmp_path / "archive")
    log = tmp_path / "complete.txt"
    log.write_text("SEARCH_PATH: " + str(root) + "\n" + "\n".join(str(x) for x in tracks) + "\n", encoding="utf-8")
    config = SimpleNamespace(
        compliant=compliant, performance_mode="balanced",
        logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))),
    )
    return phase._build_groups_from_search_path(config, str(root))


@pytest.mark.parametrize("branches,wrapper", [
    ((f"{SHOW} (one)", f"{SHOW} (two)"), "CD1"),
    ((f"{SHOW} (copy1)", f"{SHOW} (two)"), "flac"),
    ((f"{SHOW} (alt1)", f"{SHOW} (alt2)"), "Set 1"),
    ((SHOW, f"{SHOW} (copy1)"), "Disc 1"),
])
def test_part_branches_with_inner_wrappers_are_one_show(tmp_path, branches, wrapper):
    root, tracks = _make_tree(tmp_path, branches, wrapper)
    groups = _groups(tmp_path, tracks)
    assert len(groups) == 1
    group = groups[0]
    assert group["main_dir_path"] == str(root)
    assert group["main_dir_name"] == SHOW
    assert group["aggregation_reason"] == "dated_named_show_parts"
    assert group["music_file_count"] == 6
    assert len(group["music_dirs"]) == 2
    assert phase._group_trailing_parentheticals(group) == ""


def test_multiple_media_levels_are_allowed_without_flattening(tmp_path):
    root, tracks = _make_tree(tmp_path, child_wrapper="CD 1")
    # Move one of the recordings under a deeper, still-supplemental FLAC wrapper.
    old = root / f"{SHOW} (one)" / "CD 1"
    (old / "flac").mkdir()
    for track in list(old.glob("*.flac")):
        track.rename(old / "flac" / track.name)
    all_tracks = sorted(root.rglob("*.flac"))
    groups = _groups(tmp_path, all_tracks)
    assert len(groups) == 1
    assert groups[0]["music_file_count"] == 6
    dest = tmp_path / "dest"
    dest.mkdir()
    record = SimpleNamespace(show_name=SHOW, parentheticals="", main_dir_name=SHOW,
        main_dir_path=str(root), setlist_file="", music_dirs=groups[0]["music_dirs"],
        setlist_files=[], original_main_dir_path="")
    config = SimpleNamespace(tag_copy_and_delete_path=str(dest), rename_compliantly=True)
    _group, updated = taglib.prepare_inventory_copy_delete_target(config, groups[0], record)
    assert updated.main_dir_path == str(dest / SHOW)
    assert len(list((dest / SHOW).rglob("*.flac"))) == 6
    assert (dest / SHOW / f"{SHOW} (one)" / "CD 1" / "flac").is_dir()
    assert len(list(dest.iterdir())) == 1


@pytest.mark.parametrize("bad_wrapper", [
    "Opening Artist", "Other Band 1976-03-08", "New Show", "1977-06-01",
])
def test_named_child_containing_independent_branch_must_not_merge(tmp_path, bad_wrapper):
    root, tracks = _make_tree(tmp_path, child_wrapper="")
    part = root / f"{SHOW} (one)" / bad_wrapper
    part.mkdir(parents=True)
    extra = part / "01 independent.flac"
    extra.write_bytes(b"unrelated")
    groups = _groups(tmp_path, tracks + [extra])
    assert len(groups) > 1
    assert all(group["main_dir_path"] != str(root) for group in groups)


def test_unrelated_direct_audio_prevents_merging(tmp_path):
    root, tracks = _make_tree(tmp_path, child_wrapper="CD1")
    other = root / "Opening Artist"
    other.mkdir()
    track = other / "01 opening.flac"
    track.write_bytes(b"opening")
    groups = _groups(tmp_path, tracks + [track])
    assert len(groups) > 1
    assert all(group["main_dir_path"] != str(root) for group in groups)


def test_lone_part_keeps_standalone_identity(tmp_path):
    root, tracks = _make_tree(tmp_path, (f"{SHOW} (Set 1)",), "CD1")
    groups = _groups(tmp_path, tracks)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] != str(root)
    assert groups[0]["main_dir_path"] == str(root / f"{SHOW} (Set 1)")


def test_compliant_mode_keeps_individual_music_directories(tmp_path):
    root, tracks = _make_tree(tmp_path)
    groups = _groups(tmp_path, tracks, compliant=True)
    assert len(groups) == 2
    assert all(group["main_dir_path"] != str(root) for group in groups)


def test_tags_cannot_split_or_merge_part_branches(tmp_path, monkeypatch):
    root, tracks = _make_tree(tmp_path)
    monkeypatch.setattr(phase, "collect_group_flac_tag_info", lambda *_args, **_kwargs: {
        "flac_tag_artist_values": ["Different Artist"],
        "flac_tag_album_values": ["Incorrect old album"],
    })
    groups = _groups(tmp_path, tracks)
    assert len(groups) == 1 and groups[0]["main_dir_path"] == str(root)
