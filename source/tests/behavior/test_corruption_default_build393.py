"""Build 393 regressions for the acceptable-corruption default."""

__version__ = "v433"

import pytest

pytestmark = pytest.mark.behavior
import tlo_options
from inventory_parser_lib import Config


def test_build393_acceptable_corruption_default_is_100():
    option = next(o for o in tlo_options.OPTIONS if o.config_field == "acceptable_corruption_percent")
    assert option.default == 100
    assert Config(False, False, ".").acceptable_corruption_percent == 100


def test_build393_explicit_zero_remains_valid():
    assert tlo_options.parse_percent_0_100("0") == 0
