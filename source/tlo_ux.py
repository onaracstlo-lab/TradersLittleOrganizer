"""User-experience helpers for TLO GUI review, preview, progress, and issue reporting."""

from __future__ import annotations

__version__ = "v407"


import copy
import os
import re
import subprocess
import tempfile
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable, Optional

from inventory_list_lib import (
    _normalize_input_path,
    _parse_inventory_file,
    _split_optional_volume_prefix,
    _strip_optional_quotes,
)
from tlo_media_rules import MEDIA_EXTENSIONS


# ttk.Progressbar.start() receives the animation interval in milliseconds.
# Build 352 intentionally uses ten times the former 12 ms interval so the
# indeterminate activity indicator moves at one-tenth its previous speed.
ACTIVITY_INDICATOR_INTERVAL_MS = 120


@dataclass(frozen=True)
class ValidationStatus:
    level: str
    message: str
    normalized: str = ""

    @property
    def valid(self) -> bool:
        return self.level != "error"

    @property
    def display(self) -> str:
        marker = {"ok": "OK", "warning": "Warning", "error": "Error"}.get(self.level, "Info")
        return f"{marker}: {self.message}"


@dataclass
class RunIssue:
    category: str
    message: str
    path: str = ""
    severity: str = "warning"
    source: str = "run"

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (
            self.category.casefold(),
            self.message.casefold(),
            os.path.normcase(os.path.normpath(self.path)) if self.path else "",
            self.severity.casefold(),
        )


@dataclass
class PreviewTag:
    source_path: str
    target_path: str
    artist: str
    album: str
    track: str
    title: str
    action: str = "would tag"
    reason: str = ""


@dataclass
class PreviewItem:
    path: str
    media_files: int
    shn_files: int
    actions: tuple[str, ...]
    show_name: str = ""
    artist: str = ""
    album: str = ""
    track_source: str = ""
    tags: list[PreviewTag] = field(default_factory=list)
    notes: tuple[str, ...] = ()
    unresolved: tuple[str, ...] = ()


@dataclass
class PreviewResult:
    operation: str
    roots: list[str] = field(default_factory=list)
    music_folders: int = 0
    media_files: int = 0
    shn_files: int = 0
    samples: list[PreviewItem] = field(default_factory=list)
    issues: list[RunIssue] = field(default_factory=list)
    elapsed_seconds: float = 0.0
    truncated: bool = False


@dataclass
class RunSnapshot:
    stage: str = "Ready"
    current_item: str = ""
    roots_total: int = 0
    roots_completed: int = 0
    directories: int = 0
    show_groups: int = 0
    tagged_files: int = 0
    folders: int = 0
    skipped_folders: int = 0
    warnings: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0
    completed: bool = False
    success: bool = False


def _path_without_volume_prefix(value: str) -> str:
    _volume, path_text = _split_optional_volume_prefix(_strip_optional_quotes(str(value or "")))
    return str(path_text or "").strip()


def validate_search_path(value: str, tlo_home: str) -> ValidationStatus:
    raw = str(value or "").strip()
    if raw:
        try:
            physical = _path_without_volume_prefix(raw)
            normalized = _normalize_input_path(physical)
        except Exception as exc:
            return ValidationStatus("error", str(exc))
        if not os.path.isabs(normalized):
            return ValidationStatus("error", "Search Path must be fully qualified.", normalized)
        if not os.path.exists(normalized):
            return ValidationStatus("error", f"Search Path does not exist: {normalized}", normalized)
        if not os.path.isdir(normalized):
            return ValidationStatus("error", f"Search Path is not a directory: {normalized}", normalized)
        try:
            os.listdir(normalized)
        except OSError as exc:
            return ValidationStatus("error", f"Search Path cannot be read: {exc}", normalized)
        return ValidationStatus("ok", f"Search Path is ready: {normalized}", normalized)

    home = str(tlo_home or "").strip()
    if not home:
        return ValidationStatus("error", "TLOHome is not set, so toBeInventoried.txt cannot be found.")
    inventory_file = os.path.join(home, "toBeInventoried.txt")
    if not os.path.isfile(inventory_file):
        return ValidationStatus("error", f"Search Path is blank and inventory file is missing: {inventory_file}")
    try:
        items = _parse_inventory_file(inventory_file)
    except Exception as exc:
        return ValidationStatus("error", f"Inventory file is not valid: {exc}", inventory_file)
    if not items:
        return ValidationStatus("error", f"Inventory file contains no usable paths: {inventory_file}", inventory_file)
    return ValidationStatus("ok", f"Using {len(items)} path(s) from {inventory_file}", inventory_file)


def validate_optional_destination(value: str, label: str) -> ValidationStatus:
    raw = str(value or "").strip()
    if not raw:
        return ValidationStatus("ok", f"{label} is not selected.")
    try:
        normalized = _normalize_input_path(_strip_optional_quotes(raw))
    except Exception as exc:
        return ValidationStatus("error", str(exc))
    if not os.path.isabs(normalized):
        return ValidationStatus("error", f"{label} must be fully qualified.", normalized)
    if not os.path.isdir(normalized):
        return ValidationStatus("error", f"{label} must be an existing directory: {normalized}", normalized)
    if not os.access(normalized, os.W_OK):
        return ValidationStatus("error", f"{label} is not writable: {normalized}", normalized)
    return ValidationStatus("ok", f"{label} is ready: {normalized}", os.path.normpath(normalized))


