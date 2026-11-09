"""Build 641: release blockers, updater, and city provenance."""
from pathlib import Path
from types import SimpleNamespace
import pytest
pytestmark = pytest.mark.behavior

def test_two_ruff_f401_imports_absent():
    root = Path(__file__).resolve().parents[2]
    assert 'import csv\n' not in (root/'tlo_phase23_v2.py').read_text().split('import json')[0]
    assert 'import catalog_path_for_tlo' not in (root/'tlo_setlist_metadata_lookup.py').read_text()

def test_setlist_city_conflict_logs_source_and_nonoverride(monkeypatch):
    import tlo_phase23_v2 as p
    from tlo_models import Candidate, ShowMetadata
    from tlo_setlist_metadata_lookup import SetlistVenueLocationResult
    r = ShowMetadata(group_number=1, main_dir_name='Example', main_dir_path='/tmp/Example',setlist_file='/tmp/example.txt',music_file_count=1,venue='Venue A',city='Greensboro',region='NC',location='Greensboro, NC')
    evidence={'venue':[Candidate('Venue A','etreedb',95)],'city':[Candidate('Greensboro','etreedb',95)],'region':[Candidate('NC','etreedb',95)]}
    monkeypatch.setattr(p,'extract_setlist_venue_location',lambda *_a,**_k: SetlistVenueLocationResult(venue='Venue B',city='Reidsville',region='NC',country='',location='Reidsville, NC',source='setlist',raw='',confidence=92))
    observations=[]
    p._apply_setlist_metadata_to_noncompliant_record(SimpleNamespace(compliant=False,tlo_dbs_dir=''),r,evidence,observations)
    assert r.city=='Greensboro' and r.venue=='Venue A'
    assert any('etreedb city' in line for line in observations)
    assert any('did not override existing city' in line for line in observations)
    assert any('did not override existing venue' in line for line in observations)

def test_unsupported_rename_is_explained_and_never_falls_back(tmp_path,monkeypatch):
    import tlo_github_updates as up
    if up.os.name == 'nt':
        pytest.skip('POSIX native rename-specific test')
    # Code-level guarantee: no hard-link/no replacement fallback is used.
    src=Path(up._publish_verified_download.__code__.co_filename).read_text()
    branch=src.split('def _publish_verified_download',1)[1].split('def _download_and_report_verified_asset',1)[0]
    assert 'errno.ENOTSUP' in branch and 'Choose a local Downloads folder' in branch
    assert 'os.link(' not in branch and 'os.replace(' not in branch
