from pathlib import Path
from types import SimpleNamespace
import tlo_phase23_v2 as phase

def test_build390_nested_music_folder_is_discovered_after_parent_music(tmp_path):
    parent = tmp_path / "Main Artist 2000-01-01 Venue"
    opener = parent / "Opening Artist 2000-01-01 Venue"
    opener.mkdir(parents=True)
    (parent / "01.flac").write_bytes(b"x")
    (opener / "01.flac").write_bytes(b"x")
    logs = SimpleNamespace(dead_end=lambda *a, **k: None)
    config = SimpleNamespace(logs=logs)
    found = phase._discover_music_dirs(config, str(parent))
    dirs = {Path(item["music_dir"]).name for item in found}
    assert dirs == {parent.name, opener.name}