def validate_tag_path(value: str) -> ValidationStatus:
    raw = str(value or "").strip()
    if not raw:
        return ValidationStatus("error", "Choose a Tagging Path.")
    try:
        normalized = _normalize_input_path(_strip_optional_quotes(raw))
    except Exception as exc:
        return ValidationStatus("error", str(exc))
    if not os.path.isabs(normalized):
        return ValidationStatus("error", "Tagging Path must be fully qualified.", normalized)
    if not os.path.isdir(normalized):
        return ValidationStatus("error", f"Tagging Path does not exist: {normalized}", normalized)
    try:
        os.listdir(normalized)
    except OSError as exc:
        return ValidationStatus("error", f"Tagging Path cannot be read: {exc}", normalized)
    return ValidationStatus("ok", f"Tagging Path is ready: {normalized}", os.path.normpath(normalized))


def _yes_no(value: object) -> str:
    return "Yes" if bool(value) else "No"


MAIN_WINDOW_CHECKBOX_SPECS = (
    ("etree_lookup", "etreeDB"),
    ("compliant", "Compliant"),
    ("tag_during_inventory", "Tag in Place"),
    ("artist_in_album", "Artist in Album Tag"),
    ("setlistfm_lookup", "setlist.fm"),
    ("setlistfm_upgrade", "setlist.fm upgrade"),
    ("rename_compliantly", "Rename Compliantly"),
    ("tag_copy_during_inventory", "Tag Copy"),
    ("convert_shn", "Convert shn"),
    ("as_is_artist_name", "As-Is Artist Name"),
    ("tag_copy_and_delete_enabled", "Tag Copy/Delete Original"),
    ("dry_run", "Dry run"),
)


def main_window_checkbox_values(source, *, dry_run=None) -> dict[str, bool]:
    """Return the current main-window checkbox values from a dict or config object."""
    def read(name, default=False):
        if isinstance(source, dict):
            return source.get(name, default)
        return getattr(source, name, default)

    tag_copy = read("main_window_tag_copy_selected", read("tag_copy_during_inventory", False))
    copy_delete = read(
        "main_window_tag_copy_delete_selected",
        read("tag_copy_and_delete_enabled", bool(read("tag_copy_and_delete_path", ""))),
    )
    values = {
        "etree_lookup": bool(read("etree_lookup", False)),
        "compliant": bool(read("compliant", False)),
        "tag_during_inventory": bool(read("tag_during_inventory", False)),
        "artist_in_album": bool(read("artist_in_album", True)),
        "setlistfm_lookup": bool(read("setlistfm_lookup", False)),
        "setlistfm_upgrade": bool(read("setlistfm_upgrade", False)),
        "rename_compliantly": bool(read("rename_compliantly", False)),
        "tag_copy_during_inventory": bool(tag_copy),
        "convert_shn": bool(read("convert_shn", False)),
        "as_is_artist_name": bool(read("as_is_artist_name", False)),
        "tag_copy_and_delete_enabled": bool(copy_delete),
        "dry_run": bool(read("main_window_dry_run", False) if dry_run is None else dry_run),
    }
    return values


def main_window_checkbox_review_lines(source, *, dry_run=None) -> list[str]:
    """Format every main-window checkbox consistently for all review dialogs."""
    values = main_window_checkbox_values(source, dry_run=dry_run)
    lines = ["Main-window checkbox values:"]
    lines.extend(f"  {label}: {_yes_no(values[field])}" for field, label in MAIN_WINDOW_CHECKBOX_SPECS)
    return lines


def operation_review_lines(
    config,
    *,
    operation: str,
    path_text: str = "",
    dry_run=None,
    main_checkbox_source=None,
    original_files_may_change=None,
) -> list[str]:
    """Build a consistent review summary for Inventory, Tag, and Add Shows."""
    operation_name = str(operation or "Operation")
    lines = [f"Operation: {operation_name}"]
    if path_text:
        lines.append(f"Path: {path_text}")
    elif str(getattr(config, "search_path_override", "") or "").strip():
        lines.append(f"Search Path: {getattr(config, 'search_path_override', '')}")
    else:
        lines.append(f"Search Paths: {os.path.join(getattr(config, 'TLOHome', ''), 'toBeInventoried.txt')}")

    lines.extend(main_window_checkbox_review_lines(main_checkbox_source or config, dry_run=dry_run))

    operation_folded = operation_name.casefold()
    if operation_folded.startswith("tag"):
        lines.append("Standalone Tag behavior: tags the selected path directly; inventory copy modes are not used.")
    elif operation_folded.startswith("add shows"):
        lines.append("Add Shows behavior: inventory copy modes are reported but are not used by Add Shows.")
    else:
        lines.append(
            f"Performance: {getattr(config, 'performance_mode', 'balanced')} / "
            f"max workers {getattr(config, 'max_workers', 0)}"
        )
        lines.append(f"Acceptable corruption %: {int(getattr(config, 'acceptable_corruption_percent', 100) or 0)}")
        copy_delete = str(getattr(config, "tag_copy_and_delete_path", "") or "").strip()
        destination = str(getattr(config, "tag_copy_destination", "") or copy_delete).strip()
        if destination:
            lines.append(f"Copy destination: {destination}")

    is_dry_run = main_window_checkbox_values(main_checkbox_source or config, dry_run=dry_run)["dry_run"]
    if original_files_may_change is None:
        changes_originals = (not is_dry_run) and bool(
            getattr(config, "rename_compliantly", False)
            or getattr(config, "convert_shn", False)
            or getattr(config, "tag_during_inventory", False)
            or getattr(config, "tag_copy_and_delete_path", "")
            or operation_folded.startswith("tag")
            or operation_folded.startswith("add shows - process new")
        )
    else:
        changes_originals = (not is_dry_run) and bool(original_files_may_change)
    lines.append(f"Original files may be changed: {_yes_no(changes_originals)}")
    return lines


