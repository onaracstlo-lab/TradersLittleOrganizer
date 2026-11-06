"""Build 611: structure-first reinventory of dated shows with named part children."""

from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior

SHOW = "Return to Forever 1976-03-07 Olympia Paris, France"


def _fixture(tmp_path, names=None):
    names = names or (f"{SHOW} (copy1)", f"{SHOW} (two)")
    root = tmp_path / "inventory" / SHOW
    files = []
    for i, name in enumerate(names):
        folder = root / name
        folder.mkdir(parents=True)
        for track in range(1 + (i * 6), 7 + (i * 6)):
            music = folder / f"{track:02d} test.flac"
            music.write_bytes(f"track{track}".encode("ascii"))
            files.append(music)
    return root, files


def _groups(search, files, *, compliant=False):
    log = search.parent / "music-entries.log"
    log.write_text("SEARCH_PATH: " + str(search) + "\n" + "\n".join(str(f) for f in files) + "\n", encoding="utf-8")
    config = SimpleNamespace(compliant=compliant, performance_mode="balanced", logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))))
    return phase._build_groups_from_search_path(config, str(search))


def test_manual_named_parent_and_original_reinventory_are_single_show(tmp_path):
    root, files = _fixture(tmp_path)
    groups = _groups(tmp_path / "inventory", files)
    assert len(groups) == 1
    g = groups[0]
    assert g["main_dir_name"] == SHOW
    assert g["main_dir_path"] == str(root)
    assert g["aggregation_reason"] == "dated_named_show_parts"
    assert g["music_file_count"] == 12
    assert len(g["music_dirs"]) == 2
    assert g["setlist_file"] == ""
    # The recorded child suffixes are physical grouping labels, never show qualifiers.
    assert phase._group_trailing_parentheticals(g) == ""


def test_metadata_resolves_one_show_without_child_qualifiers_or_setlist(tmp_path):
    from tlo_artist_db import ArtistMatcher

    root, files = _fixture(tmp_path)
    group = _groups(tmp_path / "inventory", files)[0]
    group["group_number"] = 1
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"return to forever": {"Return to Forever"}}
    matcher.master_aliases = {"Return to Forever": ["Return to Forever"]}
    matcher.master_norms = {"Return to Forever": {"returntoforever"}}
    conf = SimpleNamespace(
        compliant=False, current_volume_label="", current_slam="", as_is_artist_name=False,
        compliant_artist_mode="master", etree_lookup=False, setlistfm_lookup=False,
        thorough_setlist_matching=False, tlo_dbs_dir=str(tmp_path),
        venue_reference_db_file=str(tmp_path / "venues.txt"), debug=False,
    )
    record, _dates, unresolved = phase._extract_metadata_for_group(conf, group, matcher)
    assert not unresolved
    assert record.artist == "Return to Forever"
    assert record.date == "1976-03-07"
    assert record.show_name == SHOW
    assert not record.parentheticals
    assert record.music_file_count == 12
    assert record.main_dir_path == str(root)


def test_copy_delete_moves_one_root_and_preserves_both_children(tmp_path):
    root, files = _fixture(tmp_path)
    group = _groups(tmp_path / "inventory", files)[0]
    dest = tmp_path / "update2"
    dest.mkdir()
    config = SimpleNamespace(tag_copy_and_delete_path=str(dest), rename_compliantly=True)
    record = SimpleNamespace(
        show_name=SHOW, parentheticals="", main_dir_name=root.name,
        main_dir_path=str(root), setlist_file="", music_dirs=group["music_dirs"],
        setlist_files=[], original_main_dir_path="",
    )
    new_group, new_record = taglib.prepare_inventory_copy_delete_target(config, group, record)
    published = dest / SHOW
    assert published.is_dir() and not root.exists()
    assert new_record.main_dir_path == str(published)
    assert new_group["main_dir_path"] == str(published)
    assert sorted(p.name for p in published.iterdir()) == sorted([f"{SHOW} (copy1)", f"{SHOW} (two)"])
    assert len(list(published.rglob("*.flac"))) == 12
    assert len(list(dest.iterdir())) == 1
    for original in files:
        rel = original.relative_to(root)
        assert (published / rel).read_bytes() == f"track{int(original.name[:2])}".encode("ascii")


