"""Build 674: duplicate holding directories must be writable and atomic."""
import importlib.util
import os
from pathlib import Path
import pytest
pytestmark = pytest.mark.behavior
ROOT=Path(__file__).resolve().parents[2]
def load():
    spec=importlib.util.spec_from_file_location('deletedupes_674',ROOT/'tlo-deleteDupes.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

@pytest.mark.skipif(os.name == "nt", reason="POSIX filesystem/shell semantics verified in required Linux CI tests")
def test_unix_unwritable_partition_root_falls_back_to_sibling(tmp_path,monkeypatch):
    m=load();search=tmp_path/'music';search.mkdir()
    default=tmp_path/'pretend-partition-root'/'duplicates'
    monkeypatch.setattr(m,'_duplicates_root_for_search',lambda _:str(default))
    real_makedirs=m.os.makedirs
    def makedirs(path,*args,**kwargs):
        if os.path.normpath(path)==os.path.normpath(default):raise PermissionError('root is read only')
        return real_makedirs(path,*args,**kwargs)
    monkeypatch.setattr(m.os,'makedirs',makedirs)
    monkeypatch.setattr(m.os,'name','posix')
    assert Path(m._prepare_duplicates_root(str(search)))==tmp_path/'duplicates'

def test_explicit_same_filesystem_destination(tmp_path):
    m=load();search=tmp_path/'search';search.mkdir();held=tmp_path/'holding'
    assert m._prepare_duplicates_root(str(search),str(held))==str(held)
    assert held.is_dir()

def test_search_inside_holding_folder_rejected(tmp_path):
    m=load();held=tmp_path/'holding';search=held/'search';search.mkdir(parents=True)
    with pytest.raises(m.DeleteDupesError):m._prepare_duplicates_root(str(search),str(held))

def test_explicit_different_device_rejected(tmp_path,monkeypatch):
    m=load();search=tmp_path/'search';search.mkdir()
    held=tmp_path/'holding';held.mkdir()
    actual=m.os.stat
    def fake_stat(p,*args,**kw):
        result=actual(p,*args,**kw)
        if str(p)==str(held):
            class Result:
                st_dev=result.st_dev+1
            return Result()
        return result
    monkeypatch.setattr(m.os,'stat',fake_stat)
    with pytest.raises(m.DeleteDupesError,match='same filesystem'):
        m._prepare_duplicates_root(str(search),str(held))

def test_option_is_forwarded_from_cli(monkeypatch,tmp_path):
    m=load(); root=tmp_path/'root';root.mkdir();home=tmp_path/'home';home.mkdir()
    calls=[]
    monkeypatch.setattr(m,'resolve_tlo_home',lambda *_a,**_kw:str(home))
    monkeypatch.setattr(m,'delete_duplicate_copy_directories',lambda *a,**kw:(calls.append((a,kw)),0)[1])
    assert m.main(['--duplicates-dir',str(tmp_path/'held'),str(root)])==0
    assert calls[0][1]['duplicates_root']==str(tmp_path/'held')
