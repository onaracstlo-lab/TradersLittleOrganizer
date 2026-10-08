import json
import stat
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

import tlo_copy_requests as CR
import tlo_github_updates as GU
import tlo_inventory_update as IU
import tlo_setlistfm_lookup as SFM
import tlo_text_utils as TU
import initial_dir_walk_lib as IW
from test_build503_copy_request_direct_paths_volumes import _artist_db, _music_folder, _row, _request
from tlo_bootlist_volume_policy import write_bootlist_rows

pytestmark = pytest.mark.behavior

SHOW = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"


def _setup(tmp_path):
    home = tmp_path / "home"; home.mkdir(); _artist_db(home)
    vol = tmp_path / "VOL"; _music_folder(vol, "Dead/show-one", b"one")
    write_bootlist_rows(str(home), [_row(SHOW, "VOL", "Dead/show-one")])
    dest = tmp_path / "dest"; dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(_request(tmp_path, "Grateful Dead\n")), str(dest))["request_id"]
    return home, vol, dest, rid


@pytest.mark.parametrize("row", [
    "[B] /Volumes/Backup/../..",
    "[B] /Volumes/Backup/..",
    "[B] /mnt/e",
    "[B] E:\\\\",
    "[B] E:",
])
def test_build507_delete_script_rejects_roots_and_parent_traversal(row):
    assert IU._delete_path_from_bootlist_volume_path(row) == ""


@pytest.mark.parametrize("row,expected", [
    ("[Backup-1] E:\\\\boots\\\\Dead", r"E:\boots\Dead"),
    ("[Backup-1] /mnt/e/boots/Dead", "/mnt/e/boots/Dead"),
    ("[Backup-1] /Volumes/Backup-1/boots/Dead", "/Volumes/Backup-1/boots/Dead"),
])
def test_build507_delete_script_accepts_paths_below_volume_root(row, expected):
    label, path = IU._delete_target_from_bootlist_volume_path(row)
    assert label == "Backup-1"
    assert path == expected


def test_build507_delete_target_rejects_tlohome_and_ancestor(tmp_path):
    home = tmp_path / "disk" / "tlo"; home.mkdir(parents=True)
    assert IU._canonical_safe_delete_path(str(home), tlo_home=str(home)) == ""
    assert IU._canonical_safe_delete_path(str(home.parent), tlo_home=str(home)) == ""


def test_build507_non_ascii_key_never_crashes_and_invisible_is_explained(monkeypatch):
    monkeypatch.setenv("SETLISTFM_API_KEY", "abc")
    monkeypatch.setenv("SETLISTFMUPGRADE_API_KEY", "abc”")
    assert SFM.upgrade_api_key_status() == "invalid-characters"
    monkeypatch.setenv("SETLISTFM_API_KEY", "abc\u200b")
    monkeypatch.setenv("SETLISTFMUPGRADE_API_KEY", "abc\u200b")
    assert SFM.upgrade_api_key_status() == "invalid-characters"


def test_build507_interrupted_pending_copy_recovers_reservation_and_temp(tmp_path):
    home, vol, dest, rid = _setup(tmp_path)
    target = dest / "show-one"
    state = CR.load_request(str(home), rid)
    CR._set_pending_copy(str(home), state, item=SHOW, kind="show", source=str(vol / "Dead/show-one"), target=str(target), temp="", phase="prepared")
    CR._reserve_copy_target(str(target))
    temp = CR._create_owned_copy_temp(str(dest), rid)
    CR._set_pending_copy(str(home), state, item=SHOW, kind="show", source=str(vol / "Dead/show-one"), target=str(target), temp=temp, phase="copying")
    (Path(temp) / "partial.flac").write_bytes(b"partial")
    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert result.copied
    assert not Path(temp).exists()
    assert target.is_dir() and any(target.rglob("*.flac"))
    assert not CR.load_request(str(home), rid).get("pending_copy")


def test_build507_live_temp_is_not_swept(tmp_path):
    _home, _vol, dest, _rid = _setup(tmp_path)
    temp = CR._create_owned_copy_temp(str(dest), "another-live-pass")
    assert CR._cleanup_stale_copy_temps(str(dest)) == []
    assert Path(temp).exists()


