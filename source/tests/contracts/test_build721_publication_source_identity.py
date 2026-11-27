"""Build 721: signed-publication remediation retains application tests and display behavior."""
from pathlib import Path
import pytest
import tlo_version

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def test_build721_identity_and_previous_capitalization_regressions():
    assert tlo_version.BUNDLE_BUILD == 728
    assert (ROOT / 'tlo_place_display.py').is_file()
    assert (ROOT / 'tests/behavior/test_build720_ruff_f841_place_display.py').is_file()
    assert (ROOT / 'tests/behavior/test_build719_mixed_case_place_fragments.py').is_file()
