"""Compatibility test entry point for TLO GitHub Build Process v067.

The categorized suite lives under tests/. Importing the tests here preserves the
existing CI command: python -m pytest -q test_tlo_requirements.py.
"""

__version__ = "v397"

from tests.contracts.test_legacy_contracts import *  # noqa: F401,F403
from tests.contracts.test_build364_contracts import *  # noqa: F401,F403
from tests.contracts.test_build365_contracts import *  # noqa: F401,F403
from tests.contracts.test_build366_contracts import *  # noqa: F401,F403
from tests.contracts.test_build367_contracts import *  # noqa: F401,F403
from tests.contracts.test_build368_contracts import *  # noqa: F401,F403
from tests.contracts.test_build369_contracts import *  # noqa: F401,F403
from tests.contracts.test_build370_contracts import *  # noqa: F401,F403
from tests.behavior.test_legacy_behavior import *  # noqa: F401,F403
from tests.behavior.test_copy_transfer_behavior import *  # noqa: F401,F403
from tests.behavior.test_commercial_release_behavior import *  # noqa: F401,F403
from tests.behavior.test_artist_resolution_build371 import *  # noqa: F401,F403
from tests.behavior.test_artist_resolution_build373 import *  # noqa: F401,F403
from tests.behavior.test_venue_resolution_build375 import *  # noqa: F401,F403
from tests.behavior.test_partial_year_dates_build376 import *  # noqa: F401,F403
from tests.behavior.test_artist_abbreviation_build378 import *  # noqa: F401,F403
from tests.behavior.test_artist_band_fallback_build392 import *  # noqa: F401,F403
from tests.behavior.test_corruption_default_build393 import *  # noqa: F401,F403
from tests.behavior.test_setlist_location_build395 import *  # noqa: F401,F403
from tests.unit.test_build397_review_fixes import *  # noqa: F401,F403
from tests.contracts.test_build397_review_contracts import *  # noqa: F401,F403
from tests.behavior.test_eac_track_table_build379 import *  # noqa: F401,F403
from tests.behavior.test_compliant_dash_date_build380 import *  # noqa: F401,F403
from tests.behavior.test_setlist_location_build381 import *  # noqa: F401,F403
from tests.behavior.test_structured_setlist_artist_build382 import *  # noqa: F401,F403
from tests.behavior.test_delete_dupes_behavior import *  # noqa: F401,F403
from tests.behavior.test_research_behavior import *  # noqa: F401,F403
from tests.integration.test_legacy_integration import *  # noqa: F401,F403
from tests.unit.test_core_units import *  # noqa: F401,F403

try:
    import tkinter  # noqa: F401
except ImportError:
    tkinter = None
else:
    from tests.behavior.test_gui_behavior import *  # noqa: F401,F403

from tests.behavior.test_reverse_copy_delete_build383 import *  # noqa: F401,F403
from tests.behavior.test_reverse_copy_delete_build384 import *  # noqa: F401,F403
from tests.behavior.test_build386_features import *  # noqa: F401,F403
from tests.behavior.test_build387_features import *  # noqa: F401,F403
from tests.behavior.test_build388_features import *  # noqa: F401,F403
from tests.behavior.test_build389_features import *  # noqa: F401,F403
from tests.behavior.test_build390_features import *  # noqa: F401,F403
from tests.behavior.test_build391_features import *  # noqa: F401,F403
from tests.behavior.test_setlist_false_positive_build396 import *  # noqa: F401,F403
