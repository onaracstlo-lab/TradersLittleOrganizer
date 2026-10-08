"""Build 506 remediation for the v505 targeted review findings."""


import importlib.util
import os
import shutil
import types
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]

import tlo_copy_requests as CR
import tlo_setlistfm_lookup as sfm
from tlo_bootlist_volume_policy import write_bootlist_rows
from tlo_text_utils import decode_text_bytes, read_text_file_full
from tests.behavior.test_build503_copy_request_direct_paths_volumes import _artist_db, _music_folder, _row

SHOW = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"


def _setup(tmp_path, request_line="Grateful Dead"):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol = tmp_path / "VOLROOT"
    _music_folder(vol, "Dead/show-one", b"one")
    write_bootlist_rows(str(home), [_row(SHOW, "VOL", "Dead/show-one")])
    dest = tmp_path / "dest"
    dest.mkdir()
    req = tmp_path / "req.txt"
    req.write_text(request_line + "\n", encoding="utf-8")
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    return home, vol, dest, rid


class _V:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _gui_probe(tmp_path, monkeypatch, tag_field):
    pytest.importorskip("tkinter")
    spec = importlib.util.spec_from_file_location("tlo_main_build506", ROOT / "tlo-main.py")
    gui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gui)
    home = tmp_path / f"home-{tag_field}"
    (home / "TLO_DBs").mkdir(parents=True)
    monkeypatch.setenv("TLOHome", str(home))

    class Probe(gui.App):
        def __init__(self):
            pass

        def _confirm_tag_copy_destination(self, initial_value=None):
            return str(home)

        def _confirm_tag_copy_delete_destination(self, initial_value=""):
            return str(home)

        def __getattr__(self, name):
            if name.startswith("__"):
                raise AttributeError(name)
            return lambda *args, **kwargs: str(home)

    app = Probe()
    app.cli_args = types.SimpleNamespace(
        debug=False,
        silent=False,
        TLOHome=str(home),
        current_storage_volume=None,
        search_path_copy_override="",
        search_path_copy_delete_override="",
    )
    app.vars = {
        key: _V("")
        for key in (
            "search_path_override",
            "search_path_slam_override",
            "performance_mode",
            "max_workers",
            "corrupt_files",
            "corrupt_folders",
            "corrupt_folder_threshold",
        )
    }
    app.vars["performance_mode"].set("balanced")
    app.vars["max_workers"].set("2")
    app.vars["corrupt_folder_threshold"].set("100")
    fields = (
        "compliant",
        "rename_compliantly",
        "as_is_artist_name",
        "proper_grammar",
        "tag_during_inventory",
        "tag_copy_during_inventory",
        "tag_copy_and_delete_enabled",
        "convert_shn",
        "artist_in_album",
        "delete_extra_tags",
        "etree_lookup",
        "setlistfm_lookup",
        "setlistfm_upgrade",
        "thorough_setlist_matching",
    )
    app.bool_vars = {field: _V(False) for field in fields}
    app.bool_vars[tag_field].set(True)
    app.bool_vars["delete_extra_tags"].set(True)
    return gui, app


@pytest.mark.parametrize(
    "tag_field",
    ["tag_during_inventory", "tag_copy_during_inventory", "tag_copy_and_delete_enabled"],
)
def test_build506_delete_extra_tags_build_config_works_for_each_tag_mode(tmp_path, monkeypatch, tag_field):
    _gui, app = _gui_probe(tmp_path, monkeypatch, tag_field)
    assert app._build_config().delete_extra_tags is True


def test_build506_reservation_race_never_deletes_foreign_directory(tmp_path, monkeypatch):
    home, vol, dest, rid = _setup(tmp_path)
    real = shutil.disk_usage

    def disk_usage_then_race(path):
        foreign = dest / "show-one"
        foreign.mkdir(exist_ok=True)
        (foreign / "USER_DATA.flac").write_bytes(b"not TLO's")
        return real(path)

    monkeypatch.setattr(CR.shutil, "disk_usage", disk_usage_then_race)
    res = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert res.failures and "Destination appeared during copy" in res.failures[0][1]
    assert (dest / "show-one" / "USER_DATA.flac").read_bytes() == b"not TLO's"


def test_build506_copy_uses_temp_tree_and_failure_never_exposes_partial_final_tree(tmp_path, monkeypatch):
    home, vol, dest, rid = _setup(tmp_path)
    final_target = dest / "show-one"
    observed = {}

    def fail_during_temp_copy(source, temp_target, *, ignore_root_names=()):
        temp = Path(temp_target)
        observed["temp"] = temp
        observed["final_exists_during_copy"] = final_target.exists()
        observed["final_entries_during_copy"] = list(final_target.iterdir()) if final_target.exists() else []
        (temp / "partial").mkdir()
        (temp / "partial" / "track.flac").write_bytes(b"partial")
        raise RuntimeError("simulated interrupted copy")

    monkeypatch.setattr(CR, "_copy_into_temp_target", fail_during_temp_copy)
    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert result.failures and "simulated interrupted copy" in result.failures[0][1]
    assert observed["temp"].name.startswith(CR.STALE_COPY_PREFIX)
    assert observed["final_exists_during_copy"] is True  # empty reservation only
    assert observed["final_entries_during_copy"] == []
    assert not final_target.exists()
    assert not list(dest.glob(f"{CR.STALE_COPY_PREFIX}*"))


