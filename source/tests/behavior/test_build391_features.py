import pytest

pytestmark = pytest.mark.behavior
import tlo_corruption as corruption
import tlo_options

def test_build391_corruption_threshold_uses_strict_more_than_comparison():
    assert corruption.exceeds_threshold(20,2,10) is False
    assert corruption.exceeds_threshold(20,3,10) is True
    assert corruption.exceeds_threshold(1,1,0) is True
    assert corruption.exceeds_threshold(10,10,100) is False

def test_build391_corruption_input_is_0_to_100():
    option = next(o for o in tlo_options.OPTIONS if o.config_field == "acceptable_corruption_percent")
    assert tlo_options.parse_percent_0_100("0") == 0
    assert tlo_options.parse_percent_0_100("100") == 100
    with pytest.raises(Exception): tlo_options.parse_percent_0_100("101")
