"""Build 401 setlist-family and literal-directory enumeration regressions."""
__version__ = "v448"

import inspect
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

import tlo_file_listing as F
import tlo_inventory_update as U
import tlo_postprocess as P
import tlo_research_lib as R
import tlo_reverse_copy_delete as V


def test_build401_setlist_family_is_exact_base_or_altn_only():
    base = "Phish1997-11-17"
    assert F.is_setlist_family_name("Phish1997-11-17.txt", base)
    assert F.is_setlist_family_name("Phish1997-11-17(alt1).txt", base)
    assert F.is_setlist_family_name("Phish1997-11-17(ALT23).txt", base)
    assert not F.is_setlist_family_name("Phish1997-11-17LateShow.txt", base)
    assert not F.is_setlist_family_name("Phish1997-11-17(set2).txt", base)


def test_build401_infer_setlists_does_not_surface_longer_show_prefix(tmp_path):
    home = tmp_path / "TLOHome [2024]"
    setlists = home / "setlists"
    setlists.mkdir(parents=True)
    base = P._normalized_setlist_base("Phish 1997-11-17", fallback="Show")
    exact = setlists / f"{base}.txt"
    alt = setlists / f"{base}(alt1).txt"
    longer = setlists / f"{base}LateShow.txt"
    exact.write_text("exact", encoding="utf-8")
    alt.write_text("alt", encoding="utf-8")
    longer.write_text("keep", encoding="utf-8")
    got = U.infer_setlist_paths_for_show(str(home), "Phish 1997-11-17")
    assert {Path(x).name for x in got} == {exact.name, alt.name}


def test_build401_replaced_setlist_cleanup_preserves_longer_kept_show(tmp_path):
    home = tmp_path / "TLO [2024]"
    setlists = home / "setlists"
    setlists.mkdir(parents=True)
    short_show = "Phish 1997-11-17"
    long_show = "Phish 1997-11-17 Late Show"
    short_base = P._normalized_setlist_base(short_show)
    long_base = P._normalized_setlist_base(long_show)
    short_exact = setlists / f"{short_base}.txt"
    short_alt = setlists / f"{short_base}(alt1).txt"
    long_file = setlists / f"{long_base}.txt"
    for path in (short_exact, short_alt, long_file):
        path.write_text(path.name, encoding="utf-8")
    P._remove_replaced_setlists(
        str(home),
        [{"Show": short_show, "VolumePath": ""}],
        [{"Show": long_show, "VolumePath": ""}],
    )
    assert not short_exact.exists()
    assert not short_alt.exists()
    assert long_file.exists()


def test_build401_literal_directory_scandir_handles_brackets(tmp_path):
    directory = tmp_path / "logs [2024]"
    directory.mkdir()
    (directory / "metaA.log").write_text("x", encoding="utf-8")
    (directory / "compB.log").write_text("y", encoding="utf-8")
    assert [Path(p).name for p in F.scandir_matching_files(str(directory), "meta*.log")] == ["metaA.log"]
    assert [Path(p).name for p in F.scandir_matching_files(str(directory), "comp*.log")] == ["compB.log"]


def test_build401_no_user_path_glob_calls_remain_in_affected_modules():
    for module in (P, R, V, U):
        source = inspect.getsource(module)
        assert "glob.glob(" not in source