def _inventory_roots(config) -> list[tuple[str, str, str]]:
    """Return (root, copy_mode, copy_destination) without mutating inventory state."""
    override = str(getattr(config, "search_path_override", "") or "").strip()
    if override:
        _volume, raw_path = _split_optional_volume_prefix(_strip_optional_quotes(override))
        normalized = _normalize_input_path(raw_path)
        copy_mode = ""
        copy_destination = ""
        if str(getattr(config, "search_path_copy_override", "") or "").strip():
            copy_mode = "copy"
            copy_destination = _normalize_input_path(str(getattr(config, "search_path_copy_override", "")))
        elif str(getattr(config, "search_path_copy_delete_override", "") or "").strip():
            copy_mode = "copy-delete"
            copy_destination = _normalize_input_path(str(getattr(config, "search_path_copy_delete_override", "")))
        return [(os.path.normpath(normalized), copy_mode, copy_destination)]

    inventory_file = os.path.join(getattr(config, "TLOHome", ""), "toBeInventoried.txt")
    roots: list[tuple[str, str, str]] = []
    for item in _parse_inventory_file(inventory_file):
        normalized = item[1]
        copy_mode = item[4] if len(item) > 4 else ""
        copy_destination = item[5] if len(item) > 5 else ""
        roots.append((os.path.normpath(normalized), copy_mode, copy_destination))
    return roots


def _preview_actions(config, *, copy_mode: str = "", tagger: bool = False, shn_count: int = 0) -> tuple[str, ...]:
    actions: list[str] = []
    if tagger:
        actions.append("write audio tags")
    elif bool(getattr(config, "tag_during_inventory", False)):
        actions.append("write audio tags in place")
    elif bool(getattr(config, "tag_copy_during_inventory", False)):
        actions.append("copy folder and tag copy")
    elif str(getattr(config, "tag_copy_and_delete_path", "") or "").strip():
        actions.append("move folder on the same partition; otherwise copy, verify file sizes, then remove original")
    elif copy_mode == "copy":
        actions.append("copy folder")
    elif copy_mode == "copy-delete":
        actions.append("move folder on the same partition; otherwise copy, verify file sizes, then remove original")
    else:
        actions.append("inventory only")

    if bool(getattr(config, "rename_compliantly", False)):
        actions.append("rename to resolved compliant show name")
    if bool(getattr(config, "convert_shn", False)) and shn_count:
        actions.append("convert SHN to FLAC and remove verified SHN source")
    return tuple(actions)


class _PreviewLogSink:
    """Minimal log surface used by inventory discovery during a dry run."""

    def __init__(self, complete_path_file: str, issue_callback=None):
        self.paths = SimpleNamespace(complete_paths=complete_path_file)
        self.issue_callback = issue_callback

    def complete_paths(self, message, *args):
        text = message % args if args else str(message)
        with open(self.paths.complete_paths, "a", encoding="utf-8", newline="\n") as outfile:
            outfile.write(text.rstrip("\r\n") + "\n")

    def dead_end(self, message, *args):
        text = message % args if args else str(message)
        if self.issue_callback:
            self.issue_callback("Inaccessible path", text)

    def duplicate(self, message, *args):
        text = message % args if args else str(message)
        if self.issue_callback:
            self.issue_callback("Duplicate discovery path", text)

    def groups(self, *_args, **_kwargs):
        return None

    def conflicts(self, *_args, **_kwargs):
        return None

    def show_metadata(self, *_args, **_kwargs):
        return None

    def tag_success(self, *_args, **_kwargs):
        return None

    def tag_error(self, *_args, **_kwargs):
        return None

    def tag(self, *_args, **_kwargs):
        return None


def _preview_config_for_root(config, root: str, complete_path_file: str, result: PreviewResult):
    from logging_lib import ARTIST_SQLITE_DB_FILENAME, TLO_DBS_DIRNAME, VENUE_REFERENCE_DB_FILENAME

    preview_config = copy.copy(config)
    preview_config.current_search_path = os.path.normpath(root)
    preview_config.current_search_index = 1
    preview_config.current_slam = ""
    preview_config.current_volume_label = ""
    preview_config.current_volume_key = ""
    preview_config.current_log_token = "P"
    preview_config.current_metadata_records = []
    preview_config.active_search_paths = []
    preview_config.current_run_log_tokens = []

    def add_discovery_issue(category: str, message: str) -> None:
        result.issues.append(RunIssue(category, message, root, "warning", "preview"))

    preview_config.logs = _PreviewLogSink(complete_path_file, add_discovery_issue)
    if not str(getattr(preview_config, "artist_sqlite_db_file", "") or "").strip():
        preview_config.artist_sqlite_db_file = os.path.join(
            preview_config.TLOHome, TLO_DBS_DIRNAME, ARTIST_SQLITE_DB_FILENAME
        )
    if not str(getattr(preview_config, "venue_reference_db_file", "") or "").strip():
        preview_config.venue_reference_db_file = os.path.join(
            preview_config.TLOHome, TLO_DBS_DIRNAME, VENUE_REFERENCE_DB_FILENAME
        )
    return preview_config


def _include_tag_details(config, *, tagger: bool) -> bool:
    return bool(
        tagger
        or getattr(config, "tag_during_inventory", False)
        or getattr(config, "tag_copy_during_inventory", False)
        or str(getattr(config, "tag_copy_and_delete_path", "") or "").strip()
    )


