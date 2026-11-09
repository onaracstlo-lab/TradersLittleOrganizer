"""Build 643: safe defaults, preference conflicts, and held-SHN copy exclusion."""
import pytest
pytestmark = pytest.mark.behavior

def test_absent_corruption_policies_are_safe():
    from tlo_options import parse_corrupt_file_policy, parse_corrupt_folder_policy,validate_corruption_policy
    assert parse_corrupt_file_policy(None)=='keep'
    assert parse_corrupt_folder_policy(None)=='never'
    values={}
    validate_corruption_policy(values)
    assert parse_corrupt_file_policy('delete')=='delete'  # explicit choice still honored

def test_preferences_refuse_stale_editor_without_writing(tmp_path):
    import tlo_preferences as prefs
    import hashlib
    path=prefs.path_for(tmp_path)
    path.write_text(prefs.default_text(),encoding='utf-8')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    external=prefs.default_text().replace('auto_update = false','auto_update = true')
    path.write_text(external,encoding='utf-8')
    with pytest.raises(ValueError,match='changed since this editor opened'):
        prefs.save_text(tmp_path,prefs.default_text(),expected_digest=digest)
    assert path.read_text(encoding='utf-8')==external

def test_copy_requests_exclude_held_shn_at_any_depth(tmp_path):
    from tlo_copy_requests import _copy_into_temp_target,_walk_tree_size_and_reject_links
    from tlo_tree_compare import directory_trees_exactly_match
    src=tmp_path/'source';src.mkdir()
    show=src/'show';show.mkdir()
    (show/'track.flac').write_bytes(b'flac')
    held=show/'.tlo-shn-originals'/'id';held.mkdir(parents=True)
    (held/'track.shn').write_bytes(b'original')
    dst=tmp_path/'dest'
    _copy_into_temp_target(str(src),str(dst))
    assert (dst/'show'/'track.flac').read_bytes()==b'flac'
    assert not (dst/'show'/'.tlo-shn-originals').exists()
    assert _walk_tree_size_and_reject_links(str(src))==4
    assert directory_trees_exactly_match(str(src),str(dst),ignore_root_names={'.tlo-shn-originals'})

def test_tag_copy_excludes_held_shn(tmp_path):
    from tlo_tag_lib import _copy_entire_directory_tree
    src=tmp_path/'src';src.mkdir()
    (src/'track.flac').write_bytes(b'data')
    h=src/'.tlo-shn-originals'/'u';h.mkdir(parents=True)
    (h/'track.shn').write_bytes(b'hold')
    dst=tmp_path/'dst'
    _copy_entire_directory_tree(str(src),str(dst))
    assert (dst/'track.flac').exists() and not (dst/'.tlo-shn-originals').exists()

def test_shn_report_is_read_only(tmp_path):
    from tools.report_held_shn_originals import scan
    original=tmp_path/'show'/'.tlo-shn-originals'/'some-id'/'audio.shn'
    original.parent.mkdir(parents=True)
    original.write_bytes(b'preserved')
    assert list(scan(tmp_path))==[(original,9)]
    assert original.read_bytes()==b'preserved'
