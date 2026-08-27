"""Repair corrupt FLACs from duplicate copies, then move duplicates to a partition holding folder."""

__version__ = "v413"

import argparse
import hashlib
import csv
import ntpath
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple


from console_output_lib import console_emit
from tlo_path_inputs import normalize_platform_input_path, resolve_tlo_home, strip_optional_quotes
from tlo_text_utils import normalized_compare_value


_COPY_SUFFIX_RE = re.compile(r"^(?P<base>.+?)\s+\(copy\s*(?P<number>[1-9]\d*)\)$", re.IGNORECASE)
# Identity matching is intentionally conservative.  It recognizes the date forms
# used in normal TLO show-folder names plus a standalone four-digit 19xx/20xx
# year.  Unknown dates are not useful for duplicate discovery because they would
# make every unknown-date show by the same artist a candidate.
_SHOW_IDENTITY_DATE_RE = re.compile(
    r"(?<![0-9])(?P<date>"
    r"(?:19|20)\d{2}-(?:0?[1-9]|1[0-2]|xx)-(?:0?[1-9]|[12]\d|3[01]|xx)"
    r"|(?:19|20)\d{2}-(?:19|20)\d{2}"
    r"|(?:19|20)\d{2}"
    r")(?![0-9-])",
    re.IGNORECASE,
)


FLAC_VALIDATION_TIMEOUT_SECONDS = 180


class DeleteDupesError(RuntimeError):
    """Raised for invalid paths or an unsafe/unverifiable duplicate comparison."""



def _normalized_path_key(path_name: str) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(path_name)))


def _is_same_or_descendant(path_name: str, root: str) -> bool:
    """Return True when path_name is root or lies beneath root."""
    try:
        return os.path.commonpath([_normalized_path_key(path_name), _normalized_path_key(root)]) == _normalized_path_key(root)
    except (ValueError, OSError):
        return False


def _partition_root_for_path(
    path_name: str,
    *,
    platform_name: Optional[str] = None,
    ismount_func=os.path.ismount,
) -> str:
    """Return the drive/share or mounted-filesystem root containing path_name."""
    platform_name = platform_name or os.name
    if platform_name == "nt":
        normalized = ntpath.abspath(ntpath.normpath(str(path_name or "")))
        drive, _tail = ntpath.splitdrive(normalized)
        if not drive:
            raise DeleteDupesError(f"Unable to determine partition root for Input Path: {path_name}")
        return ntpath.normpath(drive + ntpath.sep)

    current = os.path.abspath(os.path.normpath(str(path_name or "")))
    while True:
        if ismount_func(current):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return current
        current = parent


def _duplicates_root_for_search(search_root: str) -> str:
    """Return <partition-root>/duplicates for the filesystem being searched."""
    partition_root = _partition_root_for_path(search_root)
    return os.path.normpath(os.path.join(partition_root, "duplicates"))


def _prepare_duplicates_root(search_root: str, duplicates_root: Optional[str] = None) -> str:
    """Create and validate the partition-root duplicates holding directory."""
    destination = os.path.abspath(os.path.normpath(duplicates_root or _duplicates_root_for_search(search_root)))
    search_key = _normalized_path_key(search_root)
    destination_key = _normalized_path_key(destination)
    if search_key == destination_key or _is_same_or_descendant(search_root, destination):
        raise DeleteDupesError(
            f"Input Path may not be the duplicates holding folder or one of its descendants: {destination}"
        )
    if os.path.lexists(destination) and os.path.islink(destination):
        raise DeleteDupesError(f"Duplicates holding path must not be a symbolic link: {destination}")
    try:
        os.makedirs(destination, exist_ok=True)
    except OSError as exc:
        raise DeleteDupesError(f"Unable to create duplicates holding folder: {destination}: {exc}") from exc
    if not os.path.isdir(destination):
        raise DeleteDupesError(f"Duplicates holding path is not a directory: {destination}")
    return destination


def _prune_excluded_dir_names(current_dir: str, dir_names: List[str], excluded_paths: Iterable[str]) -> None:
    """Prevent os.walk from descending into holding directories such as /duplicates."""
    excluded = {_normalized_path_key(path_name) for path_name in excluded_paths if path_name}
    if not excluded:
        return
    kept = []
    for dir_name in dir_names:
        child = os.path.join(current_dir, dir_name)
        if _normalized_path_key(child) in excluded:
            continue
        kept.append(dir_name)
    dir_names[:] = kept


@dataclass(frozen=True)
class TreeManifest:
    directories: frozenset[str]
    files: Tuple[Tuple[str, int], ...]
    symlinks: Tuple[Tuple[str, str], ...]


@dataclass(frozen=True)
class CopyCandidate:
    number: int
    path: str
    source_kind: str = "numbered"
    alphabetical_rank: int = 0


