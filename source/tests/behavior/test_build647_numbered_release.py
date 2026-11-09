"""Build 647: reject accidental Build 646 reissues and Ruff F401 regression."""
from pathlib import Path
import pytest
from tlo_version import BUNDLE_BUILD, VERSION, DISPLAY_VERSION

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]

def test_new_numbered_release_not_a_v646_reissue():
    assert BUNDLE_BUILD >= 647
    assert VERSION == f'v{BUNDLE_BUILD}'
    assert DISPLAY_VERSION == f'v1.7 Build {BUNDLE_BUILD}'
    for fn in (f'CHANGES_{VERSION}.txt',f'BUILD_VERIFICATION_{VERSION}.txt',
               f'REGRESSION_RESULTS_{VERSION}.txt',f'SOURCE_BUNDLE_README_{VERSION}.txt',
               f'TLO_Inventory_Requirements_Working_{VERSION}.docx',
               f'TLO_Inventory_User_Manual_{VERSION}.rtf'):
        assert (ROOT / fn).is_file(), fn

def test_ruff_f401_unused_import_not_reintroduced():
    text = (ROOT/'tests/behavior/test_build646_staged_city_database.py').read_text(encoding='utf-8')
    assert 'from tlo_cities import catalog_for_tlo, _cached_layered' not in text
    assert 'from tlo_cities import catalog_for_tlo' in text
    assert text.count('from tlo_cities import _cached_layered') == 1

def test_city_database_is_external_and_not_embedded():
    assert (ROOT/'TLO_DBs/cities.csv').read_bytes() == (ROOT/'cities.csv').read_bytes()
    assert not (ROOT/'tlo_cities_embedded.py').exists()
    for script in ('createWindowsDist.ps1','createLinuxDist.sh','createMacOSDist.sh'):
        text = (ROOT/script).read_text(encoding='utf-8')
        assert 'stage_city_database.py' in text
