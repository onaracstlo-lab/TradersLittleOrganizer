"""Behavior tests for the tlo-deleteDupes main."""

__version__ = "v370"

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_module():
    spec = importlib.util.spec_from_file_location("tlo_delete_dupes_v370", ROOT / "tlo-deleteDupes.py")
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



def test_corrupt_kept_flac_is_repaired_from_lowest_healthy_numeric_copy(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy1 = root / "Bill 2013 HOB Boston (copy 1)"
    copy2 = root / "Bill 2013 HOB Boston (copy 2)"
    copy10 = root / "Bill 2013 HOB Boston (copy 10)"

    _write(original / "disc1" / "01.flac", b"BAD!")
    _write(copy1 / "disc1" / "01.flac", b"BAD?")
    _write(copy2 / "disc1" / "01.flac", b"GOOD")
    _write(copy10 / "disc1" / "01.flac", b"BEST")

    checked = []

    def health(path, **_kwargs):
        checked.append(str(path))
        return Path(path).read_bytes() in {b"GOOD", b"BEST"}

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=health,
    )

    assert count == 3
    assert (original / "disc1" / "01.flac").read_bytes() == b"GOOD"
    # copy 1 is checked before copy 2, and copy 10 is never needed as a repair source.
    copy1_index = checked.index(str(copy1 / "disc1" / "01.flac"))
    copy2_index = checked.index(str(copy2 / "disc1" / "01.flac"))
    assert copy1_index < copy2_index
    assert str(copy10 / "disc1" / "01.flac") not in checked
    assert trashed == [str(copy1.resolve()), str(copy2.resolve()), str(copy10.resolve())]


def test_unrepairable_corrupt_kept_flac_does_not_keep_qualifying_copies(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy1 = root / "Bill 2013 HOB Boston (copy1)"
    copy2 = root / "Bill 2013 HOB Boston (copy2)"

    _write(original / "01.flac", b"BAD0")
    _write(copy1 / "01.flac", b"BAD1")
    _write(copy2 / "01.flac", b"BAD2")

    def health(path, **_kwargs):
        return False

    trashed = []
    messages = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda message, **kwargs: messages.append((message, kwargs)),
        ffmpeg_executable="fake-ffmpeg",
        health_check=health,
    )

    assert count == 2
    assert (original / "01.flac").read_bytes() == b"BAD0"
    assert trashed == [str(copy1.resolve()), str(copy2.resolve())]
    assert any("could not be replaced; continuing" in message for message, _ in messages)


def test_only_structurally_qualifying_copies_are_repair_sources_or_trashed(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy1 = root / "Bill 2013 HOB Boston (copy1)"
    copy2 = root / "Bill 2013 HOB Boston (copy2)"

    _write(original / "01.flac", b"BAD!")
    _write(copy1 / "01.flac", b"GOOD")
    _write(copy1 / "extra.txt", b"different tree")
    _write(copy2 / "01.flac", b"BEST")

    checked = []

    def health(path, **_kwargs):
        checked.append(str(path))
        return Path(path).read_bytes() in {b"GOOD", b"BEST"}

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=health,
    )

    assert count == 1
    assert (original / "01.flac").read_bytes() == b"BEST"
    assert str(copy1 / "01.flac") not in checked
    assert trashed == [str(copy2.resolve())]
    assert copy1.exists()


def test_flac_health_check_requests_full_decode_and_uses_xerror(tmp_path):
    module = _load_module()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")
    seen = {}

    class Result:
        returncode = 0

    def fake_run(command, **kwargs):
        seen["command"] = command
        seen["kwargs"] = kwargs
        return Result()

    assert module.flac_file_is_healthy(str(flac), ffmpeg_executable="ffmpeg", run_func=fake_run)
    assert "-xerror" in seen["command"]
    assert seen["command"][-3:] == ["-f", "null", "-"]
    assert str(flac) in seen["command"]
    assert seen["kwargs"]["check"] is False


def test_flac_health_check_returns_false_on_decoder_failure(tmp_path):
    module = _load_module()
    flac = tmp_path / "track.flac"
    flac.write_bytes(b"placeholder")

    class Result:
        returncode = 1

    assert not module.flac_file_is_healthy(
        str(flac), ffmpeg_executable="ffmpeg", run_func=lambda *a, **k: Result()
    )


