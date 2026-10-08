"""Build 568 GitHub runner regressions: volume isolation, unchanged test assumptions."""
import pytest
import tlo_manual_updates as MU
import tlo_bootlist_volume_policy as BP

pytestmark = pytest.mark.behavior


def test_ci_volume_label_mismatch_still_fails_closed(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    home.mkdir()
    target = str(tmp_path / "library" / "show")
    MU.write_bootlist(str(home), [{"Show": "show", "VolumePath": BP.format_volume_path("Volume-A", target)}])
    monkeypatch.setattr(MU, "os_volume_label_for_path", lambda _p: "Volume-B")
    with pytest.raises(MU.ManualUpdateError, match="different volume"):
        MU._matching_bootlist_rows(str(home), target)


def test_ci_volume_label_match_succeeds(tmp_path, monkeypatch):
    home = tmp_path / "TLOHome"
    home.mkdir()
    target = str(tmp_path / "library" / "show")
    record = {"Show": "show", "VolumePath": BP.format_volume_path("Volume-A", target)}
    MU.write_bootlist(str(home), [record])
    monkeypatch.setattr(MU, "os_volume_label_for_path", lambda _p: "Volume-A")
    assert MU._matching_bootlist_rows(str(home), target) == [record]
