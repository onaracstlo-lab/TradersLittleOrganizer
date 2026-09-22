"""Manual folder-name corrections with coordinated bootlist/setlist updates."""

__version__ = "v489"

import copy
import ntpath
import os
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from tlo_folder_rename import rename_folder_exact_case, same_existing_entry
from tlo_inventory_update import (
    _build_single_folder_group,
    _record_namespace_from_dict,
    create_or_replace_generated_setlist,
    identify_folder_dict,
    infer_setlist_paths_for_show,
    parse_volume_path_value,
    read_bootlist,
    write_bootlist,
)
from tlo_path_inputs import normalize_platform_input_path, strip_optional_quotes
from tlo_bootlist_volume_policy import (
    format_volume_path,
    normalize_path_for_compare,
    os_volume_label_for_path,
    volume_key,
)
from tlo_phase23_v2 import _find_date_matches


class ManualUpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualUpdateItem:
    original_path: str
    new_name: str
    line_number: int = 0


def _is_comment_line(text: str) -> bool:
    cleaned = str(text or "").lstrip("\ufeff").strip()
    lowered = cleaned.lower()
    return (not cleaned) or cleaned.startswith("#") or lowered == "rem" or lowered.startswith("rem ")


def _validate_new_leaf(value: str) -> str:
    leaf = strip_optional_quotes(str(value or "").strip())
    if not leaf:
        raise ManualUpdateError("New Name is required.")
    if leaf in {".", ".."} or "/" in leaf or "\\" in leaf:
        raise ManualUpdateError(f"New Name must contain only a folder name, not a path: {value}")
    if os.name == "nt" and any(ch in leaf for ch in '<>:"|?*'):
        raise ManualUpdateError(f"New Name contains characters Windows does not allow in a folder name: {leaf}")
    return leaf


def parse_manual_updates_file(path_name: str) -> List[ManualUpdateItem]:
    path = normalize_platform_input_path(strip_optional_quotes(path_name))
    if not os.path.isfile(path):
        raise ManualUpdateError(f"Manual Updates control file not found: {path}")
    items: List[ManualUpdateItem] = []
    with open(path, "r", encoding="utf-8-sig", errors="strict") as infile:
        for line_number, raw in enumerate(infile, start=1):
            line = raw.rstrip("\r\n")
            if _is_comment_line(line):
                continue
            if line.count("---->") != 1:
                raise ManualUpdateError(
                    f"Line {line_number} must be exactly: Path ----> Folder Name"
                )
            left, right = line.split("---->", 1)
            original = normalize_platform_input_path(strip_optional_quotes(left.strip()))
            new_leaf = _validate_new_leaf(right.strip())
            if not original:
                raise ManualUpdateError(f"Line {line_number} is missing the Original path.")
            if not os.path.isabs(original):
                raise ManualUpdateError(f"Line {line_number} Original path must be fully qualified: {left.strip()}")
            items.append(ManualUpdateItem(os.path.normpath(original), new_leaf, line_number))
    if not items:
        raise ManualUpdateError(f"Manual Updates control file contains no usable updates: {path}")
    return items


def _portable_path(path_text: str) -> str:
    return str(path_text or "").strip().replace("\\", "/").rstrip("/").casefold()


def _portable_leaf(path_text: str) -> str:
    value = str(path_text or "").strip().rstrip("\\/")
    if not value:
        return ""
    if "\\" in value or (len(value) >= 2 and value[1] == ":"):
        return ntpath.basename(value).casefold()
    return os.path.basename(value).casefold()


def unidentified_shows_path(tlo_home: str) -> str:
    return os.path.join(tlo_home, "unidentifiedShows.txt")


def _read_unidentified_show_paths(tlo_home: str) -> List[str]:
    path_name = unidentified_shows_path(tlo_home)
    if not os.path.isfile(path_name):
        return []
    out: List[str] = []
    with open(path_name, "r", encoding="utf-8", errors="ignore") as infile:
        for raw in infile:
            clean = raw.strip()
            if clean:
                out.append(clean)
    return out


