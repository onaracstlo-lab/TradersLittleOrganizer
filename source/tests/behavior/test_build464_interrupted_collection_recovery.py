"""Build 464: interrupted sibling collection recovery is automatic and diagnosable."""

from __future__ import annotations

__version__ = "v465"

import json
import os
from pathlib import Path

import pytest

import tlo_sibling_collections as sibling

pytestmark = pytest.mark.behavior


def _audio(folder: Path, name: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"not-real-audio")


def _payload(container: Path, final_path: Path, members: list[Path]) -> dict:
    return {
        "schema": 1,
        "temporary_path": str(container),
        "final_path": str(final_path),
        "generated_info": "info.txt",
        "members": [
            {"original": str(member), "child_name": member.name}
            for member in members
        ],
    }


def test_interrupted_final_container_that_matches_original_member_recovers(tmp_path):
    """Reproduce the Pink Floyd nested duplicate-path failure from Build 463."""
    root = tmp_path / "boots"
    base = root / "Pink Floyd - Early Flights"
    alt = root / "Pink Floyd - Early Flights (alt1)"
    _audio(base, "01 - Base.flac")
    _audio(alt, "01 - Alternate.flac")

    temp = root / f"{sibling.TEMP_PREFIX}interrupted"
    temp.mkdir()
    payload = _payload(temp, base, [base, alt])
    (temp / sibling.JOURNAL_NAME).write_text(json.dumps(payload), encoding="utf-8")

    # Simulate process termination after all members were moved and the
    # temporary container had already been renamed to the final path, but before
    # the journal was removed.  The final path is also one original member.
    os.rename(base, temp / base.name)
    os.rename(alt, temp / alt.name)
    os.rename(temp, base)

    assert (base / sibling.JOURNAL_NAME).is_file()
    assert (base / base.name / "01 - Base.flac").is_file()
    assert sibling.recover_interrupted_sibling_consolidations(str(root)) == 1

    assert (base / "01 - Base.flac").is_file()
    assert (alt / "01 - Alternate.flac").is_file()
    assert not (base / base.name).exists()
    assert not (base / sibling.JOURNAL_NAME).exists()
    assert not any(path.name.startswith(sibling.TEMP_PREFIX) for path in root.iterdir())


def test_ambiguous_recovery_reports_exact_original_and_staged_paths(tmp_path):
    root = tmp_path / "boots"
    original1 = root / "Artist - Collection D1"
    original2 = root / "Artist - Collection D2"
    _audio(original1, "01.flac")
    _audio(original2, "02.flac")

    temp = root / f"{sibling.TEMP_PREFIX}ambiguous"
    temp.mkdir()
    payload = _payload(temp, root / "Artist - Collection", [original1, original2])
    (temp / sibling.JOURNAL_NAME).write_text(json.dumps(payload), encoding="utf-8")

    # Duplicate one member into staging without removing the original.  TLO
    # must not guess which copy is authoritative.
    _audio(temp / original1.name, "01.flac")

    with pytest.raises(sibling.SiblingCollectionRecoveryError) as excinfo:
        sibling.recover_interrupted_sibling_consolidations(str(root))

    message = str(excinfo.value)
    assert "Interrupted sibling-collection move requires recovery." in message
    assert f"Recovery container: {temp}" in message
    assert f"Recovery journal: {temp / sibling.JOURNAL_NAME}" in message
    assert f"Planned final folder: {root / 'Artist - Collection'}" in message
    assert f"original: {original1}" in message
    assert f"staged:   {temp / original1.name}" in message
    assert "BOTH original and staged copies exist" in message
    assert "do not delete or merge them manually" in message


def test_unreadable_journal_blocks_even_when_container_is_final_name(tmp_path):
    root = tmp_path / "boots"
    final = root / "Artist - Collection"
    final.mkdir(parents=True)
    (final / sibling.JOURNAL_NAME).write_text("not json", encoding="utf-8")

    with pytest.raises(sibling.SiblingCollectionRecoveryError) as excinfo:
        sibling.recover_interrupted_sibling_consolidations(str(root))

    message = str(excinfo.value)
    assert f"Recovery container: {final}" in message
    assert f"Recovery journal: {final / sibling.JOURNAL_NAME}" in message
    assert "recovery journal cannot be read" in message


def test_orphan_temporary_collection_folder_blocks_normal_inventory(tmp_path):
    root = tmp_path / "boots"
    orphan = root / f"{sibling.TEMP_PREFIX}orphan"
    orphan.mkdir(parents=True)

    with pytest.raises(sibling.SiblingCollectionRecoveryError) as excinfo:
        sibling.recover_interrupted_sibling_consolidations(str(root))

    message = str(excinfo.value)
    assert f"Recovery container: {orphan}" in message
    assert "without its recovery journal" in message


def test_dry_run_diagnostic_explains_how_to_get_automatic_recovery(tmp_path):
    root = tmp_path / "boots"
    original = root / "Artist - Collection D1"
    temp = root / f"{sibling.TEMP_PREFIX}paused"
    _audio(temp / original.name, "01.flac")
    payload = _payload(temp, root / "Artist - Collection", [original])
    (temp / sibling.JOURNAL_NAME).write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(sibling.SiblingCollectionRecoveryError) as excinfo:
        sibling.assert_no_interrupted_sibling_consolidations(str(root))

    message = str(excinfo.value)
    assert "Dry Run is read-only" in message
    assert "Run a normal (non-Dry-Run) inventory" in message
    assert f"original: {original}" in message
    assert f"staged:   {temp / original.name}" in message
    assert "STAGED_ONLY" in message
