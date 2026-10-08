"""Live-path regression tests for atomic staged Tag Copy (F-05, Build 563)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _operation(tmp_path):
    src = tmp_path / "shows" / "Artist 2001-01-01 Venue"
    dst = tmp_path / "copies"
    src.mkdir(parents=True)
    dst.mkdir()
    (src / "disc1").mkdir()
    (src / "disc1" / "01.flac").write_bytes(b"audio" * 25)
    (src / "empty").mkdir()
    group = {
        "main_dir_path": str(src), "main_dir_name": src.name,
        "music_dirs": [str(src / "disc1")],
        "music_files": [str(src / "disc1" / "01.flac")],
        "setlist_files": [], "txt_files": [],
    }
    record = SimpleNamespace(main_dir_path=str(src), main_dir_name=src.name,
        show_name=src.name, setlist_file="", music_dirs=[str(src / "disc1")], setlist_files=[])
    config = SimpleNamespace(tag_copy_during_inventory=True, tag_copy_destination=str(dst), rename_compliantly=False)
    return src, dst, group, record, config


def test_live_tag_copy_verifies_staging_before_publication(tmp_path, monkeypatch):
    import tlo_tag_lib as tag
    src, dst, group, record, config = _operation(tmp_path)
    verified = []
    real = tag._verify_copy_by_file_size

    def check(src_path, target_path):
        assert Path(target_path).name.startswith(".tlo-partial-")
        assert not (dst / src.name).exists()
        assert (Path(target_path) / "disc1" / "01.flac").exists()
        verified.append(target_path)
        return real(src_path, target_path)

    monkeypatch.setattr(tag, "_verify_copy_by_file_size", check)
    updated_group, updated_record = tag.prepare_inventory_tagging_target(config, group, record)
    assert verified and len(verified) == 1
    assert Path(updated_record.main_dir_path) == dst / src.name
    assert updated_group["music_files"] == [str(dst / src.name / "disc1" / "01.flac")]
    assert src.exists() and (dst / src.name / "empty").is_dir()
    assert not list(dst.glob(".tlo-partial-*"))


def test_copy_interruption_leaves_no_final_folder(tmp_path, monkeypatch):
    import tlo_tag_lib as tag
    src, dst, group, record, config = _operation(tmp_path)

    def fail_after_writing(_src, temp):
        assert Path(temp).name.startswith(".tlo-partial-")
        (Path(temp) / "partial.flac").write_bytes(b"only partly copied")
        assert not (dst / src.name).exists()
        raise InterruptedError("simulated cancellation")

    monkeypatch.setattr(tag, "_copy_tree_into_reserved_directory", fail_after_writing)
    with pytest.raises(tag.TaggerError, match="simulated cancellation"):
        tag.prepare_inventory_tagging_target(config, group, record)
    assert src.exists()
    assert not (dst / src.name).exists()
    assert not list(dst.glob(".tlo-partial-*"))


def test_verification_failure_never_publishes(tmp_path, monkeypatch):
    import tlo_tag_lib as tag
    src, dst, group, record, config = _operation(tmp_path)

    def fail(_src, _dest):
        raise tag.TaggerError("size verification failed")

    monkeypatch.setattr(tag, "_verify_copy_by_file_size", fail)
    with pytest.raises(tag.TaggerError, match="size verification failed"):
        tag.prepare_inventory_tagging_target(config, group, record)
    assert not (dst / src.name).exists()
    assert not list(dst.glob(".tlo-partial-*"))
    assert src.exists()


def test_publish_race_preserves_foreign_target_and_chooses_alt(tmp_path, monkeypatch):
    import tlo_tag_lib as tag
    src, dst, group, record, config = _operation(tmp_path)
    real_publish = tag._publish_staged_directory_noreplace
    seen = []

    def racing_publish(stage, target):
        seen.append(target)
        if len(seen) == 1:
            Path(target).mkdir()
            (Path(target) / "other-file.txt").write_bytes(b"foreign")
        real_publish(stage, target)

    monkeypatch.setattr(tag, "_publish_staged_directory_noreplace", racing_publish)
    result, _ = tag.prepare_inventory_tagging_target(config, group, record)
    assert len(seen) >= 2
    assert (dst / src.name / "other-file.txt").read_bytes() == b"foreign"
    assert Path(result["main_dir_path"]).name.endswith("(alt1)")
    assert (Path(result["main_dir_path"]) / "disc1" / "01.flac").read_bytes() == b"audio" * 25
    assert not list(dst.glob(".tlo-partial-*"))


def test_publish_fails_closed_when_atomic_api_unavailable(tmp_path, monkeypatch):
    import tlo_tag_lib as tag
    src, dst, group, record, config = _operation(tmp_path)
    monkeypatch.setattr(tag, "_publish_staged_directory_noreplace", lambda *_: (_ for _ in ()).throw(tag.TaggerError("not supported")))
    with pytest.raises(tag.TaggerError, match="not supported"):
        tag.prepare_inventory_tagging_target(config, group, record)
    assert src.exists() and not (dst / src.name).exists()
    assert not list(dst.glob(".tlo-partial-*"))


def test_tag_copy_rejects_destination_inside_source(tmp_path):
    import tlo_tag_lib as tag
    src, dst, group, record, config = _operation(tmp_path)
    (src / "inside").mkdir()
    config.tag_copy_destination = str(src / "inside")
    with pytest.raises(tag.TaggerError, match="must not be"):
        tag.prepare_inventory_tagging_target(config, group, record)
    assert not list((src / "inside").iterdir())


def test_abrupt_worker_exit_never_exposes_normal_show(tmp_path):
    if not sys.platform.startswith("linux"):
        pytest.skip("subprocess force-exit probe uses the Linux no-replace publish path")
    src, dst, group, record, config = _operation(tmp_path)
    script = '''import os, sys
import tlo_tag_lib as t
from types import SimpleNamespace
source, destination = sys.argv[1:]
real = t._copy_tree_into_reserved_directory
def interrupted(_source, staging):
    with open(os.path.join(staging, 'partial.flac'), 'wb') as output:
        output.write(b'partway')
    os._exit(47) # no finally block runs, simulates terminated worker

t._copy_tree_into_reserved_directory = interrupted
record = SimpleNamespace(main_dir_path=source, main_dir_name=os.path.basename(source), show_name=os.path.basename(source), setlist_file='', music_dirs=[], setlist_files=[])
group = {'main_dir_path': source, 'music_dirs': [], 'music_files': []}
config = SimpleNamespace(tag_copy_during_inventory=True, tag_copy_destination=destination, rename_compliantly=False)
t.prepare_inventory_tagging_target(config, group, record)
'''
    run = subprocess.run([sys.executable, "-c", script, str(src), str(dst)], cwd=Path(__file__).resolve().parents[2], timeout=20, check=False, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert run.returncode == 47
    assert not (dst / src.name).exists()
    left = list(dst.glob(".tlo-partial-*"))
    assert len(left) == 1 and (left[0] / "partial.flac").read_bytes() == b"partway"
    from tlo_path_policy import is_phase1_pruned_directory
    assert is_phase1_pruned_directory(left[0].name)
    assert src.exists()
