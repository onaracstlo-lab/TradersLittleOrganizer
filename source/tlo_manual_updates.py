"""Manual folder-name corrections with coordinated bootlist/setlist updates."""

__version__ = "v476"

import ntpath
import os
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from tlo_folder_rename import rename_folder_exact_case, same_existing_entry
from tlo_inventory_update import (
    create_or_replace_generated_setlist,
    identify_folder_dict,
    infer_setlist_paths_for_show,
    parse_volume_path_value,
    read_bootlist,
    write_bootlist,
)
from tlo_path_inputs import normalize_platform_input_path, strip_optional_quotes


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
    with open(path_name, "w", encoding="utf-8", newline="") as outfile:
        for item in kept:
            outfile.write(item + "\n")


def _matching_bootlist_rows(tlo_home: str, original_path: str) -> List[Dict[str, str]]:
    rows = read_bootlist(tlo_home)
    exact: List[Dict[str, str]] = []
    leaf_matches: List[Dict[str, str]] = []
    target = _portable_path(original_path)
    target_leaf = _portable_leaf(original_path)
    for row in rows:
        _volume, physical = parse_volume_path_value(row.get("VolumePath", ""))
        if _portable_path(physical) == target:
            exact.append(row)
        elif target_leaf and _portable_leaf(physical) == target_leaf:
            leaf_matches.append(row)
    if exact:
        return exact
    if len(leaf_matches) == 1:
        return leaf_matches
    if len(leaf_matches) > 1:
        raise ManualUpdateError(
            f"More than one inventory row has the folder name {os.path.basename(original_path)}; "
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
    return f"[{volume}] {new_physical}" if volume else new_physical


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


def apply_folder_manual_update(config, original_path: str, new_name: str) -> Dict[str, str]:
    """Rename one folder in place and replace its bootlist/setlist inventory identity."""
    original = os.path.normpath(normalize_platform_input_path(strip_optional_quotes(original_path)))
    if not os.path.isabs(original):
        raise ManualUpdateError(f"Original must be a fully qualified folder path: {original_path}")
    new_leaf = _validate_new_leaf(new_name)
    parent = os.path.dirname(original)
    target = os.path.normpath(os.path.join(parent, new_leaf))
    old_leaf = os.path.basename(original)

    rows_to_replace = _matching_bootlist_rows(config.TLOHome, original)
    old_setlists: List[str] = []
    for row in rows_to_replace:
        old_setlists.extend(infer_setlist_paths_for_show(config.TLOHome, row.get("Show", "")))
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
    old_rows_all = read_bootlist(config.TLOHome)
    try:
        # Remove old exported setlists before creating the replacement so a
        # same-base manual correction does not spuriously become (alt1).
        _delete_paths([path for path, _payload in snapshots])
        record = identify_folder_dict(config, active_path)
        # Manual Updates is explicitly user-directed.  The requested leaf is
        # authoritative for the inventory Show identity; the normal metadata
        # engine still supplies the exported setlist body and supporting fields.
        record["show_name"] = new_leaf
        record["main_dir_path"] = active_path
        generated = create_or_replace_generated_setlist(config.TLOHome, record)

        replace_keys = {(row.get("Show", ""), row.get("VolumePath", "")) for row in rows_to_replace}
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
        if isinstance(exc, ManualUpdateError):
            raise
        raise ManualUpdateError(str(exc).strip() or exc.__class__.__name__) from exc

    return {
        "original": original,
        "new_path": active_path,
        "new_name": new_leaf,
        "setlist": generated,
        "rows_replaced": str(len(rows_to_replace)),
    }


def apply_unidentified_manual_update(
    config,
    original_path: str,
    new_name: str,
    destination_path: str,
) -> Dict[str, str]:
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
    for row in old_rows:
        _volume, physical = parse_volume_path_value(row.get("VolumePath", ""))
        if _portable_path(physical) == _portable_path(final_path):
            raise ManualUpdateError(f"Destination folder is already present in bootlist.csv: {final_path}")

    unidentified_file = unidentified_shows_path(config.TLOHome)
    unidentified_snapshot = b""
    unidentified_existed = os.path.isfile(unidentified_file)
    if unidentified_existed:
        with open(unidentified_file, "rb") as infile:
            unidentified_snapshot = infile.read()

    generated = ""
    try:
        record = identify_folder_dict(config, final_path)
        record["show_name"] = new_leaf
        record["main_dir_path"] = final_path
        generated = create_or_replace_generated_setlist(config.TLOHome, record)
        rows = list(old_rows)
        rows.append({"Show": new_leaf, "VolumePath": final_path})
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
                os.makedirs(os.path.dirname(unidentified_file), exist_ok=True)
                with open(unidentified_file, "wb") as outfile:
                    outfile.write(unidentified_snapshot)
            elif os.path.isfile(unidentified_file):
                os.remove(unidentified_file)
        except Exception:
            pass
        if isinstance(exc, ManualUpdateError):
            raise
        raise ManualUpdateError(str(exc).strip() or exc.__class__.__name__) from exc

    return {
        "original": original,
        "unidentified_path": matched_unidentified,
        "destination_parent": destination_parent,
        "new_path": final_path,
        "new_name": new_leaf,
        "setlist": generated,
        "rows_replaced": "0",
    }


def apply_manual_updates_file(
    config,
    path_name: str,
    *,
    unidentified_destinations: Dict[int, str] | None = None,
) -> Dict[str, object]:
    results = []
    errors = []
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
                results.append(
                    apply_unidentified_manual_update(
                        config, item.original_path, item.new_name, destination
                    )
                )
            else:
                results.append(apply_folder_manual_update(config, item.original_path, item.new_name))
        except Exception as exc:
            errors.append({"line": item.line_number, "path": item.original_path, "error": str(exc)})
    return {"updated": len(results), "errors": errors, "results": results}
