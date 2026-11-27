"""Date conflicts require independent online/local performance corroboration."""
from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import pytest
from unittest.mock import patch
from urllib.error import HTTPError

from tlo_artist_db import ArtistMatcher
from tlo_etree_lookup import ETreeDBError, lookup_venue_and_location
from tlo_setlistfm_lookup import SetlistFMResult, SetlistFMError, api_get, search_setlists

TRACKS = ("Thickfreakness", "Girl Is on My Mind", "10 A.M. Automatic", "Set You Free",
          "The Breaks", "Stack Shot Billy", "Busted", "Everywhere I Go",
          "Strange Times", "Same Old Thing", "Tighten Up", "Howlin' for You",
          "Too Afraid to Love You", "Next Girl", "She's Long Gone", "Ten Cent Pistol",
          "Your Touch", "I'll Be Your Man", "No Trust", "I Got Mine",
          "Everlasting Light", "Till I Get My Way")
FIRST, SECOND = "2010-06-04", "2010-06-06"
pytestmark = pytest.mark.behavior

DB = Path(__file__).resolve().parents[2] / "TLO_DBs"


def _text(tracks):
    return "\n".join(f"{i:02d} {title}" for i, title in enumerate(tracks, 1))


def _result(day, tracks=TRACKS, venue="Crossroads KC", city="Kansas City", artist="The Black Keys"):
    return SetlistFMResult(artist, date.fromisoformat(day).strftime("%d-%m-%Y"),
                          venue, city + ", MO", city, "Missouri", "MO", "United States",
                          "US", "https://example.invalid/" + day, "", (_text(tracks),) if tracks else ())