def preview_operation(
    config,
    *,
    operation: str,
    tag_path: str = "",
    sample_limit: Optional[int] = None,
    cancel_check=None,
) -> PreviewResult:
    """Resolve show metadata and planned tags without changing user content."""
    from initial_dir_walk_lib import initial_dir_walk
    from tlo_artist_db import load_artist_matcher
    from tlo_phase23_v2 import _build_groups_from_search_path
    from tlo_tag_lib import build_dry_run_group_plan

    started = time.monotonic()
    result = PreviewResult(operation=operation)
    tagger = operation.casefold().startswith("tag")
    if tagger:
        status = validate_tag_path(tag_path)
        if not status.valid:
            result.issues.append(RunIssue("Invalid path", status.message, tag_path, "error", "preview"))
            result.elapsed_seconds = time.monotonic() - started
            return result
        roots = [(status.normalized, "", "")]
    else:
        try:
            roots = _inventory_roots(config)
        except Exception as exc:
            result.issues.append(RunIssue("Invalid inventory input", str(exc), "", "error", "preview"))
            result.elapsed_seconds = time.monotonic() - started
            return result

    result.roots = [root for root, _mode, _destination in roots]
    include_tags = _include_tag_details(config, tagger=tagger)

    for root, copy_mode, _copy_destination in roots:
        if cancel_check and cancel_check():
            result.issues.append(RunIssue("Preview cancelled", "Preview was cancelled.", root, "warning", "preview"))
            break
        if not os.path.isdir(root):
            result.issues.append(RunIssue("Inaccessible path", "Directory does not exist or is not accessible.", root, "error", "preview"))
            continue

        try:
            with tempfile.TemporaryDirectory(prefix="tlo-dry-run-") as temp_dir:
                complete_path_file = os.path.join(temp_dir, "compP.log")
                Path(complete_path_file).touch()
                preview_config = _preview_config_for_root(config, root, complete_path_file, result)
                initial_dir_walk(preview_config, root)
                groups = _build_groups_from_search_path(preview_config, root)
                try:
                    artist_matcher = load_artist_matcher(preview_config)
                except Exception as exc:
                    artist_matcher = None
                    result.issues.append(RunIssue(
                        "Artist database unavailable",
                        f"Artist master-name matching was skipped during this dry run: {exc}",
                        root,
                        "warning",
                        "preview",
                    ))

                for group_number, group in enumerate(groups, start=1):
                    if cancel_check and cancel_check():
                        result.issues.append(RunIssue("Preview cancelled", "Preview was cancelled.", root, "warning", "preview"))
                        break
                    group["group_number"] = group_number
                    plan = build_dry_run_group_plan(
                        preview_config,
                        group,
                        artist_matcher,
                        include_tags=include_tags,
                        standalone_tagger=tagger,
                    )
                    audio_files = list(plan.get("audio_files", []) or [])
                    shn_count = int(plan.get("shn_files", 0) or 0)
                    music_dirs = list(group.get("music_dirs", []) or [])
                    result.music_folders += max(1, len(music_dirs))
                    result.media_files += len(audio_files)
                    result.shn_files += shn_count
                    actions = _preview_actions(preview_config, copy_mode=copy_mode, tagger=tagger, shn_count=shn_count)
                    if not tagger:
                        try:
                            from tlo_corruption import classify_audio_paths, corruption_action, fully_corrupt_music_dirs, group_audio_snapshot
                            corruption_audio, snapshot_errors = group_audio_snapshot(group)
                            corruption_bad, unverifiable_files = classify_audio_paths(corruption_audio)
                            corruption_limit = int(getattr(preview_config, "acceptable_corruption_percent", 100) or 0)
                            unverifiable = list(snapshot_errors) + list(unverifiable_files)
                            corruption_policy = "unverifiable" if unverifiable else corruption_action(len(corruption_audio), len(corruption_bad), corruption_limit)
                            pct = (100.0 * len(corruption_bad) / len(corruption_audio)) if corruption_audio else 0.0
                            if corruption_policy == "unverifiable":
                                actions = tuple(actions) + (f"CORRUPTION_UNVERIFIABLE ({len(unverifiable)} read/validator error(s); WOULD_NOT_TRASH; mutation steps would be skipped)",)
                            if corruption_policy == "trash_folder_all_corrupt":
                                actions = tuple(actions) + (f"WOULD_TRASH_CORRUPT_FOLDER ({len(corruption_bad)}/{len(corruption_audio)} = {pct:.2f}%; all audio corrupt; acceptable setting ignored)",)
                            elif corruption_policy == "trash_folder_threshold":
                                actions = tuple(actions) + (f"WOULD_TRASH_CORRUPT_FOLDER ({len(corruption_bad)}/{len(corruption_audio)} = {pct:.2f}% > {corruption_limit}%)",)
                            elif corruption_policy == "trash_corrupt_files":
                                all_bad_dirs = fully_corrupt_music_dirs(group, corruption_audio, corruption_bad)
                                if all_bad_dirs:
                                    labels = ", ".join(os.path.basename(os.path.normpath(path)) or os.path.normpath(path) for path in all_bad_dirs)
                                    actions = tuple(actions) + (f"WOULD_TRASH_ALL_CORRUPT_MUSIC_FOLDER(S) ({len(all_bad_dirs)}: {labels}; acceptable setting does not protect an all-corrupt folder)",)
                                bad_dir_keys = {os.path.normcase(os.path.normpath(path)) for path in all_bad_dirs}
                                remaining_bad = [path for path in corruption_bad if os.path.normcase(os.path.normpath(os.path.dirname(path))) not in bad_dir_keys]
                                if remaining_bad:
                                    actions = tuple(actions) + (f"WOULD_TRASH_CORRUPT_FILES ({len(remaining_bad)} file(s); overall {pct:.2f}% <= {corruption_limit}%)",)
                        except Exception as exc:
                            result.issues.append(RunIssue("Corruption dry-run check failed", str(exc), str(group.get("main_dir_path") or root), "warning", "preview"))
                    tags = [PreviewTag(**entry) for entry in (plan.get("tags", []) or [])]
                    item = PreviewItem(
                        path=os.path.normpath(str(plan.get("folder") or group.get("main_dir_path") or root)),
                        media_files=len(audio_files),
                        shn_files=shn_count,
                        actions=actions,
                        show_name=str(plan.get("show_name") or ""),
                        artist=str(plan.get("artist") or ""),
                        album=str(plan.get("album") or ""),
                        track_source=str(plan.get("track_source") or ""),
                        tags=tags,
                        notes=tuple(str(value) for value in (plan.get("notes", []) or []) if str(value).strip()),
                        unresolved=tuple(str(value) for value in (plan.get("unresolved", []) or []) if str(value).strip()),
                    )
                    if sample_limit is None or sample_limit <= 0 or len(result.samples) < sample_limit:
                        result.samples.append(item)
                    else:
                        result.truncated = True
                    for issue_text in plan.get("issues", []) or []:
                        result.issues.append(RunIssue("Dry-run analysis", str(issue_text), item.path, "warning", "preview"))
        except Exception as exc:
            result.issues.append(RunIssue("Dry-run analysis failed", str(exc), root, "error", "preview"))

    result.elapsed_seconds = time.monotonic() - started
    return result



