"""Build 545 temporary-tree pruning and Copy Request symlink-safety regressions."""

from __future__ import annotations
from tests._release_artifacts import release_history
from tests import _release_artifacts as RA

import os
from pathlib import Path

import pytest

import tlo_copy_requests as CR
import tlo_folder_rename as FR
import tlo_path_policy as PP
import tlo_reverse_folders as RF
import tlo_tag_lib as TL
import tlo_tree_compare as TC

pytestmark = pytest.mark.behavior


def _make_symlink(link: Path, target: Path | str, *, target_is_directory: bool = False) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symbolic links unavailable on this host: {exc}")


def test_build545_real_work_folder_names_are_phase1_pruned(tmp_path):
    destination = tmp_path / "Artist 2000-01-01 Venue"
    tag_partial = Path(TL._owned_partial_copy_path(str(destination)))
    case_temp = Path(FR._temporary_case_rename_path(str(destination)))
    reverse_temp = Path(RF._reverse_partial_path(str(destination)))

    assert tag_partial.name.startswith(".tlo-partial-")
    assert case_temp.name.startswith(".tlo-case-rename-")
    assert reverse_temp.name.startswith(".tlo-restore-")

    for path_name in (tag_partial, case_temp, reverse_temp):
        assert PP.is_phase1_pruned_directory(path_name.name), path_name.name


def test_build545_tree_compare_treats_file_symlinks_as_links(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    target = tmp_path / "outside.txt"
    target.write_bytes(b"same bytes")

    _make_symlink(left / "info.txt", target)
    _make_symlink(right / "info.txt", target)
    assert TC.directory_trees_exactly_match(str(left), str(right))

    (right / "info.txt").unlink()
    (right / "info.txt").write_bytes(target.read_bytes())
    assert not TC.directory_trees_exactly_match(str(left), str(right))


def test_build545_tree_compare_requires_same_symlink_target_text(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    _make_symlink(left / "link", "../one")
    _make_symlink(right / "link", "../two")

    assert not TC.directory_trees_exactly_match(str(left), str(right))


def test_build545_tree_compare_treats_directory_symlinks_as_links(tmp_path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    outside = tmp_path / "outside"
    left.mkdir()
    right.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    _make_symlink(left / "docs", outside, target_is_directory=True)
    _make_symlink(right / "docs", outside, target_is_directory=True)

    assert TC.directory_trees_exactly_match(str(left), str(right))
    # The external descendant is not part of either manifest.
    dirs, files, links = TC._tree_manifest(str(left))
    assert os.path.normcase("docs") in links
    assert not files
    assert not any("secret" in item for item in dirs)


def test_build545_copy_boundary_never_dereferences_raced_in_symlink(monkeypatch, tmp_path):
    source = tmp_path / "source"
    temp_target = tmp_path / "temp"
    source.mkdir()
    temp_target.mkdir()
    payload = source / "info.txt"
    payload.write_text("ordinary", encoding="utf-8")
    secret = tmp_path / "outside-secret.txt"
    secret.write_text("do not copy me", encoding="utf-8")

    real_walk = CR._walk_tree_size_and_reject_links
    source_checked = False

    def race_after_source_check(root, *, ignore_root_names=()):
        nonlocal source_checked
        result = real_walk(root, ignore_root_names=ignore_root_names)
        if not source_checked and os.path.samefile(root, source):
            source_checked = True
            payload.unlink()
            _make_symlink(payload, secret)
        return result

    monkeypatch.setattr(CR, "_walk_tree_size_and_reject_links", race_after_source_check)

    with pytest.raises(CR.CopyRequestError, match="symbolic link"):
        CR._copy_into_temp_target(str(source), str(temp_target))

    copied = temp_target / "info.txt"
    assert copied.is_symlink()
    assert os.readlink(copied) == str(secret)
    # The link target itself was not copied into the temporary tree as a regular file.
    assert copied.lstat().st_size == len(str(secret).encode())


def test_build545_copy_boundary_still_copies_normal_tree(tmp_path):
    source = tmp_path / "source"
    temp_target = tmp_path / "temp"
    source.mkdir()
    temp_target.mkdir()
    (source / "disc1").mkdir()
    (source / "disc1" / "01.flac").write_bytes(b"audio")
    (source / "info.txt").write_text("setlist", encoding="utf-8")

    CR._copy_into_temp_target(str(source), str(temp_target))

    assert (temp_target / "disc1" / "01.flac").read_bytes() == b"audio"
    assert (temp_target / "info.txt").read_text(encoding="utf-8") == "setlist"
    assert TC.directory_trees_exactly_match(str(source), str(temp_target))


def test_build545_version_and_documentation_contract():
    from docx import Document

    root = Path(__file__).resolve().parents[2]

    req_path = root / RA.REQUIREMENTS_FILENAME
    manual_path = root / RA.MANUAL_FILENAME
    assert req_path.is_file() and manual_path.is_file()
    req = "\n".join(p.text for p in Document(req_path).paragraphs)
    assert "Build 545: P2-L3/L-06 -> §3, §14.6" in req
    assert ".tlo-case-rename-" in req
    assert "preserve any link that appears after that check rather than dereferencing its target" in req

    manual = manual_path.read_text(encoding="utf-8", errors="ignore")
    assert "Build 545 - " in release_history()
    assert "Copy Requests reject source trees containing symbolic links" in manual

    changes = (root / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "TLO v1.7 Build 545" in changes
    first = changes.split("TLO v1.7 Build 544", 1)[0]
    assert "P2-L3 / L-06" in first
    assert "GitHub Build Process remains v108 unchanged" in first
