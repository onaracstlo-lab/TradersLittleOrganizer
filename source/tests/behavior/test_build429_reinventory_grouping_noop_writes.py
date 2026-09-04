"""Build 429 regressions for re-inventory grouping, reconciliation, and no-op mutations."""

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_inventory_update as update
import tlo_phase23_v2 as phase
import tlo_postprocess as post
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior


def _audio(folder: Path, names=("01.flac",)):
    folder.mkdir(parents=True, exist_ok=True)
    for name in names:
        (folder / name).write_bytes(b"audio")


def _complete_log(root: Path) -> Path:
    log = root / "comp.log"
    rows = [f"# completePathLog for search path: {root}", f"SEARCH_PATH: {root}"]
    rows.extend(str(path) for path in sorted(root.rglob("*.flac")))
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return log


def _config(log: Path):
    return SimpleNamespace(
        compliant=False,
        logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))),
        performance_mode="balanced",
    )


@pytest.mark.parametrize(
    "relative",
    [
        ("Source 2 EXTRAS",),
        ("Right Channel (Soundboard Feed)",),
        ("Open Mic Lithium",),
        ("art-docs",),
        ("Concert Pictures", "Video"),
        ("Disc 1", "Flac"),
        ("Disc end tracks",),
    ],
)
def test_dated_show_supplemental_descendants_do_not_become_independent_shows(tmp_path, relative):
    root = tmp_path / "boots"
    show = root / "Artist 1999-04-03 Venue City, ST"
    target = show.joinpath(*relative)
    _audio(target, ("01.flac", "02.flac"))
    log = _complete_log(root)

    groups = phase._build_groups_from_search_path(_config(log), str(root))

    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == os.path.normpath(str(show))
    assert groups[0]["music_file_count"] == 2


def test_unrelated_nested_show_blocks_supplemental_promotion(tmp_path):
    root = tmp_path / "boots"
    show = root / "Main Artist 1999-04-03 Venue City, ST"
    _audio(show / "EXTRAS", ("01.flac",))
    opening = show / "Opening Artist 1999-04-03 Other Venue City, ST"
    _audio(opening, ("01.flac",))
    log = _complete_log(root)

    groups = phase._build_groups_from_search_path(_config(log), str(root))

    assert len(groups) == 2
    assert all(group["main_dir_path"] != os.path.normpath(str(show)) for group in groups)


def test_conflicting_tagged_artist_keeps_supplemental_branch_independent(tmp_path, monkeypatch):
    root = tmp_path / "boots"
    show = root / "Main Artist 1999-04-03 Venue City, ST"
    extra = show / "EXTRAS"
    _audio(extra, ("01.flac",))
    log = _complete_log(root)
    monkeypatch.setattr(
        phase,
        "collect_group_flac_tag_info",
        lambda *_args, **_kwargs: {
            "flac_tag_samples": [],
            "flac_tag_artist_values": ["Different Artist"],
            "flac_tag_albumartist_values": [],
            "flac_tag_album_values": [],
            "flac_tag_date_values": [],
        },
    )

    groups = phase._build_groups_from_search_path(_config(log), str(root))

    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == os.path.normpath(str(extra))


def test_root_audio_and_disc_children_collapse_to_one_logical_show(tmp_path):
    root = tmp_path / "boots"
    show = root / "Uriah Heep 1972-05-04 Stadthalle Duisburg, Germany"
    _audio(show, ("sample.mp3",))
    _audio(show / "d1", ("01.flac", "02.flac"))
    _audio(show / "d2", ("01.flac", "02.flac"))
    log = _complete_log(root)
    # Phase-1 test log helper only includes FLAC; include direct root MP3 too.
    with log.open("a", encoding="utf-8") as outfile:
        outfile.write(str(show / "sample.mp3") + "\n")

    groups = phase._build_groups_from_search_path(_config(log), str(root))

    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == os.path.normpath(str(show))
    assert groups[0]["music_file_count"] == 5
    assert len(groups[0]["music_dirs"]) == 3


class _FakeEasyAudio(dict):
    def __init__(self, values):
        super().__init__(values)
        self.tags = self
        self.save_count = 0

    def add_tags(self):
        self.tags = self

    def save(self):
        self.save_count += 1


