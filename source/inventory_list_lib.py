__version__ = "v334"
# TLO-GI package version: v334
__version_summary__ = 'Rearranges the main-window checkboxes into the requested two-row, four-column layout.'
# TLO-GI version summary: Rearranges the main-window checkboxes into the requested two-row, four-column layout.
import os
import re
import shutil

from console_output_lib import console_print
from logging_lib import truncate_logs_for_tokens, prune_logs_for_tokens_and_paths
from tlo_volume_label import resolve_volume_label
from tlo_bootlist_volume_policy import (
    count_group_logs_by_volume,
    group_log_tokens_by_volume,
    read_group_log_volume_rows,
    paths_related,
    path_is_same_or_under,
    normalize_path_for_compare,
    normalize_volume_action,
    normalize_volume_label,
    parse_volume_path_value,
    volume_display_name,
    volume_key,
)


def _running_on_windows():
    return os.name == "nt"


def _running_on_wsl():
    if _running_on_windows():
        return False

    try:
        with open("/proc/version", "r", encoding="utf-8") as infile:
            version_text = infile.read().lower()
        return "microsoft" in version_text or "wsl" in version_text
    except OSError:
        return False


def _is_windows_drive_path(path_text):
    return bool(re.match(r"^[A-Za-z]:([\\/].*)?$", path_text))


def _is_linux_path(path_text):
    return path_text.startswith("/")


def _is_wsl_mount_path(path_text):
    return bool(re.match(r"^/mnt/[A-Za-z]($|/)", path_text.replace("\\", "/")))


def _windows_to_wsl_path(path_text):
    drive_letter = path_text[0].lower()
    remainder = path_text[2:]
    remainder = remainder.replace("\\", "/").lstrip("/")

    if remainder:
        return f"/mnt/{drive_letter}/{remainder}"
    return f"/mnt/{drive_letter}"


def _wsl_to_windows_path(path_text):
    normalized = path_text.replace("\\", "/")
    match = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", normalized)
    if not match:
        return path_text
    drive = match.group(1).upper()
    remainder = (match.group(2) or "").replace("/", "\\")
    if remainder:
        return f"{drive}:\\{remainder}"
    return f"{drive}:\\"


def _windows_drive_path_has_nonroot_remainder(path_text):
    match = re.match(r"^[A-Za-z]:([\\/].*)?$", path_text or "")
    if not match:
        return False
    remainder = (match.group(1) or "").replace("\\", "/").strip("/")
    return bool(remainder)


def _is_wsl_drive_root(path_text):
    return bool(re.fullmatch(r"/mnt/[A-Za-z]/?", str(path_text or "").replace("\\", "/")))


def _normalize_input_path(path_text):
    original_path_text = path_text
    path_text = path_text.strip()

    if not path_text:
        return path_text

    if _running_on_windows():
        if _is_wsl_mount_path(path_text):
            return _wsl_to_windows_path(path_text)
        if not _is_windows_drive_path(path_text):
            raise ValueError(f"Invalid path format for Windows: {path_text}")

        if len(path_text) == 2 and path_text[1] == ":" and path_text[0].isalpha():
            return path_text + "\\"

        return path_text

    if _is_windows_drive_path(path_text):
        normalized = _windows_to_wsl_path(path_text)
        if _windows_drive_path_has_nonroot_remainder(original_path_text) and _is_wsl_drive_root(normalized):
            raise ValueError(
                f"Windows search path was reduced to the drive root while normalizing: {original_path_text}. "
                "Quote the path or use forward slashes so the full directory is preserved."
            )
        return normalized

    if _is_linux_path(path_text):
        return path_text

    return path_text


def _strip_optional_quotes(text):
    text = text.strip()

    if len(text) >= 2:
        if text[0] == '"' and text[-1] == '"':
            return text[1:-1]
        if text[0] == "'" and text[-1] == "'":
            return text[1:-1]

    return text


_PATH_DIRECTIVE_RE = re.compile(r"(?<!\S)(--?\$slam|--\$copy-delete|--\$copy)(?=\s|$)", re.IGNORECASE)


