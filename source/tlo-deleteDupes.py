"""Repair corrupt FLACs from duplicate copies, then move duplicates to a partition holding folder."""

__version__ = "v367"
# TLO-GI package version: v367
__version_summary__ = 'Moves qualifying duplicate folders into a partition-root duplicates holding folder instead of Trash/Recycle Bin.'
# TLO-GI version summary: Moves qualifying duplicate folders into a partition-root duplicates holding folder instead of Trash/Recycle Bin.

import argparse
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


def directory_trees_match_for_duplicate_deletion(original: str, copy_path: str) -> bool:
    """Return True when trees have identical names/structure and file sizes.

    This deliberately implements the cleanup rule requested for tlo-deleteDupes:
    equal relative folder structure, equal relative file names, and equal file
    sizes. It does not hash file bytes.
    """
    original = os.path.normpath(str(original or ""))
    copy_path = os.path.normpath(str(copy_path or ""))
    if not os.path.isdir(original) or not os.path.isdir(copy_path):
        return False
    try:
        if os.path.samefile(original, copy_path):
            return False
    except OSError:
        pass
    return _scan_tree(original) == _scan_tree(copy_path)


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


def _matching_unsuffixed_duplicate_groups(
    search_root: str,
    *,
    emit=console_emit,
    exclude_paths: Iterable[str] = (),
) -> Tuple[Dict[str, List[CopyCandidate]], Dict[str, str]]:
    """Find matching same-artist/date sibling folders without copy suffixes.

    For each same-parent artist/date set, folders are analyzed alphabetically. The
    first folder is the master. Every later folder is treated as a copy candidate
    and qualifies only when the existing recursive name/structure/size rule says
    that its tree matches the master. The returned canonical map points each
    qualifying later folder at the master that must survive.
    """
    grouped: Dict[str, List[CopyCandidate]] = {}
    canonical_master_by_path: Dict[str, str] = {}

    for current_dir, dir_names, _file_names in os.walk(search_root, topdown=True, followlinks=False):
        _prune_excluded_dir_names(current_dir, dir_names, exclude_paths)
        identity_groups: Dict[Tuple[str, str], List[str]] = {}
        for dir_name in list(dir_names):
            full_path = os.path.normpath(os.path.join(current_dir, dir_name))
            if not os.path.isdir(full_path) or os.path.islink(full_path):
                continue
            _base, copy_number = _copy_suffix_info(dir_name)
            if copy_number is not None:
                continue
            identity = _show_identity(dir_name)
            if not identity[0]:
                continue
            identity_groups.setdefault(identity, []).append(full_path)

        for siblings in identity_groups.values():
            if len(siblings) < 2:
                continue
            ordered = sorted(siblings, key=_alphabetical_name_key)
            master = ordered[0]
            for rank, later_path in enumerate(ordered[1:], start=1):
                try:
                    matches = directory_trees_match_for_duplicate_deletion(master, later_path)
                except DeleteDupesError as exc:
                    emit(f"Skipped unverifiable duplicate folder: {later_path} ({exc})", error=True)
                    matches = False
                if not matches:
                    continue
                candidate = CopyCandidate(
                    number=rank,
                    path=later_path,
                    source_kind="alphabetical",
                    alphabetical_rank=rank,
                )
                grouped.setdefault(master, []).append(candidate)
                canonical_master_by_path[os.path.normcase(os.path.normpath(later_path))] = master

    return grouped, canonical_master_by_path


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
) -> List[Tuple[str, List[CopyCandidate]]]:
    """Return every qualifying duplicate group with one surviving master folder.

    Unsuffixed same-artist/date siblings are analyzed alphabetically: the first
    folder is the master and later folders can qualify as copies under the same
    recursive structure/name/size rule. Copy-suffixed folders retain the existing
    exact-base/same-artist-date discovery rules. If their apparent original is an
    unsuffixed folder already proven to be a duplicate, the qualifying copy is
    attached to that folder's canonical alphabetical master so cleanup never
    depends on a master that will itself be moved away.
    """
    grouped, canonical_master_by_path = _matching_unsuffixed_duplicate_groups(
        search_root, emit=emit, exclude_paths=exclude_paths
    )

    for candidate in _copy_candidates(search_root, exclude_paths=exclude_paths):
        if not os.path.isdir(candidate.path):
            continue
        try:
            originals = _potential_originals_for_copy(candidate.path)
        except DeleteDupesError as exc:
            emit(f"Skipped unverifiable copy folder: {candidate.path} ({exc})", error=True)
            continue
        for original_path in originals:
            canonical_original = canonical_master_by_path.get(
                os.path.normcase(os.path.normpath(original_path)),
                original_path,
            )
            try:
                matches = directory_trees_match_for_duplicate_deletion(canonical_original, candidate.path)
            except DeleteDupesError as exc:
                emit(f"Skipped unverifiable copy folder: {candidate.path} ({exc})", error=True)
                matches = False
            if not matches:
                continue
            grouped.setdefault(canonical_original, []).append(candidate)
            break

    result = []
    for original_path, candidates in grouped.items():
        # De-duplicate candidate paths defensively in case multiple discovery
        # routes reach the same folder. Numbered copies keep numeric order;
        # unsuffixed copies keep their alphabetical rank.
        unique: Dict[str, CopyCandidate] = {}
        for candidate in candidates:
            unique.setdefault(os.path.normcase(os.path.normpath(candidate.path)), candidate)
        ordered = sorted(unique.values(), key=_candidate_sort_key)
        result.append((original_path, ordered))
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
) -> bool:
    """Return True only when the entire FLAC audio stream decodes without error."""
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
            **_subprocess_no_window_kwargs(),
        )
    except KeyboardInterrupt:
        raise
    except Exception:
        return False
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


