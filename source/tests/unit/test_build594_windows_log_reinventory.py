"""Build 594: Windows replacement of open token logs is safe and lossless."""
import logging
import os
from pathlib import Path

import pytest

import logging_lib as LL

pytestmark = pytest.mark.unit


def _handler_for(log):
    return next(handler for handler in log.handlers if isinstance(handler, logging.FileHandler))


def test_open_groups_log_can_be_pruned_without_winerror_and_continues_appending(monkeypatch, tmp_path):
    """Emulate Windows refusing os.replace while a FileHandler holds its target."""
    home = tmp_path / 'home'
    manager = LL.LogManager(str(home))
    manager.start_search_path(str(tmp_path / 'parent'), log_token='2', volume_label='VOL', log_mode='w')
    groups = Path(manager.paths.groups)
    manager.groups('GROUP_NUMBER: 1')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'child'))
    manager.groups('END_GROUP')
    manager.groups('GROUP_NUMBER: 2')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'sibling'))
    manager.groups('END_GROUP')
    handler = _handler_for(manager._groups_logger)
    assert handler.stream is not None and not handler.stream.closed

    replace = os.replace
    def windows_replace(src, dst):
        if os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(groups)):
            assert handler.stream is None or handler.stream.closed, 'emulated WinError 5: destination open'
        return replace(src, dst)
    monkeypatch.setattr(LL.os, 'replace', windows_replace)

    assert LL._prune_structured_log(str(groups), [str(tmp_path / 'parent' / 'child')], 'END_GROUP')
    manager.groups('GROUP_NUMBER: 3')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'later'))
    manager.groups('END_GROUP')
    text = groups.read_text(encoding='utf-8')
    assert 'parent/child' not in text.replace('\\', '/')
    assert 'parent/sibling' in text.replace('\\', '/')
    assert 'parent/later' in text.replace('\\', '/')
    assert text.count('GROUP_NUMBER:') == 2
    assert handler.mode == 'a'
    manager._close_scope_handlers()


def test_replacement_error_preserves_existing_log_and_allows_future_append(monkeypatch, tmp_path):
    manager = LL.LogManager(str(tmp_path))
    manager.start_search_path(str(tmp_path / 'parent'), log_token='3', log_mode='w')
    path = Path(manager.paths.groups)
    manager.groups('GROUP_NUMBER: 1')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'child'))
    manager.groups('END_GROUP')
    before = path.read_bytes()
    monkeypatch.setattr(LL.os, 'replace', lambda *_: (_ for _ in ()).throw(PermissionError(5, 'locked')))
    with pytest.raises(PermissionError):
        LL._prune_structured_log(str(path), [str(tmp_path / 'parent' / 'child')], 'END_GROUP')
    assert path.read_bytes() == before
    assert list(path.parent.glob('.groups3.log.*.tmp')) == []
    manager.groups('SAFE_APPEND')
    assert path.read_bytes().startswith(before)
    assert path.read_text(encoding='utf-8').endswith('SAFE_APPEND\n')
    manager._close_scope_handlers()


def test_switching_log_scope_closes_old_file_handles(tmp_path):
    manager = LL.LogManager(str(tmp_path))
    manager.start_search_path('first', log_token='4')
    old = _handler_for(manager._groups_logger)
    old_path = Path(manager.paths.groups)
    manager.start_search_path('second', log_token='5')
    assert old.stream is None or old.stream.closed
    assert _handler_for(manager._groups_logger).stream is not None
    old_path.rename(old_path.with_name('groups4.bak'))
    manager._close_scope_handlers()


def test_reconfiguring_same_named_logger_closes_previous_handler(tmp_path):
    manager = LL.LogManager(str(tmp_path))
    path = tmp_path / 'one.log'
    first = manager._configure_logger('test594', str(path))
    old = _handler_for(first)
    second = manager._configure_logger('test594', str(path), 'a')
    assert second is first
    assert old.stream is None or old.stream.closed
    assert old not in second.handlers
    for h in tuple(second.handlers):
        second.removeHandler(h)
        h.close()


def test_transient_windows_sharing_lock_retries_and_keeps_other_groups(monkeypatch, tmp_path):
    manager = LL.LogManager(str(tmp_path))
    manager.start_search_path('some', log_token='6')
    path = Path(manager.paths.groups)
    manager.groups('GROUP_NUMBER: 1')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'child'))
    manager.groups('END_GROUP')
    manager.groups('GROUP_NUMBER: 2')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'other'))
    manager.groups('END_GROUP')
    original_replace = os.replace
    calls = []

    def sometimes_locked(src, dst):
        calls.append(dst)
        if len(calls) < 3:
            error = PermissionError(13, 'locked')
            error.winerror = 32
            raise error
        return original_replace(src, dst)

    monkeypatch.setattr(LL.os, 'replace', sometimes_locked)
    monkeypatch.setattr(LL.os, 'name', 'nt')
    monkeypatch.setattr(LL.time, 'sleep', lambda *_: None)
    try:
        assert LL._prune_structured_log(str(path), [str(tmp_path / 'parent' / 'child')], 'END_GROUP')
        assert len(calls) == 3
        assert 'parent/other' in path.read_text().replace('\\', '/')
    finally:
        manager._close_scope_handlers()


def test_unrelated_permission_failure_is_not_retried(monkeypatch, tmp_path):
    manager = LL.LogManager(str(tmp_path))
    manager.start_search_path('some', log_token='7')
    path = Path(manager.paths.groups)
    manager.groups('GROUP_NUMBER: 1')
    manager.groups('MAIN_DIR_PATH: %s', str(tmp_path / 'parent' / 'child'))
    manager.groups('END_GROUP')
    calls = []
    def fail(src, dst):
        calls.append(dst)
        error = PermissionError(13, 'other')
        error.winerror = 999
        raise error
    monkeypatch.setattr(LL.os, 'replace', fail)
    monkeypatch.setattr(LL.os, 'name', 'nt')
    try:
        with pytest.raises(PermissionError):
            LL._prune_structured_log(str(path), [str(tmp_path / 'parent' / 'child')], 'END_GROUP')
        assert len(calls) == 1
        assert 'parent/child' in path.read_text().replace('\\', '/')
    finally:
        manager._close_scope_handlers()


def test_three_successive_inventories_of_same_path_preserve_other_scope(tmp_path, monkeypatch):
    home = tmp_path / "home"
    root = tmp_path / "shows"
    child = root / "repeat"
    sibling = root / "other"
    manager = LL.LogManager(str(home))
    manager.start_search_path(str(root), log_token="2", log_mode="w")
    manager.groups("GROUP_NUMBER: 1")
    manager.groups("MAIN_DIR_PATH: %s", str(child))
    manager.groups("END_GROUP")
    manager.groups("GROUP_NUMBER: 2")
    manager.groups("MAIN_DIR_PATH: %s", str(sibling))
    manager.groups("END_GROUP")
    for count in range(3):
        assert LL._prune_structured_log(manager.paths.groups, [str(child)], "END_GROUP")
        manager.start_search_path(str(child), log_token="2", log_mode="a")
        manager.groups("GROUP_NUMBER: %d", count + 3)
        manager.groups("MAIN_DIR_PATH: %s", str(child))
        manager.groups("END_GROUP")
    text = Path(manager.paths.groups).read_text(encoding="utf-8")
    assert text.count("GROUP_NUMBER:") == 2
    assert str(sibling) in text
    assert text.count(str(child)) == 1
    assert not list(Path(manager.paths.groups).parent.glob(".groups2.log.*.tmp"))
    manager._close_scope_handlers()
