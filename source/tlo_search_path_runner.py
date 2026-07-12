__version__ = "v334"
# TLO-GI package version: v334
__version_summary__ = 'Rearranges the main-window checkboxes into the requested two-row, four-column layout.'
# TLO-GI version summary: Rearranges the main-window checkboxes into the requested two-row, four-column layout.
from console_output_lib import console_print
from initial_dir_walk_lib import initial_dir_walk
from tlo_complete_path_log import compact_complete_path_log
from inventory_parser_lib import Config
from logging_lib import setup_logging
from tlo_artist_db import load_artist_matcher
from tlo_phase23_v2 import process_groups_for_search_path_v2
from tlo_runtime_control import throttle_point, wait_if_paused, apply_process_priority



def run_search_path(config, path_name, slam_value, search_index, volume_label="", volume_key="", log_token="", log_mode="w", copy_mode="", copy_destination="", inventory_path="", artist_matcher=None, venue_matcher=None):
    apply_process_priority(config)
    wait_if_paused(config)
    config.current_search_path = path_name
    config.current_search_index = search_index
    config.current_slam = (slam_value or "").strip()
    config.current_volume_label = (volume_label or "").strip()
    config.current_volume_key = (volume_key or "").strip()
    config.current_log_token = str(log_token or "")
    config.current_log_mode = "a" if str(log_mode or "w").lower().startswith("a") else "w"
    copy_mode = str(copy_mode or "").strip().lower()
    copy_destination = str(copy_destination or "").strip()
    config.current_path_copy_destination = copy_destination if copy_mode == "copy" else ""
    config.current_path_copy_delete_destination = copy_destination if copy_mode == "copy-delete" else ""
    config.current_inventory_path = inventory_path or path_name
    config.logs.start_search_path(config.current_inventory_path, search_index, log_token=config.current_log_token, volume_label=config.current_volume_label, log_mode=config.current_log_mode)

    directory_count = initial_dir_walk(config, path_name)
    compact_complete_path_log(config.logs.paths.complete_paths)
    console_print(
        config,
        f"Stage 1 complete: directories identified = {directory_count}",
    )

    effective_artist_matcher = None
    if not config.current_slam:
        effective_artist_matcher = artist_matcher or load_artist_matcher(config)

    console_print(config, f"Stage 2 starting: {path_name}")
    original_tag_copy_flag = getattr(config, "tag_copy_during_inventory", False)
    original_tag_copy_destination = getattr(config, "tag_copy_destination", "")
    original_tag_copy_delete_path = getattr(config, "tag_copy_and_delete_path", "")
    try:
        metadata_records = process_groups_for_search_path_v2(
            config,
            effective_artist_matcher,
        )
    finally:
        config.tag_copy_during_inventory = original_tag_copy_flag
        config.tag_copy_destination = original_tag_copy_destination
        config.tag_copy_and_delete_path = original_tag_copy_delete_path
    groups = metadata_records
    show_group_count = len(metadata_records)

    return {
        "search_index": search_index,
        "path_name": path_name,
        "slam_value": slam_value,
        "volume_label": config.current_volume_label,
        "volume_key": config.current_volume_key,
        "directory_count": directory_count,
        "group_count": len(groups),
        "show_group_count": show_group_count,
        "metadata_records": metadata_records,
        "log_token": config.current_log_token,
    }


def run_search_path_job(config_snapshot, path_name, slam_value, search_index, volume_label="", volume_key="", log_token="", log_mode="w", copy_mode="", copy_destination="", inventory_path=""):
    worker_config = Config(**config_snapshot)
    apply_process_priority(worker_config)
    setup_logging(worker_config)
    return run_search_path(
        worker_config,
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
    )


def run_search_path_group_job(config_snapshot, jobs):
    """Run all search roots for one named volume serially inside one worker.

    Different named volumes may run in parallel, but roots that share one volume
    are kept together so they never write the same tokenized log files
    concurrently.
    """
    worker_config = Config(**config_snapshot)
    apply_process_priority(worker_config)
    setup_logging(worker_config)
    results = []
    shared_artist_matcher = None

    for job in jobs:
        (
            path_name,
            slam_value,
            search_index,
            volume_label,
            volume_key,
            log_token,
            log_mode,
            copy_mode,
            copy_destination,
            inventory_path,
        ) = job
        artist_matcher = None
        if not str(slam_value or "").strip():
            if shared_artist_matcher is None:
                shared_artist_matcher = load_artist_matcher(worker_config)
            artist_matcher = shared_artist_matcher

        results.append(
            run_search_path(
                worker_config,
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
            )
        )

    return results