def test_build507_cancel_cleans_transaction_and_keeps_request_open(tmp_path):
    home, vol, dest, rid = _setup(tmp_path)
    calls = {"n": 0}
    def cancel():
        calls["n"] += 1
        return calls["n"] >= 2
    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]}, cancel_check=cancel)
    assert result.cancelled is True
    assert CR.load_request(str(home), rid)["closed"] is False
    assert not (dest / "show-one").exists()
    assert not list(dest.glob(".tlo-copy-*"))


def test_build507_rtf_tokenizer_handles_textedit_and_destinations(tmp_path):
    rtf = (r"{\rtf1\ansi\ansicpg1252\cocoartf2761" "\n"
           r"{\fonttbl\f0\fswiss\fcharset0 Helvetica;}" "\n"
           r"{\colortbl;\red255\green255\blue255;}" "\n"
           r"\pard\tx720\pardirnatural\partightenfactor0" "\n"
           r"\f0\fs24 \cf0 Al Di Meola\ " "\n"
           r"Live at G\'fcrzenich, K\'f6ln, Germany\ " "\n}")
    rtf = rtf.replace("\\ \n", "\\\n")
    p = tmp_path / "s.rtf"; p.write_text(rtf, encoding="latin-1")
    text = TU.read_text_file_full(str(p))
    assert "Helvetica" not in text and "irnatural" not in text
    assert "Al Di Meola\\" not in text
    assert "Al Di Meola" in text
    assert "Live at Gürzenich, Köln, Germany" in text


def test_build507_delete_script_has_utf8_and_volume_guard(tmp_path):
    bat = tmp_path / "deleteReplacedFolders.bat"
    assert IU._append_delete_command(str(bat), r"E:\boots\Björk", "Backup-1")
    text = bat.read_text(encoding="utf-8")
    assert "chcp 65001 >nul" in text
    assert 'REM "[Backup-1]" "E:\\boots\\Björk"' in text
    assert "vol E:" not in text and "findstr" not in text
    assert "Björk" in text


def test_build507_existing_delete_script_is_archived_per_session(tmp_path):
    home = tmp_path / "home"; (home / "logs").mkdir(parents=True)
    script = Path(IU.updater_delete_script_path(str(home)))
    script.write_text("old", encoding="utf-8")
    assert IU.archive_updater_delete_script_for_new_session(str(home)) == str(script)
    assert not script.exists()
    archived = list((home / "logs").glob("deleteBackupFolders-*"))
    assert len(archived) == 1 and archived[0].read_text(encoding="utf-8") == "old"


def _write_package(path, member_name="manifest.json", extra_name="file.txt", *, symlink=False, payload=b"x"):
    manifest = {"kind":"complete", "platform_key":"linux_x64", "build":507, "databases_included":True,
                "database_files":["artists.sqlite","venues.txt"], "packaging_mode":"complete"}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(member_name, json.dumps(manifest))
        zf.writestr("TLO_DBs/artists.sqlite", b"db")
        zf.writestr("TLO_DBs/venues.txt", b"v")
        if symlink:
            info = zipfile.ZipInfo(extra_name); info.create_system = 3; info.external_attr = (stat.S_IFLNK | 0o777) << 16
            zf.writestr(info, "target")
        else:
            zf.writestr(extra_name, payload)


@pytest.mark.parametrize("member", ["../evil.txt", "/abs.txt", "C:/evil.txt"])
def test_build507_update_zip_rejects_unsafe_member_paths(tmp_path, member):
    z = tmp_path / "p.zip"; _write_package(z, extra_name=member)
    with pytest.raises(ValueError):
        GU._inspect_downloaded_package(z, expected_kind="complete", expected_platform_key="linux_x64", expected_build=507)


def test_build507_update_zip_rejects_symlink_member(tmp_path):
    z = tmp_path / "p.zip"; _write_package(z, extra_name="link", symlink=True)
    with pytest.raises(ValueError):
        GU._inspect_downloaded_package(z, expected_kind="complete", expected_platform_key="linux_x64", expected_build=507)


def test_build507_phase1_prunes_os_and_tlo_temp_directories():
    for name in [".Trashes", ".Spotlight-V100", ".fseventsd", ".TemporaryItems", ".tlo-copy-x", ".tlo-partial-x", ".tlo-restore-x", ".tlo-convert-x"]:
        assert IW._phase1_should_prune_dir(name)


def test_build507_binary_doc_is_not_decoded_as_setlist_text(tmp_path):
    p = tmp_path / "legacy.doc"; p.write_bytes(b"\xd0\xcf\x11\xe0" + b"binary" * 20)
    assert TU.read_text_file_full(str(p)) == ""