def preview_add_shows(
    config,
    *,
    mode: str = "new",
    check_duplicates: bool = True,
    sample_limit: int = 30,
    cancel_check=None,
) -> PreviewResult:
    """Resolve Add Shows metadata and planned tags without changing content."""
    from tlo_artist_db import load_artist_matcher
    from tlo_inventory_update import (
        _build_single_folder_group,
        _apply_pdup_marker,
        _metadata_to_record_dict,
        _next_pdup_number,
        _record_dict_for_new_folder,
        find_potential_duplicate_rows_for_folder,
        potential_duplicate_matches_are_remote_only,
    )
    from tlo_postprocess import _adjust_show_name_for_output
    from tlo_tag_lib import _album_for_record, build_dry_run_group_plan

    started = time.monotonic()
    duplicate_mode = str(mode or "new").strip().lower().startswith("dup")
    operation = "Add Shows - Potential Duplicate/Upgrades Dry Run" if duplicate_mode else "Add Shows - New Shows Dry Run"
    result = PreviewResult(operation=operation)
    source_name = "dups" if duplicate_mode else "readyForXfer"
    root = os.path.join(str(getattr(config, "TLOHome", "") or ""), source_name)
    result.roots = [os.path.normpath(root)]
    if not os.path.isdir(root):
        result.issues.append(RunIssue("Inaccessible path", f"Add Shows source directory does not exist: {root}", root, "error", "preview"))
        result.elapsed_seconds = time.monotonic() - started
        return result

    try:
        artist_matcher = load_artist_matcher(config)
    except Exception as exc:
        artist_matcher = None
        result.issues.append(RunIssue(
            "Artist database unavailable",
            f"Artist master-name matching was skipped during this dry run: {exc}",
            root,
            "warning",
            "preview",
        ))

    try:
        top_level = sorted(
            (entry for entry in os.scandir(root) if entry.is_dir(follow_symlinks=False)),
            key=lambda entry: entry.name.casefold(),
        )
    except OSError as exc:
        result.issues.append(RunIssue("Read error", str(exc), root, "error", "preview"))
        result.elapsed_seconds = time.monotonic() - started
        return result

    tag_enabled = bool(getattr(config, "tag_during_inventory", False))
    convert_only = bool(getattr(config, "convert_shn", False)) and not tag_enabled
    include_file_details = tag_enabled or convert_only

    for entry in top_level:
        if cancel_check and cancel_check():
            result.issues.append(RunIssue("Dry run cancelled", "Dry run was cancelled.", entry.path, "warning", "preview"))
            break
        try:
            group = _build_single_folder_group(config, entry.path)
            plan = build_dry_run_group_plan(
                config,
                group,
                artist_matcher,
                include_tags=include_file_details,
                standalone_tagger=False,
            )
            record = plan.pop("_record", None)
            if record is None:
                raise RuntimeError("Unable to resolve Add Shows metadata for dry run")
            if duplicate_mode:
                record_dict = _metadata_to_record_dict(record)
            else:
                record_dict = _record_dict_for_new_folder(config, entry.path, record, artist_matcher)
            matches = find_potential_duplicate_rows_for_folder(config, entry.path, record, artist_matcher) if (duplicate_mode or check_duplicates) else []
            remote_pdup_marker = ""
            if (
                not duplicate_mode
                and check_duplicates
                and matches
                and potential_duplicate_matches_are_remote_only(matches, str(getattr(config, "current_volume_label", "") or ""))
            ):
                remote_pdup_marker = _apply_pdup_marker(record_dict, _next_pdup_number(matches))
            final_show_name = _adjust_show_name_for_output(record_dict)
            plan["show_name"] = final_show_name
            final_artist = str(record_dict.get("artist") or plan.get("artist") or "")
            final_album = _album_for_record(config, SimpleNamespace(**record_dict))
            plan["artist"] = final_artist
            plan["album"] = final_album
            for tag in plan.get("tags", []) or []:
                tag["artist"] = final_artist or tag.get("artist", "")
                tag["album"] = final_album or tag.get("album", "")
                if convert_only:
                    is_shn = os.path.splitext(str(tag.get("source_path") or ""))[1].lower() in {".shn", ".shnf"}
                    if is_shn and str(tag.get("action") or "").startswith("would convert"):
                        tag["action"] = "would convert to FLAC; no tags written"
                        tag["artist"] = ""
                        tag["album"] = ""
                        tag["track"] = ""
                        tag["title"] = ""
                    else:
                        tag["action"] = "would not tag"
                        tag["reason"] = "Convert shn is enabled without Tag in Place"
                        tag["artist"] = ""
                        tag["album"] = ""
                        tag["track"] = ""
                        tag["title"] = ""

            audio_files = list(plan.get("audio_files", []) or [])
            shn_count = int(plan.get("shn_files", 0) or 0)
            music_dirs = list(group.get("music_dirs", []) or [])
            result.music_folders += max(1, len(music_dirs))
            result.media_files += len(audio_files)
            result.shn_files += shn_count

            actions: list[str] = ["identify show metadata"]
            notes = [str(value) for value in (plan.get("notes", []) or []) if str(value).strip()]
            if matches:
                match_names = [str(row.get("Show") or "").strip() for row in matches if str(row.get("Show") or "").strip()]
                notes.append(f"Potential bootlist matches: {len(matches)}" + (f" - {'; '.join(match_names)}" if match_names else ""))
            if duplicate_mode:
                actions.append("prepare duplicate/upgrade review")
                actions.append("leave folders unchanged during this scan")
            elif check_duplicates and matches and remote_pdup_marker:
                actions.append(f"mark show {remote_pdup_marker}; existing potential matches are on another partition")
                actions.append("add resulting show to bootlist.csv without unavailable cross-partition comparison")
                if bool(getattr(config, "rename_compliantly", False)):
                    actions.append("rename folder to resulting pdup show name")
                if bool(getattr(config, "convert_shn", False)) and shn_count:
                    actions.append("convert SHN to FLAC and remove verified SHN source")
                if tag_enabled:
                    actions.append("write tags in place")
                actions.append("move accepted pdup folder to staged")
            elif check_duplicates and matches:
                actions.append("move folder to dups as a potential duplicate")
            else:
                actions.append("add resulting show to bootlist.csv")
                if bool(getattr(config, "rename_compliantly", False)):
                    actions.append("rename folder to resulting show name")
                if bool(getattr(config, "convert_shn", False)) and shn_count:
                    actions.append("convert SHN to FLAC and remove verified SHN source")
                if tag_enabled:
                    actions.append("write tags in place")
                actions.append("move accepted folder to staged")

            tags = [PreviewTag(**tag) for tag in (plan.get("tags", []) or [])]
            item = PreviewItem(
                path=os.path.normpath(entry.path),
                media_files=len(audio_files),
                shn_files=shn_count,
                actions=tuple(actions),
                show_name=final_show_name,
                artist=final_artist,
                album=final_album,
                track_source=str(plan.get("track_source") or ""),
                tags=tags,
                notes=tuple(notes),
                unresolved=tuple(str(value) for value in (plan.get("unresolved", []) or []) if str(value).strip()),
            )
            if len(result.samples) < sample_limit:
                result.samples.append(item)
            else:
                result.truncated = True
            for issue_text in plan.get("issues", []) or []:
                result.issues.append(RunIssue("Dry-run analysis", str(issue_text), item.path, "warning", "preview"))
        except Exception as exc:
            result.issues.append(RunIssue("Dry-run analysis failed", str(exc), entry.path, "error", "preview"))

    result.elapsed_seconds = time.monotonic() - started
    return result

