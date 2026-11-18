"""Build 680: lineage/date safety, Windows-WSL delete guard, TkDND recovery."""
from types import SimpleNamespace
import sys
import pytest
import tlo_constants as const
import tlo_phase23_v2 as phase
import tlo_inventory_update as update
import tlo_dragdrop as dragdrop
import tlo_setlist_metadata_lookup as setlist
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.behavior

@pytest.mark.parametrize("folder,expected", [
    ("Grateful Dead 1977-05-08 Barton Hall SBD 1st Gen 24-96", "1977-05-08"),
    ("Grateful Dead - Cornell 1977 2nd Gen 24-96", ""),
    ("Allman Brothers Band 1971 Fillmore East Gen 24 96", ""),
])
def test_lineage_folder_never_creates_phantom_date(tmp_path, folder, expected):
    names={"Grateful Dead": ["Grateful Dead"], "Allman Brothers Band": ["Allman Brothers Band"]}
    matcher=ArtistMatcher(db_path="")
    matcher.exact_map={name.lower():{name} for name in names}
    matcher.master_aliases=names
    matcher.master_norms={name:{''.join(c for c in name.lower() if c.isalnum())} for name in names}
    config=SimpleNamespace(compliant=False,current_slam="",current_volume_label="",as_is_artist_name=False,
        compliant_artist_mode="master",etree_lookup=False,setlistfm_lookup=False,
        TLOHome=str(tmp_path),tlo_dbs_dir=str(tmp_path),debug=False)
    group={'group_number':1,'main_dir_name':folder,'main_dir_path':str(tmp_path/folder),
           'setlist_file':'','setlist_files':[],'music_dirs':[str(tmp_path/folder)],
           'music_file_count':1,'flac_tag_samples':[],'flac_tag_artist_values':[],
           'flac_tag_album_values':[],'flac_tag_albumartist_values':[],'flac_tag_date_values':[]}
    record=phase._extract_metadata_for_group(config,group,matcher)[0]
    assert (record.date if record.date != "xxxx-xx-xx" else "") == expected
    assert not getattr(record, "show_in_conflict", False)

@pytest.mark.parametrize('value', ['SBD 1st Gen 16-44','AUD 2nd gen 24-48','FM 3rd Gen 24-88','1st gen 24/96'])
def test_gen_is_never_a_month(value):
    assert 'gen' not in const.MONTHS
    assert not phase._find_date_matches(value)
    assert not setlist._INLINE_DATE_TOKEN_RE.search(value)

@pytest.mark.parametrize('month', sorted(const.AMBIGUOUS_SHORT_FOREIGN_MONTHS))
def test_short_foreign_month_requires_full_year_and_plain_day(month):
    assert not phase._find_date_matches(f'2nd {month} 24-96')
    assert f'2022-{const.MONTHS[month]:02d}-02' in {
        r['normalized'] for r in phase._find_date_matches(f'02 {month} 2022')
    }

@pytest.mark.parametrize('target,home,blocked', [
    (r'C:\Data', '/mnt/c/Data/TLOHome', True),
    (r'C:\Data\TLOHome', '/mnt/c/Data/TLOHome', True),
    ('/mnt/c/Data',r'C:\Data\TLOHome',True),
    (r'c:\data\tlohome\TLO_DBs','/mnt/C/Data/TLOHome',True),
    (r'C:\Music', '/mnt/d/TLOHome', False),
    ('/Volumes/Backup/Music',r'C:\Data\TLOHome',False),
    ('/mnt/c/Other',r'C:\Data\TLOHome',False),
])
def test_cross_syntax_delete_protection(target,home,blocked):
    outcome=update._canonical_safe_delete_path(target,tlo_home=home)
    assert (outcome == '') == blocked

@pytest.mark.parametrize('exception', [ImportError('missing'), RuntimeError('incorrect native TclError')])
def test_tkdnd_fallback_only_for_supported_failures(monkeypatch,exception):
    class FakeTk:
        class TclError(Exception): pass
        @staticmethod
        def Tk(): return 'ordinary-root'
    class FakeDnd:
        class TkinterDnD:
            @staticmethod
            def Tk(): raise exception
    monkeypatch.setattr(dragdrop,'is_drag_drop_platform',lambda:True)
    monkeypatch.setitem(sys.modules,'tkinterdnd2',FakeDnd)
    if isinstance(exception,ImportError):
        assert dragdrop.create_tk_root(FakeTk)==('ordinary-root','')
    else:
        with pytest.raises(RuntimeError):
            dragdrop.create_tk_root(FakeTk)



def test_tkdnd_native_tclerror_uses_plain_tk(monkeypatch):
    class FakeTk:
        class TclError(Exception): pass
        @staticmethod
        def Tk(): return 'ordinary-root'
    class FakeDnd:
        class TkinterDnD:
            @staticmethod
            def Tk(): raise FakeTk.TclError('native library not found')
    monkeypatch.setattr(dragdrop,'is_drag_drop_platform',lambda:True)
    monkeypatch.setitem(sys.modules,'tkinterdnd2',FakeDnd)
    assert dragdrop.create_tk_root(FakeTk)==('ordinary-root','')

def test_source_lineage_is_not_a_trailing_venue_date():
    sample = 'Barton Hall > 1st Gen'
    assert setlist._strip_trailing_performance_date_from_metadata_value(sample)==sample
    assert setlist._unsafe_short_foreign_date_token('2nd ott 24')