def find_unidentified_show_path(tlo_home: str, original_path: str) -> str:
    """Return the matching persistent unidentified-show path, if any.

    Prefer an exact portable-path match.  Otherwise match the Original leaf
    folder name only when it identifies exactly one persistent unresolved path.
    """
    original = os.path.normpath(normalize_platform_input_path(strip_optional_quotes(original_path)))
    target = _portable_path(original)
    target_leaf = _portable_leaf(original)
    entries = _read_unidentified_show_paths(tlo_home)
    exact = [item for item in entries if _portable_path(item) == target]
    if exact:
        return exact[0]
    leaf_matches = [item for item in entries if target_leaf and _portable_leaf(item) == target_leaf]
    if len(leaf_matches) == 1:
        return leaf_matches[0]
    if len(leaf_matches) > 1:
        raise ManualUpdateError(
            f"More than one unidentified show has the folder name {os.path.basename(original)}; "
            "the Original could not be matched uniquely."
        )
    return ""


def manual_update_source_kind(tlo_home: str, original_path: str) -> str:
    """Return inventory, unidentified, or missing for one Manual Updates Original."""
    try:
        _matching_bootlist_rows(tlo_home, original_path)
        return "inventory"
    except ManualUpdateError as exc:
        if not str(exc).startswith("Original folder is not present in bootlist.csv:"):
            raise
    return "unidentified" if find_unidentified_show_path(tlo_home, original_path) else "missing"


def resolve_unidentified_destination(path_text: str, new_name: str) -> Tuple[str, str]:
    """Return (destination parent, final folder) without moving anything.

    The prompt accepts either the destination parent or the already-renamed
    destination folder itself.  When the supplied path already ends in New
    Name, strip that leaf to obtain the parent; otherwise use the supplied path
    as the parent.
    """
    new_leaf = _validate_new_leaf(new_name)
    supplied = os.path.normpath(normalize_platform_input_path(strip_optional_quotes(path_text)))
    if not supplied or not os.path.isabs(supplied):
        raise ManualUpdateError(f"Path must be a fully qualified folder path: {path_text}")
    supplied_leaf = os.path.basename(supplied.rstrip("\\/"))
    if supplied_leaf.casefold() == new_leaf.casefold():
        parent = os.path.dirname(supplied)
    else:
        parent = supplied
    final_path = os.path.normpath(os.path.join(parent, new_leaf))
    if not os.path.isdir(final_path):
        raise ManualUpdateError(
            f"The manually moved/renamed folder was not found at the expected destination: {final_path}"
        )
    return parent, final_path


