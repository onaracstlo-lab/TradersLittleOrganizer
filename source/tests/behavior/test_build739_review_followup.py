"""Behavioral coverage for follow-up repair and catalog-search remediation."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _dupes():
    spec = importlib.util.spec_from_file_location("delete_dupes739", ROOT / "tlo-deleteDupes.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _streaminfo_file(path, digest):
    # A valid readable STREAMINFO block: 44.1kHz, stereo, 16-bit, 100 samples.
    header = b"\x10\x00\x10\x00" + bytes(6)
    header += ((44100 << 44) | (1 << 41) | (15 << 36) | 100).to_bytes(8, "big")
    header += digest
    assert len(header) == 34
    path.write_bytes(b"fLaC\x80\x00\x00\x22" + header + b"fixture")


def test_different_recorded_md5_refuses_repair(tmp_path):
    d = _dupes()
    keeper = tmp_path / "keeper"
    copy = tmp_path / "copy"
    keeper.mkdir(); copy.mkdir()
    original = keeper / "track.flac"
    other = copy / "track.flac"
    expected = b"x" * 16
    _streaminfo_file(original, expected)
    _streaminfo_file(other, b"y" * 16)
    assert d._recorded_flac_md5(str(original)) == expected
    assert d._recorded_flac_md5(str(other)) != expected
    assert original.stat().st_size == other.stat().st_size
    initial = original.read_bytes()
    messages = []
    result = d.repair_corrupt_flacs_from_copies(str(keeper), [SimpleNamespace(path=str(copy), number=1,
                    source_kind="numbered", alphabetical_rank=0)],
        health_check=lambda path, **_: Path(path).parent == copy,
        replace_func=lambda *_: pytest.fail("Different audio was accepted"),
        emit=lambda msg, **_: messages.append(msg))
    assert result == (0, 1, False)
    assert original.read_bytes() == initial
    assert any("Different recorded FLAC audio MD5" in m for m in messages)


def test_successful_repair_preserves_original(tmp_path):
    d = _dupes()
    original = tmp_path / "keeper.flac"
    source = tmp_path / "copy.flac"
    original.write_bytes(b"corrupt-original")
    source.write_bytes(b"verified replacement")
    d._replace_file_from_copy(str(source), str(original))
    assert original.read_bytes() == source.read_bytes()
    retained = list(tmp_path.glob(".tlo-deleteDupes-originals-*/keeper.flac"))
    assert len(retained) == 1
    assert retained[0].read_bytes() == b"corrupt-original"
    assert all(".tlo-deleteDupes-originals" not in p for p in d._relative_flac_paths(str(tmp_path)))
    assert not list(tmp_path.glob(".tlo-deleteDupes-backup-*.flac"))


def test_aux_article_and_accent_matches():
    import searchAuxDBs as aux
    obj = SimpleNamespace(db_path=ROOT / "TLO_DBs" / "artists.sqlite",
                            _validate_required_tables=aux.AuxiliarySearchApp._validate_required_tables)
    rows = aux.AuxiliarySearchApp._query_database(obj, "The Grateful Dead")
    assert any(r.master_name.casefold() == "grateful dead" for r in rows)
    from tlo_artist_db import load_artist_matcher, lookup_artist_masters
    m = load_artist_matcher(SimpleNamespace(artist_sqlite_db_file=str(obj.db_path)))
    expected = set(lookup_artist_masters("BJÖRK", m, _allow_terminal_artist_suffix_fallback=False))
    assert expected == {"Bjork"}
    rows = aux.AuxiliarySearchApp._query_database(obj, "BJÖRK")
    assert {r.master_name for r in rows} == expected


def test_aux_home_precedence(tmp_path, monkeypatch):
    import searchAuxDBs as aux
    from tlo_path_inputs import resolve_tlo_home
    homes = [tmp_path / sub for sub in ("env", "cli", "legacy")]
    for h in homes:
        h.mkdir()
    monkeypatch.setenv("TLOHome", str(homes[0]))
    args = aux.parse_args(["--TLOHome", str(homes[1]), "--myTLO", str(homes[2])])
    with pytest.raises(ValueError, match="disagree"):
        resolve_tlo_home(args.TLOHome, args.myTLO, require_writable=False)
    assert Path(resolve_tlo_home(args.TLOHome, require_writable=False)) == homes[1]
    assert aux.default_tlohome() == homes[0]
    with pytest.raises(ValueError):
        aux.parse_args(["--database", "Cities"])
    with pytest.raises(ValueError, match="fully qualified"):
        resolve_tlo_home("relative", require_writable=False)


def test_upgrade_is_explicit_without_duplicate_key(monkeypatch):
    import tlo_setlistfm_lookup as sfm
    from tlo_options import validate_setlistfm_upgrade_environment
    monkeypatch.setattr(sfm, "_persistent_windows_environment_value", lambda _: "")
    monkeypatch.setenv(sfm.ENV_API_KEY, "valid-key")
    for key in (sfm.ENV_UPGRADE_API_KEY, *sfm.ENV_UPGRADE_API_KEY_ALIASES):
        monkeypatch.delenv(key, raising=False)
    assert sfm.upgrade_api_key_available()
    validate_setlistfm_upgrade_environment({"setlistfm_lookup": True, "setlistfm_upgrade": True})
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "incorrect")
    with pytest.raises(ValueError):
        validate_setlistfm_upgrade_environment({"setlistfm_lookup": True, "setlistfm_upgrade": True})
    validate_setlistfm_upgrade_environment({"setlistfm_lookup": True, "setlistfm_upgrade": False})


def test_repair_holds_original_outside_show(tmp_path):
    d = _dupes()
    keeper = tmp_path / "keeper"
    copy = tmp_path / "copy"
    keeper.mkdir()
    copy.mkdir()
    original = keeper / "track.flac"
    source = copy / "track.flac"
    _streaminfo_file(original, b"x" * 16)
    _streaminfo_file(source, b"x" * 16)
    original.write_bytes(original.read_bytes() + b"bad")
    previous = original.read_bytes()
    def health(path, **_):
        return Path(path).read_bytes() == source.read_bytes()
    result = d.repair_corrupt_flacs_from_copies(str(keeper), [
        SimpleNamespace(path=str(copy), number=1, source_kind="numbered", alphabetical_rank=0)],
        health_check=health, emit=lambda *_a, **_kw: None)
    assert result == (1, 0, False)
    retained = list(tmp_path.glob(".tlo-deleteDupes-originals-*/track.flac"))
    assert len(retained) == 1 and retained[0].read_bytes() == previous
    assert list(keeper.iterdir()) == [original]