def _replace_file_from_copy(source_path: str, destination_path: str) -> None:
    """Copy a healthy replacement beside destination, then atomically replace it."""
    destination_dir = os.path.dirname(destination_path)
    temp_path = ""
    try:
        fd, temp_path = tempfile.mkstemp(prefix=".tlo-deleteDupes-repair-", suffix=".flac", dir=destination_dir)
        os.close(fd)
        shutil.copy2(source_path, temp_path)
        os.replace(temp_path, destination_path)
        temp_path = ""
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
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
) -> Tuple[int, int]:
    """Repair corrupt original FLACs from healthy copies in numeric copy order.

    Returns (repaired_count, unrepaired_count). Failure to repair a corrupt file
    is non-fatal; duplicate-folder cleanup continues as requested.
    """
    ordered_copies = sorted(list(copies), key=_candidate_sort_key)
    repaired_count = 0
    unrepaired_count = 0

    for relative_path in _relative_flac_paths(original_path):
        original_flac = os.path.normpath(os.path.join(original_path, relative_path))
        if health_check(original_flac, ffmpeg_executable=ffmpeg_executable):
            continue

        emit(f"Corrupt FLAC detected in kept folder: {original_flac}", error=True)
        repaired = False
        for candidate in ordered_copies:
            candidate_flac = os.path.normpath(os.path.join(candidate.path, relative_path))
            if not os.path.isfile(candidate_flac) or os.path.islink(candidate_flac):
                continue
            if not health_check(candidate_flac, ffmpeg_executable=ffmpeg_executable):
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
            if health_check(original_flac, ffmpeg_executable=ffmpeg_executable):
                emit(f"Replaced corrupt FLAC from copy {candidate.number}: {original_flac}")
                repaired_count += 1
                repaired = True
                break

            emit(
                f"Replacement from copy {candidate.number} did not validate: {original_flac}",
                error=True,
            )

        if not repaired:
            unrepaired_count += 1
            emit(f"Corrupt FLAC could not be replaced; continuing: {original_flac}", error=True)

    return repaired_count, unrepaired_count


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

    # Keep the log open during the operation so a Ctrl-C unwind closes it through
    # the context manager before main() returns 130. The historic filename remains
    # for compatibility; entries are the pre-move full source paths.
    with open(log_path, "a", encoding="utf-8", buffering=1) as log_file:
        groups = _matching_duplicate_groups(search_root, emit=emit, exclude_paths=(holding_root,))
        for original_path, qualifying in groups:
            if not os.path.isdir(original_path) or not qualifying:
                continue

            # Validate/repair the folder that will be kept before any qualifying
            # copies are moved. An unrepaired corrupt FLAC does not retain copies.
            repair_corrupt_flacs_from_copies(
                original_path,
                qualifying,
                ffmpeg_executable=validator,
                health_check=health_check,
                replace_func=replace_func,
                emit=emit,
            )

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
            "Recursively find duplicate sibling directories. Copy-suffixed folders ending in (copyN) or (copy N) "
            "retain the exact-base/same-artist-date rules. When multiple unsuffixed sibling "
            "folders have the same artist and date, they are analyzed alphabetically: the first folder "
            "is kept as the master and later folders are treated as copy candidates. The recursive "
            "directory structure, file names, and file sizes must still match before relocation. Before "
            "moving matching duplicates, fully decode-check FLAC files in the kept folder and repair "
            "corrupt files from qualifying copies. Each qualifying duplicate directory is moved as a whole "
            "into a folder named duplicates at the root of the partition containing the Input Path."
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
