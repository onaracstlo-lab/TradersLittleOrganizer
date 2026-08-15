"""Behavior tests for the tlo-deleteDupes main."""

__version__ = "v363"

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_v363", ROOT / "tlo-deleteDupes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_copy_suffix_accepts_existing_tlo_and_spaced_forms():
    module = _load_module()
    assert module._copy_base_name("Bill 2013 HOB Boston (copy2)") == "Bill 2013 HOB Boston"
    assert module._copy_base_name("Bill 2013 HOB Boston (copy 3)") == "Bill 2013 HOB Boston"
    assert module._copy_base_name("Bill 2013 HOB Boston (COPY 12)") == "Bill 2013 HOB Boston"
    assert module._copy_base_name("Bill 2013 HOB Boston (alt2)") == ""


def test_exact_names_sizes_and_nested_structure_are_trashed_and_logged(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 HOB Boston (copy 2)"
    _write(original / "01.flac", b"abcd")
    _write(original / "art" / "cover.jpg", b"123456")
    (original / "empty").mkdir(parents=True)
    _write(copy / "01.flac", b"WXYZ")  # same size; byte equality is intentionally not required
    _write(copy / "art" / "cover.jpg", b"654321")
    (copy / "empty").mkdir(parents=True)

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root), str(home), trash_func=lambda path: trashed.append(path), emit=lambda *a, **k: None
    )

    assert count == 1
    assert trashed == [str(copy.resolve())]
    assert original.exists()
    assert (home / "deletedDirs.txt").read_text(encoding="utf-8").splitlines() == [str(copy.resolve())]


@pytest.mark.parametrize("mutation", ["extra_file", "missing_file", "size", "extra_dir", "missing_dir"])
def test_any_recursive_structure_name_or_size_difference_is_not_trashed(tmp_path, mutation):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 HOB Boston (copy3)"
    _write(original / "01.flac", b"abcd")
    _write(original / "nested" / "02.flac", b"efgh")
    (original / "empty").mkdir(parents=True)
    _write(copy / "01.flac", b"abcd")
    _write(copy / "nested" / "02.flac", b"efgh")
    (copy / "empty").mkdir(parents=True)

    if mutation == "extra_file":
        _write(copy / "extra.txt", b"x")
    elif mutation == "missing_file":
        (copy / "nested" / "02.flac").unlink()
    elif mutation == "size":
        _write(copy / "01.flac", b"abcde")
    elif mutation == "extra_dir":
        (copy / "extra-empty").mkdir()
    elif mutation == "missing_dir":
        (copy / "empty").rmdir()

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root), str(home), trash_func=lambda path: trashed.append(path), emit=lambda *a, **k: None
    )
    assert count == 0
    assert trashed == []
    assert copy.exists()
    assert original.exists()
    assert (home / "deletedDirs.txt").read_text(encoding="utf-8") == ""


def test_copy_without_unsuffixed_original_is_never_trashed(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    copy = root / "Bill 2013 HOB Boston (copy 2)"
    _write(copy / "01.flac", b"abcd")
    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root), str(home), trash_func=lambda path: trashed.append(path), emit=lambda *a, **k: None
    )
    assert count == 0
    assert trashed == []
    assert copy.exists()


def test_search_is_recursive_and_original_is_never_sent_to_trash(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "artist" / "year" / "Bill 2013 HOB Boston"
    copy = root / "artist" / "year" / "Bill 2013 HOB Boston (copy2)"
    _write(original / "01.flac", b"abcd")
    _write(copy / "01.flac", b"zzzz")
    trashed = []
    module.delete_duplicate_copy_directories(
        str(root), str(home), trash_func=lambda path: trashed.append(path), emit=lambda *a, **k: None
    )
    assert trashed == [str(copy.resolve())]
    assert str(original.resolve()) not in trashed


def test_input_path_must_be_fully_qualified_and_existing_directory(tmp_path):
    module = _load_module()
    with pytest.raises(module.DeleteDupesError, match="fully qualified"):
        module.validate_input_path("relative/path")
    with pytest.raises(module.DeleteDupesError, match="does not exist"):
        module.validate_input_path(str(tmp_path / "missing"))
    file_path = tmp_path / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(module.DeleteDupesError, match="not a directory"):
        module.validate_input_path(str(file_path))


def test_main_uses_shared_tlohome_precedence_and_hidden_mytlo(tmp_path, monkeypatch):
    module = _load_module()
    env_home = tmp_path / "env-home"
    cli_home = tmp_path / "cli-home"
    my_home = tmp_path / "my-home"
    root = tmp_path / "music"
    for path in (env_home, cli_home, my_home, root):
        path.mkdir()
    monkeypatch.setenv("TLOHome", str(env_home))
    seen = {}

    def fake_delete(search_root, tlo_home, **kwargs):
        seen["search_root"] = search_root
        seen["tlo_home"] = tlo_home
        return 0

    monkeypatch.setattr(module, "delete_duplicate_copy_directories", fake_delete)
    assert module.main(["--TLOHome", str(cli_home), "--myTLO", str(my_home), str(root)]) == 0
    assert seen == {"search_root": str(root), "tlo_home": str(my_home)}


def test_keyboard_interrupt_returns_130_and_log_context_closes(tmp_path, monkeypatch):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    root.mkdir()
    monkeypatch.setattr(module, "delete_duplicate_copy_directories", lambda *a, **k: (_ for _ in ()).throw(KeyboardInterrupt()))
    assert module.main(["--TLOHome", str(home), str(root)]) == 130


def test_keyboard_interrupt_inside_cleanup_closes_real_log_context(tmp_path, monkeypatch):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 HOB Boston (copy 2)"
    _write(original / "01.flac", b"abcd")
    _write(copy / "01.flac", b"WXYZ")

    builtin_open = open
    tracked = {}

    class TrackingFile:
        def __init__(self, inner):
            self.inner = inner

        def __enter__(self):
            self.inner.__enter__()
            return self

        def __exit__(self, exc_type, exc, tb):
            return self.inner.__exit__(exc_type, exc, tb)

        def write(self, *args, **kwargs):
            return self.inner.write(*args, **kwargs)

        def flush(self):
            return self.inner.flush()

        @property
        def closed(self):
            return self.inner.closed

    def tracking_open(*args, **kwargs):
        wrapped = TrackingFile(builtin_open(*args, **kwargs))
        tracked["log"] = wrapped
        return wrapped

    def interrupting_trash(_path):
        raise KeyboardInterrupt()

    monkeypatch.setattr(module, "open", tracking_open, raising=False)
    with pytest.raises(KeyboardInterrupt):
        module.delete_duplicate_copy_directories(
            str(root), str(home), trash_func=interrupting_trash, emit=lambda *a, **k: None
        )

    assert tracked["log"].closed
    assert copy.exists()
    assert original.exists()
    assert (home / "deletedDirs.txt").read_text(encoding="utf-8") == ""