def _relative_key(path_name: str, root: str) -> str:
    """Return a normalized relative path key without resolving symlinks."""
    return os.path.normcase(os.path.normpath(os.path.relpath(path_name, root)))


def _scan_tree(root: str) -> TreeManifest:
    """Return recursive structure plus file names/sizes for one directory tree.

    Directory identity for this utility intentionally does not compare file bytes,
    timestamps, ownership, permissions, or other filesystem metadata. It requires
    the same relative directory structure, the same relative file names, and the
    same file sizes. Symlinks are not followed; corresponding symlinks must have
    the same relative name and link target.
    """
    directories: Set[str] = set()
    files: Dict[str, int] = {}
    symlinks: Dict[str, str] = {}

    def visit(current: str) -> None:
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            raise DeleteDupesError(f"Unable to read directory during comparison: {current}: {exc}") from exc

        for entry in entries:
            full_path = entry.path
            relative = _relative_key(full_path, root)
            try:
                if entry.is_symlink():
                    symlinks[relative] = os.readlink(full_path)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    directories.add(relative)
                    visit(full_path)
                    continue
                if entry.is_file(follow_symlinks=False):
                    files[relative] = entry.stat(follow_symlinks=False).st_size
                    continue
            except OSError as exc:
                raise DeleteDupesError(f"Unable to inspect path during comparison: {full_path}: {exc}") from exc

            raise DeleteDupesError(f"Unsupported filesystem object during comparison: {full_path}")

    visit(root)
    return TreeManifest(
        directories=frozenset(directories),
        files=tuple(sorted(files.items())),
        symlinks=tuple(sorted(symlinks.items())),
    )


def _tree_manifest_mismatch_reason(left: TreeManifest, right: TreeManifest) -> str:
    """Return one short human-readable reason two scanned trees do not match."""
    if len(left.files) != len(right.files):
        return "different number of files"
    if left.directories != right.directories or left.symlinks != right.symlinks:
        return "different sub-structure"

    left_files = dict(left.files)
    right_files = dict(right.files)
    if set(left_files) != set(right_files):
        return "different file names"
    for relative_path in sorted(left_files):
        if left_files[relative_path] != right_files[relative_path]:
            return f"{relative_path} different sizes"
    return "different contents"


def compare_directory_trees_for_duplicate_deletion(original: str, copy_path: str) -> Tuple[bool, str]:
    """Return (matches, simple reason) under deleteDupes' structure/name/size rule."""
    original = os.path.normpath(str(original or ""))
    copy_path = os.path.normpath(str(copy_path or ""))
    if not os.path.isdir(original) or not os.path.isdir(copy_path):
        return False, "folder missing"
    try:
        if os.path.samefile(original, copy_path):
            return False, "same folder"
    except OSError:
        pass
    left = _scan_tree(original)
    right = _scan_tree(copy_path)
    if left == right:
        return True, ""
    return False, _tree_manifest_mismatch_reason(left, right)


def directory_trees_match_for_duplicate_deletion(original: str, copy_path: str) -> bool:
    """Return True when trees have identical names/structure and file sizes."""
    matches, _reason = compare_directory_trees_for_duplicate_deletion(original, copy_path)
    return matches


def _copy_suffix_info(directory_name: str) -> Tuple[str, Optional[int]]:
    match = _COPY_SUFFIX_RE.match(str(directory_name or "").strip())
    if not match:
        return "", None
    return match.group("base").strip(), int(match.group("number"))


def _copy_base_name(directory_name: str) -> str:
    base, _number = _copy_suffix_info(directory_name)
    return base


def _show_identity(directory_name: str) -> Tuple[str, str]:
    """Return normalized (artist, date) identity for a TLO-style folder name.

    The trailing copy suffix is ignored.  Artist is the material before the
    first recognized date token.  Matching is case/punctuation insensitive via
    normalized_compare_value(), while date matching is exact after case folding.
    A standalone 19xx/20xx year counts as a date for this duplicate-cleanup
    utility because older/commercial-style folder names may contain only a year.
    """
    text = str(directory_name or "").strip()
    base, number = _copy_suffix_info(text)
    if number is not None:
        text = base
    match = _SHOW_IDENTITY_DATE_RE.search(text)
    if not match:
        return "", ""
    artist_raw = re.sub(r"[\s._-]+$", "", text[: match.start()]).strip()
    artist = normalized_compare_value(artist_raw)
    date_value = str(match.group("date") or "").casefold()
    if not artist or not date_value:
        return "", ""
    return artist, date_value


def _same_artist_and_date(left_name: str, right_name: str) -> bool:
    left_identity = _show_identity(left_name)
    right_identity = _show_identity(right_name)
    return bool(left_identity[0] and left_identity == right_identity)


