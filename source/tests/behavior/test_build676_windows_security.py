"""Build 676: destructive path checks must be OS-flavor aware; TkDND is optional per Tk root."""
from types import SimpleNamespace
import pytest

import tlo_inventory_update as iu
import tlo_dragdrop as dnd

pytestmark = pytest.mark.behavior


@pytest.mark.parametrize('protected', [
    r'C:\.tlo', r'c:\.TLO', r'C:\.tlo\TLO_DBs',
    'C:\\', r'c:\other\..',
])
def test_windows_drive_protects_home_root_descendants_and_ancestors(protected):
    assert iu._canonical_safe_delete_path(protected, tlo_home=r'C:\.tlo') == ''


def test_windows_sibling_path_is_allowed_if_not_inside_home():
    assert iu._canonical_safe_delete_path(r'C:\Music\Dead', tlo_home=r'C:\.tlo') == r'C:\Music\Dead'
    assert iu._canonical_safe_delete_path(r'E:\Music\Dead', tlo_home=r'C:\.tlo') == r'E:\Music\Dead'


def test_windows_nonroot_home_and_partial_prefix_safety():
    home = r'C:\Data\TLOHome'
    for candidate in [home, r'C:\Data',r'C:\Data\TLOHome\TLO_DBs']:
        assert iu._canonical_safe_delete_path(candidate, tlo_home=home) == ''
    assert iu._canonical_safe_delete_path(r'C:\Data\TLOHomely\music', tlo_home=home)
    assert iu._canonical_safe_delete_path(r'C:\Data\elsewhere', tlo_home=home)


@pytest.mark.parametrize('unsafe', [r'C:\Music\..\Other', 'C:\\', 'C:', r'C:\..\Music',r'..\Music',r'\\SERVER\Share'])
def test_destructive_targets_fail_closed(unsafe):
    assert iu._canonical_safe_delete_path(unsafe, tlo_home=r'C:\.tlo') == ''


def test_posix_protected_mount_paths():
    assert iu._canonical_safe_delete_path('/mnt/e/music',tlo_home='/mnt/e/music') == ''
    assert iu._canonical_safe_delete_path('/mnt/e/music/discs',tlo_home='/mnt/e/music') == ''
    assert iu._canonical_safe_delete_path('/mnt/e',tlo_home='/mnt/e/music') == ''
    assert iu._canonical_safe_delete_path('/mnt/e/other',tlo_home='/mnt/e/music').replace('\\','/') == '/mnt/e/other'


def test_plain_tk_entry_does_not_crash_windows_root(monkeypatch):
    monkeypatch.setattr(dnd,'is_drag_drop_platform', lambda:True)
    entry=SimpleNamespace()
    setter=SimpleNamespace(set=lambda _: None)
    for func in [dnd.enable_folder_path_drop,dnd.enable_search_path_folder_drop,
                 dnd.enable_single_folder_or_txt_drop,dnd.enable_leaf_folder_drop,dnd.enable_single_txt_file_drop]:
        assert func(entry,setter).enabled is False


def test_capable_drop_target_registers_and_delivers(monkeypatch,tmp_path):
    monkeypatch.setattr(dnd,'is_drag_drop_platform',lambda:True)
    track={}
    class Entry:
        def drop_target_register(self,value):track['register']=value
        def dnd_bind(self,event,callback):track['event']=event;track['cb']=callback
        def icursor(self,_):pass
        def focus_set(self):pass
        tk=SimpleNamespace(splitlist=lambda raw:[str(tmp_path)])
    class Variable:
        value=''
        def get(self):return self.value
        def set(self,s):self.value=s
    v=Variable()
    status=dnd.enable_search_path_folder_drop(Entry(),v)
    assert status.enabled and status.provider=='tkinterdnd2'
    assert track['register']=='DND_Files'
    assert track['event']=='<<Drop:DND_Files>>'
    assert track['cb'](SimpleNamespace(data=str(tmp_path),action='copy'))=='copy'
    assert v.value==str(tmp_path)
