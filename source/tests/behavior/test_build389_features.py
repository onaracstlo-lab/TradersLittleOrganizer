from types import SimpleNamespace
import tlo_phase23_v2 as phase

def test_build389_albumartist_wins_over_artist_within_low_priority_tag_evidence():
    record = SimpleNamespace(flac_tag_samples=[{"artist":"Track Guest","albumartist":"Show Artist"}])
    term, source = phase._selected_artist_tag_candidate(record, matcher=None, observations=[])
    assert term == "Show Artist"
    assert source == "flac_tag_albumartist"