@pytest.mark.parametrize("suffixes", [
    ("(alt1)", "(copy2)"),
    ("(Set 1)", "(Set 2)"),
    ("(CD1)", "(Disc2)"),
    ("(one)", "(two)"),
    ("", "(alt1)"),
])
def test_parent_matched_part_labels_form_one_show(tmp_path, suffixes):
    names = [SHOW + (" " + suffix if suffix else "") for suffix in suffixes]
    root, files = _fixture(tmp_path, names)
    groups = _groups(tmp_path / "inventory", files)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(root)
    assert phase._group_trailing_parentheticals(groups[0]) == ""


def test_tag_values_must_not_affect_folder_grouping(tmp_path, monkeypatch):
    root, files = _fixture(tmp_path)
    def conflicting(_samples, **_kwargs):
        return {"flac_tag_artist_values": ["Opening Act"], "flac_tag_albumartist_values": []}
    monkeypatch.setattr(phase, "collect_group_flac_tag_info", conflicting)
    groups = _groups(tmp_path / "inventory", files)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(root)


def test_unrelated_artist_child_is_not_merged(tmp_path):
    _root, files = _fixture(tmp_path)
    other = _root / "Opening Act"
    other.mkdir()
    song = other / "01 opening.flac"
    song.write_bytes(b"opening")
    groups = _groups(tmp_path / "inventory", files + [song])
    assert len(groups) == 3


def test_other_dated_show_child_is_not_merged(tmp_path):
    root, files = _fixture(tmp_path, (f"{SHOW} (copy1)", "Other Band 1976-03-07 Other Venue Paris, France"))
    assert len(_groups(tmp_path / "inventory", files)) == 2
    assert root.exists()


def test_single_child_keeps_its_name_and_legacy_copy_identity(tmp_path):
    root, files = _fixture(tmp_path, (f"{SHOW} (copy1)",))
    groups = _groups(tmp_path / "inventory", files)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(root / f"{SHOW} (copy1)")
    assert groups[0]["aggregation_reason"] != "dated_named_show_parts"


def test_standalone_disc_set_name_is_valid(tmp_path):
    show = tmp_path / "archive" / f"{SHOW} (Set 1)"
    show.mkdir(parents=True)
    track = show / "01.flac"
    track.write_bytes(b"audio")
    groups = _groups(tmp_path / "archive", [track])
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(show)


def test_compliant_stays_path_only_and_separate(tmp_path):
    root, files = _fixture(tmp_path)
    groups = _groups(tmp_path / "inventory", files, compliant=True)
    assert len(groups) == 2
    assert all(g["main_dir_path"] != str(root) for g in groups)


def test_nonmatching_parent_name_never_claims_child_parts(tmp_path):
    show = tmp_path / "archive" / "1976-03-07 collection"
    a = show / f"{SHOW} (copy1)"
    b = show / f"{SHOW} (two)"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    tracks = []
    for part in (a, b):
        track = part / "01.flac"
        track.write_bytes(b"audio")
        tracks.append(track)
    assert len(_groups(tmp_path / "archive", tracks)) == 2


def test_explicit_alternate_editions_with_restarted_track_numbers_still_group(tmp_path):
    root, _files = _fixture(tmp_path, (f"{SHOW} (copy1)", f"{SHOW} (alt1)"))
    second = root / f"{SHOW} (alt1)"
    for track in second.glob("*.flac"):
        track.rename(second / f"{int(track.name[:2]) - 6:02d} other.flac")
    files = sorted(root.rglob("*.flac"))
    groups = _groups(tmp_path / "inventory", files)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(root)
    assert groups[0]["music_file_count"] == 12