def _potential_originals_for_copy(copy_path: str) -> List[str]:
    """Return same-parent kept-folder candidates, exact base first.

    A copy-suffixed directory may match its exact unsuffixed base name or any
    other non-copy sibling whose normalized artist and date are the same.  Only
    the copy-suffixed directory can ever be selected for relocation.
    """
    copy_path = os.path.normpath(copy_path)
    parent = os.path.dirname(copy_path)
    copy_name = os.path.basename(copy_path)
    base, number = _copy_suffix_info(copy_name)
    if not base or number is None or not os.path.isdir(parent):
        return []

    exact_path = os.path.normpath(os.path.join(parent, base))
    results: List[str] = []
    seen: Set[str] = set()

    def add(path_name: str) -> None:
        normalized = os.path.normpath(path_name)
        key = os.path.normcase(normalized)
        if key in seen or not os.path.isdir(normalized) or os.path.islink(normalized):
            return
        # A copy folder is never used as the kept/original side of comparison.
        _candidate_base, candidate_number = _copy_suffix_info(os.path.basename(normalized))
        if candidate_number is not None:
            return
        seen.add(key)
        results.append(normalized)

    # Preserve the historic exact-name rule as the first and preferred match.
    add(exact_path)

    try:
        sibling_names = sorted(os.listdir(parent), key=lambda value: os.path.normcase(value))
    except OSError as exc:
        raise DeleteDupesError(f"Unable to read sibling directories for duplicate discovery: {parent}: {exc}") from exc

    for sibling_name in sibling_names:
        sibling_path = os.path.join(parent, sibling_name)
        if not os.path.isdir(sibling_path) or os.path.islink(sibling_path):
            continue
        if os.path.normcase(os.path.normpath(sibling_path)) == os.path.normcase(copy_path):
            continue
        if _same_artist_and_date(base, sibling_name):
            add(sibling_path)
    return results


def _alphabetical_name_key(path_name: str) -> Tuple[str, str]:
    """Return a deterministic case-insensitive alphabetical key for one folder."""
    name = os.path.basename(os.path.normpath(path_name))
    return (name.casefold(), name)


def _candidate_sort_key(candidate: CopyCandidate) -> Tuple[int, int, str, str]:
    """Order numbered copies numerically and unsuffixed duplicates alphabetically."""
    path_key = os.path.normcase(os.path.normpath(candidate.path))
    if candidate.source_kind == "numbered":
        return (0, int(candidate.number), path_key.casefold(), path_key)
    return (1, int(candidate.alphabetical_rank), path_key.casefold(), path_key)


def _record_tree_mismatch(recorder, left_path: str, right_path: str, reason: str) -> None:
    """Record one comparison failure when a mismatch recorder was supplied."""
    if recorder is None:
        return
    recorder(left_path, right_path, reason)


def _keeper_preference_key(path_name: str) -> Tuple[int, int, str, str]:
    """Prefer an unsuffixed folder, then the most natural deterministic name.

    Unsuffixed folders are preferred because they are generally the user's
    intended master.  When a content-equivalence cluster contains only numbered
    copy folders, the lowest copy number is preferred.  Ties are resolved
    alphabetically without regard to case.
    """
    name = os.path.basename(os.path.normpath(path_name))
    _base, copy_number = _copy_suffix_info(name)
    if copy_number is None:
        return (0, 0, name.casefold(), name)
    return (1, int(copy_number), name.casefold(), name)


def _copy_candidate_for_cluster_member(path_name: str, alphabetical_rank: int) -> CopyCandidate:
    """Return a CopyCandidate descriptor for a folder that will be relocated."""
    _base, copy_number = _copy_suffix_info(os.path.basename(os.path.normpath(path_name)))
    if copy_number is not None:
        return CopyCandidate(number=int(copy_number), path=path_name, source_kind="numbered")
    return CopyCandidate(
        number=int(alphabetical_rank),
        path=path_name,
        source_kind="alphabetical",
        alphabetical_rank=int(alphabetical_rank),
    )