def _split_path_and_directives(line_text):
    """Parse one toBeInventoried.txt line.

    The physical path must come first.  Optional directives may follow in any
    order: --$slam / -$slam, --$copy, and --$copy-delete.  Directive values run
    until the next directive marker or the end of the line, so paths and artist
    names may contain spaces without additional quoting.
    """
    text = str(line_text or "").strip()
    matches = list(_PATH_DIRECTIVE_RE.finditer(text))
    if not matches:
        return _strip_optional_quotes(text), "", "", ""

    path_part = text[:matches[0].start()].strip()
    values = {"slam": "", "copy": "", "copy_delete": ""}
    seen = {}

    for index, match in enumerate(matches):
        marker = match.group(1).lower()
        value_start = match.end()
        value_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = _strip_optional_quotes(text[value_start:value_end].strip())
        if not value:
            raise ValueError(f"Missing value for {match.group(1)} directive in inventory line: {line_text}")
        if marker.endswith("$slam"):
            key = "slam"
        elif marker == "--$copy":
            key = "copy"
        elif marker == "--$copy-delete":
            key = "copy_delete"
        else:
            raise ValueError(f"Unrecognized inventory directive {match.group(1)} in line: {line_text}")
        if key in seen:
            raise ValueError(f"Duplicate {match.group(1)} directive in inventory line: {line_text}")
        seen[key] = match.group(1)
        values[key] = value

    if values["copy"] and values["copy_delete"]:
        raise ValueError("--$copy and --$copy-delete are mutually exclusive on one toBeInventoried.txt line")

    return _strip_optional_quotes(path_part), values["slam"], values["copy"], values["copy_delete"]


def _split_path_and_string(line_text):
    path_part, slam_value, _copy_value, _copy_delete_value = _split_path_and_directives(line_text)
    return path_part, slam_value


def _has_bracketed_volume_prefix(path_text):
    raw = _strip_optional_quotes(str(path_text or "")).lstrip()
    return bool(re.match(r"^\[[^\]]*\]", raw))


def _split_optional_volume_prefix(path_text):
    """Return (volume_label, physical_path_text) from an optional [volume]path.

    The [volume] prefix is user supplied and is not part of the physical path.
    Missing prefixes are resolved later to the operating-system volume label.
    An explicit [] prefix remains an explicit blank visible volume.
    """
    raw = _strip_optional_quotes(path_text)
    volume_label, physical_path = parse_volume_path_value(raw)
    physical_path = _strip_optional_quotes(physical_path)
    return normalize_volume_label(volume_label), physical_path


def _is_comment_line(line_text):
    """Return True for supported whole-line comments in toBeInventoried.txt."""
    cleaned = str(line_text or "").lstrip("\ufeff").strip()
    lowered = cleaned.lower()
    return cleaned.startswith("#") or lowered == "rem" or lowered.startswith("rem ")


def _check_access(normalized_path):
    try:
        entries = os.listdir(normalized_path)
    except FileNotFoundError:
        return False, f"path does not exist: {normalized_path}"
    except NotADirectoryError:
        return False, f"path is not a directory: {normalized_path}"
    except (OSError, PermissionError) as exc:
        return False, f"directory access check failed for {normalized_path}: {exc}"

    if not entries:
        return False, f"path is empty: {normalized_path}"

    return True, ""


def _normalize_copy_destination(raw_destination, directive_name):
    destination = _strip_optional_quotes(str(raw_destination or "").strip())
    if not destination:
        return ""
    normalized = _normalize_input_path(destination)
    if not os.path.isabs(normalized) or not os.path.isdir(normalized):
        raise ValueError(f"{directive_name} destination must be an existing fully qualified directory path: {raw_destination}")
    return os.path.normpath(normalized)


def _path_is_same_or_under(child_path, parent_path):
    child = _canonical_search_path(child_path)
    parent = _canonical_search_path(parent_path)
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _paths_on_same_filesystem(path_a, path_b):
    try:
        return os.stat(path_a).st_dev == os.stat(path_b).st_dev
    except OSError:
        return False


