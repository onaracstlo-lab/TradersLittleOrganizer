"""Build 654: UNC paths are share-scoped volumes, not drive-letter substitutes."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

import inventory_list_lib as INV
import tlo_bootlist_volume_policy as BP
import tlo_copy_requests as CR
import tlo_path_inputs as PI
import tlo_postprocess as PP
import tlo_volume_label as VL
from tlo_unc import (
    compose_unc_path, is_unc_path, root_from_unc_label,
    share_relative_path, unc_label, unc_root,
)

SHARE = r"\\rich-server\Music"
SHOW = SHARE + r"\Grateful Dead\1977-05-08"
VOLUME = "UNC:rich-server/music"


def test_parse_share_and_reject_device_and_partial_paths():
    assert is_unc_path(SHOW)
    assert unc_root(SHOW).casefold() == SHARE.casefold()
    assert unc_label(SHOW) == VOLUME
    assert unc_label(r"\\RICH-SERVER\MUSIC\x") == VOLUME
    assert share_relative_path(SHOW) == "/Grateful Dead/1977-05-08"
    assert root_from_unc_label(VOLUME).casefold() == SHARE.casefold()
    for bad in (r"\\server", r"\\?\C:\files", r"\\.\C:\files", r"\\server\share:bad", "\\\\server\\share\\\0bad"):
        assert not is_unc_path(bad)


def test_windows_search_path_accepts_unc_with_no_drive(monkeypatch):
    monkeypatch.setattr(INV, "_running_on_windows", lambda: True)
    assert INV._normalize_input_path(SHOW) == SHOW
    assert INV._normalize_input_path("file://rich-server/Music/Grateful%20Dead/1977-05-08") == SHOW
    assert INV._normalize_input_path(r"C:\Music") == r"C:\Music"
    assert INV._normalize_input_path("/mnt/c/Music") == r"C:\Music"
    with pytest.raises(ValueError, match="Invalid UNC"):
        INV._normalize_input_path(r"\\?\C:\Music")


def test_unmounted_unc_does_not_silently_become_relative_linux_path(monkeypatch):
    monkeypatch.setattr(INV, "_running_on_windows", lambda: False)
    with pytest.raises(ValueError, match="UNC shares must be accessed on Windows"):
        INV._normalize_input_path(SHOW)
    if PI.os.name != "nt":
        with pytest.raises(ValueError, match="UNC paths require Windows"):
            PI.normalize_platform_input_path(SHOW)


def test_unc_identity_not_os_volume_label(monkeypatch):
    monkeypatch.setattr(VL, "_windows_volume_label", lambda path: pytest.fail("remote volumes must not be probed"))
    info = VL.resolve_volume_label(SHOW)
    assert info.label == VOLUME
    assert info.volume_key == SHARE.casefold()
    assert info.label_source == "unc_share"
    assert VL.resolve_physical_drive_id(SHOW) == ""
    assert BP.os_volume_label_for_path(SHOW) == VOLUME


def test_inventory_assigns_share_identifier_even_if_os_has_no_label(monkeypatch):
    assigned = INV._assign_volume_labels([(SHOW, SHOW, "", "")])
    assert assigned[0][3] == VOLUME
    assert assigned[0][4] == SHARE.casefold()
    with pytest.raises(ValueError, match="volume mismatch"):
        INV._assign_volume_labels([(f"[Other]{SHOW}", SHOW, "", "Other")])
    same = INV._assign_volume_labels([(f"[{VOLUME}]{SHOW}", SHOW, "", VOLUME)])
    assert same[0][3] == VOLUME


def test_bootlist_persists_share_identity_and_relative_folder():
    expected = f"[{VOLUME}] /Grateful Dead/1977-05-08"
    assert BP.format_volume_path("", SHOW) == expected
    assert BP.format_volume_path(VOLUME, SHOW) == expected
    assert BP.parse_volume_path_value(expected) == (VOLUME, "/Grateful Dead/1977-05-08")
    assert BP.format_log_volume_path(VOLUME, SHOW) == expected
    assert BP.storage_path_without_drive(SHOW) == "/Grateful Dead/1977-05-08"
    assert BP.paths_related(SHOW, SHARE + r"\Grateful Dead")
    assert BP.normalize_path_for_compare(SHOW) == "/Grateful Dead/1977-05-08"


def test_two_shares_same_relative_path_stay_distinct_in_inventory():
    a = BP.format_volume_path("", r"\\server-a\music\same\show")
    b = BP.format_volume_path("", r"\\server-b\music\same\show")
    assert a != b
    assert BP.volume_key(BP.parse_volume_path_value(a)[0]) != BP.volume_key(BP.parse_volume_path_value(b)[0])


def test_copy_requests_reconstruct_share_without_drive(monkeypatch):
    monkeypatch.setattr(CR.os.path, "isdir", lambda path: path.casefold() == SHARE.casefold())
    paths, connected = CR._physical_paths_for_volume_stored(VOLUME, "/Grateful Dead/1977-05-08", {})
    assert paths == [SHOW.replace("Music", "music")]
    assert connected
    assert compose_unc_path(VOLUME, "/../outside") == ""
    assert compose_unc_path(VOLUME, r"..\..\outside") == ""


def test_copy_requests_missing_share_is_waiting(monkeypatch):
    monkeypatch.setattr(CR.os.path, "isdir", lambda path: False)
    paths, connected = CR._physical_paths_for_volume_stored(VOLUME, "/show", {})
    assert paths == [SHARE.replace("Music", "music") + r"\show"]
    assert not connected


def test_manual_update_share_aware_volume_matches(tmp_path):
    BP.write_bootlist_rows(str(tmp_path), [{"Show": "GD", "VolumePath": BP.format_volume_path("", SHOW)}])
    import tlo_manual_updates as MU
    found = MU._matching_bootlist_rows(str(tmp_path), SHOW)
    assert len(found) == 1
    assert found[0]["Show"] == "GD"
    with pytest.raises(MU.ManualUpdateError):
        MU._matching_bootlist_rows(str(tmp_path), r"\\other-server\Music\Grateful Dead\1977-05-08")


def test_postprocess_rejects_unc_without_explicit_allowlist(monkeypatch):
    record = {"main_dir_path": SHOW, "original_main_dir_path": ""}
    assert not PP._safe_setlist_source_for_record(SHOW + r"\info.txt", record)
    approved = SimpleNamespace(allowed_unc_roots=(SHOW,))
    monkeypatch.setattr(PP, "is_safe_authorized_unc_file", lambda source, roots: source.endswith("info.txt") and tuple(roots) == (SHOW,))
    assert PP._safe_setlist_source_for_record(SHOW + r"\info.txt", record, config=approved)
    assert not PP._safe_setlist_source_for_record(SHOW + r"\info.txt", record)