def _candidate_components_for_parent(current_dir: str, dir_names: Iterable[str]) -> List[List[str]]:
    """Return sibling candidate components that warrant duplicate comparison.

    Two sibling folders enter the same discovery component when either:
      * they share the same normalized artist/date identity, or
      * they belong to the same exact copy family (X, X (copy2), X (copy3)).

    The second rule intentionally allows copy folders to be compared with each
    other even when no unsuffixed X folder exists or when X has different
    contents.  Candidate discovery is not duplicate proof; tree equivalence is
    established separately.
    """
    paths: List[str] = []
    names: List[str] = []
    for dir_name in dir_names:
        full_path = os.path.normpath(os.path.join(current_dir, dir_name))
        if not os.path.isdir(full_path) or os.path.islink(full_path):
            continue
        paths.append(full_path)
        names.append(dir_name)
    if len(paths) < 2:
        return []

    parent = list(range(len(paths)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    # Exact X/(copyN) families.  Unsuffixed X and all numbered copies of X
    # receive the same family key.  Multiple numbered copies therefore compare
    # with one another even if X is absent.
    exact_families: Dict[str, List[int]] = {}
    exact_family_has_copy: Set[str] = set()
    for index, name in enumerate(names):
        base, copy_number = _copy_suffix_info(name)
        family_name = base if copy_number is not None else name
        family_key = os.path.normcase(str(family_name).strip())
        exact_families.setdefault(family_key, []).append(index)
        if copy_number is not None:
            exact_family_has_copy.add(family_key)
    for family_key, members in exact_families.items():
        if family_key not in exact_family_has_copy or len(members) < 2:
            continue
        first = members[0]
        for member in members[1:]:
            union(first, member)

    # Same artist/date broadens candidate discovery across non-identical names.
    identity_groups: Dict[Tuple[str, str], List[int]] = {}
    for index, name in enumerate(names):
        identity = _show_identity(name)
        if identity[0]:
            identity_groups.setdefault(identity, []).append(index)
    for members in identity_groups.values():
        if len(members) < 2:
            continue
        first = members[0]
        for member in members[1:]:
            union(first, member)

    components: Dict[int, List[str]] = {}
    for index, path_name in enumerate(paths):
        components.setdefault(find(index), []).append(path_name)
    result = [
        sorted(component, key=_alphabetical_name_key)
        for component in components.values()
        if len(component) >= 2
    ]
    result.sort(key=lambda component: _alphabetical_name_key(component[0]))
    return result


def _matching_unsuffixed_duplicate_groups(
    search_root: str,
    *,
    emit=console_emit,
    exclude_paths: Iterable[str] = (),
    mismatch_recorder=None,
) -> Tuple[Dict[str, List[CopyCandidate]], Dict[str, str]]:
    """Compatibility wrapper for callers of the former single-master helper.

    Build 375 no longer protects one alphabetically first master for an entire
    artist/date set.  It forms content-equivalence clusters across unsuffixed and
    copy-suffixed candidates.  This wrapper exposes the resulting groups while
    returning a canonical-map shape compatible with older internal callers.
    """
    groups = _matching_duplicate_groups(
        search_root,
        emit=emit,
        exclude_paths=exclude_paths,
        mismatch_recorder=mismatch_recorder,
    )
    grouped = {keeper: list(candidates) for keeper, candidates in groups}
    canonical: Dict[str, str] = {}
    for keeper, candidates in groups:
        for candidate in candidates:
            canonical[os.path.normcase(os.path.normpath(candidate.path))] = keeper
    return grouped, canonical


def _copy_candidates(search_root: str, *, exclude_paths: Iterable[str] = ()) -> List[CopyCandidate]:
    """Return every recursively discovered copy-suffixed folder in stable order."""
    candidates: List[CopyCandidate] = []
    for current_dir, dir_names, _file_names in os.walk(search_root, topdown=True, followlinks=False):
        _prune_excluded_dir_names(current_dir, dir_names, exclude_paths)
        for dir_name in list(dir_names):
            _base, number = _copy_suffix_info(dir_name)
            if number is None:
                continue
            path_name = os.path.normpath(os.path.join(current_dir, dir_name))
            if os.path.isdir(path_name) and not os.path.islink(path_name):
                candidates.append(CopyCandidate(number=number, path=path_name))
    candidates.sort(key=lambda item: (item.path.count(os.sep), os.path.normcase(os.path.dirname(item.path)), item.number, os.path.normcase(item.path)))
    return candidates


def _matching_duplicate_groups(
    search_root: str,
    *,
    emit=console_emit,
    exclude_paths: Iterable[str] = (),
    mismatch_recorder=None,
) -> List[Tuple[str, List[CopyCandidate]]]:
    """Return duplicate equivalence clusters and the one folder kept per cluster.

    Candidate discovery happens among siblings.  Same artist/date folders are
    candidates regardless of their remaining name text, and exact X/(copyN)
    families are candidates even when artist/date cannot be parsed.  Every
    candidate tree is scanned once and folders with identical manifests form a
    content-equivalence cluster.  This means copies are compared with one another
    as well as with unsuffixed folders.

    Each cluster with two or more identical trees keeps exactly one folder.  An
    unsuffixed folder is preferred when available; otherwise the lowest-numbered
    copy is preferred.  Remaining ties are alphabetical.  All other identical
    cluster members are relocation candidates.  Different content clusters stay
    in place as independent masters/variants.
    """
    result: List[Tuple[str, List[CopyCandidate]]] = []

    for current_dir, dir_names, _file_names in os.walk(search_root, topdown=True, followlinks=False):
        _prune_excluded_dir_names(current_dir, dir_names, exclude_paths)
        components = _candidate_components_for_parent(current_dir, list(dir_names))
        for component in components:
            manifests: Dict[str, TreeManifest] = {}
            scan_failed: Set[str] = set()
            for path_name in component:
                try:
                    manifests[path_name] = _scan_tree(path_name)
                except DeleteDupesError as exc:
                    emit(f"Skipped unverifiable duplicate folder: {path_name} ({exc})", error=True)
                    scan_failed.add(path_name)

            # Keep mismatch logging simple but comprehensive: every pair in the
            # discovery component that can be compared and differs receives one
            # concise reason.  A failed scan is logged once against the first
            # other component member when possible.
            ordered_component = sorted(component, key=_alphabetical_name_key)
            for left_index, left_path in enumerate(ordered_component):
                for right_path in ordered_component[left_index + 1 :]:
                    if left_path in scan_failed or right_path in scan_failed:
                        if left_path in scan_failed or right_path in scan_failed:
                            _record_tree_mismatch(mismatch_recorder, left_path, right_path, "unable to compare")
                        continue
                    left_manifest = manifests[left_path]
                    right_manifest = manifests[right_path]
                    if left_manifest == right_manifest:
                        continue
                    _record_tree_mismatch(
                        mismatch_recorder,
                        left_path,
                        right_path,
                        _tree_manifest_mismatch_reason(left_manifest, right_manifest),
                    )

            manifest_clusters: Dict[TreeManifest, List[str]] = {}
            for path_name, manifest in manifests.items():
                manifest_clusters.setdefault(manifest, []).append(path_name)

            for cluster_paths in manifest_clusters.values():
                if len(cluster_paths) < 2:
                    continue
                ordered_cluster = sorted(cluster_paths, key=_keeper_preference_key)
                keeper = ordered_cluster[0]
                movers = ordered_cluster[1:]
                alphabetical_order = {
                    path_name: rank
                    for rank, path_name in enumerate(
                        sorted(movers, key=_alphabetical_name_key), start=1
                    )
                }
                candidates = [
                    _copy_candidate_for_cluster_member(path_name, alphabetical_order[path_name])
                    for path_name in movers
                ]
                candidates.sort(key=_candidate_sort_key)
                result.append((keeper, candidates))

    # Shallow groups retain the historical processing order; keeper name makes
    # order deterministic within a directory depth.
    result.sort(key=lambda item: (item[0].count(os.sep), _alphabetical_name_key(item[0])))
    return result

def _unique_duplicates_destination(duplicates_root: str, source_name: str) -> str:
    """Return a collision-safe destination without overwriting earlier moved folders."""
    first = os.path.join(duplicates_root, source_name)
    if not os.path.lexists(first):
        return first
    index = 2
    while True:
        candidate = os.path.join(duplicates_root, f"{source_name} (moved {index})")
        if not os.path.lexists(candidate):
            return candidate
        index += 1


def _move_duplicate_folder_to_duplicates(
    copy_path: str,
    duplicates_root: str,
    *,
    move_func=os.rename,
) -> Tuple[str, str]:
    """Move one qualifying duplicate directory as a whole into /duplicates."""
    source = os.path.abspath(os.path.normpath(copy_path))
    destination_root = os.path.abspath(os.path.normpath(duplicates_root))
    if not os.path.isdir(source) or os.path.islink(source):
        raise DeleteDupesError(f"Duplicate folder is no longer a valid directory: {source}")
    if _is_same_or_descendant(source, destination_root):
        raise DeleteDupesError(f"Duplicate folder is already inside the duplicates holding folder: {source}")
    try:
        if os.stat(source).st_dev != os.stat(destination_root).st_dev:
            raise DeleteDupesError(
                f"Duplicate holding folder is not on the same partition as the source: {source} -> {destination_root}"
            )
    except OSError as exc:
        raise DeleteDupesError(f"Unable to verify duplicate move partition: {source}: {exc}") from exc

    destination = _unique_duplicates_destination(destination_root, os.path.basename(source))
    try:
        move_func(source, destination)
    except KeyboardInterrupt:
        raise
    except Exception as exc:
        raise DeleteDupesError(f"Unable to move duplicate folder: {source} -> {destination}: {exc}") from exc
    if os.path.exists(source) or not os.path.isdir(destination):
        raise DeleteDupesError(f"Duplicate folder move did not complete: {source} -> {destination}")
    return source, destination


def _bundled_ffmpeg_executable() -> str:
    """Return the imageio-ffmpeg executable bundled with the application."""
    try:
        import imageio_ffmpeg  # type: ignore

        executable = str(imageio_ffmpeg.get_ffmpeg_exe() or "").strip()
    except Exception as exc:
        raise DeleteDupesError(f"Bundled FLAC validator is unavailable: {exc}") from exc
    if not executable or not os.path.isfile(executable):
        raise DeleteDupesError("Bundled FLAC validator is unavailable; imageio-ffmpeg did not provide ffmpeg.")
    return executable


def _subprocess_no_window_kwargs() -> dict:
    """Avoid opening an extra console window for the decoder on Windows."""
    if os.name != "nt":
        return {}
    creation_flag = int(getattr(subprocess, "CREATE_NO_WINDOW", 0) or 0)
    return {"creationflags": creation_flag} if creation_flag else {}


def flac_file_is_healthy(
    path_name: str,
    *,
    ffmpeg_executable: Optional[str] = None,
    run_func=subprocess.run,
    timeout_seconds: float = FLAC_VALIDATION_TIMEOUT_SECONDS,
) -> Optional[bool]:
    """Return True/False for healthy/corrupt, or None when validation times out."""
    normalized = os.path.normpath(str(path_name or ""))
    if os.path.splitext(normalized)[1].lower() != ".flac" or not os.path.isfile(normalized):
        return False
    executable = ffmpeg_executable or _bundled_ffmpeg_executable()
    command = [
        executable,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-xerror",
        "-i",
        normalized,
        "-map",
        "0:a:0",
        "-f",
        "null",
        "-",
    ]
    try:
        completed = run_func(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=max(1.0, float(timeout_seconds)),
            **_subprocess_no_window_kwargs(),
        )
    except KeyboardInterrupt:
        raise
    except subprocess.TimeoutExpired:
        return None
    except (OSError, MemoryError):
        return None
    except Exception:
        # Unexpected validator/infrastructure failures are unverifiable, not
        # proof that the FLAC itself is corrupt.
        return None
    return int(getattr(completed, "returncode", 1) or 0) == 0


def _relative_flac_paths(root: str) -> List[str]:
    """Return every regular non-symlink FLAC path relative to root."""
    relative_paths: List[str] = []
    for current_dir, dir_names, file_names in os.walk(root, topdown=True, followlinks=False):
        # Do not descend through directory symlinks even if os.walk reports them.
        dir_names[:] = [
            name for name in dir_names if not os.path.islink(os.path.join(current_dir, name))
        ]
        for file_name in file_names:
            if os.path.splitext(file_name)[1].lower() != ".flac":
                continue
            full_path = os.path.join(current_dir, file_name)
            if os.path.islink(full_path) or not os.path.isfile(full_path):
                continue
            relative_paths.append(os.path.relpath(full_path, root))
    return sorted(relative_paths, key=lambda value: os.path.normcase(os.path.normpath(value)))


def _sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _replace_file_from_copy(source_path: str, destination_path: str) -> None:
    """Stage and byte-verify a replacement, then atomically install it.

    The current keeper bytes remain at destination until the fully staged copy
    has been verified.  A temporary backup is retained through the atomic
    replacement so an installation error never destroys the prior bytes.
    """
    destination_dir = os.path.dirname(destination_path)
    temp_path = ""
    backup_path = ""
    try:
        fd, temp_path = tempfile.mkstemp(prefix=".tlo-deleteDupes-repair-", suffix=".flac", dir=destination_dir)
        os.close(fd)
        shutil.copy2(source_path, temp_path)
        if os.path.getsize(source_path) != os.path.getsize(temp_path) or _sha256_file(source_path) != _sha256_file(temp_path):
            raise DeleteDupesError(f"Staged FLAC repair copy failed byte verification: {source_path}")

        fd, backup_path = tempfile.mkstemp(prefix=".tlo-deleteDupes-backup-", suffix=".flac", dir=destination_dir)
        os.close(fd)
        shutil.copy2(destination_path, backup_path)
        os.replace(temp_path, destination_path)
        temp_path = ""
        try:
            os.remove(backup_path)
            backup_path = ""
        except OSError:
            # The repair succeeded; retaining a backup is safer than treating a
            # cleanup failure as a failed repair.
            pass
    finally:
        for cleanup_path in (temp_path,):
            if cleanup_path:
                try:
                    os.remove(cleanup_path)
                except OSError:
                    pass
        # If destination installation failed, destination was never replaced.
        # The backup is therefore redundant and can be removed.  If installation
        # succeeded but backup cleanup failed, intentionally leave it in place.
        if backup_path and os.path.exists(destination_path):
            try:
                if _sha256_file(destination_path) == _sha256_file(source_path):
                    pass
                else:
                    os.replace(backup_path, destination_path)
                    backup_path = ""
            except Exception:
                pass
            if backup_path and os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except OSError:
                    pass


def repair_corrupt_flacs_from_copies(
    original_path: str,
    copies: Iterable[CopyCandidate],
    *,
    ffmpeg_executable: Optional[str] = None,
    health_check=flac_file_is_healthy,
    replace_func=_replace_file_from_copy,
    emit=console_emit,
) -> Tuple[int, int, bool]:
    """Repair corrupt original FLACs from healthy copies in numeric copy order.

    Returns (repaired_count, unrepaired_count, keeper_unverifiable). A timeout
    makes the keeper unverifiable so its duplicate cluster is not relocated.
    """
    ordered_copies = sorted(list(copies), key=_candidate_sort_key)
    repaired_count = 0
    unrepaired_count = 0

    for relative_path in _relative_flac_paths(original_path):
        original_flac = os.path.normpath(os.path.join(original_path, relative_path))
        original_health = health_check(original_flac, ffmpeg_executable=ffmpeg_executable)
        if original_health is True:
            continue
        if original_health is None:
            emit(f"FLAC validation timed out; keeper cluster is unverifiable: {original_flac}", error=True)
            return repaired_count, unrepaired_count, True

        emit(f"Corrupt FLAC detected in kept folder: {original_flac}", error=True)
        repaired = False
        for candidate in ordered_copies:
            candidate_flac = os.path.normpath(os.path.join(candidate.path, relative_path))
            if not os.path.isfile(candidate_flac) or os.path.islink(candidate_flac):
                continue
            candidate_health = health_check(candidate_flac, ffmpeg_executable=ffmpeg_executable)
            if candidate_health is not True:
                if candidate_health is None:
                    emit(f"FLAC validation timed out for repair candidate; skipping: {candidate_flac}", error=True)
                continue
            try:
                replace_func(candidate_flac, original_flac)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                emit(
                    f"Unable to replace corrupt FLAC from copy {candidate.number}: "
                    f"{original_flac} ({exc})",
                    error=True,
                )
                continue

            # Verify the bytes as installed, not merely the source copy.
            replacement_health = health_check(original_flac, ffmpeg_executable=ffmpeg_executable)
            if replacement_health is True:
                emit(f"Replaced corrupt FLAC from copy {candidate.number}: {original_flac}")
                repaired_count += 1
                repaired = True
                break
            if replacement_health is None:
                emit(f"Replacement validation timed out; keeper cluster is unverifiable: {original_flac}", error=True)
                return repaired_count, unrepaired_count, True

            emit(
                f"Replacement from copy {candidate.number} did not validate: {original_flac}",
                error=True,
            )

        if not repaired:
            unrepaired_count += 1
            emit(f"Corrupt FLAC could not be replaced; continuing: {original_flac}", error=True)

    return repaired_count, unrepaired_count, False


def validate_input_path(path_text: str) -> str:
    """Validate and normalize the required fully qualified directory input."""
    cleaned = strip_optional_quotes(path_text).strip()
    if not cleaned:
        raise DeleteDupesError("Input Path must be supplied.")
    normalized = normalize_platform_input_path(cleaned)
    if not os.path.isabs(normalized):
        raise DeleteDupesError(f"Input Path must be a fully qualified path: {cleaned}")
    if not os.path.exists(normalized):
        raise DeleteDupesError(f"Input Path does not exist: {normalized}")
    if not os.path.isdir(normalized):
        raise DeleteDupesError(f"Input Path is not a directory: {normalized}")
    if not os.access(normalized, os.R_OK):
        raise DeleteDupesError(f"Input Path is not readable: {normalized}")
    return os.path.normpath(normalized)


def delete_duplicate_copy_directories(
    search_root: str,
    tlo_home: str,
    *,
    emit=console_emit,
    ffmpeg_executable: Optional[str] = None,
    health_check=flac_file_is_healthy,
    replace_func=_replace_file_from_copy,
    duplicates_root: Optional[str] = None,
    move_func=os.rename,
    trash_func=None,
) -> int:
    """Repair kept-folder FLACs, move qualifying duplicates, and log source paths.

    trash_func is retained only as a compatibility/test hook for older callers.
    Normal execution never uses Trash/Recycle Bin; it moves whole directories into
    the partition-root duplicates holding folder.
    """
    search_root = validate_input_path(search_root)
    log_path = os.path.join(tlo_home, "deletedDirs.txt")
    mismatch_log_path = os.path.join(tlo_home, "deleteDupesMismatches.txt")
    moved_count = 0
    validator = ffmpeg_executable or _bundled_ffmpeg_executable()

    # Older tests/embedders may still provide trash_func. Preserve that injection
    # point without changing normal CLI behavior; production execution always
    # creates and uses <partition-root>/duplicates.
    legacy_trash_hook = trash_func
    if legacy_trash_hook is not None:
        holding_root = os.path.abspath(
            os.path.normpath(duplicates_root or os.path.join(search_root, ".tlo-legacy-duplicates"))
        )
    else:
        holding_root = _prepare_duplicates_root(search_root, duplicates_root)

    # Keep both logs open during the operation so a Ctrl-C unwind closes them through
    # their context managers before main() returns 130. deletedDirs.txt remains only
    # the pre-move full paths of folders actually relocated. Non-matching comparisons
    # are recorded separately as CSV: folder name, folder name, simple reason.
    with open(log_path, "a", encoding="utf-8", buffering=1) as log_file, open(
        mismatch_log_path, "a", encoding="utf-8", newline="", buffering=1
    ) as mismatch_file:
        mismatch_writer = csv.writer(mismatch_file, lineterminator="\n")
        seen_mismatches: Set[Tuple[str, str, str]] = set()

        def record_mismatch(left_path: str, right_path: str, reason: str) -> None:
            left_name = os.path.basename(os.path.normpath(left_path))
            right_name = os.path.basename(os.path.normpath(right_path))
            key = (left_name.casefold(), right_name.casefold(), str(reason))
            if key in seen_mismatches:
                return
            seen_mismatches.add(key)
            mismatch_writer.writerow([left_name, right_name, str(reason)])
            mismatch_file.flush()

        groups = _matching_duplicate_groups(
            search_root,
            emit=emit,
            exclude_paths=(holding_root,),
            mismatch_recorder=record_mismatch,
        )
        for original_path, qualifying in groups:
            if not os.path.isdir(original_path) or not qualifying:
                continue

            # Validate/repair the folder that will be kept before any qualifying
            # copies are moved. An unrepaired corrupt FLAC does not retain copies.
            _repaired, _unrepaired, keeper_unverifiable = repair_corrupt_flacs_from_copies(
                original_path,
                qualifying,
                ffmpeg_executable=validator,
                health_check=health_check,
                replace_func=replace_func,
                emit=emit,
            )
            if keeper_unverifiable:
                emit(
                    f"Skipping duplicate cluster because kept folder has an unverifiable FLAC: {original_path}",
                    error=True,
                )
                continue
            if _unrepaired > 0:
                emit(
                    f"Skipping duplicate cluster because kept folder still has unrepaired corrupt FLAC files: {original_path}",
                    error=True,
                )
                continue

            for candidate in qualifying:
                copy_path = candidate.path
                if not os.path.isdir(copy_path):
                    continue
                source_path = os.path.abspath(os.path.normpath(copy_path))
                if legacy_trash_hook is not None:
                    legacy_trash_hook(source_path)
                    destination_path = os.path.join(holding_root or "duplicates", os.path.basename(source_path))
                else:
                    source_path, destination_path = _move_duplicate_folder_to_duplicates(
                        copy_path, holding_root, move_func=move_func
                    )
                log_file.write(source_path + "\n")
                log_file.flush()
                moved_count += 1
                emit(f"Moved duplicate folder to {destination_path}")

    return moved_count


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="tlo-deleteDupes.py",
        description=(
            "Recursively find duplicate sibling directories. Candidate folders are discovered from exact "
            "X/(copyN) families and from same-artist/date sibling names. Copies are compared with one another "
            "as well as with unsuffixed folders, and identical recursive trees form content-equivalence "
            "clusters. Each cluster keeps one preferred folder (an unsuffixed name when available; otherwise "
            "the lowest-numbered copy) and relocates the other identical members. The recursive directory "
            "structure, file names, and file sizes must match before relocation. Before moving matching "
            "duplicates, fully decode-check FLAC files in the kept folder and repair corrupt files from the "
            "other qualifying cluster members. Each duplicate directory is moved as a whole into a folder "
            "named duplicates at the root of the partition containing the Input Path."
        ),
    )
    parser.add_argument(
        "--TLOHome",
        dest="TLOHome",
        default="",
        metavar="DIR",
        help="TLOHome directory. Defaults from the TLOHome environment variable when present.",
    )
    parser.add_argument("--myTLO", dest="myTLO", default="", metavar="DIR", help=argparse.SUPPRESS)
    parser.add_argument("path", metavar="PATH", help="Fully qualified directory path to search recursively.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        args = _parse_args(argv)
        tlo_home = resolve_tlo_home(args.TLOHome, args.myTLO, error_type=DeleteDupesError)
        search_root = validate_input_path(args.path)
        moved_count = delete_duplicate_copy_directories(search_root, tlo_home)
        console_emit(f"Complete: duplicate_folders_moved={moved_count}")
        return 0
    except KeyboardInterrupt:
        console_emit("Duplicate-folder cleanup cancelled.", error=True)
        return 130
    except Exception as exc:
        console_emit(f"ERROR: {exc}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
