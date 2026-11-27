"""Rename Compliantly must accept verified artist/date trading shorthand."""
import unittest
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from tlo_artist_db import ArtistMatcher, _compressed_artist_key, _letters_only
from tlo_folder_rename import rename_folder_exact_case
from tlo_rename_safety import safe_rename_target

pytestmark = pytest.mark.behavior

DB = Path(__file__).resolve().parents[2] / "TLO_DBs"
TARGET = "Trey Anastasio 2005-12-02 The Warfield San Francisco, CA"
SOURCE = "trey05-12-02.flac"


def _matcher():
    matcher = ArtistMatcher(db_path="")
    matcher.master_aliases = {
        "Trey Anastasio": ["Trey Anastasio", "Anastasio, Trey", "trey"],
        "Grateful Dead": ["Grateful Dead", "gd"],
    }
    matcher.exact_map = {alias.casefold(): {master} for master, aliases in
                         matcher.master_aliases.items() for alias in aliases}
    matcher.compressed_map = {_compressed_artist_key(k): v for k, v in matcher.exact_map.items()}
    matcher.master_norms = {m: {_letters_only(a) for a in aliases}
                            for m, aliases in matcher.master_aliases.items()}
    return matcher


class ShorthandRenameTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.config = SimpleNamespace(
            compliant=False, current_volume_label="", current_slam="",
            as_is_artist_name=False, compliant_artist_mode="master",
            etree_lookup=False, setlistfm_lookup=False, tlo_dbs_dir=str(DB),
            TLOHome=str(self.root), debug=False, rename_compliantly=True,
        )

    def record(self, parent, leaf=SOURCE, header=True, matcher=None, wrong_second_date=False):
        from tlo_phase23_v2 import _extract_metadata_for_group

        path = self.root / parent / leaf
        path.mkdir(parents=True)
        prefix = "gd" if leaf.startswith("gd") else "trey"
        show_date = "1977-05-08" if prefix == "gd" else "2005-12-02"
        files = [path / f"{prefix}{show_date}d1t01.flac",
                 path / f"{prefix}{'2002-05-12' if wrong_second_date else show_date}d1t02.flac"]
        for file in files:
            file.write_bytes(b"placeholder media; metadata-only fixture")
        txt = path / f"{prefix}{show_date}.txt"
        if header:
            txt.write_text("Trey Anastasio\nThe Warfield\nSan Francisco, Ca\nDecember 2, 2005\n\n"
                           "Source: Nakamichi 701s -> Luminous P/S -> Sony M1 DAT (48 kHz)\n\n"
                           "Disc 1\n1. 70 Volt Parade (prerecorded)\n2. Push On Til The Day\n",
                           encoding="utf-8")
        group = dict(group_number=1, main_dir_name=leaf, main_dir_path=str(path),
                     setlist_file=str(txt) if header else "", setlist_files=[str(txt)] if header else [],
                     music_dirs=[str(path)], music_files=list(map(str, files)), music_file_count=2,
                     flac_tag_samples=[], flac_tag_artist_values=[], flac_tag_album_values=[],
                     flac_tag_albumartist_values=[], flac_tag_date_values=[])
        record, dates, unresolved = _extract_metadata_for_group(self.config, group, matcher or _matcher())
        return path, group, record, dates, unresolved

    def test_reported_path_setlist_and_alias_then_physical_rename(self):
        path, _, record, dates, unresolved = self.record("x/A/Anastasio, Trey/2005")
        self.assertEqual(record.show_name, TARGET)
        self.assertEqual(record.verified_rename_prefix, "trey")
        self.assertFalse(unresolved)
        self.assertEqual({d["normalized"] for d in dates}, {"2002-05-12", "2005-12-02"})
        self.assertTrue(any(c.source.startswith("path_artist_before_abbreviation:") for c in record.evidence["artist"]))
        self.assertTrue(any(c.source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER" for c in record.evidence["artist"]))
        accepted, reason = safe_rename_target(path.name, record.show_name, artist=record.artist,
                                              date=record.date, verified_prefix=record.verified_rename_prefix)
        self.assertEqual((accepted, reason), (TARGET, ""))
        destination = path.with_name(accepted)
        rename_folder_exact_case(str(path), str(destination))
        self.assertFalse(path.exists())
        self.assertTrue((destination / "trey2005-12-02d1t01.flac").is_file())

    def test_setlist_without_artist_parent(self):
        _, _, rec, _, unresolved = self.record("tmp")
        self.assertEqual(rec.show_name, TARGET)
        self.assertFalse(unresolved)
        self.assertTrue(any(c.source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER" for c in rec.evidence["artist"]))

    def test_alias_and_repeated_full_dates_without_setlist_or_artist_parent(self):
        _, _, rec, _, unresolved = self.record("tmp", header=False)
        self.assertEqual(rec.artist, "Trey Anastasio")
        self.assertEqual(rec.date, "2005-12-02")
        self.assertEqual(rec.verified_rename_prefix, "trey")
        self.assertFalse(unresolved)
        self.assertTrue(any(c.source == "filename_shorthand_date_validation" for c in rec.evidence["date"]))

    def test_disagreeing_tracks_do_not_resolve_ambiguous_date(self):
        _, _, rec, _, unresolved = self.record("tmp", header=False, wrong_second_date=True)
        self.assertFalse(rec.date)
        self.assertTrue(any("date conflict" in r for r in unresolved))
        self.assertFalse(rec.verified_rename_prefix)

    def test_short_alias_with_no_literal_artist_word_requires_verified_mapping(self):
        _, _, rec, _, unresolved = self.record("tmp", leaf="gd1977-05-08.flac", header=False)
        self.assertFalse(unresolved)
        self.assertEqual(rec.artist, "Grateful Dead")
        self.assertEqual(rec.verified_rename_prefix, "gd")
        self.assertEqual(safe_rename_target("gd1977-05-08.flac", rec.show_name,
                           artist=rec.artist, date=rec.date, verified_prefix="gd"), (rec.show_name, ""))
        self.assertFalse(safe_rename_target("gd1977-05-08.flac", rec.show_name,
                         artist=rec.artist, date=rec.date)[0])

    def test_colliding_alias_is_not_proof(self):
        matcher = _matcher()
        matcher.exact_map["trey"].add("Another Trey")
        _, _, rec, _, _ = self.record("tmp", matcher=matcher)
        self.assertEqual(rec.artist, "Trey Anastasio")
        self.assertFalse(rec.verified_rename_prefix)

    def test_protection_against_losing_other_identity(self):
        for source in ("trey05-12-02.flac24", "trey05-12-02.flac (late)",
                       "trey05-12-02.flac (24)", "trey05-12-02.flac 12345",
                       "trey05-12-02 SBD", "trey2004-12-02.flac",
                       "trey05-12-02 The Fillmore", "fake05-12-02.flac"):
            with self.subTest(source=source):
                self.assertFalse(safe_rename_target(source, TARGET, artist="Trey Anastasio",
                                 date="2005-12-02", verified_prefix="trey")[0])
        target = TARGET + " (late) (24)"
        self.assertEqual(safe_rename_target(SOURCE + " (late) (24)", target,
                         artist="Trey Anastasio", date="2005-12-02", verified_prefix="trey"), (target, ""))

    def test_inventory_rename_in_place(self):
        from tlo_tag_lib import prepare_inventory_tagging_target
        path, group, record, _, _ = self.record("x/A/Anastasio, Trey/2005")
        _, moved = prepare_inventory_tagging_target(self.config, group, record)
        self.assertEqual(Path(moved.main_dir_path), path.with_name(TARGET))
        self.assertEqual(Path(moved.original_main_dir_path), path)
        self.assertFalse(path.exists())

    def test_add_shows_rename_in_place(self):
        from tlo_inventory_update import _metadata_to_record_dict, _rename_add_shows_folder_compliantly
        path, _, record, _, _ = self.record("tmp", leaf="gd1977-05-08.flac", header=False)
        row = _metadata_to_record_dict(record)
        self.assertEqual(row["verified_rename_prefix"], "gd")
        result = _rename_add_shows_folder_compliantly(self.config, str(path), row)
        self.assertEqual(Path(result), path.with_name(record.show_name))
        self.assertFalse(path.exists())

    def test_copy_delete_real_transfer(self):
        from tlo_tag_lib import prepare_inventory_copy_delete_target
        path, group, record, _, _ = self.record("x/A/Anastasio, Trey/2005")
        destination_parent = self.root / "tmp"
        destination_parent.mkdir()
        self.config.tag_copy_and_delete_path = str(destination_parent)
        logs = []
        moved_group, moved_record = prepare_inventory_copy_delete_target(self.config, group, record, logs.append)
        dest = destination_parent / TARGET
        self.assertEqual(Path(moved_record.main_dir_path), dest)
        self.assertEqual(Path(moved_record.original_main_dir_path), path)
        self.assertEqual(Path(moved_group["main_dir_path"]), dest)
        self.assertFalse(path.exists())
        self.assertTrue((dest / "trey2005-12-02d1t01.flac").is_file())
        self.assertFalse(any("RENAME_COMPLIANTLY_SKIP" in log for log in logs))


if __name__ == "__main__":
    unittest.main()


@pytest.mark.parametrize("flavor,folder", [
    ("windows", r"C:\Music\tmp\trey05-12-02.flac"),
    ("windows", r"\\server\share\Music\tmp\trey05-12-02.flac"),
    ("posix", "/mnt/d/Music/tmp/trey05-12-02.flac"),
    ("posix", "/Music/tmp/trey05-12-02.flac"),
])
def test_build733_rooted_shorthand_date_validation(flavor, folder, monkeypatch):
    """Use native path semantics even on a runner of the other platform."""
    import ntpath
    import posixpath
    import tlo_phase23_v2 as phase

    paths = ntpath if flavor == "windows" else posixpath
    monkeypatch.setattr(phase, "os", SimpleNamespace(path=paths, sep=paths.sep))
    candidates, optional = phase._collect_pattern_matches(folder, _matcher())
    matches = candidates or optional
    assert matches
    assert {item["part_path"] for item in matches} == {folder}
    assert phase._all_clean_path_parts(folder)[0][1] == folder
    group = dict(main_dir_name=SOURCE, main_dir_path=folder, music_dirs=[],
                 music_files=[paths.join(folder, f"trey2005-12-02d1t0{i}.flac")
                              for i in (1, 2)], setlist_files=[], setlist_file="")
    # These Windows/UNC paths are synthetic; the native filesystem tests
    # above exercise real media discovery separately.
    monkeypatch.setattr(phase, "_is_music_file", lambda path: paths.splitext(path)[1] == ".flac")
    date_rows = [dict(raw=m["date_raw"], normalized=m["date_norm"], part=m["part"],
                      part_path=m["part_path"], source="path_pattern") for m in matches]
    evidence, conflicts, observations = {}, [], []
    chosen, _ = phase._resolve_date_from_candidates_with_setlist_validation(
        group, date_rows, evidence, conflicts, "date conflict across path pattern matches", observations)
    assert chosen == "2005-12-02"
    assert not conflicts
    assert any(c.source == "filename_shorthand_date_validation" for c in evidence["date"])