def format_preview(result: PreviewResult) -> str:
    heading = "DRY RUN - no files were changed"
    lines = [
        heading,
        "",
        f"Operation: {result.operation}",
        f"Search roots: {len(result.roots)}",
        f"Music folders found: {result.music_folders}",
        f"Media files found: {result.media_files}",
        f"SHN/SHNF files found: {result.shn_files}",
        f"Dry-run issues: {len(result.issues)}",
        f"Elapsed: {format_elapsed(result.elapsed_seconds)}",
    ]
    if result.roots:
        lines.extend(["", "Roots:"])
        lines.extend(f"  {root}" for root in result.roots)
    if result.samples:
        lines.extend(["", "Resolved work by show:"])
        for item in result.samples:
            action_text = "; ".join(item.actions)
            lines.append("")
            lines.append(f"Folder: {item.path}")
            lines.append(f"Resulting show name: {item.show_name or '[unable to determine]'}")
            lines.append(f"Media files: {item.media_files} | SHN/SHNF: {item.shn_files}")
            lines.append(f"Planned action: {action_text}")
            if item.unresolved:
                lines.append(f"Unresolved metadata: {'; '.join(item.unresolved)}")
            if item.tags:
                lines.append(f"Tag title source: {item.track_source or 'not determined'}")
                lines.append("Planned file tags:")
                for tag in item.tags:
                    display_path = tag.source_path
                    if tag.target_path and os.path.normpath(tag.target_path) != os.path.normpath(tag.source_path):
                        display_path = f"{tag.source_path} -> {tag.target_path}"
                    lines.append(f"  File: {display_path}")
                    lines.append(f"    Action: {tag.action}" + (f" | {tag.reason}" if tag.reason else ""))
                    if tag.track or tag.title or tag.action not in {"would skip", "would not tag"}:
                        lines.append(f"    Artist: {tag.artist or 'Unknown'}")
                        lines.append(f"    Album: {tag.album or 'Unknown'}")
                        lines.append(f"    Track: {tag.track or '[not written]'}")
                        lines.append(f"    Title: {tag.title or '[not written]'}")
            elif item.artist or item.album:
                lines.append(f"Resolved artist: {item.artist or '[unable to determine]'}")
                lines.append(f"Resolved album: {item.album or '[unable to determine]'}")
            if item.notes:
                lines.append("Analysis notes:")
                lines.extend(f"  {note}" for note in item.notes)
        if result.truncated:
            lines.append("  ... additional shows omitted from this display")
    if result.issues:
        lines.extend(["", "Issues:"])
        for issue in result.issues:
            path_text = f" | {issue.path}" if issue.path else ""
            lines.append(f"  {issue.severity.upper()} {issue.category}: {issue.message}{path_text}")
    return "\n".join(lines) + "\n"


