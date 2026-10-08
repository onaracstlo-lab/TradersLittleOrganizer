"""Build 556 corruption validation regressions for reversible tag-write probes."""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen import MutagenError
from mutagen.flac import FLAC

import tlo_corruption as corruption
import tlo_phase23_v2 as phase23
import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
FLAC_FIXTURE = ROOT / "tests" / "fixtures" / "build543_silence.flac"


def _copy_flac(tmp_path: Path, name: str = "track.flac") -> Path:
    target = tmp_path / name
    shutil.copy2(FLAC_FIXTURE, target)
    return target


def test_build556_real_flac_tag_probe_restores_existing_probe_value_and_mtime(tmp_path):
    path = _copy_flac(tmp_path)
    audio = FLAC(path)
    audio[corruption._TAG_TEST_KEY] = ["pre-existing value", "second value"]
    audio["artist"] = ["Existing Artist"]
    audio.save()
    fixed_ns = 1_700_000_000_123_456_789
    path.touch()
    # Set both atime and mtime to a deterministic value after the fixture setup.
    import os
    os.utime(path, ns=(fixed_ns, fixed_ns))
    before_tags = dict(FLAC(path))

    bad, unverifiable = corruption.classify_audio_paths([str(path)], check_tag_write=True)

    assert bad == []
    assert unverifiable == []
    assert dict(FLAC(path)) == before_tags
    assert path.stat().st_mtime_ns == fixed_ns


def test_build556_real_flac_tag_probe_removes_temporary_key_when_originally_absent(tmp_path):
    path = _copy_flac(tmp_path)
    before_tags = dict(FLAC(path))
    assert corruption._TAG_TEST_KEY not in FLAC(path)

    corruption._validate_tag_write_round_trip(str(path))

    assert dict(FLAC(path)) == before_tags
    assert corruption._TAG_TEST_KEY not in FLAC(path)


def test_build556_header_only_validation_does_not_attempt_tag_write(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)

    def should_not_run(_path):
        raise AssertionError("tag-write probe must not run for header-only validation")

    monkeypatch.setattr(corruption, "_validate_tag_write_round_trip", should_not_run)
    bad, unverifiable = corruption.classify_audio_paths([str(path)], check_tag_write=False)

    assert bad == []
    assert unverifiable == []


def test_build556_tag_write_format_failure_is_corruption(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    monkeypatch.setattr(
        corruption,
        "_validate_tag_write_round_trip",
        lambda _path: (_ for _ in ()).throw(MutagenError("tag save failed")),
    )

    bad, unverifiable = corruption.classify_audio_paths([str(path)], check_tag_write=True)

    assert bad == [str(path)]
    assert unverifiable == []


def test_build556_tag_write_permission_failure_is_unverifiable(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    monkeypatch.setattr(
        corruption,
        "_validate_tag_write_round_trip",
        lambda _path: (_ for _ in ()).throw(PermissionError("read-only media")),
    )

    bad, unverifiable = corruption.classify_audio_paths([str(path)], check_tag_write=True)

    assert bad == []
    assert len(unverifiable) == 1
    assert unverifiable[0][0] == str(path)
    assert "PermissionError" in unverifiable[0][1]


def test_build556_tag_restore_failure_is_unverifiable(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    monkeypatch.setattr(
        corruption,
        "_validate_tag_write_round_trip",
        lambda _path: (_ for _ in ()).throw(corruption._TagWriteRestoreError("restore verification failed")),
    )

    bad, unverifiable = corruption.classify_audio_paths([str(path)], check_tag_write=True)

    assert bad == []
    assert len(unverifiable) == 1
    assert "restore verification failed" in unverifiable[0][1]


def test_build556_inventory_tag_probe_is_disabled_for_dry_run():
    assert phase23._corruption_tag_write_check_enabled(SimpleNamespace(dry_run=False), True) is True
    assert phase23._corruption_tag_write_check_enabled(SimpleNamespace(dry_run=True), True) is False
    assert phase23._corruption_tag_write_check_enabled(SimpleNamespace(dry_run=False), False) is False


def test_build556_standalone_tagger_requests_tag_write_corruption_check(monkeypatch, tmp_path):
    captured = {}
    record = SimpleNamespace(main_dir_path=str(tmp_path), artist="", show_name="")
    config = taglib.build_tagger_config(tlo_home=str(tmp_path), corrupt_files="keep")

    monkeypatch.setattr(taglib, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))

    class RemovedOutcome:
        show_removed = True
        unverifiable = False

    import tlo_corruption

    def fake_handle(_config, _group, _record, **kwargs):
        captured.update(kwargs)
        return RemovedOutcome()

    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", fake_handle)
    stats = taglib.process_tagging_group(
        config,
        {"main_dir_path": str(tmp_path), "music_dirs": [str(tmp_path)]},
        object(),
        emit=lambda _text: None,
    )

    assert stats["skipped"] == 1
    assert captured["check_tag_write"] is True
