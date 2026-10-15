"""Build 587: potential-duplicate isolation and Tag's TLOHome DB bootstrap."""
from types import SimpleNamespace

import pytest

import tlo_inventory_update as updater
import tlo_tag_lib as tagger

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize("existing_volume", ["[Remote] F:\\Old", "[Local] E:\\Old", "Show Without Volume"])
@pytest.mark.parametrize("rename_compliantly", [False, True])
def test_potential_duplicate_never_staged_or_inventoried(tmp_path, monkeypatch, existing_volume, rename_compliantly):
    home = tmp_path / "home"
    incoming = home / "readyForXfer" / "Grateful Dead 1977-05-08 Barton Hall Ithaca NY"
    incoming.mkdir(parents=True)
    (incoming / "01 Scarlet Begonias.flac").write_bytes(b"synthetic test content")
    (incoming / "info.txt").write_text("01 Scarlet Begonias\n")
    preexisting = {"Show": incoming.name, "VolumePath": existing_volume}
    updater.write_bootlist(str(home), [preexisting])
    original_contents = {p.name: p.read_bytes() for p in incoming.iterdir()}
    config = SimpleNamespace(TLOHome=str(home), rename_compliantly=rename_compliantly, compliant=False)
    monkeypatch.setattr(updater, "prepare_updater_config", lambda c: c)
    monkeypatch.setattr(updater, "load_artist_matcher", lambda c: object())
    monkeypatch.setattr(updater, "identify_folder", lambda *a, **kw: object())
    monkeypatch.setattr(updater, "_record_dict_for_new_folder", lambda *a, **kw: {
        "show_name": incoming.name, "artist": "Grateful Dead", "setlist_file": str(incoming / "info.txt")
    })
    monkeypatch.setattr(updater, "find_potential_duplicate_rows_for_folder", lambda *a, **kw: [preexisting])
    # Explicitly fail if duplicate path enters ANY acceptance side effect.
    def forbidden(*_args, **_kwargs):
        pytest.fail("Potential duplicate reached an accepted-show side effect")
    for name in ("_rename_add_shows_folder_compliantly", "create_or_replace_generated_setlist",
                 "_add_bootlist_row_for_record", "_tag_add_shows_folder_in_place"):
        monkeypatch.setattr(updater, name, forbidden)
    monkeypatch.setattr(updater, "_log_add_shows_metadata", lambda *a, **kw: None)

    result = updater.process_new_shows(config, "[Current]E:\\Music", check_duplicates=True)
    assert result["processed"] == result["duplicates"] == 1
    assert result["staged"] == result["errors"] == 0
    assert result["potential_duplicates_unavailable"] == 0
    moved = home / "dups" / incoming.name
    assert moved.is_dir() and not incoming.exists()
    assert {p.name: p.read_bytes() for p in moved.iterdir()} == original_contents
    assert not list((home / "staged").iterdir())
    assert not list((home / "setlists").iterdir())
    assert updater.read_bootlist(str(home)) == [preexisting]
    assert "pdup" not in moved.name.lower()


def test_duplicate_destination_collision_preserves_both(tmp_path, monkeypatch):
    home = tmp_path / "home"
    incoming = home / "readyForXfer" / "Band 2000-01-01 Venue"
    incoming.mkdir(parents=True)
    (incoming / "info.txt").write_text("incoming")
    duplicate = home / "dups" / incoming.name
    duplicate.mkdir(parents=True)
    (duplicate / "info.txt").write_text("old")
    existing = {"Show": incoming.name, "VolumePath": "[remote] F:\\old"}
    updater.write_bootlist(str(home), [existing])
    config = SimpleNamespace(TLOHome=str(home), compliant=True, rename_compliantly=True)
    monkeypatch.setattr(updater, "prepare_updater_config", lambda c: c)
    monkeypatch.setattr(updater, "load_artist_matcher", lambda c: object())
    monkeypatch.setattr(updater, "identify_folder", lambda *a, **kw: object())
    monkeypatch.setattr(updater, "find_potential_duplicate_rows_for_folder", lambda *a, **kw: [existing])
    monkeypatch.setattr(updater, "_record_dict_for_new_folder", lambda *a, **kw: {"show_name": incoming.name})
    monkeypatch.setattr(updater, "_log_add_shows_metadata", lambda *a, **kw: None)
    result = updater.process_new_shows(config, "[current] E:\\Music")
    assert result["duplicates"] == 1 and result["errors"] == 0
    assert (duplicate / "info.txt").read_text() == "old"
    assert (home / "dups" / f"{incoming.name}_2" / "info.txt").read_text() == "incoming"


def test_gui_tag_initializes_database_paths_before_validation(tmp_path, monkeypatch):
    home = tmp_path / "tlo-home"
    home.mkdir()
    config = SimpleNamespace(TLOHome=str(home), compliant=True,
        tag_during_inventory=True, tag_copy_during_inventory=False,
        tag_copy_destination="", tag_copy_and_delete_path="",
        rename_compliantly=False, convert_shn=False,
        etree_lookup=False, setlistfm_lookup=False)
    paths_seen = []
    def check(c):
        paths_seen.append((c.artist_sqlite_db_file, c.venue_reference_db_file))
        assert c.artist_sqlite_db_file == str(home / "TLO_DBs" / "artists.sqlite")
        assert c.venue_reference_db_file == str(home / "TLO_DBs" / "venues.txt")
    monkeypatch.setattr(tagger, "validate_required_databases", check)
    monkeypatch.setattr(tagger, "load_artist_matcher", lambda _c: object())
    monkeypatch.setattr(tagger, "_groups_from_inventory_discovery", lambda *_args: [])
    totals = tagger.run_tagger_jobs(config, [{"path": str(home)}], emit=lambda _: None)
    assert totals["groups"] == 0
    assert len(paths_seen) == 1


def test_standalone_tag_initializes_database_paths_before_validation(tmp_path, monkeypatch):
    home = tmp_path / "tlo-home"
    home.mkdir()
    seen = []
    def check(c):
        seen.append(c.artist_sqlite_db_file)
        assert c.artist_sqlite_db_file == str(home / "TLO_DBs" / "artists.sqlite")
    monkeypatch.setattr(tagger, "validate_required_databases", check)
    monkeypatch.setattr(tagger, "load_artist_matcher", lambda _c: object())
    monkeypatch.setattr(tagger, "_groups_from_inventory_discovery", lambda *_args: [])
    totals = tagger.run_tagger(tlo_home=str(home), tag_path=str(home), emit=lambda _: None)
    assert totals["groups"] == 0
    assert len(seen) == 1
