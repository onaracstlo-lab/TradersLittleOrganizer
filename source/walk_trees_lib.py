__version__ = "v334"
# TLO-GI package version: v334
__version_summary__ = 'Rearranges the main-window checkboxes into the requested two-row, four-column layout.'
# TLO-GI version summary: Rearranges the main-window checkboxes into the requested two-row, four-column layout.
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, as_completed
from concurrent.futures.process import BrokenProcessPool


from console_output_lib import console_print
from inventory_list_lib import prepare_inventory_items
from tlo_artist_db import load_artist_matcher
from logging_lib import allocate_log_tokens
from tlo_search_path_runner import run_search_path, run_search_path_group_job
from tlo_volume_label import resolve_physical_drive_id
from tlo_runtime_control import (
    is_cancel_requested,
    register_active_executor,
    unregister_active_executor,
    register_active_pause_proxy,
    unregister_active_pause_proxy,
    normalize_performance_mode,
)


def _config_snapshot(config, force_silent=False):
    return {
        "debug": config.debug,
        "silent": True if force_silent else config.silent,
        "TLOHome": config.TLOHome,
        "logs": None,
        "tlo_dbs_dir": "",
        "artist_sqlite_db_file": "",
        "venue_reference_db_file": "",
        "current_search_path": "",
        "current_search_index": 0,
        "current_slam": "",
        "current_volume_label": "",
        "current_volume_key": "",
        "current_path_copy_destination": "",
        "current_path_copy_delete_destination": "",
        "current_inventory_path": "",
        "search_path_override": "",
        "search_path_slam_override": "",
        "search_path_copy_override": "",
        "search_path_copy_delete_override": "",
        "compliant": config.compliant,
        "tag_during_inventory": getattr(config, "tag_during_inventory", False),
        "tag_copy_during_inventory": getattr(config, "tag_copy_during_inventory", False),
        "tag_copy_destination": getattr(config, "tag_copy_destination", ""),
        "tag_copy_and_delete_path": getattr(config, "tag_copy_and_delete_path", ""),
        "rename_compliantly": getattr(config, "rename_compliantly", False),
        "convert_shn": getattr(config, "convert_shn", False),
        "etree_lookup": config.etree_lookup,
        "setlistfm_lookup": getattr(config, "setlistfm_lookup", False),
        "setlistfm_min_interval_seconds": getattr(config, "setlistfm_min_interval_seconds", 0.600),
        "setlistfm_max_calls": getattr(config, "setlistfm_max_calls", 1400),
        "setlistfm_run_id": getattr(config, "setlistfm_run_id", ""),
        "active_search_paths": [],
        "inventory_complete": False,
        "inventory_scanning_complete": False,
        "current_log_token": "",
        "current_log_mode": "w",
        "active_log_tokens": [],
        "current_run_log_tokens": [],
        "current_metadata_records": [],
        "newly_allocated_log_tokens": [],
        "cancel_requested": False,
        "performance_mode": config.performance_mode,
        "max_workers": config.max_workers,
        "runtime_pause_proxy": getattr(config, "runtime_pause_proxy", None),
        "prepared_inventory_items": [],
        "inventory_volume_actions": dict(getattr(config, "inventory_volume_actions", {}) or {}),
        "volume_action_callback": None,
        "capacity_alert_callback": None,
    }


def _unpack_inventory_item(item):
    path_name, slam_value, volume_label, volume_key = item[:4]
    log_token = item[4] if len(item) > 4 else ""
    log_mode = item[5] if len(item) > 5 else "w"
    copy_mode = item[6] if len(item) > 6 else ""
    copy_destination = item[7] if len(item) > 7 else ""
    inventory_path = item[8] if len(item) > 8 else path_name
    return path_name, slam_value, volume_label, volume_key, log_token, log_mode, copy_mode, copy_destination, inventory_path


def _path_worker_count(config, search_path_count):
    if search_path_count < 2:
        return 1

    mode = normalize_performance_mode(getattr(config, "performance_mode", "balanced"))
    requested_max = int(getattr(config, "max_workers", 0) or 0)
    cpu_count = os.cpu_count() or 1

    if mode == "gentle":
        default_workers = 1
    elif mode == "balanced":
        default_workers = min(2, cpu_count, search_path_count)
    elif mode == "fast":
        default_workers = min(cpu_count, search_path_count)
    else:
        # Extreme is intentionally uncapped by the performance mode itself:
        # one path worker per queued search root unless the user supplies
        # --max-workers/Max Workers to impose an explicit cap.
        default_workers = search_path_count

    if requested_max > 0:
        default_workers = min(default_workers, requested_max, search_path_count)

    return max(1, default_workers)


