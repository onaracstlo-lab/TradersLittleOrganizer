"""Focused unit regressions for the Build 397 technical-review remediations."""
__version__ = "v426"

import importlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def _matcher(*masters):
    from tlo_artist_db import ArtistMatcher
    matcher = ArtistMatcher(db_path="")
    for master in masters:
        matcher.exact_map.setdefault(master.casefold(), set()).add(master)
        matcher.master_aliases[master] = [master]
        matcher.master_norms[master] = {"".join(ch for ch in master.casefold() if ch.isalpha())}
    return matcher


@pytest.mark.parametrize("stem,artist", [
    ("Two Gentlemen 1979-10-05", "Two"),
    ("Two Gentlemen In New York 1979-10-05", "Two"),
    ("Live In Boston 1999-01-01", "Live"),
    ("The Wall 1980-08-09", "The"),
])
def test_one_word_artist_date_must_be_first_substantive_component(stem, artist):
    import tlo_phase23_v2 as P
    assert P._setlist_filename_artist_match_is_credible(stem, artist) is False


@pytest.mark.parametrize("stem", [
    "Prince 1984-06-07", "Prince - 1984-06-07", "Prince_1984-06-07",
    "Prince.1984-06-07", "Prince 06-07-1984", "Prince - Purple Rain Tour",
])
def test_supported_one_word_artist_filename_structures_remain_valid(stem):
    import tlo_phase23_v2 as P
    assert P._setlist_filename_artist_match_is_credible(stem, "Prince") is True


def test_setlist_metadata_rejects_over_16mib_before_read(tmp_path):
    import tlo_setlist_metadata_lookup as M
    from tlo_text_utils import MAX_TEXT_FULL_BYTES
    path = tmp_path / "huge.txt"
    with path.open("wb") as handle:
        handle.truncate(MAX_TEXT_FULL_BYTES + 1)
    assert M._read_text_file(str(path)) == ("", "too-large")
    result = M.extract_setlist_venue_location(str(path), str(tmp_path))
    assert result.source == "setlist_metadata:file_too_large"


def test_setlist_metadata_reads_only_sample_ceiling(tmp_path, monkeypatch):
    import tlo_setlist_metadata_lookup as M
    from tlo_text_utils import MAX_TEXT_SAMPLE_BYTES
    path = tmp_path / "sample.txt"
    path.write_bytes(b"Albany New York\n" + b"x" * (MAX_TEXT_SAMPLE_BYTES + 1000))
    text, _encoding = M._read_text_file(str(path))
    assert len(text.encode("latin-1", errors="ignore")) <= MAX_TEXT_SAMPLE_BYTES
    assert text.startswith("Albany New York")


def test_flac_validator_timeout_is_unverifiable(tmp_path):
    import importlib.util
    source = Path(__file__).resolve().parents[2] / "tlo-deleteDupes.py"
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_build397", source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    flac = tmp_path / "track.flac"; flac.write_bytes(b"placeholder")
    seen = {}
    def fake_run(command, **kwargs):
        seen.update(kwargs)
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout", 0))
    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=fake_run) is None
    assert seen["timeout"] == module.FLAC_VALIDATION_TIMEOUT_SECONDS


def test_unverifiable_keeper_blocks_duplicate_cluster_relocation(tmp_path):
    import importlib.util
    source = Path(__file__).resolve().parents[2] / "tlo-deleteDupes.py"
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_build397b", source)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    original = tmp_path / "Show"; copy = tmp_path / "Show (copy2)"
    original.mkdir(); copy.mkdir(); (original/"01.flac").write_bytes(b"a"); (copy/"01.flac").write_bytes(b"a")
    candidate = module.CopyCandidate(path=str(copy), number=2)
    result = module.repair_corrupt_flacs_from_copies(str(original), [candidate], health_check=lambda *a, **k: None, emit=lambda *a, **k: None)
    assert result == (0, 0, True)


def test_update_source_ignores_environment_redirect(monkeypatch):
    import tlo_github_updates as U
    monkeypatch.setenv("TLO_GITHUB_OWNER", "attacker")
    monkeypatch.setenv("TLO_GITHUB_REPO", "payloads")
    U = importlib.reload(U)
    assert U.DEFAULT_REPO_OWNER == "onaracstlo-lab"
    assert U.DEFAULT_REPO_NAME == "TradersLittleOrganizer"


def test_update_rejects_declared_oversize_before_network(tmp_path, monkeypatch):
    import tlo_github_updates as U
    monkeypatch.setattr(U.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(AssertionError("network should not run")))
    asset = {"name":"TLO.zip", "browser_download_url":"https://github.com/x/y/TLO.zip", "size":U.MAX_UPDATE_ASSET_BYTES + 1}
    with pytest.raises(ValueError, match="implausibly large"):
        U._download_asset(asset, tmp_path/"TLO.zip")


def test_update_stream_aborts_when_response_exceeds_declared_size(tmp_path, monkeypatch):
    import tlo_github_updates as U
    class Response:
        headers = {"Content-Length": "4"}
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self, _size):
            if getattr(self, "done", False): return b""
            self.done=True; return b"12345"
    asset = {"name":"TLO.zip", "browser_download_url":"https://github.com/x/y/TLO.zip", "size":4, "digest":"sha256:" + "0"*64}
    monkeypatch.setattr(U, "_open_download_url", lambda *a, **k: Response())
    with pytest.raises(IOError, match="exceeded the declared size"):
        U._download_asset(asset, tmp_path/"TLO.zip")
    assert not (tmp_path/"TLO.zip").exists()


def test_shared_location_connective_set_used_by_both_engines():
    import tlo_constants as C, tlo_phase23_v2 as P, tlo_setlist_metadata_lookup as M
    assert P.LOCATION_CONNECTIVE_WORDS is C.LOCATION_CONNECTIVE_WORDS
    assert M.LOCATION_CONNECTIVE_WORDS is C.LOCATION_CONNECTIVE_WORDS
    assert "in" in C.LOCATION_CONNECTIVE_WORDS


def test_setlistfm_compatibility_cli_uses_production_lookup(monkeypatch, tmp_path):
    import setlistFM as C
    seen = {}
    monkeypatch.setattr(C, "resolve_tlo_home", lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(C, "search_setlists", lambda artist, date, **kwargs: (seen.update({"artist":artist,"date":date,**kwargs}) or []))
    assert C.main(["Artist", "2000-01-01", "--silent"]) == 2
    assert seen["tlo_home"] == str(tmp_path)
    assert seen["run_id"] == "setlistFM-cli"


def test_macos_trash_passes_path_as_argv_not_applescript(monkeypatch):
    import tlo_corruption as C
    seen = {}
    monkeypatch.setattr(C.sys, "platform", "darwin")
    def fake_run(args, **kwargs): seen["args"] = args; seen["kwargs"] = kwargs; return SimpleNamespace(returncode=0)
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    path = '/tmp/name"\nbeep'
    C.move_to_trash(path)
    assert seen["args"][-1] == str(Path(path).resolve())
    assert path not in seen["args"][2]