def _atomic_write_bytes(path_name: str, payload: bytes) -> None:
    os.makedirs(os.path.dirname(path_name) or ".", exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{os.path.basename(path_name)}-", suffix=".tmp", dir=os.path.dirname(path_name) or ".")
    try:
        with os.fdopen(fd, "wb") as outfile:
            outfile.write(payload)
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(temp_name, path_name)
    except Exception:
        try:
            os.remove(temp_name)
        except OSError:
            pass
        raise


def _remove_unidentified_show_path(tlo_home: str, matched_path: str) -> None:
    path_name = unidentified_shows_path(tlo_home)
    if not os.path.isfile(path_name):
        return
    target = _portable_path(matched_path)
    kept: List[str] = []
    with open(path_name, "r", encoding="utf-8", errors="ignore") as infile:
        for raw in infile:
            clean = raw.strip()
            if clean and _portable_path(clean) != target:
                kept.append(clean)
    payload = "".join(item + "\n" for item in kept).encode("utf-8")
    _atomic_write_bytes(path_name, payload)


def _matching_bootlist_rows(tlo_home: str, original_path: str) -> List[Dict[str, str]]:
    """Match a physical Original to canonical bootlist rows without crossing volumes."""
    rows = read_bootlist(tlo_home)
    target_path = normalize_path_for_compare(original_path)
    target_leaf = _portable_leaf(original_path)
    target_volume = volume_key(os_volume_label_for_path(original_path))

    path_matches: List[Tuple[Dict[str, str], str]] = []
    for row in rows:
        row_volume, physical = parse_volume_path_value(row.get("VolumePath", ""))
        if normalize_path_for_compare(physical) == target_path:
            path_matches.append((row, volume_key(row_volume)))

    if path_matches:
        if target_volume:
            same_volume = [row for row, row_volume in path_matches if row_volume == target_volume]
            if same_volume:
                return same_volume
            raise ManualUpdateError(
                f"Original path exists in bootlist.csv only on a different volume: {original_path}"
            )
        if len(path_matches) == 1:
            return [path_matches[0][0]]
        raise ManualUpdateError(
            f"More than one inventory row has the path {original_path}; the volume could not be resolved uniquely."
        )

    # Leaf-only matching is a legacy fallback and is safe only when both sides
    # have a known, matching visible volume label.  Never use it to jump from a
    # supplied physical path to a same-named folder on another volume.
    leaf_matches: List[Dict[str, str]] = []
    if target_volume and target_leaf:
        for row in rows:
            row_volume, physical = parse_volume_path_value(row.get("VolumePath", ""))
            if volume_key(row_volume) == target_volume and _portable_leaf(physical) == target_leaf:
                leaf_matches.append(row)
    if len(leaf_matches) == 1:
        return leaf_matches
    if len(leaf_matches) > 1:
        raise ManualUpdateError(
            f"More than one inventory row on the same volume has the folder name {os.path.basename(original_path)}; "
            "the Original path could not be matched uniquely."
        )
    raise ManualUpdateError(f"Original folder is not present in bootlist.csv: {original_path}")


def _replace_volume_path_leaf(volume_path: str, old_leaf: str, new_leaf: str) -> str:
    volume, physical = parse_volume_path_value(volume_path)
    physical = str(physical or "").strip()
    if not physical:
        new_physical = new_leaf
    elif "\\" in physical or (len(physical) >= 2 and physical[1] == ":"):
        parent = ntpath.dirname(physical)
        new_physical = ntpath.join(parent, new_leaf) if parent else new_leaf
    else:
        parent = os.path.dirname(physical)
        new_physical = os.path.join(parent, new_leaf) if parent else new_leaf
    had_volume_prefix = str(volume_path or "").lstrip().startswith("[")
    return f"[{volume}] {new_physical}" if (volume or had_volume_prefix) else new_physical


def _snapshot_setlists(paths: Sequence[str]) -> List[Tuple[str, bytes]]:
    snapshots: List[Tuple[str, bytes]] = []
    seen = set()
    for path in paths:
        norm = os.path.normpath(path)
        key = os.path.normcase(norm)
        if key in seen or not os.path.isfile(norm):
            continue
        seen.add(key)
        with open(norm, "rb") as infile:
            snapshots.append((norm, infile.read()))
    return snapshots


def _restore_setlists(snapshots: Sequence[Tuple[str, bytes]]) -> None:
    for path, payload in snapshots:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as outfile:
            outfile.write(payload)


def _delete_paths(paths: Sequence[str]) -> None:
    for path in paths:
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


def _manual_update_tag_warnings(stats: Dict[str, object], messages: Sequence[str]) -> List[str]:
    skipped = int(stats.get("skipped", 0) or 0)
    errors = int(stats.get("errors", 0) or 0)
    if not skipped and not errors:
        return []
    warnings = [f"tag update: skipped_folders={skipped}, file_errors={errors}"]
    for raw in messages:
        line = str(raw or "").strip()
        if not line:
            continue
        upper = line.upper()
        if "ERROR" in upper or "SKIP" in upper or "CANCEL" in upper:
            warnings.append(line)
        if len(warnings) >= 6:
            break
    return warnings


def _apply_manual_name_tag_identity(record_dict: Dict[str, str], new_name: str) -> Dict[str, str]:
    """Make a parseable user-entered New Name authoritative for Artist/Album tags."""
    record = dict(record_dict or {})
    text = str(new_name or "").strip()
    date_matches = [
        item for item in _find_date_matches(text)
        if item.get("normalized") and len(item.get("normalized", "")) == 10
    ]
    if date_matches:
        chosen = sorted(date_matches, key=lambda item: (int(item.get("start", 0)), -len(item.get("raw", ""))))[0]
        start = int(chosen.get("start", 0))
        artist = text[:start].strip(" -_,")
        album_piece = text[start:].strip()
        if artist:
            record["artist"] = artist
        if album_piece:
            record["album_name"] = album_piece
        record["date"] = chosen.get("normalized", record.get("date", ""))
        return record
    if " - " in text:
        artist, album_piece = text.split(" - ", 1)
        artist = artist.strip()
        album_piece = album_piece.strip()
        if artist and album_piece:
            record["artist"] = artist
            record["album_name"] = album_piece
    return record


def _update_manual_folder_tags(config, folder_path: str, record_dict: Dict[str, str]) -> Tuple[Dict[str, object], List[str]]:
    """Update one manually corrected folder's audio tags before inventory commit.

    This intentionally uses the inventory-time tagging behavior without invoking
    the standalone tagger corruption pass.  Manual Updates is a metadata/path
    correction workflow; checking Update Tags must not unexpectedly delete or
    move corrupt files or folders.
    """
    from tlo_tag_lib import tag_group_with_record

    tag_config = copy.copy(config)
    # Manual Updates' Update Tags option must never perform SHN conversion or
    # delete SHN/SHNF originals.  Conversion remains an explicit Tag/Inventory
    # workflow.
    setattr(tag_config, "convert_shn", False)
    group = _build_single_folder_group(tag_config, folder_path)
    record = _record_namespace_from_dict(record_dict)
    record.main_dir_path = os.path.normpath(folder_path)
    record.main_dir_name = os.path.basename(record.main_dir_path)
    messages: List[str] = []
    stats = tag_group_with_record(
        tag_config,
        group,
        record,
        emit=messages.append,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        fallback_to_title_tags_on_track_problem=True,
    )
    return stats, _manual_update_tag_warnings(stats, messages)


def apply_folder_manual_update(
    config, original_path: str, new_name: str, *, update_tags: bool = False
) -> Dict[str, object]:
    """Rename one folder in place and replace its bootlist/setlist inventory identity."""
    original = os.path.normpath(normalize_platform_input_path(strip_optional_quotes(original_path)))
    if not os.path.isabs(original):
        raise ManualUpdateError(f"Original must be a fully qualified folder path: {original_path}")
    new_leaf = _validate_new_leaf(new_name)
    parent = os.path.dirname(original)
    target = os.path.normpath(os.path.join(parent, new_leaf))
    old_leaf = os.path.basename(original)

    rows_to_replace = _matching_bootlist_rows(config.TLOHome, original)
    old_rows_all = read_bootlist(config.TLOHome)
    replace_keys = {(row.get("Show", ""), row.get("VolumePath", "")) for row in rows_to_replace}
    old_shows = {str(row.get("Show", "") or "").strip() for row in rows_to_replace}
    surviving_old_shows = {
        str(row.get("Show", "") or "").strip()
        for row in old_rows_all
        if (row.get("Show", ""), row.get("VolumePath", "")) not in replace_keys
    }
    old_setlists: List[str] = []
    setlists_safe_to_delete: List[str] = []
    for show in old_shows:
        family = infer_setlist_paths_for_show(config.TLOHome, show)
        old_setlists.extend(family)
        if show not in surviving_old_shows:
            setlists_safe_to_delete.extend(family)
    snapshots = _snapshot_setlists(old_setlists)

    renamed_by_tlo = False
    if os.path.isdir(original):
        if target != original:
            if os.path.lexists(target) and not same_existing_entry(original, target):
                raise ManualUpdateError(f"New Name already exists beside Original: {target}")
            try:
                rename_folder_exact_case(original, target)
            except Exception as exc:
                raise ManualUpdateError(f"Unable to rename Original folder: {exc}") from exc
            renamed_by_tlo = True
    elif not os.path.isdir(target):
        raise ManualUpdateError(
            f"Original folder does not exist and the expected already-renamed folder was not found: {target}"
        )

    active_path = target
    generated = ""
    tag_stats: Dict[str, object] = {}
    tag_warnings: List[str] = []
    tags_attempted = False
    try:
        record = identify_folder_dict(config, active_path)
        # Manual Updates is explicitly user-directed.  The requested leaf is
        # authoritative for the inventory Show identity; the normal metadata
        # engine still supplies the exported setlist body and supporting fields.
        record["show_name"] = new_leaf
        record["main_dir_path"] = active_path
        if update_tags:
            record = _apply_manual_name_tag_identity(record, new_leaf)
            tags_attempted = True
            tag_stats, tag_warnings = _update_manual_folder_tags(config, active_path, record)

        # Finalize the inventory identity only after the optional tag update has
        # completed.  Remove old exported setlists immediately before creating
        # the replacement so a same-base manual correction does not spuriously
        # become (alt1). Tag write warnings do not discard the user's manual
        # path correction; they are returned to the GUI for explicit reporting.
        _delete_paths(setlists_safe_to_delete)
        generated = create_or_replace_generated_setlist(config.TLOHome, record)

        kept = [
            row for row in old_rows_all
            if (row.get("Show", ""), row.get("VolumePath", "")) not in replace_keys
        ]
        for old_row in rows_to_replace:
            kept.append({
                "Show": new_leaf,
                "VolumePath": _replace_volume_path_leaf(old_row.get("VolumePath", ""), old_leaf, new_leaf),
            })
        write_bootlist(config.TLOHome, kept)
    except Exception as exc:
        if generated and os.path.isfile(generated):
            try:
                os.remove(generated)
            except OSError:
                pass
        _restore_setlists(snapshots)
        try:
            write_bootlist(config.TLOHome, old_rows_all)
        except Exception:
            pass
        if renamed_by_tlo and os.path.isdir(target) and not os.path.exists(original):
            try:
                rename_folder_exact_case(target, original)
            except Exception:
                pass
        detail = str(exc).strip() or exc.__class__.__name__
        if tags_attempted:
            detail += " Tag writes may already have been applied; Manual Updates does not roll audio tags back."
        if isinstance(exc, ManualUpdateError):
            raise ManualUpdateError(detail) from exc
        raise ManualUpdateError(detail) from exc

    return {
        "original": original,
        "new_path": active_path,
        "new_name": new_leaf,
        "setlist": generated,
        "rows_replaced": str(len(rows_to_replace)),
        "update_tags": "yes" if update_tags else "no",
        "tag_stats": tag_stats,
        "tag_warnings": tag_warnings,
    }


def apply_unidentified_manual_update(
    config,
    original_path: str,
    new_name: str,
    destination_path: str,
    *,
    update_tags: bool = False,
) -> Dict[str, object]:
    """Inventory an already manually moved/renamed unidentified show.

    This branch never renames or moves a folder.  Original is used only to
    locate the persistent unidentifiedShows.txt entry.
    """
    original = os.path.normpath(normalize_platform_input_path(strip_optional_quotes(original_path)))
    if not os.path.isabs(original):
        raise ManualUpdateError(f"Original must be a fully qualified folder path: {original_path}")
    new_leaf = _validate_new_leaf(new_name)
    matched_unidentified = find_unidentified_show_path(config.TLOHome, original)
    if not matched_unidentified:
        raise ManualUpdateError(
            f"Original folder is not present in bootlist.csv or unidentifiedShows.txt: {original}"
        )
    destination_parent, final_path = resolve_unidentified_destination(destination_path, new_leaf)

    old_rows = read_bootlist(config.TLOHome)
    final_key = normalize_path_for_compare(final_path)
    final_volume = volume_key(os_volume_label_for_path(final_path))
    for row in old_rows:
        row_volume, physical = parse_volume_path_value(row.get("VolumePath", ""))
        same_path = normalize_path_for_compare(physical) == final_key
        same_volume = not final_volume or not volume_key(row_volume) or volume_key(row_volume) == final_volume
        if same_path and same_volume:
            raise ManualUpdateError(f"Destination folder is already present in bootlist.csv: {final_path}")

    unidentified_file = unidentified_shows_path(config.TLOHome)
    unidentified_snapshot = b""
    unidentified_existed = os.path.isfile(unidentified_file)
    if unidentified_existed:
        with open(unidentified_file, "rb") as infile:
            unidentified_snapshot = infile.read()

    generated = ""
    tag_stats: Dict[str, object] = {}
    tag_warnings: List[str] = []
    tags_attempted = False
    try:
        record = identify_folder_dict(config, final_path)
        record["show_name"] = new_leaf
        record["main_dir_path"] = final_path
        if update_tags:
            record = _apply_manual_name_tag_identity(record, new_leaf)
            tags_attempted = True
            tag_stats, tag_warnings = _update_manual_folder_tags(config, final_path, record)
        # No move/rename occurs in this branch.  The tag update, when selected,
        # runs against the manually changed folder before bootlist/setlist state
        # is finalized.
        generated = create_or_replace_generated_setlist(config.TLOHome, record)
        rows = list(old_rows)
        rows.append({
            "Show": new_leaf,
            "VolumePath": format_volume_path(os_volume_label_for_path(final_path), final_path),
        })
        write_bootlist(config.TLOHome, rows)
        _remove_unidentified_show_path(config.TLOHome, matched_unidentified)
    except Exception as exc:
        if generated and os.path.isfile(generated):
            try:
                os.remove(generated)
            except OSError:
                pass
        try:
            write_bootlist(config.TLOHome, old_rows)
        except Exception:
            pass
        try:
            if unidentified_existed:
                _atomic_write_bytes(unidentified_file, unidentified_snapshot)
            elif os.path.isfile(unidentified_file):
                os.remove(unidentified_file)
        except Exception:
            pass
        detail = str(exc).strip() or exc.__class__.__name__
        if tags_attempted:
            detail += " Tag writes may already have been applied; Manual Updates does not roll audio tags back."
        if isinstance(exc, ManualUpdateError):
            raise ManualUpdateError(detail) from exc
        raise ManualUpdateError(detail) from exc

    return {
        "original": original,
        "unidentified_path": matched_unidentified,
        "destination_parent": destination_parent,
        "new_path": final_path,
        "new_name": new_leaf,
        "setlist": generated,
        "rows_replaced": "0",
        "update_tags": "yes" if update_tags else "no",
        "tag_stats": tag_stats,
        "tag_warnings": tag_warnings,
    }


def apply_manual_updates_file(
    config,
    path_name: str,
    *,
    unidentified_destinations: Dict[int, str] | None = None,
    update_tags: bool = False,
) -> Dict[str, object]:
    results = []
    errors = []
    tag_warnings: List[str] = []
    destinations = dict(unidentified_destinations or {})
    for item in parse_manual_updates_file(path_name):
        try:
            kind = manual_update_source_kind(config.TLOHome, item.original_path)
            if kind == "unidentified":
                destination = destinations.get(item.line_number, "")
                if not destination:
                    raise ManualUpdateError(
                        "This unidentified show requires a destination Path from the Manual Updates window."
                    )
                item_result = apply_unidentified_manual_update(
                    config, item.original_path, item.new_name, destination,
                    update_tags=update_tags,
                )
            else:
                item_result = apply_folder_manual_update(
                    config, item.original_path, item.new_name, update_tags=update_tags
                )
            results.append(item_result)
            for warning in item_result.get("tag_warnings", []) or []:
                tag_warnings.append(f"Line {item.line_number}: {warning}")
        except Exception as exc:
            errors.append({"line": item.line_number, "path": item.original_path, "error": str(exc)})
    return {
        "updated": len(results),
        "errors": errors,
        "results": results,
        "update_tags": "yes" if update_tags else "no",
        "tag_warnings": tag_warnings,
    }
