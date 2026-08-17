"""Compatibility test entry point for TLO GitHub Build Process v067.

The categorized suite lives under tests/. Importing the tests here preserves the
existing CI command: python -m pytest -q test_tlo_requirements.py.
"""

__version__ = "v377"

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