def _run_serial(config, inventory_items):
    all_metadata_records = []
    total_directories_identified = 0
    total_show_groups_processed = 0
    shared_artist_matcher = None
    for search_index, item in enumerate(inventory_items, start=1):
        path_name, slam_value, volume_label, volume_key, log_token, log_mode, copy_mode, copy_destination, inventory_path = _unpack_inventory_item(item)
        if is_cancel_requested() or getattr(config, "cancel_requested", False):
            raise KeyboardInterrupt
        if not slam_value:
            if shared_artist_matcher is None:
                shared_artist_matcher = load_artist_matcher(config)
            artist_matcher = shared_artist_matcher
        else:
            artist_matcher = None

        result = run_search_path(
            config,
            path_name,
            slam_value,
            search_index,
            volume_label=volume_label,
            volume_key=volume_key,
            log_token=log_token,
            log_mode=log_mode,
            copy_mode=copy_mode,
            copy_destination=copy_destination,
            inventory_path=inventory_path,
            artist_matcher=artist_matcher,
            venue_matcher=None,
        )
        total_directories_identified += result["directory_count"]
        total_show_groups_processed += result["show_group_count"]
        all_metadata_records.extend(result["metadata_records"])

        console_print(
            config,
            f"Search path complete: {path_name} | directories identified: {result['directory_count']} | show groups processed: {result['show_group_count']}",
        )

    return all_metadata_records, total_directories_identified, total_show_groups_processed


def _inventory_item_drive_sort_key(item):
    import re
    path_name = str((item or [""])[0] or "").replace("\\", "/")
    match = re.match(r"^([A-Za-z]):", path_name)
    if match:
        return (0, match.group(1).upper(), path_name.casefold())
    match = re.match(r"^/mnt/([A-Za-z])(?:/|$)", path_name, flags=re.IGNORECASE)
    if match:
        return (0, match.group(1).upper(), path_name.casefold())
    return (1, "", path_name.casefold())


def _canonical_path_key(path_name):
    return os.path.normcase(os.path.normpath(str(path_name or "")))


def _split_serial_and_parallel_items(config, inventory_items):
    """Split roots into blank-label and named-label phases.

    Blank-label roots are deliberately searched one at a time and are run after
    named-volume work. Named roots are eligible for parallel work, but a later
    grouping pass serializes named volumes that are on the same physical disk.
    """
    del config  # retained in the signature for compatibility with older callers/tests
    empty_volume_items = []
    named_volume_items = []
    for item in inventory_items:
        volume_label = str(item[2] or "").strip() if len(item) >= 3 else ""
        if volume_label:
            named_volume_items.append(item)
        else:
            empty_volume_items.append(item)
    empty_volume_items.sort(key=_inventory_item_drive_sort_key)
    return empty_volume_items, named_volume_items


def _group_named_volume_items(inventory_items):
    """Return named-volume item groups in stable input order."""
    groups = {}
    order = []
    for item in inventory_items:
        volume_label = str(item[2] or "").strip() if len(item) >= 3 else ""
        key = volume_label.casefold()
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    return [groups[key] for key in order]


def _physical_drive_key_for_item(item):
    """Return the scheduling-only physical disk key for a search item."""
    path_name = str((item or [""])[0] or "")
    try:
        return (resolve_physical_drive_id(path_name) or "").strip()
    except Exception:
        return ""


def _group_named_volume_items_by_physical_drive(named_volume_items):
    """Group named-volume roots for parallel scheduling.

    Visible volumes still own their normal log identity. This function only
    decides which roots may run concurrently. If two visible volume labels are
    detected on the same physical hard drive, their roots are placed into the
    same work group and therefore run serially inside one worker. If the
    physical disk cannot be detected, the volume keeps the existing one-visible-
    volume-per-worker behavior.
    """
    visible_groups = _group_named_volume_items(named_volume_items)
    physical_groups = {}
    order = []
    for visible_group in visible_groups:
        physical_key = ""
        for item in visible_group:
            physical_key = _physical_drive_key_for_item(item)
            if physical_key:
                break
        if not physical_key:
            volume_label = str(visible_group[0][2] or "").strip() if visible_group else ""
            physical_key = f"visible-volume:{volume_label.casefold()}"
        if physical_key not in physical_groups:
            physical_groups[physical_key] = []
            order.append(physical_key)
        physical_groups[physical_key].extend(visible_group)
    return [physical_groups[key] for key in order]