def format_elapsed(seconds: float) -> str:
    total = max(0, int(round(float(seconds or 0))))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:d}:{secs:02d}"


_PATH_AFTER_PREFIX_RE = re.compile(r"^(?:WARN|ERROR|INFO|[A-Z][A-Z0-9_]+):\s*(.*?)\s*\|\s*(.*)$")


def _extract_path_from_line(line: str) -> str:
    match = _PATH_AFTER_PREFIX_RE.match(line.strip())
    if match:
        possible = match.group(1).strip()
        if possible and (os.path.isabs(possible) or re.match(r"^[A-Za-z]:[\\/]", possible)):
            return possible
    for marker in ("Search path complete:", "Queued search path "):
        if marker in line:
            tail = line.split(marker, 1)[1].strip()
            if marker.endswith("path ") and ":" in tail:
                tail = tail.split(":", 1)[1].strip()
            return tail.split(" | ", 1)[0].strip()
    return ""


def classify_issue_line(line: str) -> Optional[RunIssue]:
    text = str(line or "").strip()
    if not text:
        return None
    upper = text.upper()
    severity = "warning"
    category = "Warning"
    if upper.startswith("ERROR:") or "_ERROR:" in upper or upper.startswith("TAG_FILE_ERROR:"):
        severity = "error"
        category = "File or operation error"
    if "UNIDENTIFIED" in upper or "SHOW NAME NOT DETERMINED" in upper:
        category = "Unidentified show"
    elif "NO SETLIST" in upper or "SETLIST" in upper and ("MISSING" in upper or "NOT FOUND" in upper):
        category = "Missing setlist"
    elif "TRACK" in upper and ("MISMATCH" in upper or "UNKNOWN" in upper or "SKIPPED" in upper):
        category = "Track-title mismatch"
    elif "CORRUPT" in upper or "UNREADABLE" in upper or "FAILED TO OPEN" in upper:
        category = "Unreadable audio"
    elif "COPY" in upper and ("FAILED" in upper or "VERIFY" in upper or "CAPACITY" in upper):
        category = "Copy or verification problem"
    elif "LOOKUP" in upper and ("FAILED" in upper or "NO USABLE" in upper):
        category = "Online lookup problem"
    elif upper.startswith("WARN:") or upper.startswith("WARN_SUMMARY:"):
        category = "Tagging warning"
    elif severity != "error":
        return None
    return RunIssue(category, text, _extract_path_from_line(text), severity, "run")


