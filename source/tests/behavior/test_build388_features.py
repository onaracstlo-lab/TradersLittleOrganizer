import tlo_setlist_metadata_lookup as setmeta

def test_build388_inline_setlist_artist_date_header_is_recognized():
    support = setmeta._SupportData("/definitely/missing")
    artist, venue, confidence = setmeta._extract_inline_artist_date_header(["Kinky Friedman January 17, 1987"], support)
    assert artist == "Kinky Friedman"
    assert venue == ""
    assert confidence >= 88

def test_build388_inline_setlist_artist_date_venue_is_recognized_with_known_venue(tmp_path):
    dbdir = tmp_path / "db"
    dbdir.mkdir()
    (dbdir / "venues.txt").write_text("Lone Star Cafe\n", encoding="utf-8")
    support = setmeta._SupportData(str(dbdir))
    artist, venue, confidence = setmeta._extract_inline_artist_date_header(["Kinky Friedman January 17, 1987 Lone Star Cafe"], support)
    assert artist == "Kinky Friedman"
    assert venue == "Lone Star Cafe"
    assert confidence >= 90
