"""Build 590: Add New Shows must not accept silently untagged performances."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_inventory_update as updater
import tlo_corruption

pytestmark = pytest.mark.behavior


class FakeLogs:
    current_log_token = "A"
    def __init__(self):
        self.messages = []
    def tag(self, message, *args):
        self.messages.append(message % args if args else message)
    def conflicts(self, message, *args):
        self.messages.append(message % args if args else message)


def _fixture(tmp_path, monkeypatch, files=("01.flac", "02.flac"), *, tag=True, deep=False):
    home = tmp_path / "tlohome"
    folder = home / "readyForXfer" / "Fictional Band 2001-03-04 The Venue Boston MA"
    folder.mkdir(parents=True)
    for name in files:
        (folder / name).write_bytes(b"synthetic media")
    (folder / "info.txt").write_text("Fictional Band\n2001-03-04\n01 Song\n02 Song\n", encoding="utf-8")
    logs = FakeLogs()
    config = SimpleNamespace(TLOHome=str(home), compliant=True, rename_compliantly=False,
                             tag_during_inventory=tag, deep_audio_check=deep,
                             convert_shn=False, corrupt_files="keep", corrupt_folders="never",
                             corrupt_folder_threshold=100, logs=logs)
    record = {"show_name": folder.name, "artist": "Fictional Band", "date": "2001-03-04",
              "main_dir_path": str(folder), "setlist_file": str(folder / "info.txt")}
    monkeypatch.setattr(updater, "prepare_updater_config", lambda c: c)
    monkeypatch.setattr(updater, "load_artist_matcher", lambda c: object())
    monkeypatch.setattr(updater, "identify_folder", lambda *a, **k: object())
    monkeypatch.setattr(updater, "_record_dict_for_new_folder", lambda *a, **k: dict(record))
    monkeypatch.setattr(updater, "find_potential_duplicate_rows_for_folder", lambda *a, **k: [])
    monkeypatch.setattr(updater, "_log_add_shows_metadata", lambda *a, **k: None)
    return home, folder, config, logs


def _outcome(*, removed=False, unverifiable=False):
    return SimpleNamespace(show_removed=removed, unverifiable=unverifiable,
                           unexpected_error="", whole_folder_trash_failed=False)


def test_no_tag_and_no_deep_never_check_corruption(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch, tag=False)
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: pytest.fail("opt-out corruption check"))
    result = updater.process_new_shows(config, "[TEST]")
    assert result["staged"] == 1 and result["held"] == result["tagged"] == 0
    assert not folder.exists()
    assert updater.read_bootlist(str(home))


@pytest.mark.parametrize("status,tagged,errors,skipped", [
    ("skip", 0, 0, 1), ("partial", 1, 0, 0), ("error", 1, 1, 0),
])
def test_partial_skipped_or_failed_tag_never_staged(tmp_path, monkeypatch, status, tagged, errors, skipped):
    home, folder, config, logs = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: _outcome())
    monkeypatch.setattr(updater, "_tag_add_shows_folder_in_place", lambda *a, **k: {
        "groups": 1, "tagged": tagged, "unchanged": 0, "skipped": skipped, "errors": errors})
    result = updater.process_new_shows(config, "[TEST]")
    assert result["held"] == 1 and result["staged"] == result["errors"] == 0
    assert folder.is_dir() and (folder / "01.flac").exists()
    assert not list((home / "staged").iterdir())
    assert not list((home / "setlists").iterdir())
    assert not updater.read_bootlist(str(home))
    assert any("ADD_SHOWS_HELD" in s for s in logs.messages)
    assert result["issues"][0]["level"] == "warning"


def test_successful_tag_accepts_all_tracks_and_records_unchanged(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    seen = []
    def corruption(*args, **kwargs):
        seen.append(kwargs)
        return _outcome()
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", corruption)
    monkeypatch.setattr(updater, "_tag_add_shows_folder_in_place", lambda *a, **k: {
        "groups": 1, "tagged": 2, "unchanged": 1, "skipped": 0, "errors": 0})
    result = updater.process_new_shows(config, "[TEST]")
    assert result["staged"] == result["unchanged"] == 1
    assert result["tagged"] == 2 and result["held"] == result["tag_errors"] == 0
    assert (home / "staged" / folder.name).is_dir()
    assert len(list((home / "setlists").glob("*.txt"))) == 1
    assert updater.read_bootlist(str(home))[0]["Show"] == folder.name
    assert seen and seen[0]["check_tag_write"] is True and seen[0]["deep_audio_check"] is False


@pytest.mark.parametrize("unverifiable,removed", [(True, False), (False, True)])
def test_deep_audio_gate_no_tagging_holds_or_removes(tmp_path, monkeypatch, unverifiable, removed):
    home, folder, config, logs = _fixture(tmp_path, monkeypatch, tag=False, deep=True)
    seen = []
    def corruption(*args, **kwargs):
        seen.append(kwargs)
        return _outcome(removed=removed, unverifiable=unverifiable)
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", corruption)
    result = updater.process_new_shows(config, "[TEST]")
    assert seen[0]["check_tag_write"] is False and seen[0]["deep_audio_check"] is True
    assert result["staged"] == 0
    assert result["held"] == int(unverifiable)
    assert result["removed_corrupt"] == int(removed)
    assert not updater.read_bootlist(str(home))
    assert not list((home / "setlists").iterdir())
    assert any("may be very slow" in s for s in logs.messages)


def test_deep_with_tagging_performs_both_checks(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch, deep=True)
    seen = []
    def corruption(*args, **kwargs):
        seen.append(kwargs)
        return _outcome()
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", corruption)
    monkeypatch.setattr(updater, "_tag_add_shows_folder_in_place", lambda *a, **k: {
        "groups": 1, "tagged": 2, "unchanged": 0, "skipped": 0, "errors": 0})
    assert updater.process_new_shows(config, "[TEST]")["staged"] == 1
    assert seen[0]["check_tag_write"] is seen[0]["deep_audio_check"] is True


def test_shn_without_conversion_reported_separately(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch, files=("01.flac", "02.shn"))
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: _outcome())
    monkeypatch.setattr(updater, "_tag_add_shows_folder_in_place", lambda *a, **k: {
        "groups": 1, "tagged": 1, "unchanged": 0, "skipped": 0, "errors": 0})
    result = updater.process_new_shows(config, "[TEST]")
    assert result["staged"] == 1 and result["tag_excluded"] == 1


def test_unsupported_copy_mode_rejected_before_any_processing(tmp_path, monkeypatch):
    _, folder, config, _ = _fixture(tmp_path, monkeypatch, tag=False)
    config.main_window_tag_copy_selected = True
    with pytest.raises(updater.InventoryUpdateError, match="Tag in Place"):
        updater.process_new_shows(config, "[TEST]")
    assert folder.exists()


def test_staging_collision_inventory_uses_actual_destination_name(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    (home / "staged").mkdir()
    (home / "staged" / folder.name).mkdir()
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: _outcome())
    monkeypatch.setattr(updater, "_tag_add_shows_folder_in_place", lambda *a, **k: {
        "groups": 1, "tagged": 2, "unchanged": 0, "skipped": 0, "errors": 0})
    result = updater.process_new_shows(config, "[TEST]")
    assert result["staged"] == 1
    rows = updater.read_bootlist(str(home))
    assert len(rows) == 1
    assert rows[0]["VolumePath"].split("] ", 1)[-1] != folder.name
    assert (home / "staged" / rows[0]["VolumePath"].split("] ", 1)[-1]).is_dir()


def test_export_failure_restores_source_and_inventory(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: _outcome())
    monkeypatch.setattr(updater, "_tag_add_shows_folder_in_place", lambda *a, **k: {
        "groups": 1, "tagged": 2, "unchanged": 0, "skipped": 0, "errors": 0})
    monkeypatch.setattr(updater, "_add_bootlist_row_for_record", lambda *a, **k: (_ for _ in ()).throw(OSError("write failed")))
    result = updater.process_new_shows(config, "[TEST]")
    assert result["errors"] == 1 and result["staged"] == 0
    assert folder.is_dir() and not list((home / "staged").iterdir())
    assert not updater.read_bootlist(str(home))
    assert not list((home / "setlists").iterdir())


def test_existing_duplicate_still_bypasses_all_tagging(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(updater, "find_potential_duplicate_rows_for_folder", lambda *a, **k: [{"Show": folder.name}])
    monkeypatch.setattr(updater, "_add_shows_audio_phase", lambda *a, **k: pytest.fail("duplicate inspected or tagged"))
    result = updater.process_new_shows(config, "[TEST]")
    assert result["duplicates"] == 1 and result["staged"] == 0
    assert (home / "dups" / folder.name).is_dir()
    assert not updater.read_bootlist(str(home))


def test_real_two_track_flac_tagging_accepts_only_after_writes(tmp_path, monkeypatch):
    """Exercise the real tag writer and setlist rather than mocked tag counts."""
    import shutil
    from mutagen.flac import FLAC
    source = Path(__file__).resolve().parents[1] / "fixtures" / "build543_silence.flac"
    if not source.is_file():
        pytest.skip("FLAC fixture absent")
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    shutil.copyfile(source, folder / "01.flac")
    shutil.copyfile(source, folder / "02.flac")
    (folder / "info.txt").write_text(
        "Fictional Band\n2001-03-04\nThe Venue, Boston, MA\n\n01 Song One\n02 Song Two\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: _outcome())
    result = updater.process_new_shows(config, "[TEST]")
    assert result["staged"] == 1, result
    assert result["tagged"] == 2, result
    target = home / "staged" / folder.name
    assert FLAC(target / "01.flac")["title"] == ["Song One"]
    assert FLAC(target / "02.flac")["title"] == ["Song Two"]
    assert FLAC(target / "01.flac")["artist"] == ["Fictional Band"]


def test_real_mixed_flac_shn_exclusion_only_tags_supported_audio(tmp_path, monkeypatch):
    import shutil
    from mutagen.flac import FLAC
    source = Path(__file__).resolve().parents[1] / "fixtures" / "build543_silence.flac"
    if not source.is_file():
        pytest.skip("FLAC fixture absent")
    home, folder, config, _ = _fixture(tmp_path, monkeypatch, files=("01 Song One.flac", "02 Legacy.shn"))
    shutil.copyfile(source, folder / "01 Song One.flac")
    (folder / "info.txt").write_text(
        "Fictional Band\n2001-03-04\nThe Venue, Boston, MA\n\n01 Song One\n02 Legacy\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", lambda *a, **k: _outcome())
    result = updater.process_new_shows(config, "[TEST]")
    assert result["staged"] == result["tagged"] == result["tag_excluded"] == 1, result
    target = home / "staged" / folder.name
    assert FLAC(target / "01 Song One.flac")["title"] == ["Song One"]
    assert (target / "02 Legacy.shn").read_bytes() == b"synthetic media"


def test_duplicate_replacement_tag_skip_cannot_schedule_old_folder_deletion(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    dups = home / "dups"
    dups.mkdir()
    duplicate = dups / folder.name
    folder.rename(duplicate)
    existing = {"Show": folder.name, "VolumePath": "[Backup] C:\\old-shows\\same-date"}
    updater.write_bootlist(str(home), [existing])
    monkeypatch.setattr(updater, "_add_shows_audio_phase", lambda *a, **k: {
        "accepted": False, "removed": False, "reason": "Tagging incomplete: 1 of 2 files failed"})
    with pytest.raises(updater.InventoryUpdateError, match="No inventory, setlist or old-show deletion"):
        updater.process_duplicate_folder(config, {"folder": str(duplicate), "record": {
            "show_name": duplicate.name, "artist": "Fictional Band"}}, [existing], "[New]")
    assert updater.read_bootlist(str(home)) == [existing]
    assert duplicate.is_dir()
    assert not list((home / "setlists").iterdir())
    assert not list((home / "staged").iterdir())
    assert not Path(updater.updater_delete_script_path(str(home))).exists()


def test_duplicate_replacement_commit_failure_rolls_back_every_output(tmp_path, monkeypatch):
    home, folder, config, _ = _fixture(tmp_path, monkeypatch)
    dups = home / "dups"
    dups.mkdir()
    duplicate = dups / folder.name
    folder.rename(duplicate)
    existing = {"Show": folder.name, "VolumePath": "[Backup] C:\\old-shows\\same-date"}
    updater.write_bootlist(str(home), [existing])
    original_bootlist_bytes = (home / "bootlist.csv").read_bytes()
    monkeypatch.setattr(updater, "_add_shows_audio_phase", lambda *a, **k: {
        "accepted": True, "removed": False, "reason": ""})
    monkeypatch.setattr(updater, "_add_bootlist_row_for_record",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        updater.process_duplicate_folder(config, {"folder": str(duplicate), "record": {
            "show_name": duplicate.name, "artist": "Fictional Band"}}, [existing], "[New]")
    assert duplicate.is_dir() and not list((home / "staged").iterdir())
    assert (home / "bootlist.csv").read_bytes() == original_bootlist_bytes
    assert not list((home / "setlists").iterdir())
    assert not Path(updater.updater_delete_script_path(str(home))).exists()
