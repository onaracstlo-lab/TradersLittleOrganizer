"""Build 482: Manual Updates CI fixtures use canonical VolumePath values."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_manual_updates as MU
from tlo_bootlist_volume_policy import format_volume_path

pytestmark = pytest.mark.behavior
__version__ = "v484"


def _music_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    (path / "01.flac").write_bytes(b"x")
    return path


def test_build482_manual_update_matches_canonical_row_with_nonblank_linux_volume_label(tmp_path, monkeypatch):
    """Protect the exact GitHub Linux failure that exposed the stale Build 478 fixture."""
    home = tmp_path / "TLOHome"
    (home / "setlists").mkdir(parents=True)
    original = _music_dir(tmp_path / "library" / "Old Folder")

    # Simulate a Linux runner whose filesystem exposes a visible volume label.
    monkeypatch.setattr(MU, "os_volume_label_for_path", lambda _path: "CI-VOLUME")
    MU.write_bootlist(
        str(home),
        [{"Show": "Old Folder", "VolumePath": format_volume_path("CI-VOLUME", str(original))}],
    )
    monkeypatch.setattr(
        MU,
        "identify_folder_dict",
        lambda config, folder: {"show_name": "x", "main_dir_path": folder},
    )
    monkeypatch.setattr(MU, "create_or_replace_generated_setlist", lambda home_, record: "")

    result = MU.apply_folder_manual_update(
        SimpleNamespace(TLOHome=str(home)), str(original), "New Folder", update_tags=False
    )

    assert result["new_path"].endswith("New Folder")
    rows = MU.read_bootlist(str(home))
    assert len(rows) == 1
    assert rows[0]["Show"] == "New Folder"
    assert rows[0]["VolumePath"].startswith("[CI-VOLUME] ")