def test_matching_audio_tags_skip_save(tmp_path, monkeypatch):
    path = tmp_path / "01.flac"
    path.write_bytes(b"audio")
    fake = _FakeEasyAudio({
        "artist": ["Artist"],
        "album": ["Album"],
        "title": ["Song"],
        "tracknumber": ["01"],
    })
    monkeypatch.setattr(taglib, "MutagenFile", lambda *_args, **_kwargs: fake)

    changed = taglib.write_audio_tags(str(path), "Artist", "Album", "01", "Song", total_tracks=1)

    assert changed is False
    assert fake.save_count == 0


def test_extra_existing_value_for_written_tag_forces_save(tmp_path, monkeypatch):
    path = tmp_path / "01.flac"
    path.write_bytes(b"audio")
    fake = _FakeEasyAudio({
        "artist": ["Artist", "Other Artist"],
        "album": ["Album"],
        "title": ["Song"],
        "tracknumber": ["01"],
    })
    monkeypatch.setattr(taglib, "MutagenFile", lambda *_args, **_kwargs: fake)

    changed = taglib.write_audio_tags(str(path), "Artist", "Album", "01", "Song", total_tracks=1)

    assert changed is True
    assert fake.save_count == 1
    assert fake["artist"] == ["Artist"]


def test_obsolete_disc_or_total_tag_forces_save_even_when_main_tags_match(tmp_path, monkeypatch):
    path = tmp_path / "01.flac"
    path.write_bytes(b"audio")
    fake = _FakeEasyAudio({
        "artist": ["Artist"],
        "album": ["Album"],
        "title": ["Song"],
        "tracknumber": ["01"],
        "discnumber": ["1"],
    })
    monkeypatch.setattr(taglib, "MutagenFile", lambda *_args, **_kwargs: fake)

    changed = taglib.write_audio_tags(str(path), "Artist", "Album", "01", "Song", total_tracks=1)

    assert changed is True
    assert fake.save_count == 1
    assert "discnumber" not in fake


def test_inventory_rename_noop_never_calls_os_rename(tmp_path, monkeypatch):
    folder = tmp_path / "Artist 1999-04-03 Venue City, ST"
    folder.mkdir()
    group = {"main_dir_path": str(folder), "main_dir_name": folder.name}
    record = SimpleNamespace(show_name=folder.name, parentheticals="", main_dir_name=folder.name)
    config = SimpleNamespace(rename_compliantly=True, tag_copy_during_inventory=False)
    calls = []
    monkeypatch.setattr(taglib.os, "rename", lambda *args: calls.append(args))

    new_group, _record = taglib.prepare_inventory_tagging_target(config, group, record)

    assert new_group["main_dir_path"] == str(folder)
    assert calls == []


def test_add_shows_rename_noop_never_calls_os_rename(tmp_path, monkeypatch):
    folder = tmp_path / "Artist 1999-04-03 Venue City, ST"
    folder.mkdir()
    config = SimpleNamespace(rename_compliantly=True)
    record = {"show_name": folder.name, "parentheticals": ""}
    calls = []
    monkeypatch.setattr(update.os, "rename", lambda *args: calls.append(args))

    result = update._rename_add_shows_folder_compliantly(config, str(folder), record)

    assert result == str(folder)
    assert calls == []


def test_reinventory_reconciliation_explains_prepared_processed_unresolved_and_net_change():
    config = SimpleNamespace(
        inventory_path_actions=[{"action": "re-inventory", "volume": "B&J MNOQUV", "path": "/mnt/h/boots"}],
        inventory_volume_actions={},
        current_show_groups_prepared=3384,
        current_corruption_groups_removed=6,
    )
    replaced = [{} for _ in range(3349)]
    records = [{} for _ in range(3378)]
    rows = [{} for _ in range(3376)]

    data = post._build_reinventory_reconciliation(config, replaced, records, rows, ["/one", "/two"])

    assert data["previous_rows_replaced"] == 3349
    assert data["groups_prepared"] == 3384
    assert data["prepared_vs_previous_delta"] == 35
    assert data["stage3_records"] == 3378
    assert data["stage3_groups_omitted"] == 6
    assert data["corruption_groups_removed"] == 6
    assert data["unresolved_rows_omitted"] == 2
    assert data["final_new_rows"] == 3376
    assert data["net_replacement_row_change"] == 27
