"""Historical corruption defaults superseded by the Build 442 split policy."""

__version__ = "v448"

import pytest

pytestmark = pytest.mark.behavior
import tlo_options
from inventory_parser_lib import Config


def test_current_corruption_defaults_preserve_pre442_destructive_behavior():
    assert tlo_options.OPTIONS_BY_FIELD["corrupt_files"].default == "delete"
    assert tlo_options.OPTIONS_BY_FIELD["corrupt_folders"].default == "all"
    config = Config(False, False, ".")
    assert config.corrupt_files == "delete"
    assert config.corrupt_folders == "all"
    assert config.corrupt_folder_threshold == 100


def test_folder_threshold_parser_accepts_endpoints():
    assert tlo_options.parse_percent_0_100("0") == 0
    assert tlo_options.parse_percent_0_100("100") == 100