def _folder_size_bytes(root_path):
    total = 0
    stack = [root_path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            total += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return total


def _format_bytes(num_bytes):
    value = float(max(0, int(num_bytes or 0)))
    units = ["bytes", "KB", "MB", "GB", "TB", "PB"]
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "bytes":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0
    return f"{int(value)} bytes"


def _effective_copy_directive_for_item(config, path_name, copy_mode, copy_destination):
    global_copy_delete = str(getattr(config, "tag_copy_and_delete_path", "") or "").strip()
    if global_copy_delete:
        return "copy-delete", os.path.normpath(global_copy_delete), "Tag Copy and Delete Path override"

    mode = str(copy_mode or "").strip().lower()
    destination = str(copy_destination or "").strip()
    if mode and destination:
        return mode, os.path.normpath(destination), f"per-path --${mode}"

    if bool(getattr(config, "tag_copy_during_inventory", False)) and str(getattr(config, "tag_copy_destination", "") or "").strip():
        return "copy", os.path.normpath(str(getattr(config, "tag_copy_destination", "") or "").strip()), "Tag Copy destination"

    return "", "", ""


def _collect_copy_capacity_requirements(config, accessible_items):
    requirements = {}
    size_cache = {}
    for item in accessible_items:
        path_name, _slam_value, _volume_label, _physical_key = item[:4]
        copy_mode = item[4] if len(item) > 4 else ""
        copy_destination = item[5] if len(item) > 5 else ""
        effective_mode, destination, source_label = _effective_copy_directive_for_item(config, path_name, copy_mode, copy_destination)
        if not effective_mode or not destination:
            continue
        if os.path.normcase(os.path.normpath(path_name)) == os.path.normcase(os.path.normpath(destination)) or _path_is_same_or_under(destination, path_name):
            raise ValueError(f"Copy destination must not be the source folder or a child of it: source={path_name} destination={destination}")
        if path_name not in size_cache:
            size_cache[path_name] = _folder_size_bytes(path_name)
        source_size = size_cache[path_name]
        # Copy/Delete on the same filesystem is performed as a move and does not
        # need another full copy of the source tree.  Cross-filesystem copy/delete
        # and ordinary Tag Copy both require destination free space.
        required_bytes = 0 if effective_mode == "copy-delete" and _paths_on_same_filesystem(path_name, destination) else source_size
        entry = requirements.setdefault(os.path.normpath(destination), {"required": 0, "sources": [], "modes": set()})
        entry["required"] += required_bytes
        entry["sources"].append({
            "path": path_name,
            "size": source_size,
            "required": required_bytes,
            "mode": effective_mode,
            "source_label": source_label,
        })
        entry["modes"].add(effective_mode)
    return requirements


def _copy_capacity_check_requested(config, accessible_items):
    if str(getattr(config, "tag_copy_and_delete_path", "") or "").strip():
        return bool(accessible_items)
    if bool(getattr(config, "tag_copy_during_inventory", False)) and str(getattr(config, "tag_copy_destination", "") or "").strip():
        return bool(accessible_items)
    for item in accessible_items:
        copy_mode = item[4] if len(item) > 4 else ""
        copy_destination = item[5] if len(item) > 5 else ""
        if str(copy_mode or "").strip() and str(copy_destination or "").strip():
            return True
    return False


def _validate_copy_destination_capacity(config, accessible_items):
    if not _copy_capacity_check_requested(config, accessible_items):
        return
    console_print(
        config,
        "Note: checking source folder sizes before checking whether copy/copy-delete destinations have enough capacity. Large source trees may take a while to total.",
    )
    requirements = _collect_copy_capacity_requirements(config, accessible_items)
    problems = []
    for destination, detail in requirements.items():
        try:
            free_bytes = shutil.disk_usage(destination).free
        except OSError as exc:
            raise ValueError(f"Unable to check free space for copy destination {destination}: {exc}") from exc
        required = int(detail.get("required", 0) or 0)
        if required > free_bytes:
            problems.append((destination, required, free_bytes, detail.get("sources", [])))

    if not problems:
        if requirements:
            for destination, detail in requirements.items():
                console_print(
                    config,
                    f"Copy destination capacity check passed: {destination} | required {_format_bytes(detail.get('required', 0))}",
                )
        return

    lines = ["Copy destination capacity check failed."]
    for destination, required, free_bytes, sources in problems:
        lines.append("")
        lines.append(f"Destination: {destination}")
        lines.append(f"Required additional space: {_format_bytes(required)}")
        lines.append(f"Available space: {_format_bytes(free_bytes)}")
        lines.append(f"Additional space needed: {_format_bytes(required - free_bytes)}")
        lines.append("Source(s):")
        for source in sources:
            lines.append(
                f"  {source['path']} | source size {_format_bytes(source['size'])} | "
                f"space needed {_format_bytes(source['required'])} | {source['mode']}"
            )
    message = "\n".join(lines)
    callback = getattr(config, "capacity_alert_callback", None)
    if callable(callback):
        try:
            callback(message)
        except Exception:
            pass
    raise ValueError(message)


def _parse_inventory_file(file_path):
    parsed_items = []

    with open(file_path, "r", encoding="utf-8-sig") as infile:
        for line_number, raw_line in enumerate(infile, start=1):
            line = raw_line.rstrip("\r\n")
            stripped = line.strip()

            if not stripped or _is_comment_line(line):
                continue

            raw_path_entry, assoc_value, copy_value, copy_delete_value = _split_path_and_directives(stripped)
            volume_label, raw_path = _split_optional_volume_prefix(raw_path_entry)

            if not raw_path:
                raise ValueError(
                    f"Missing path in inventory file at line {line_number}: {file_path}"
                )

            normalized_path = _normalize_input_path(raw_path)
            copy_mode = ""
            copy_destination = ""
            if copy_value:
                copy_mode = "copy"
                copy_destination = _normalize_copy_destination(copy_value, "--$copy")
            elif copy_delete_value:
                copy_mode = "copy-delete"
                copy_destination = _normalize_copy_destination(copy_delete_value, "--$copy-delete")
            if copy_mode and copy_destination:
                parsed_items.append((raw_path_entry, normalized_path, assoc_value, volume_label, copy_mode, copy_destination))
            else:
                parsed_items.append((raw_path_entry, normalized_path, assoc_value, volume_label))

    return parsed_items


def _canonical_search_path(path_text):
    return os.path.normcase(os.path.normpath(path_text))


def _drive_sort_key(path_text):
    text = str(path_text or "").replace("\\", "/")
    match = re.match(r"^([A-Za-z]):", text)
    if match:
        return (0, match.group(1).upper(), text.casefold())
    match = re.match(r"^/mnt/([A-Za-z])(?:/|$)", text, flags=re.IGNORECASE)
    if match:
        return (0, match.group(1).upper(), text.casefold())
    return (1, "", text.casefold())


def _paths_overlap(path_a, path_b):
    canonical_a = _canonical_search_path(path_a)
    canonical_b = _canonical_search_path(path_b)

    try:
        shared = os.path.commonpath([canonical_a, canonical_b])
    except ValueError:
        return False

    return shared == canonical_a or shared == canonical_b


def _collect_search_path_issues(candidate_items, inventory_file):
    issues = []
    seen = {}

    for line_number, item in enumerate(candidate_items, start=1):
        raw_path, normalized_path = item[:2]
        key = _canonical_search_path(normalized_path)
        if key in seen:
            first_line, first_raw_path, _first_normalized = seen[key]
            issues.append({
                "raw_path": raw_path,
                "normalized_path": normalized_path,
                "reason": (
                    "duplicate search path: "
                    f"{raw_path} (line {line_number}) duplicates {first_raw_path} (line {first_line}) in {inventory_file}"
                ),
            })
            continue
        seen[key] = (line_number, raw_path, normalized_path)

    seen_items = list(seen.values())
    for index, (line_a, raw_a, normalized_a) in enumerate(seen_items):
        for line_b, raw_b, normalized_b in seen_items[index + 1:]:
            if _paths_overlap(normalized_a, normalized_b):
                issues.append({
                    "raw_path": raw_a,
                    "normalized_path": normalized_a,
                    "reason": (
                        "overlapping search paths: "
                        f"{raw_a} (line {line_a}) overlaps {raw_b} (line {line_b}) in {inventory_file}"
                    ),
                })
                issues.append({
                    "raw_path": raw_b,
                    "normalized_path": normalized_b,
                    "reason": (
                        "overlapping search paths: "
                        f"{raw_b} (line {line_b}) overlaps {raw_a} (line {line_a}) in {inventory_file}"
                    ),
                })
    return issues



def _volume_labels_match(label_a, label_b):
    return normalize_volume_label(label_a).casefold() == normalize_volume_label(label_b).casefold()


def _raise_volume_label_mismatch(raw_path, normalized_path, supplied_label, os_label):
    supplied_display = normalize_volume_label(supplied_label)
    os_display = normalize_volume_label(os_label)
    raise ValueError(
        "Search path volume mismatch: "
        f"the search path supplies [{supplied_display}] for {raw_path}, "
        f"but the operating system reports [{os_display}] for {normalized_path}. "
        "The path will not be processed. Correct the bracketed volume label or mount the expected drive."
    )


def _assign_volume_labels(candidate_items):
    assigned = []

    for item in candidate_items:
        raw_path, normalized_path, assoc_value, explicit_volume_label = item[:4]
        copy_mode = item[4] if len(item) > 4 else ""
        copy_destination = item[5] if len(item) > 5 else ""
        info = resolve_volume_label(normalized_path)
        physical_volume_key = info.volume_key or _canonical_search_path(normalized_path)
        os_volume_label = normalize_volume_label(getattr(info, "label", ""))
        os_label_known = bool(os_volume_label or getattr(info, "label_source", ""))
        if _has_bracketed_volume_prefix(raw_path):
            # Explicit bracketed labels, including [], are user-visible labels and
            # must be preserved exactly after normal label cleanup.  When the OS
            # can report a label for the mounted drive, the supplied label must
            # match it so an incorrect/mis-mounted drive is not inventoried.
            volume_label = normalize_volume_label(explicit_volume_label)
            if os_label_known and not _volume_labels_match(volume_label, os_volume_label):
                _raise_volume_label_mismatch(raw_path, normalized_path, volume_label, os_volume_label)
        else:
            # Missing bracketed labels are filled from the operating-system volume
            # label so logging and existing-volume comparison use the same visible
            # name the OS reports for that root.  If the OS reports no label, the
            # empty label remains valid.
            volume_label = os_volume_label
        if copy_mode and copy_destination:
            assigned.append((raw_path, normalized_path, assoc_value, volume_label, physical_volume_key, copy_mode, copy_destination))
        else:
            assigned.append((raw_path, normalized_path, assoc_value, volume_label, physical_volume_key))

    return assigned



def _default_existing_path_action_prompt(config, volume_label: str, path_name: str, row_count: int, path_count: int) -> str:
    label_display = volume_display_name(volume_label)
    if getattr(config, "silent", False):
        console_print(
            config,
            f"Path [{volume_label}] {path_name} overlaps {row_count} existing group log entry/entries; silent mode defaults to re-inventory.",
        )
        return "reinventory"
    while True:
        try:
            response = input(
                f"Path [{volume_label}] {path_name} ({label_display}) overlaps {row_count} existing group log entry/entries "
                f"and {path_count} queued search path(s). Choose skip or re-inventory [s/r]: "
            )
        except EOFError:
            console_print(
                config,
                f"Path [{volume_label}] {path_name} overlaps existing group logs; no input available, defaulting to re-inventory.",
            )
            return "reinventory"
        try:
            return normalize_volume_action(response)
        except ValueError:
            console_print(config, "Please enter skip or re-inventory (s/r).")


def _related_group_rows_for_item(path_name: str, volume_label: str, group_rows):
    key = volume_key(volume_label)
    return [
        row for row in group_rows
        if volume_key(row.get("Volume", "")) == key
        and paths_related(path_name, row.get("Path", ""))
    ]


def _token_rows_by_relationship(related_rows, requested_path: str):
    exact = []
    children = []
    parents = []
    requested_key = normalize_path_for_compare(requested_path)
    for row in related_rows:
        token = (row.get("Token") or "").strip()
        row_path = row.get("Path", "")
        if not token:
            continue
        row_key = normalize_path_for_compare(row_path)
        if row_key == requested_key:
            exact.append(row)
        elif path_is_same_or_under(row_path, requested_path):
            children.append(row)
        elif path_is_same_or_under(requested_path, row_path):
            parents.append(row)
    return exact, children, parents


def _tokens_from_rows(rows) -> list[str]:
    return sorted({(row.get("Token") or "").strip() for row in rows if (row.get("Token") or "").strip()}, key=lambda value: (len(value), value))


def _call_batch_prompt(prompt_callback, collisions):
    if not callable(prompt_callback):
        return None
    try:
        result = prompt_callback(collisions)
    except TypeError:
        return None
    if result is None:
        return None
    if isinstance(result, dict):
        return {int(k): normalize_volume_action(v) for k, v in result.items()}
    return None


def _call_legacy_prompt(prompt_callback, volume_label, path_name, row_count, path_count):
    if not callable(prompt_callback):
        return None
    for args in ((volume_label, path_name, row_count, path_count), (volume_label, row_count, path_count)):
        try:
            return normalize_volume_action(prompt_callback(*args))
        except TypeError:
            continue
    return None


def _volume_identity_for_physical_path(path_name):
    info = resolve_volume_label(path_name)
    return (
        normalize_volume_label(getattr(info, "label", "")),
        getattr(info, "volume_key", "") or _canonical_search_path(path_name),
    )


def _inventory_scope_for_item(config, item):
    """Return the volume/path identity that this item should write to logs.

    Normal inventory and Tag Copy inventory are owned by the original source
    tree.  Tag Copy/Delete Original is different: metadata is read from the
    original, but the resulting inventory belongs to the destination parent
    directory because the original is removed after transfer.
    """
    source_path, _slam_value, source_volume_label, source_physical_key = item[:4]
    copy_mode = item[4] if len(item) > 4 else ""
    copy_destination = item[5] if len(item) > 5 else ""
    effective_mode, destination, _source_label = _effective_copy_directive_for_item(config, source_path, copy_mode, copy_destination)
    if effective_mode == "copy-delete" and destination:
        destination_label, destination_key = _volume_identity_for_physical_path(destination)
        return {
            "source_path": source_path,
            "inventory_path": os.path.normpath(destination),
            "volume_label": destination_label,
            "physical_volume_key": destination_key,
            "copy_mode": effective_mode,
            "copy_destination": destination,
            "source_volume_label": source_volume_label,
            "source_physical_volume_key": source_physical_key,
        }
    if effective_mode == "copy" and destination:
        return {
            "source_path": source_path,
            "inventory_path": source_path,
            "volume_label": source_volume_label,
            "physical_volume_key": source_physical_key,
            "copy_mode": effective_mode,
            "copy_destination": destination,
            "source_volume_label": source_volume_label,
            "source_physical_volume_key": source_physical_key,
        }
    return {
        "source_path": source_path,
        "inventory_path": source_path,
        "volume_label": source_volume_label,
        "physical_volume_key": source_physical_key,
        "copy_mode": copy_mode,
        "copy_destination": copy_destination,
        "source_volume_label": source_volume_label,
        "source_physical_volume_key": source_physical_key,
    }


def _resolve_existing_volume_actions(config, accessible_items):
    group_rows = read_group_log_volume_rows(config.TLOHome)

    decisions = []
    for item_index, item in enumerate(accessible_items):
        source_path, _slam_value, _source_volume_label, _source_physical_key = item[:4]
        scope = _inventory_scope_for_item(config, item)
        path_name = scope["inventory_path"]
        volume_label = scope["volume_label"]
        same_volume_rows = [
            row for row in group_rows
            if volume_key(row.get("Volume", "")) == volume_key(volume_label)
        ]
        related_rows = [] if not volume_label else _related_group_rows_for_item(path_name, volume_label, group_rows)

        if not volume_label:
            # Drives with no visible volume label are intentionally append-only.
            # There is no skip/re-inventory decision and the log header omits the
            # path so every blank-label run shares one blank-volume log set.
            action = "append_blank"
            console_print(
                config,
                f"Blank volume label inventory: {path_name} will append to the blank-volume log set; duplicate control is left to the user.",
            )
        elif not same_volume_rows:
            action = "new"
        elif related_rows:
            # Deterministic volume/path policy: same labeled volume + overlapping
            # path always re-inventories the affected subtree.  No prompt is shown.
            action = "reinventory"
            console_print(
                config,
                f"Existing inventory decision: [{volume_label}] {path_name} -> re-inventory "
                f"({len(related_rows)} related stored path/header entry/entries)",
            )
        else:
            # Same labeled volume, no path overlap: append the new path to the
            # existing volume log header and append this inventory's log entries.
            action = "new"
            console_print(
                config,
                f"Existing inventory decision: [{volume_label}] {path_name} -> append non-overlapping path to existing volume log.",
            )

        exact_rows, child_rows, parent_rows = _token_rows_by_relationship(related_rows, path_name)
        decisions.append({
            "item_index": item_index,
            "source_path": source_path,
            "volume": volume_label or "",
            "volume_key": volume_key(volume_label),
            "path": path_name,
            "path_key": normalize_path_for_compare(path_name),
            "action": action,
            "exact_tokens": _tokens_from_rows(exact_rows),
            "child_tokens": _tokens_from_rows(child_rows),
            "parent_tokens": _tokens_from_rows(parent_rows),
            "related_tokens": _tokens_from_rows(related_rows),
            "same_volume_tokens": _tokens_from_rows(same_volume_rows),
            "related_group_paths": [row.get("Path", "") for row in related_rows],
            "same_volume_group_paths": [row.get("Path", "") for row in same_volume_rows],
            "copy_mode": scope.get("copy_mode", ""),
            "copy_destination": scope.get("copy_destination", ""),
        })
    config.inventory_path_actions = list(decisions)
    config.inventory_volume_actions = {d["volume_key"]: d["action"] for d in decisions}
    return decisions

def _prepare_log_reuse_for_decision(config, decision, path_name, volume_label):
    action = (decision or {}).get("action", "new")
    same_volume_tokens = list((decision or {}).get("same_volume_tokens") or [])

    if not volume_label:
        if same_volume_tokens:
            return same_volume_tokens[0], "a"
        return "", "w"

    if action != "reinventory":
        if same_volume_tokens:
            token = same_volume_tokens[0]
            console_print(config, f"Inventory will append [{volume_label}] {path_name} to existing volume log token {token}.")
            return token, "a"
        return "", "w"

    exact_tokens = list((decision or {}).get("exact_tokens") or [])
    child_tokens = list((decision or {}).get("child_tokens") or [])
    parent_tokens = list((decision or {}).get("parent_tokens") or [])

    if exact_tokens:
        token = exact_tokens[0]
        truncated = truncate_logs_for_tokens(config.TLOHome, exact_tokens)
        if truncated:
            console_print(config, f"Re-inventory will replace {len(truncated)} exact related log file(s) for [{volume_label}] {path_name}.")
        return token, "w"

    if child_tokens and not parent_tokens:
        token = child_tokens[0]
        truncated = truncate_logs_for_tokens(config.TLOHome, child_tokens)
        if truncated:
            console_print(config, f"Re-inventory will replace {len(truncated)} child/subtree related log file(s) for [{volume_label}] {path_name}.")
        return token, "w"

    if parent_tokens:
        token = parent_tokens[0]
        pruned = prune_logs_for_tokens_and_paths(config.TLOHome, parent_tokens, [path_name])
        if pruned:
            console_print(config, f"Re-inventory pruned {len(pruned)} prior child-path log file(s) before appending [{volume_label}] {path_name}.")
        else:
            console_print(config, f"Re-inventory will append child-path results to existing log token {token} for [{volume_label}] {path_name}.")
        return token, "a"

    if same_volume_tokens:
        return same_volume_tokens[0], "a"
    return "", "w"

def apply_existing_volume_actions(config, accessible_items):
    decisions = _resolve_existing_volume_actions(config, accessible_items)
    filtered = []
    skipped = []
    for item_index, item in enumerate(accessible_items):
        source_path, slam_value, _source_volume_label, _source_physical_volume_key = item[:4]
        scope = _inventory_scope_for_item(config, item)
        inventory_path = scope["inventory_path"]
        volume_label = scope["volume_label"]
        physical_volume_key = scope["physical_volume_key"]
        copy_mode = scope.get("copy_mode", "") or ""
        copy_destination = scope.get("copy_destination", "") or ""
        decision = next((d for d in decisions if d.get("item_index") == item_index), None)
        action = (decision or {}).get("action", "new")
        if action == "skip":
            skipped.append((source_path, inventory_path, volume_label))
            continue

        token, log_mode = _prepare_log_reuse_for_decision(config, decision, inventory_path, volume_label)
        if copy_mode or copy_destination or os.path.normpath(str(inventory_path or "")) != os.path.normpath(str(source_path or "")):
            filtered.append((
                source_path,
                slam_value,
                volume_label,
                physical_volume_key,
                token,
                log_mode,
                copy_mode,
                copy_destination,
                inventory_path,
            ))
        else:
            filtered.append((source_path, slam_value, volume_label, physical_volume_key, token, log_mode))
    if skipped:
        console_print(config, f"Skipped {len(skipped)} search path(s) based on existing inventory decision(s).")
        for source_path, inventory_path, volume_label in skipped:
            console_print(config, f"  skipped: [{volume_label}] {inventory_path} (source: {source_path})")
    if not filtered:
        raise ValueError("No inventory roots remain after existing-inventory decisions.")
    return filtered


def prepare_inventory_items(config):
    prepared = getattr(config, "prepared_inventory_items", None)
    if prepared:
        return prepared
    accessible_items = load_accessible_inventory_paths(config)
    prepared = apply_existing_volume_actions(config, accessible_items)
    config.prepared_inventory_items = prepared
    return prepared

def load_accessible_inventory_paths(config):
    inventory_file = os.path.join(config.TLOHome, "toBeInventoried.txt")

    if getattr(config, "search_path_override", ""):
        raw_path_entry = _strip_optional_quotes(config.search_path_override)
        volume_label, raw_path = _split_optional_volume_prefix(raw_path_entry)
        assoc_value = _strip_optional_quotes(getattr(config, "search_path_slam_override", ""))
        copy_value = _strip_optional_quotes(getattr(config, "search_path_copy_override", "") or "")
        copy_delete_value = _strip_optional_quotes(getattr(config, "search_path_copy_delete_override", "") or "")
        if copy_value and copy_delete_value:
            raise ValueError("--$copy and --$copy-delete are mutually exclusive for a single --search-path.")
        if not raw_path:
            raise ValueError("--search-path was provided but no usable search path was found.")
        normalized_path = _normalize_input_path(raw_path)
        copy_mode = ""
        copy_destination = ""
        if copy_value:
            copy_mode = "copy"
            copy_destination = _normalize_copy_destination(copy_value, "--$copy")
        elif copy_delete_value:
            copy_mode = "copy-delete"
            copy_destination = _normalize_copy_destination(copy_delete_value, "--$copy-delete")
        if copy_mode and copy_destination:
            candidate_items = [(raw_path_entry, normalized_path, assoc_value, volume_label, copy_mode, copy_destination)]
        else:
            candidate_items = [(raw_path_entry, normalized_path, assoc_value, volume_label)]
        inventory_source = "command line --search-path"
    else:
        if not os.path.isfile(inventory_file):
            raise FileNotFoundError(f"Inventory file not found: {inventory_file}")

        candidate_items = _parse_inventory_file(inventory_file)
        inventory_source = inventory_file

    validation_issues = _collect_search_path_issues(candidate_items, inventory_source)
    candidate_items = _assign_volume_labels(candidate_items)

    accessible_items = []
    inaccessible_items = []

    for item in candidate_items:
        raw_path, normalized_path, assoc_value, volume_label, volume_key = item[:5]
        copy_mode = item[5] if len(item) > 5 else ""
        copy_destination = item[6] if len(item) > 6 else ""
        is_accessible, reason = _check_access(normalized_path)
        if is_accessible:
            if copy_mode and copy_destination:
                accessible_items.append((normalized_path, assoc_value, volume_label, volume_key, copy_mode, copy_destination))
            else:
                accessible_items.append((normalized_path, assoc_value, volume_label, volume_key))
        else:
            if copy_mode and copy_destination:
                inaccessible_items.append((raw_path, normalized_path, assoc_value, volume_label, volume_key, copy_mode, copy_destination, reason))
            else:
                inaccessible_items.append((raw_path, normalized_path, assoc_value, volume_label, volume_key, reason))

    console_print(
        config,
        f"Inventory roots loaded: {len(accessible_items)} accessible, {len(inaccessible_items)} inaccessible",
            )

    if validation_issues:
        console_print(config, f"Invalid inventory roots: {len(validation_issues)}")
        for item in validation_issues:
            console_print(config, f"  {item['raw_path']}")
            if item.get("normalized_path"):
                console_print(config, f"    normalized: {item['normalized_path']}")
            if item.get("reason"):
                console_print(config, f"    reason: {item['reason']}")
        raise ValueError("One or more inventory roots failed validation.")

    if inaccessible_items:
        console_print(config, f"Inaccessible inventory roots: {len(inaccessible_items)}")
        for item in inaccessible_items:
            bad_path, normalized_path, bad_value, bad_volume_label, _bad_volume_key = item[:5]
            reason = item[-1]
            display_path = f"{bad_path} -$slam {bad_value}" if bad_value else bad_path
            console_print(config, f"  {display_path}")
            console_print(config, f"    normalized: {normalized_path}")
            if bad_volume_label:
                console_print(config, f"    volume_label: {bad_volume_label}")
            console_print(config, f"    reason: {reason}")

    if not accessible_items:
        raise ValueError("No accessible inventory roots were found.")

    _validate_copy_destination_capacity(config, accessible_items)

    return accessible_items
