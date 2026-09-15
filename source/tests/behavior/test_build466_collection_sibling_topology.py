"""Build 466: alt collections never create a same-name parent/child pair."""

from __future__ import annotations

__version__ = "v467"

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
import tlo_sibling_collections as sibling
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior


def _audio(folder: Path, titles):
    folder.mkdir(parents=True, exist_ok=True)
    for number, title in enumerate(titles, 1):
        (folder / f"{number:02d} - {title}.flac").write_bytes(b"audio")
    (folder / "setlist.txt").write_text(
        "\n".join(f"{number:02d}. {title}" for number, title in enumerate(titles, 1)) + "\n",
        encoding="utf-8",
    )


def _complete_log(root: Path) -> Path:
    log = root / "comp.log"
    rows = [f"# completePathLog for search path: {root}", f"SEARCH_PATH: {root}"]
    rows.extend(str(audio) for audio in sorted(root.rglob("*.flac")))
    log.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return log


def _phase_config(log: Path):
    return SimpleNamespace(
        compliant=False,
        logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))),
        performance_mode="balanced",
    )


def test_alt_collection_uses_alt0_instead_of_same_name_child(tmp_path):
    root = tmp_path / "boots"
    base = root / "Pink Floyd - Early Flights"
    alt1 = root / "Pink Floyd - Early Flights (alt1)"
    alt2 = root / "Pink Floyd - Early Flights (alt2)"
    _audio(base, ("Astronomy", "Lucifer"))
    _audio(alt1, ("Embryo", "Green"))
    _audio(alt2, ("Cymbaline", "Echoes"))
    log = _complete_log(root)

    result = sibling.consolidate_sibling_collections(str(root), str(log))

    assert len(result) == 1
    original = base / "Pink Floyd - Early Flights (alt0)"
    assert base.is_dir()
    assert original.is_dir()
    assert (base / alt1.name).is_dir()
    assert (base / alt2.name).is_dir()
    assert not (base / base.name).exists()
    assert result[0]["children"][0] == str(original)

    groups = phase._build_groups_from_search_path(_phase_config(log), str(root))
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(base)
    assert groups[0]["aggregate_album_name"] == base.name
    assert groups[0]["aggregation_reason"] == "consolidated_sibling_collection"
    ordered = [os.path.relpath(path, base) for path in taglib._rescan_group_audio_files(groups[0])]
    assert ordered[0].startswith(original.name + os.sep)
    assert ordered[2].startswith(alt1.name + os.sep)
    assert ordered[4].startswith(alt2.name + os.sep)


def test_alt0_log_rewrite_points_to_new_child_name(tmp_path):
    root = tmp_path / "boots"
    base = root / "Artist - Alternate Collection"
    alt1 = root / "Artist - Alternate Collection (alt1)"
    _audio(base, ("One", "Two"))
    _audio(alt1, ("Three", "Four"))
    log = _complete_log(root)

    sibling.consolidate_sibling_collections(str(root), str(log))
    text = log.read_text(encoding="utf-8")
    assert str(base / "Artist - Alternate Collection (alt0)" / "01 - One.flac") in text
    assert str(base / base.name / "01 - One.flac") not in text


def test_failed_alt_collection_commit_restores_unsuffixed_original(tmp_path, monkeypatch):
    root = tmp_path / "boots"
    base = root / "Artist - Collection"
    alt1 = root / "Artist - Collection (alt1)"
    _audio(base, ("One", "Two"))
    _audio(alt1, ("Three", "Four"))
    log = _complete_log(root)
    monkeypatch.setattr(
        sibling,
        "_rewrite_complete_path_log",
        lambda *_args: (_ for _ in ()).throw(OSError("forced log failure")),
    )

    assert sibling.consolidate_sibling_collections(str(root), str(log)) == []
    assert (base / "01 - One.flac").is_file()
    assert (alt1 / "01 - Three.flac").is_file()
    assert not (base / "Artist - Collection (alt0)").exists()
    assert not any(path.name.startswith(sibling.TEMP_PREFIX) for path in root.iterdir())


def test_schema2_journal_records_original_and_staged_names(tmp_path):
    root = tmp_path / "boots"
    base = root / "Artist - Collection"
    alt1 = root / "Artist - Collection (alt1)"
    _audio(base, ("One", "Two"))
    _audio(alt1, ("Three", "Four"))
    log = _complete_log(root)
    plan = sibling.discover_collection_plans(str(root), sibling._logged_media_paths(str(log)))[0]
    payload = sibling._journal_payload(plan, str(root / ".tlo-collection-test"))

    assert payload["schema"] == 2
    first = payload["members"][0]
    assert first["child_name"] == "Artist - Collection"
    assert first["staged_name"] == "Artist - Collection (alt0)"
