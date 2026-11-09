"""Build 625 regression updated by Build 637: exact names/sizes determine duplicates."""
import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def module():
    spec = importlib.util.spec_from_file_location('tlo_delete_dupes_625', ROOT / 'tlo-deleteDupes.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

@pytest.mark.parametrize('extension', ['flac','shn','mp3','wav','txt'])
def test_equal_size_different_bytes_are_duplicates(tmp_path, extension):
    m=module(); home=tmp_path/'home'; home.mkdir(); root=tmp_path/'music'; root.mkdir()
    original=root/'Band 2000-01-01'; copy=root/'Band 2000-01-01 (copy1)'
    original.mkdir(); copy.mkdir()
    (original/f'01.{extension}').write_bytes(b'AAAA')
    (copy/f'01.{extension}').write_bytes(b'BBBB')
    seen=[]
    assert m.compare_directory_trees_for_duplicate_deletion(str(original), str(copy)) == (True, '')
    assert m.delete_duplicate_copy_directories(str(root), str(home), trash_func=seen.append,
            emit=lambda *a, **k: None, ffmpeg_executable='stub', health_check=lambda *a, **k: True) == 1
    assert seen == [str(copy.resolve())]


def test_identical_tree_matches_and_mismatch_reason(tmp_path):
    m=module(); a=tmp_path/'a'; b=tmp_path/'b'; a.mkdir(); b.mkdir()
    (a/'file.mp3').write_bytes(b'hello'); (b/'file.mp3').write_bytes(b'hello')
    assert m.compare_directory_trees_for_duplicate_deletion(str(a), str(b)) == (True,'')
    (b/'file.mp3').write_bytes(b'world')
    same, reason=m.compare_directory_trees_for_duplicate_deletion(str(a), str(b))
    assert same and reason == ''  # equal name and size; content is intentionally ignored
    (b/'file.mp3').write_bytes(b'longer')
    same, reason=m.compare_directory_trees_for_duplicate_deletion(str(a),str(b))
    assert not same and 'sizes' in reason


def test_symlink_rejected(tmp_path):
    m=module(); a=tmp_path/'a'; b=tmp_path/'b'; a.mkdir(); b.mkdir()
    (a/'f').write_bytes(b'x'); (b/'f').write_bytes(b'x')
    try: (b/'link').symlink_to('f')
    except OSError: pytest.skip('symlink unsupported')
    with pytest.raises(m.DeleteDupesError,match='symlink'):
        m.compare_directory_trees_for_duplicate_deletion(str(a),str(b))


def test_duplicate_scan_never_reads_file_contents(tmp_path, monkeypatch):
    m = module(); root = tmp_path / 'dup'; root.mkdir()
    (root / '01.flac').write_bytes(b'data')
    monkeypatch.setattr(m.os, 'open', lambda *a, **k: (_ for _ in ()).throw(AssertionError('hash read')))
    assert dict(m._scan_tree(str(root)).files) == {'01.flac': 4}