def _build_volume_work_groups(empty_volume_items, named_volume_items):
    """Build named-volume work groups first, then one serial blank-volume group."""
    work_groups = []
    work_groups.extend(_group_named_volume_items_by_physical_drive(named_volume_items))
    if empty_volume_items:
        work_groups.append(list(empty_volume_items))
    return work_groups


def _run_parallel_paths(config, volume_groups, worker_count):
    path_count = sum(len(group) for group in volume_groups)
    named_count = sum(1 for group in volume_groups if str(group[0][2] or "").strip())
    blank_count = len(volume_groups) - named_count
    console_print(
        config,
        f"Parallel volume-group search enabled: {worker_count} worker(s) for "
        f"{named_count} named volume(s), {blank_count} blank-volume group(s), "
        f"and {path_count} search path(s)",
    )

    completed = {}
    manager = None
    pause_proxy = None

    try:
        manager = multiprocessing.Manager()
        pause_proxy = manager.Event()
        config.runtime_pause_proxy = pause_proxy
        register_active_pause_proxy(pause_proxy)
        snapshot = _config_snapshot(config, force_silent=True)

        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            register_active_executor(executor)
            try:
                future_map = {}
                next_search_index = 1
                for volume_group in volume_groups:
                    jobs = []
                    volume_label = str(volume_group[0][2] or "").strip()
                    for item in volume_group:
                        path_name, slam_value, item_volume_label, volume_key, log_token, log_mode, copy_mode, copy_destination, inventory_path = _unpack_inventory_item(item)
                        jobs.append((
                            path_name,
                            slam_value,
                            next_search_index,
                            item_volume_label,
                            volume_key,
                            log_token,
                            log_mode,
                            copy_mode,
                            copy_destination,
                            inventory_path,
                        ))
                        next_search_index += 1
                    future_map[executor.submit(
                        run_search_path_group_job,
                        snapshot,
                        jobs,
                    )] = volume_label

                for future in as_completed(future_map):
                    if is_cancel_requested() or getattr(config, "cancel_requested", False):
                        raise KeyboardInterrupt
                    results = future.result()
                    for result in results:
                        completed[result["search_index"]] = result
                        console_print(
                            config,
                            f"Search path complete: {result['path_name']} | directories identified: {result['directory_count']} | show groups processed: {result['show_group_count']}",
                        )
            finally:
                unregister_active_executor(executor)
    finally:
        unregister_active_pause_proxy(pause_proxy)
        config.runtime_pause_proxy = None
        if manager is not None:
            try:
                manager.shutdown()
            except Exception:
                pass

    all_metadata_records = []
    total_directories_identified = 0
    total_show_groups_processed = 0
    for search_index in sorted(completed):
        result = completed[search_index]
        total_directories_identified += result["directory_count"]
        total_show_groups_processed += result["show_group_count"]
        all_metadata_records.extend(result["metadata_records"])

    return all_metadata_records, total_directories_identified, total_show_groups_processed


