"""Behavioral checks for Build 739 review follow-up recovery and CLI consistency."""
import csv
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from tlo_copy_requests import _copy_into_temp_target, _walk_tree_size_and_reject_links
from tlo_tag_lib import _copy_verify_and_publish, prepare_inventory_copy_delete_target
from tlo_tree_compare import directory_trees_exactly_match
from tlo_storage_identities import register_inventory_root

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.behavior


def _dupes():
    spec = importlib.util.spec_from_file_location("delete_dupes743", ROOT / "tlo-deleteDupes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_recovery_directory_excluded_recursively_from_verified_copies(tmp_path):
    source = tmp_path / "source"
    show = source / "show"
    held = show / ".tlo-deleteDupes-originals-xyz" / "CD1"
    held.mkdir(parents=True)
    (held / "01.flac").write_bytes(b"bad")
    (show / "01.flac").write_bytes(b"good")
    (show / ".tlo-copy-inflight").mkdir()
    (show / ".tlo-copy-inflight" / "partial.flac").write_bytes(b"partial")
    dest = tmp_path / "dest"; dest.mkdir()
    target = Path(_copy_verify_and_publish(str(source), str(dest), "copied", exact=False))
    assert (target / "show" / "01.flac").read_bytes() == b"good"
    assert not (target / "show" / held.parent.name).exists()
    assert not (target / "show" / ".tlo-copy-inflight").exists()
    req = tmp_path / "request"
    _copy_into_temp_target(str(source), str(req))
    assert _walk_tree_size_and_reject_links(str(source)) == 4
    assert directory_trees_exactly_match(str(source), str(req), ignore_root_names={".tlo-shn-originals"})
    assert (held / "01.flac").read_bytes() == b"bad"


def test_disc_repair_original_outside_show_and_logged(tmp_path):
    d = _dupes()
    collection = tmp_path / "collection"
    show = collection / "Phish 1997-11-29"
    keeper, copy = show / "CD1", show / "CD1 (copy2)"
    keeper.mkdir(parents=True); copy.mkdir()
    original, replacement = keeper / "d1t01.flac", copy / "d1t01.flac"
    original.write_bytes(b"bad data")
    replacement.write_bytes(b"new data")
    log = tmp_path / "deleteDupesRepairs.txt"
    repaired = d.repair_corrupt_flacs_from_copies(str(keeper), [
        SimpleNamespace(path=str(copy), number=2, source_kind="numbered", alphabetical_rank=0)
    ], health_check=lambda path, **_: Path(path).read_bytes() == b"new data",
       search_root=str(collection), holding_run={}, repair_log=str(log), emit=lambda *_a, **_kw: None)
    assert repaired == (1, 0, False)
    rows = list(csv.reader(log.open(encoding="utf-8")))
    assert len(rows) == 1
    _, recorded_keeper, held, recorded_copy = rows[0]
    assert Path(recorded_keeper) == original and Path(recorded_copy) == replacement
    assert not Path(held).is_relative_to(show)
    assert Path(held).read_bytes() == b"bad data"
    assert Path(held).parts[-3:] == ("Phish 1997-11-29", "CD1", "d1t01.flac")


def test_copy_delete_refuses_nested_held_original(tmp_path):
    from tlo_tag_lib import TaggerError
    source = tmp_path / "show"; held = source / ".tlo-deleteDupes-originals-abc"
    held.mkdir(parents=True); (held / "01.flac").write_bytes(b"original")
    dest = tmp_path / "dest"; dest.mkdir()
    with pytest.raises(TaggerError, match="recovery/work directory"):
        prepare_inventory_copy_delete_target(SimpleNamespace(tag_copy_and_delete_path=str(dest)),
            {"main_dir_path": str(source)}, SimpleNamespace())
    assert (held / "01.flac").read_bytes() == b"original" and not list(dest.iterdir())


def test_explicit_label_when_os_label_unavailable(tmp_path, monkeypatch):
    import tlo_storage_identities as s
    home, root = tmp_path / "home", tmp_path / "Live"
    home.mkdir(); root.mkdir()
    capture = s.capture_storage
    def no_label(path):
        info = capture(path)
        info["label"] = ""
        return info
    monkeypatch.setattr(s, "capture_storage", no_label)
    _, identity = register_inventory_root(str(home), str(root), suggested_name="Elements")
    assert identity["name"] == "Elements"


def test_duplicate_dry_run_does_not_create_logs_or_move(tmp_path):
    home, root = tmp_path / "home", tmp_path / "music"
    home.mkdir(); root.mkdir()
    for name in ("show", "show (copy2)"):
        folder = root / name; folder.mkdir(); (folder / "01.flac").write_bytes(b"fixture")
    result = subprocess.run([sys.executable, str(ROOT / "tlo-deleteDupes.py"), "--tlo-home", str(home),
                             "--dry-run", str(root)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 candidate duplicate folders" in result.stdout
    assert not list(home.iterdir()) and (root / "show (copy2)" / "01.flac").is_file()


@pytest.mark.parametrize("script", ["tlo-tag.py", "tlo-deleteDupes.py", "tlo-gi.py", "tlo-research.py", "tlo-reverse.py"])
def test_all_cli_home_aliases_are_documented(script):
    result = subprocess.run([sys.executable, str(ROOT / script), "--help"], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0 and "--tlo-home" in result.stdout


def test_standalone_tag_dry_run_no_writes(tmp_path):
    home, folder = tmp_path / "home", tmp_path / "music"
    home.mkdir(); folder.mkdir()
    result = subprocess.run([sys.executable, str(ROOT / "tlo-tag.py"), "--tlo-home", str(home),
                             "--dry-run", str(folder)], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(home.iterdir()) and not list(folder.iterdir())