class DateConflictTest(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / "B/Black Keys/2010/Black Keys 2010-06-04-CrossroadsKC"
        self.folder.mkdir(parents=True)
        self.setlist = self.folder / "Black Keys Crossroads KC.txt"
        self.config = SimpleNamespace(
            compliant=False, current_volume_label="", current_slam="",
            as_is_artist_name=False, compliant_artist_mode="master",
            etree_lookup=True, setlistfm_lookup=True, thorough_setlist_matching=False,
            debug=False, TLOHome=str(self.root), tlo_dbs_dir=str(DB))
        self.matcher = ArtistMatcher(db_path="")
        self.matcher.exact_map = {"the black keys": {"Black Keys"}, "black keys": {"Black Keys"}}
        self.matcher.master_aliases = {"Black Keys": ["Black Keys", "The Black Keys"]}
        self.matcher.master_norms = {"Black Keys": {"blackkeys", "theblackkeys"}}

    def extract(self, answers, *, tracks=TRACKS, header="", etree_answers=None, named_tracks=True):
        import tlo_phase23_v2 as phase
        self.setlist.write_text("Black Keys Crossroads KC\n" + header + "\n" + _text(tracks), encoding="utf-8")
        files = [str(self.folder / (f"{i:02d}-{title}.flac" if named_tracks else f"track{i:02d}.flac"))
                 for i, title in enumerate(TRACKS, 1)]
        samples = [dict(file=files[i], artist="The Black Keys", album="06-04-2010 Crossroads KC",
                        date=f"2010-06-06T20:{49+i:02d}:07-05:00") for i in range(2)]
        group = dict(group_number=1, main_dir_name=self.folder.name, main_dir_path=str(self.folder),
                     setlist_file=str(self.setlist), setlist_files=[str(self.setlist)],
                     music_dirs=[str(self.folder)], music_files=files, music_file_count=22,
                     flac_tag_samples=samples, flac_tag_artist_values=["The Black Keys"],
                     flac_tag_album_values=["06-04-2010 Crossroads KC"],
                     flac_tag_albumartist_values=[], flac_tag_date_values=[s["date"] for s in samples])
        def response(source, day):
            value = source.get(day, [])
            if isinstance(value, Exception):
                raise value
            return value
        if etree_answers is None:
            etree_answers = {d: RuntimeError("mock service outage") for d in (FIRST, SECOND)}
        with patch.object(phase, "lookup_venue_and_location",
                          side_effect=lambda artist, day, **kw: response(etree_answers, day)) as etree, \
             patch.object(phase, "lookup_setlistfm_venue_and_location",
                          side_effect=lambda artist, day, **kw: response(answers, day)) as fm:
            record, dates, issues = phase._extract_metadata_for_group(self.config, group, self.matcher)
            if self.config.setlistfm_lookup:
                self.assertEqual([c.args[1] for c in fm.call_args_list], [FIRST, SECOND])
                self.assertTrue(all(c.kwargs.get("thorough") for c in fm.call_args_list))
            if self.config.etree_lookup:
                self.assertEqual([c.args[1] for c in etree.call_args_list], [FIRST, SECOND])
        return record, dates, issues

    def test_reported_conflict_queries_both_distinct_dates_not_both_timestamps(self):
        r, dates, issues = self.extract({FIRST: [_result(FIRST)], SECOND: []})
        self.assertEqual(r.show_name, "Black Keys 2010-06-04 Crossroads KC Kansas City, MO")
        self.assertFalse(issues)
        self.assertEqual({d["normalized"] for d in dates}, {FIRST, SECOND})
        self.assertTrue(any("ordered title match=22 score=1.00" in o for o in r.observations))
        self.assertTrue(any("date conflict resolved" in o for o in r.observations))
        self.assertTrue(any(c.source.startswith("date_conflict_validation:") for c in r.evidence["date"]))
        self.assertFalse(any("conflicting DATE tag ignored" in o for o in r.observations))

    def test_wrong_folder_date_can_lose_even_with_equal_track_counts(self):
        r, _, issues = self.extract({FIRST: [_result(FIRST, tuple(reversed(TRACKS)))],
                                     SECOND: [_result(SECOND)]})
        self.assertEqual(r.date, SECOND)
        self.assertFalse(issues)
        self.assertEqual([item["url"] for item in r.setlistfm_setlist_candidates],
                         ["https://example.invalid/" + SECOND])

    def test_equally_supported_dates_do_not_guess(self):
        from tlo_phase23_v2 import _record_is_unidentified_for_mutation
        r, _, issues = self.extract({FIRST: [_result(FIRST)], SECOND: [_result(SECOND)]})
        self.assertEqual(r.date, "")
        self.assertTrue(_record_is_unidentified_for_mutation(r, issues))
        self.assertTrue(any("date conflict" in i for i in issues))

    def test_failure_is_not_negative_confirmation(self):
        r, _, issues = self.extract({FIRST: [_result(FIRST)], SECOND: RuntimeError("rate limit")})
        self.assertEqual(r.date, "")
        self.assertTrue(issues)

    def test_explicit_local_performance_date_survives_service_outages(self):
        outage = RuntimeError("offline")
        r, _, issues = self.extract({FIRST: outage, SECOND: outage}, header="Date: 2010-06-04")
        self.assertEqual(r.date, FIRST)
        self.assertFalse(issues)

    def test_venue_clue_selects_date_without_song_titles(self):
        r, _, issues = self.extract({FIRST: [_result(FIRST, (), venue="Different Venue", city="St Louis")],
                                     SECOND: [_result(SECOND, ())]}, tracks=(), named_tracks=False)
        self.assertEqual(r.date, SECOND)
        self.assertFalse(issues)

    def test_other_same_date_performance_not_attached_to_winner(self):
        wrong = _result(FIRST, tuple(reversed(TRACKS)), venue="Other Place", city="St Louis")
        r, _, _ = self.extract({FIRST: [wrong, _result(FIRST)], SECOND: []})
        self.assertEqual(r.venue, "Crossroads KC")
        self.assertEqual(len(r.setlistfm_setlist_candidates), 1)

    def test_disabled_lookup_preserves_local_precedence(self):
        self.config.etree_lookup = self.config.setlistfm_lookup = False
        r, _, _ = self.extract({})
        self.assertEqual(r.date, FIRST)


class CurrentGraphQLTest(unittest.TestCase):
    def test_current_direct_cursor_arguments_and_exact_artist_article(self):
        import tlo_etree_lookup as etree

        def graph(query, variables):
            self.assertNotIn("pagination:", query)
            self.assertIn("first: 5", query)
            self.assertIn("first: $first", query)
            if variables["artistName"] != "The Black Keys":
                return {"artistsRoot": {"edges": []}}
            following = bool(variables.get("after"))
            if following:
                self.assertIn("after: $after", query)
                self.assertEqual(variables["after"], "next-cursor")
            node = dict(id=2 if following else 1, date=FIRST if following else SECOND,
                        year=2010, venue="Crossroads KC", city="Kansas City", state="MO",
                        set1=_text(TRACKS), set2="", set3="")
            return {"artistsRoot": {"edges": [{"node": {"id": 5, "name": "The Black Keys",
                    "nameNormalized": "black keys", "performances": {
                        "edges": [{"node": node}],
                        "pageInfo": {"hasNextPage": not following,
                                     "endCursor": "" if following else "next-cursor"}}}}]}}
        with patch.object(etree, "graphql_request", side_effect=graph) as request:
            rows = lookup_venue_and_location("Black Keys", FIRST)
        self.assertEqual([r.normalized_date for r in rows], [FIRST])
        self.assertEqual(rows[0].venue, "Crossroads KC")
        self.assertTrue(rows[0].set1)
        self.assertEqual(request.call_count, 3)

    def test_incomplete_etree_cursor_is_failure(self):
        import tlo_etree_lookup as etree
        payload = {"artistsRoot": {"edges": [{"node": {"id": 5, "name": "Black Keys",
                   "performances": {"edges": [], "pageInfo": {"hasNextPage": True}}}}]}}
        with patch.object(etree, "graphql_request", return_value=payload):
            with self.assertRaises(ETreeDBError):
                lookup_venue_and_location("Black Keys", FIRST)

    def test_setlistfm_exact_date_search_404_is_empty_but_429_is_failure(self):
        import tlo_setlistfm_lookup as fm
        def error(status):
            return HTTPError("https://api.setlist.fm/rest/1.0", status, "mock", {}, BytesIO(b"mock"))
        with patch.object(fm, "wait_for_rate_limit"), patch.object(fm.urllib.request, "urlopen", side_effect=error(404)):
            self.assertEqual(api_get("/search/setlists", {"p": "1"}, "test-key")["setlist"], [])
        with patch.object(fm, "wait_for_rate_limit"), patch.object(fm.urllib.request, "urlopen", side_effect=error(429)):
            with self.assertRaises(SetlistFMError):
                api_get("/search/setlists", {"p": "1"}, "test-key")

    def test_setlistfm_page_limit_is_not_complete_evidence(self):
        import tlo_setlistfm_lookup as fm
        with patch.object(fm, "api_get", return_value={"setlist": [{}], "total": 2, "itemsPerPage": 1}):
            with self.assertRaises(SetlistFMError):
                search_setlists("Black Keys", FIRST, "test-key", thorough=True, max_pages=1)


class LegacyVenueDateConflictTest(DateConflictTest):
    """Exercise every conflict test with a short legacy catalog match present."""
    def setUp(self):
        super().setUp()
        support = self.root / "TLO_DBs"
        support.mkdir()
        (support / "venues.txt").write_text("Crossroads\n", encoding="utf-8")
        self.config.tlo_dbs_dir = str(support)

    def test_explicit_conflicting_venue_is_not_expanded(self):
        r, _, issues = self.extract({FIRST: [_result(FIRST)], SECOND: []},
                                    header="Venue: Crossroads")
        self.assertEqual(r.venue, "Crossroads")
        self.assertFalse(r.date)
        self.assertTrue(issues)

    def test_unrelated_longer_name_is_not_expanded(self):
        r, _, issues = self.extract({FIRST: [_result(FIRST, venue="Crossroads Downtown")],
                                     SECOND: []})
        self.assertEqual(r.venue, "Crossroads")
        self.assertFalse(r.date)
        self.assertTrue(issues)