class RunMonitor:
    """Convert existing console messages into a structured GUI status snapshot."""

    def __init__(self, operation: str):
        self.operation = operation
        self.started = time.monotonic()
        self.snapshot = RunSnapshot(stage="Preparing")
        self.issues: list[RunIssue] = []
        self._issue_keys: set[tuple[str, str, str, str]] = set()
        self._queued_roots: set[str] = set()
        self.last_lines: list[str] = []

    def add_issue(self, issue: RunIssue) -> None:
        if issue.key in self._issue_keys:
            return
        self._issue_keys.add(issue.key)
        self.issues.append(issue)
        if issue.severity == "error":
            self.snapshot.errors += 1
        else:
            self.snapshot.warnings += 1

    def feed(self, text: str) -> RunSnapshot:
        for raw_line in str(text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            self.last_lines.append(line)
            if len(self.last_lines) > 100:
                del self.last_lines[:-100]
            self._feed_line(line)
        self.snapshot.elapsed_seconds = time.monotonic() - self.started
        return self.snapshot

    def _feed_line(self, line: str) -> None:
        lower = line.casefold()
        if lower.startswith("inventory request accepted"):
            self.snapshot.stage = "Preparing inventory"
        elif lower.startswith("starting tlo-gi") or lower == "starting inventory":
            self.snapshot.stage = "Starting inventory"
        elif lower.startswith("inventory roots loaded:"):
            self.snapshot.stage = "Validating roots"
            match = re.search(r"(\d+) accessible", line)
            if match:
                self.snapshot.roots_total = int(match.group(1))
        elif lower.startswith("queued search path"):
            self.snapshot.stage = "Queued"
            queued_path = _extract_path_from_line(line)
            if queued_path:
                self._queued_roots.add(os.path.normcase(os.path.normpath(queued_path)))
            if not self.snapshot.roots_total:
                self.snapshot.roots_total = len(self._queued_roots)
            self.snapshot.current_item = queued_path
        elif lower.startswith("stage 2 complete"):
            self.snapshot.stage = "Analyzing shows"
            self.snapshot.current_item = line.split(":", 1)[1].split(" | ", 1)[0].strip() if ":" in line else ""
        elif lower.startswith("stage 3 starting"):
            self.snapshot.stage = "Resolving metadata and tagging"
            self.snapshot.current_item = line.split(":", 1)[1].strip() if ":" in line else ""
        elif lower.startswith("search path complete:"):
            self.snapshot.stage = "Scanning"
            self.snapshot.roots_completed += 1
            self.snapshot.current_item = _extract_path_from_line(line)
            match = re.search(r"directories identified:\s*(\d+)", line, re.I)
            if match:
                self.snapshot.directories += int(match.group(1))
            match = re.search(r"show groups processed:\s*(\d+)", line, re.I)
            if match:
                self.snapshot.show_groups += int(match.group(1))
        elif lower.startswith("totals: directories identified:"):
            self.snapshot.stage = "Finishing scan"
            match = re.search(r"directories identified:\s*(\d+)", line, re.I)
            if match:
                self.snapshot.directories = int(match.group(1))
            match = re.search(r"show groups processed:\s*(\d+)", line, re.I)
            if match:
                self.snapshot.show_groups = int(match.group(1))
        elif lower.startswith("inventory phase complete"):
            self.snapshot.stage = "Aggregating results"
        elif lower.startswith("postprocess:"):
            self.snapshot.stage = line.split(":", 1)[1].strip().capitalize()
        elif lower.startswith("cleanup, aggregation"):
            self.snapshot.stage = "Finalizing"
        elif lower.startswith("starting tlo tagger"):
            self.snapshot.stage = "Starting tagger"
        elif lower.startswith("tagging path:"):
            self.snapshot.stage = "Scanning tagging path"
            self.snapshot.current_item = line.split(":", 1)[1].strip()
        elif lower.startswith("complete: folders="):
            self.snapshot.stage = "Complete"
            self.snapshot.completed = True
            self.snapshot.success = self.snapshot.errors == 0
            for field_name, key in (
                ("folders", "folders"),
                ("tagged_files", "tagged_files"),
                ("skipped_folders", "skipped_folders"),
                ("errors", "file_errors"),
            ):
                match = re.search(rf"{re.escape(key)}=(\d+)", line)
                if match:
                    setattr(self.snapshot, field_name, int(match.group(1)))
        elif lower.startswith("elapsed time:"):
            self.snapshot.stage = "Complete" if self.snapshot.completed else self.snapshot.stage
        else:
            path = _extract_path_from_line(line)
            if path:
                self.snapshot.current_item = path

        issue = classify_issue_line(line)
        if issue:
            self.add_issue(issue)

    def finish(self, *, success: bool) -> RunSnapshot:
        self.snapshot.elapsed_seconds = time.monotonic() - self.started
        self.snapshot.completed = True
        self.snapshot.success = bool(success)
        self.snapshot.stage = "Complete" if success else "Stopped with errors"
        return self.snapshot

    def completion_text(self) -> str:
        snap = self.snapshot
        lines = [
            f"{self.operation} {'completed' if snap.success else 'did not complete successfully'}.",
            "",
            f"Elapsed time: {format_elapsed(snap.elapsed_seconds)}",
        ]
        if self.operation.casefold().startswith("tag"):
            lines.extend([
                f"Folders processed: {snap.folders}",
                f"Files tagged: {snap.tagged_files}",
                f"Skipped folders: {snap.skipped_folders}",
            ])
        else:
            lines.extend([
                f"Search paths completed: {snap.roots_completed}",
                f"Music directories identified: {snap.directories}",
                f"Show groups processed: {snap.show_groups}",
            ])
        lines.extend([
            f"Warnings: {snap.warnings}",
            f"Errors: {snap.errors}",
        ])
        return "\n".join(lines)


def merge_issues(*issue_groups: Iterable[RunIssue]) -> list[RunIssue]:
    merged: list[RunIssue] = []
    seen: set[tuple[str, str, str, str]] = set()
    for group in issue_groups:
        for issue in group:
            if issue.key in seen:
                continue
            seen.add(issue.key)
            merged.append(issue)
    return merged


def collect_current_log_issues(tlo_home: str, tokens: Iterable[str], *, tagger: bool = False) -> list[RunIssue]:
    logs_dir = os.path.join(str(tlo_home or ""), "logs")
    if not os.path.isdir(logs_dir):
        return []
    paths: list[str] = []
    if tagger:
        paths.extend([os.path.join(logs_dir, "tagsT.txt"), os.path.join(logs_dir, "tageT.txt")])
    for token in tokens or []:
        paths.append(os.path.join(logs_dir, f"tage{token}.txt"))
    issues: list[RunIssue] = []
    for path_name in paths:
        if not os.path.isfile(path_name):
            continue
        try:
            with open(path_name, "r", encoding="utf-8", errors="replace") as infile:
                for line in infile:
                    issue = classify_issue_line(line)
                    if issue:
                        issue.source = os.path.basename(path_name)
                        issues.append(issue)
        except OSError:
            continue
    return merge_issues(issues)


def open_path(path_name: str) -> bool:
    target = str(path_name or "").strip()
    if not target:
        return False
    if os.path.isfile(target):
        target_to_open = target
    elif os.path.isdir(target):
        target_to_open = target
    else:
        parent = os.path.dirname(target)
        if not parent or not os.path.isdir(parent):
            return False
        target_to_open = parent
    try:
        if os.name == "nt":
            os.startfile(target_to_open)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", target_to_open])
        else:
            subprocess.Popen(["xdg-open", target_to_open])
        return True
    except Exception:
        return False


def issue_group_counts(issues: Iterable[RunIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.category] = counts.get(issue.category, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())))