def walk_trees(config):
    if is_cancel_requested() or getattr(config, "cancel_requested", False):
        raise KeyboardInterrupt
    inventory_items = prepare_inventory_items(config)
    normalized_items = []
    missing_token_positions = []
    for item in inventory_items:
        path_name, slam_value, volume_label, volume_key, log_token, log_mode, copy_mode, copy_destination, inventory_path = _unpack_inventory_item(item)
        if not str(log_token or "").strip():
            missing_token_positions.append(len(normalized_items))
        normalized_items.append([
            path_name,
            slam_value,
            volume_label,
            volume_key,
            str(log_token or "").strip(),
            log_mode or "w",
            copy_mode or "",
            copy_destination or "",
            inventory_path or path_name,
        ])

    # Missing tokens are allocated by visible volume label, not by physical drive
    # letter/path.  Multiple non-overlapping roots on the same labeled volume share
    # one token; the first write creates/truncates that token and later roots append.
    missing_by_volume = {}
    for item_index in missing_token_positions:
        volume_label = normalized_items[item_index][2]
        key = str(volume_label or "").strip().casefold()
        missing_by_volume.setdefault(key, []).append(item_index)
    allocated_tokens = allocate_log_tokens(config.TLOHome, len(missing_by_volume))
    for offset, (_volume_key, item_indexes) in enumerate(missing_by_volume.items()):
        token = allocated_tokens[offset]
        for position, item_index in enumerate(item_indexes):
            normalized_items[item_index][4] = token
            normalized_items[item_index][5] = "w" if position == 0 else "a"

    inventory_items = [tuple(item) for item in normalized_items]
    config.active_search_paths = [item[0] for item in inventory_items]
    current_tokens = [str(item[4] or "").strip() for item in inventory_items if str(item[4] or "").strip()]
    # current_run_log_tokens defines the records postprocess may aggregate. This
    # prevents a small path-scoped inventory from re-exporting every old meta*.log
    # record under TLOHome/logs.
    config.current_run_log_tokens = list(dict.fromkeys(current_tokens))
    # Only fresh tokens are safe for Ctrl-C cleanup. Existing tokens reused for
    # overwrite/re-inventory may contain earlier results and must not be deleted
    # wholesale if a run is interrupted.
    config.newly_allocated_log_tokens = list(allocated_tokens)
    config.active_log_tokens = list(allocated_tokens)
    console_print(config, "Starting inventory")
    for search_index, item in enumerate(inventory_items, start=1):
        path_name, slam_value, _volume_label, _volume_key, _log_token, _log_mode, copy_mode, copy_destination, inventory_path = _unpack_inventory_item(item)
        copy_note = f" | {copy_mode}={copy_destination}" if copy_mode and copy_destination else ""
        inventory_note = f" | inventory-path={inventory_path}" if inventory_path and inventory_path != path_name else ""
        console_print(config, f"Queued search path {search_index}: {path_name} | slam={slam_value}{copy_note}{inventory_note}")

    empty_volume_items, named_volume_items = _split_serial_and_parallel_items(config, inventory_items)
    named_volume_groups = _group_named_volume_items_by_physical_drive(named_volume_items)
    empty_volume_groups = [list(empty_volume_items)] if empty_volume_items else []

    if len(empty_volume_items) > 1:
        console_print(config, f"Empty-volume path group: {len(empty_volume_items)} path(s) will run one at a time after labeled volumes complete.")
    elif len(empty_volume_items) == 1:
        console_print(config, "Empty-volume path group: 1 path will run after labeled volumes complete.")
    if named_volume_groups:
        physical_group_count = len(named_volume_groups)
        named_volume_count = len(_group_named_volume_items(named_volume_items))
        if physical_group_count < named_volume_count:
            console_print(
                config,
                f"Physical-drive scheduling: {named_volume_count} labeled volume(s) grouped into "
                f"{physical_group_count} physical drive worker group(s).",
            )

    named_worker_count = _path_worker_count(config, len(named_volume_groups)) if named_volume_groups else 0
    console_print(config, f"Inventory performance mode: {config.performance_mode} | max workers: {named_worker_count or 1}")

    all_metadata_records = []
    total_directories_identified = 0
    total_show_groups_processed = 0

    if named_volume_groups:
        ordered_named_items = [item for group in named_volume_groups for item in group]
        if named_worker_count > 1:
            try:
                work_records, work_dirs, work_groups = _run_parallel_paths(
                    config,
                    named_volume_groups,
                    named_worker_count,
                )
            except BrokenProcessPool as exc:
                console_print(
                    config,
                    f"Parallel worker pool failed; retrying labeled search paths serially: {exc}",
                    error=True,
                )
                work_records, work_dirs, work_groups = _run_serial(
                    config,
                    ordered_named_items,
                )
        else:
            work_records, work_dirs, work_groups = _run_serial(
                config,
                ordered_named_items,
            )
        all_metadata_records.extend(work_records)
        total_directories_identified += work_dirs
        total_show_groups_processed += work_groups

    if empty_volume_groups:
        # Blank-label roots are deliberately held until all labeled-volume
        # workers finish.  This prevents a labeled and unlabeled partition on
        # the same physical disk from being scanned at the same time.
        empty_records, empty_dirs, empty_groups = _run_serial(
            config,
            [item for group in empty_volume_groups for item in group],
        )
        all_metadata_records.extend(empty_records)
        total_directories_identified += empty_dirs
        total_show_groups_processed += empty_groups

    # Postprocess should use the records from this run directly.  Reading the
    # reused log token can include unrelated historical records when a child path
    # is re-inventoried under a broader prior group log.
    config.current_metadata_records = list(all_metadata_records)

    console_print(
        config,
        f"Totals: directories identified: {total_directories_identified} | show groups processed: {total_show_groups_processed}",
    )
    console_print(config, "Inventory completed successfully")

    return all_metadata_records
