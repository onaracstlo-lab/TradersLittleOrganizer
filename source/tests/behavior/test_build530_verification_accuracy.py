from __future__ import annotations
from tests import _release_artifacts as RA

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build530_history_records_the_original_reporting_change():
    changes = (ROOT / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "TLO v1.7 Build 530" in changes
    assert "Independent-verification reporting correction (IV-1)" in changes