def test_same_artist_and_year_can_match_even_when_folder_names_differ(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 House of Blues Boston (copy 2)"
    _write(original / "01.flac", b"ABCD")
    _write(original / "nested" / "notes.txt", b"notes")
    _write(copy / "01.flac", b"WXYZ")
    _write(copy / "nested" / "notes.txt", b"other")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert trashed == [str(copy.resolve())]
    assert original.exists()


def test_same_artist_and_full_date_can_match_even_when_venue_text_differs(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013-05-04 HOB Boston"
    copy = root / "Bill - 2013-05-04 - House of Blues Boston (copy3)"
    _write(original / "01.flac", b"ABCD")
    _write(copy / "01.flac", b"WXYZ")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert trashed == [str(copy.resolve())]


@pytest.mark.parametrize(
    "original_name,copy_name",
    [
        ("Bill 2013 HOB Boston", "Bill 2014 House of Blues Boston (copy2)"),
        ("Bill 2013 HOB Boston", "Bob 2013 House of Blues Boston (copy2)"),
    ],
)
def test_artist_and_date_both_must_match_for_nonexact_name_duplicate_discovery(tmp_path, original_name, copy_name):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / original_name
    copy = root / copy_name
    _write(original / "01.flac", b"ABCD")
    _write(copy / "01.flac", b"WXYZ")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 0
    assert trashed == []
    assert original.exists() and copy.exists()


def test_nonexact_name_duplicate_still_requires_full_recursive_name_structure_and_size_match(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 House of Blues Boston (copy 2)"
    _write(original / "01.flac", b"ABCD")
    _write(original / "nested" / "02.flac", b"EFGH")
    _write(copy / "01.flac", b"WXYZ")
    _write(copy / "nested" / "02.flac", b"TOO-LONG")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 0
    assert trashed == []
    assert copy.exists()


def test_nonexact_name_copy_can_repair_corrupt_kept_flac_before_folder_is_trashed(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 House of Blues Boston (copy 1)"
    _write(original / "disc1" / "01.flac", b"BAD!")
    _write(copy / "disc1" / "01.flac", b"GOOD")

    def health(path, **_kwargs):
        return Path(path).read_bytes() == b"GOOD"

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=health,
    )

    assert count == 1
    assert (original / "disc1" / "01.flac").read_bytes() == b"GOOD"
    assert trashed == [str(copy.resolve())]


def test_move_operation_moves_duplicate_directory_as_one_complete_tree(tmp_path):
    module = _load_module()
    copy = tmp_path / "Bill 2013 HOB Boston (copy 2)"
    duplicates = tmp_path / "duplicates"
    duplicates.mkdir()
    _write(copy / "01.flac", b"ABCD")
    _write(copy / "nested" / "02.flac", b"EFGH")
    (copy / "empty").mkdir(parents=True)
    source_path = str(copy.resolve())

    returned_source, returned_destination = module._move_duplicate_folder_to_duplicates(
        str(copy), str(duplicates)
    )

    destination = duplicates / copy.name
    assert returned_source == source_path
    assert returned_destination == str(destination.resolve())
    assert not copy.exists()
    assert (destination / "01.flac").read_bytes() == b"ABCD"
    assert (destination / "nested" / "02.flac").read_bytes() == b"EFGH"
    assert (destination / "empty").is_dir()


def test_show_identity_accepts_year_or_full_date_but_rejects_unknown_date():
    module = _load_module()
    assert module._show_identity("Bill 2013 HOB Boston") == ("bill", "2013")
    assert module._show_identity("Bill 2013-05-04 HOB Boston (copy 2)") == ("bill", "2013-05-04")
    assert module._show_identity("Bill xxxx-xx-xx HOB Boston") == ("", "")


def test_exact_base_mismatch_can_fall_through_to_same_artist_date_matching_original(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    # The exact unsuffixed base exists but is not the same tree.
    exact_base = root / "Bill 2013 House of Blues Boston"
    matching_original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 House of Blues Boston (copy 2)"
    _write(exact_base / "01.flac", b"TOO-LONG")
    _write(matching_original / "01.flac", b"ABCD")
    _write(copy / "01.flac", b"WXYZ")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert trashed == [str(copy.resolve())]
    assert exact_base.exists()
    assert matching_original.exists()


def test_unsuffixed_same_artist_date_duplicates_keep_first_alphabetically(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    alpha = root / "Bill 2013 Alpha Club Boston"
    beta = root / "Bill 2013 Beta Club Boston"
    gamma = root / "Bill 2013 Gamma Club Boston"
    # Create them in reverse order so filesystem creation order cannot choose the master.
    for folder, payload in ((gamma, b"GGGG"), (beta, b"BBBB"), (alpha, b"AAAA")):
        _write(folder / "01.flac", payload)
        _write(folder / "nested" / "notes.txt", b"same-size")
        (folder / "empty").mkdir(parents=True)

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 2
    assert alpha.exists()
    assert trashed == [str(beta.resolve()), str(gamma.resolve())]
    assert (home / "deletedDirs.txt").read_text(encoding="utf-8").splitlines() == [
        str(beta.resolve()),
        str(gamma.resolve()),
    ]


def test_unsuffixed_same_artist_date_later_folder_must_match_master_tree(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    alpha = root / "Bill 2013 Alpha Club Boston"
    beta = root / "Bill 2013 Beta Club Boston"
    gamma = root / "Bill 2013 Gamma Club Boston"
    _write(alpha / "01.flac", b"AAAA")
    _write(beta / "01.flac", b"BBBB")
    _write(gamma / "01.flac", b"TOO-LONG")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert alpha.exists()
    assert gamma.exists()
    assert trashed == [str(beta.resolve())]


def test_unsuffixed_duplicate_repair_sources_follow_alphabetical_order(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    alpha = root / "Bill 2013 Alpha Club Boston"
    beta = root / "Bill 2013 Beta Club Boston"
    gamma = root / "Bill 2013 Gamma Club Boston"
    _write(alpha / "disc1" / "01.flac", b"BAD!")
    _write(beta / "disc1" / "01.flac", b"GOOD")
    _write(gamma / "disc1" / "01.flac", b"BEST")

    checked = []

    def health(path, **_kwargs):
        checked.append(str(path))
        return Path(path).read_bytes() in {b"GOOD", b"BEST"}

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=health,
    )

    assert count == 2
    assert (alpha / "disc1" / "01.flac").read_bytes() == b"GOOD"
    assert str(beta / "disc1" / "01.flac") in checked
    assert str(gamma / "disc1" / "01.flac") not in checked
    assert trashed == [str(beta.resolve()), str(gamma.resolve())]


def test_unsuffixed_same_content_is_not_candidate_without_same_artist_and_date(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    first = root / "Bill 2013 Alpha Club Boston"
    other_artist = root / "Bob 2013 Beta Club Boston"
    other_date = root / "Bill 2014 Gamma Club Boston"
    for folder in (first, other_artist, other_date):
        _write(folder / "01.flac", b"AAAA")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 0
    assert trashed == []
    assert first.exists() and other_artist.exists() and other_date.exists()


def test_copy_suffix_attached_to_unsuffixed_duplicate_uses_surviving_alphabetical_master(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    alpha = root / "Bill 2013 Alpha Club Boston"
    beta = root / "Bill 2013 Beta Club Boston"
    beta_copy = root / "Bill 2013 Beta Club Boston (copy 1)"
    _write(alpha / "01.flac", b"AAAA")
    _write(beta / "01.flac", b"BBBB")
    _write(beta_copy / "01.flac", b"CCCC")

    trashed = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: trashed.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 2
    assert alpha.exists()
    assert trashed == [str(beta_copy.resolve()), str(beta.resolve())]


def test_partition_root_resolution_supports_windows_drive_and_posix_mount():
    module = _load_module()
    assert module._partition_root_for_path(
        r"E:\Music\Shows", platform_name="nt"
    ) == "E:\\"
    assert module._partition_root_for_path(
        "/mnt/music/Shows",
        platform_name="posix",
        ismount_func=lambda path: path == "/mnt/music",
    ) == "/mnt/music"


def test_cleanup_creates_partition_duplicates_folder_and_moves_whole_folder(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    partition = tmp_path / "partition"
    root = partition / "music"
    duplicates = partition / "duplicates"
    home.mkdir()
    original = root / "Bill 2013 HOB Boston"
    copy = root / "Bill 2013 HOB Boston (copy 2)"
    _write(original / "01.flac", b"ABCD")
    _write(original / "nested" / "notes.txt", b"notes")
    (original / "empty").mkdir(parents=True)
    _write(copy / "01.flac", b"WXYZ")
    _write(copy / "nested" / "notes.txt", b"xxxxx")
    # Same file size is required, not byte equality.
    (copy / "nested" / "notes.txt").write_bytes(b"other")
    (copy / "empty").mkdir(parents=True)

    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        duplicates_root=str(duplicates),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    moved = duplicates / copy.name
    assert count == 1
    assert duplicates.is_dir()
    assert original.exists()
    assert not copy.exists()
    assert (moved / "01.flac").read_bytes() == b"WXYZ"
    assert (moved / "nested" / "notes.txt").read_bytes() == b"other"
    assert (moved / "empty").is_dir()
    assert (home / "deletedDirs.txt").read_text(encoding="utf-8").splitlines() == [
        str(copy.resolve())
    ]


def test_duplicate_holding_folder_collision_uses_moved_suffix_without_overwrite(tmp_path):
    module = _load_module()
    duplicates = tmp_path / "duplicates"
    source = tmp_path / "Bill 2013 HOB Boston (copy 2)"
    existing = duplicates / source.name
    _write(source / "01.flac", b"NEW1")
    _write(existing / "01.flac", b"OLD!!")

    _source, destination = module._move_duplicate_folder_to_duplicates(str(source), str(duplicates))

    assert Path(destination).name == source.name + " (moved 2)"
    assert (existing / "01.flac").read_bytes() == b"OLD!!"
    assert (Path(destination) / "01.flac").read_bytes() == b"NEW1"


def test_existing_duplicates_holding_folder_is_excluded_when_searching_partition_root(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    partition = tmp_path / "partition"
    duplicates = partition / "duplicates"
    home.mkdir()

    original = partition / "music" / "Bill 2013 HOB Boston"
    copy = partition / "music" / "Bill 2013 HOB Boston (copy 2)"
    _write(original / "01.flac", b"ABCD")
    _write(copy / "01.flac", b"WXYZ")

    # A prior holding-area pair would qualify if TLO descended into duplicates.
    held_original = duplicates / "Bob 2014 Alpha Club"
    held_copy = duplicates / "Bob 2014 Alpha Club (copy 2)"
    _write(held_original / "01.flac", b"1234")
    _write(held_copy / "01.flac", b"5678")

    count = module.delete_duplicate_copy_directories(
        str(partition),
        str(home),
        duplicates_root=str(duplicates),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert (duplicates / copy.name).is_dir()
    assert held_original.is_dir()
    assert held_copy.is_dir()


def test_input_path_inside_duplicates_holding_folder_is_rejected(tmp_path):
    module = _load_module()
    partition = tmp_path / "partition"
    duplicates = partition / "duplicates"
    nested = duplicates / "nested"
    nested.mkdir(parents=True)

    with pytest.raises(module.DeleteDupesError, match="duplicates holding folder"):
        module._prepare_duplicates_root(str(nested), str(duplicates))


def test_delete_dupes_records_simple_mismatch_reasons_in_separate_log(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    master = root / "Bill 2013 HOB Boston"
    size_diff = root / "Bill 2013 House of Blues Boston"
    extra_file = root / "Bill 2013 Paradise Boston"
    structure_diff = root / "Bill 2013 Orpheum Boston"

    _write(master / "01.flac", b"AAAA")
    _write(master / "notes.txt", b"notes")

    _write(size_diff / "01.flac", b"LONGER")
    _write(size_diff / "notes.txt", b"notes")

    _write(extra_file / "01.flac", b"AAAA")
    _write(extra_file / "notes.txt", b"notes")
    _write(extra_file / "extra.txt", b"extra")

    _write(structure_diff / "disc1" / "01.flac", b"AAAA")
    _write(structure_diff / "notes.txt", b"notes")

    moved = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda _path: None,
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert moved == 0
    rows = list(__import__("csv").reader((home / "deleteDupesMismatches.txt").open(encoding="utf-8")))
    by_candidate = {row[1]: row[2] for row in rows if row[0] == master.name}
    assert by_candidate[size_diff.name] == "01.flac different sizes"
    assert by_candidate[extra_file.name] == "different number of files"
    assert by_candidate[structure_diff.name] == "different sub-structure"
    assert (home / "deletedDirs.txt").read_text(encoding="utf-8") == ""


def test_delete_dupes_mismatch_log_csv_quotes_folder_names_with_commas(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()
    master = root / "Alejandro Escovedo 2005-03-18 SXSW Bugsby hill, Auditorium Shores Austin, TX"
    candidate = root / "Alejandro Escovedo 2005-03-18 SXSW, Auditorium Shores Austin, TX"
    _write(master / "01.flac", b"AAAA")
    _write(candidate / "01.flac", b"BBBBB")

    module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda _path: None,
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    import csv
    with (home / "deleteDupesMismatches.txt").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows == [[master.name, candidate.name, "01.flac different sizes"]]


def test_alejandro_six_folder_case_moves_matching_plain_folder_and_logs_extra_flac(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    names = [
        "Alejandro Escovedo 2005-03-18 SXSW, Auditorium Shores Austin, TX (copy2) - Copy",
        "Alejandro Escovedo 2005-03-18 SXSW, Auditorium Shores Austin, TX (copy2) - Copy (2)",
        "Alejandro Escovedo 2005-03-18 SXSW Bugsby hill, Auditorium Shores Austin, TX",
        "Alejandro Escovedo 2005-03-18 SXSW, Auditorium Shores Austin, TX - Copy (2)",
        "Alejandro Escovedo 2005-03-18 SXSW, Auditorium Shores Austin, TX (copy2)",
        "Alejandro Escovedo 2005-03-18 SXSW, Auditorium Shores Austin, TX",
    ]
    folders = {name: root / name for name in names}
    for folder in folders.values():
        _write(folder / "01.flac", b"AAAA")
    extra_name = names[1]
    _write(folders[extra_name] / "02.flac", b"EXTRA")

    moved_paths = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: moved_paths.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    moved_names = {Path(path).name for path in moved_paths}
    assert count == 4
    assert names[5] in moved_names  # plain ...Austin, TX folder
    assert names[4] in moved_names  # terminal (copy2)
    assert names[0] in moved_names
    assert names[3] in moved_names
    assert names[2] not in moved_names  # alphabetical Bugsby master
    assert extra_name not in moved_names

    import csv
    with (home / "deleteDupesMismatches.txt").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert [names[2], extra_name, "different number of files"] in rows


def test_numbered_copies_form_their_own_duplicate_cluster_when_both_differ_from_unsuffixed_x(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    master = root / "X"
    copy2 = root / "X (copy2)"
    copy3 = root / "X (copy3)"
    _write(master / "01.flac", b"AAAA")
    _write(copy2 / "01.flac", b"BBBB")
    _write(copy2 / "02.flac", b"CCCC")
    _write(copy3 / "01.flac", b"DDDD")
    _write(copy3 / "02.flac", b"EEEE")

    moved = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: moved.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert master.exists()
    assert copy2.exists()
    assert moved == [str(copy3.resolve())]


def test_numbered_copies_compare_with_each_other_even_when_unsuffixed_master_is_absent(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    copy2 = root / "X (copy2)"
    copy3 = root / "X (copy3)"
    _write(copy2 / "disc1" / "01.flac", b"AAAA")
    _write(copy3 / "disc1" / "01.flac", b"BBBB")

    moved = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: moved.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 1
    assert copy2.exists()
    assert moved == [str(copy3.resolve())]


def test_identical_content_cluster_prefers_unsuffixed_folder_over_lower_numbered_copy(tmp_path):
    module = _load_module()
    home = tmp_path / "home"
    root = tmp_path / "music"
    home.mkdir()

    copy1 = root / "Bill 2013 HOB Boston (copy1)"
    unsuffixed = root / "Bill 2013 House of Blues Boston"
    copy2 = root / "Bill 2013 HOB Boston (copy2)"
    for folder, payload in ((copy1, b"AAAA"), (unsuffixed, b"BBBB"), (copy2, b"CCCC")):
        _write(folder / "01.flac", payload)

    moved = []
    count = module.delete_duplicate_copy_directories(
        str(root),
        str(home),
        trash_func=lambda path: moved.append(path),
        emit=lambda *a, **k: None,
        ffmpeg_executable="fake-ffmpeg",
        health_check=lambda *_a, **_k: True,
    )

    assert count == 2
    assert unsuffixed.exists()
    assert {Path(path).name for path in moved} == {copy1.name, copy2.name}