def test_build506_owned_stale_temp_is_swept_and_copy_can_resume(tmp_path):
    home, vol, dest, rid = _setup(tmp_path)
    stale = dest / f"{CR.STALE_COPY_PREFIX}old-request-deadbeef"
    stale.mkdir()
    (stale / CR.COPY_TEMP_MARKER_FILENAME).write_text('{"request_id":"old"}\n', encoding="utf-8")
    (stale / "partial.flac").write_bytes(b"partial")

    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert result.copied
    assert not stale.exists()
    assert (dest / "show-one" / "track01.flac").read_bytes() == b"one"


def test_build506_unowned_tlo_like_temp_name_is_not_deleted(tmp_path):
    home, vol, dest, rid = _setup(tmp_path)
    foreign = dest / f"{CR.STALE_COPY_PREFIX}not-owned"
    foreign.mkdir()
    (foreign / "USER_DATA.flac").write_bytes(b"keep")
    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert result.copied
    assert (foreign / "USER_DATA.flac").read_bytes() == b"keep"


def test_build506_volume_root_path_and_bracket_syntax_share_os_exclusions(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol = tmp_path / "VOLROOT"
    _music_folder(vol, "Dead/show-one", b"one")
    system = vol / "System Volume Information"
    system.mkdir()
    write_bootlist_rows(str(home), [_row(SHOW, "VOL", "Dead/show-one")])
    real = os.scandir

    def denying_scandir(path="."):
        if str(path).endswith("System Volume Information"):
            raise PermissionError(13, "Access is denied", str(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", denying_scandir)
    for index, line in enumerate((str(vol), "[VOL]")):
        req = tmp_path / f"req-{index}.txt"
        req.write_text(line + "\n", encoding="utf-8")
        dest = tmp_path / f"dest-{index}"
        dest.mkdir()
        rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
        result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
        assert len(result.copied) == 1
        target = Path(result.copied[0][2])
        assert not (target / "System Volume Information").exists()
        assert (target / "Dead" / "show-one" / "track01.flac").read_bytes() == b"one"


def test_build506_decoder_preserves_utf8_in_mixed_utf8_cp1252_file():
    raw = "Gürzenich, Köln\n".encode("utf-8") * 3 + b"caf\xe9\n"
    text, encoding = decode_text_bytes(raw)
    assert "Gürzenich" in text and "GÃ¼rzenich" not in text
    assert "café" in text
    assert encoding == "utf-8+cp1252"


def test_build506_decoder_accepts_truncated_utf8_sample_boundary():
    raw = ("Café " * 10).encode("utf-8")[:-2]
    text, encoding = decode_text_bytes(raw)
    assert "CafÃ©" not in text
    assert text.startswith("Café Café")
    assert encoding == "utf-8-truncated-sample"


@pytest.mark.parametrize("encoding", ["utf-16-le", "utf-16-be"])
def test_build506_decoder_recognizes_bomless_utf16(encoding):
    raw = "Grateful Dead\n1977-05-08\n".encode(encoding)
    text, detected = decode_text_bytes(raw)
    assert text == "Grateful Dead\n1977-05-08\n"
    assert detected == encoding
    assert "\x00" not in text


def test_build506_rtf_character_escapes_preserve_accents(tmp_path):
    path = tmp_path / "setlist.rtf"
    path.write_bytes(br"{\rtf1\ansi G\'fcrzenich K\'f6ln\par Caf\'e9\par \u252?ber\par}")
    text = read_text_file_full(str(path))
    assert "Gürzenich Köln" in text
    assert "Café" in text
    assert "über" in text


def test_build506_process_environment_precedes_persisted_windows_fallback(monkeypatch):
    persisted = {
        sfm.ENV_API_KEY: "persisted-key",
        sfm.ENV_UPGRADE_API_KEY: "persisted-key",
    }
    monkeypatch.setattr(sfm, "_persistent_windows_environment_value", lambda name: persisted.get(name, ""))
    monkeypatch.setenv(sfm.ENV_API_KEY, "session-key")
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "session-key")
    assert sfm.get_api_key() == "session-key"
    assert sfm.upgrade_api_key_status() == "available"

    monkeypatch.delenv(sfm.ENV_API_KEY)
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY)
    assert sfm.get_api_key() == "persisted-key"
    assert sfm.upgrade_api_key_status() == "available"


def test_build506_upgrade_status_explains_missing_and_mismatched_keys(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("tlo_main_build506_status", ROOT / "tlo-main.py")
    gui = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gui)

    monkeypatch.setattr(sfm, "_persistent_windows_environment_value", lambda _name: "")
    monkeypatch.delenv(sfm.ENV_API_KEY, raising=False)
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY_ALIASES[0], raising=False)
    assert sfm.upgrade_api_key_status() == "missing-normal"
    assert "SETLISTFM_API_KEY" in gui._setlistfm_upgrade_gate_message("missing-normal")

    monkeypatch.setenv(sfm.ENV_API_KEY, "normal")
    assert sfm.upgrade_api_key_status() == "missing-upgrade"
    assert "SETLISTFMUPGRADE_API_KEY" in gui._setlistfm_upgrade_gate_message("missing-upgrade")

    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "different")
    assert sfm.upgrade_api_key_status() == "mismatch"
    assert "does not match" in gui._setlistfm_upgrade_gate_message("mismatch")
