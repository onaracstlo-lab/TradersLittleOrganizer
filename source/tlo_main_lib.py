"""Command-line inventory orchestration: startup checks, scan execution, postprocess, cleanup, and timing output."""

__version__ = "v328"
# TLO-GI package version: v328
__version_summary__ = 'Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.'
# TLO-GI version summary: Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.

import sys
import time

from console_output_lib import console_emit, console_print
from logging_lib import delete_logs_for_tokens, setup_logging
from tlo_runtime_control import clear_cancel_request, request_cancel_and_terminate_active_executor, terminate_all_children, apply_process_priority
from tlo_db_validation import validate_required_databases
from tlo_options import apply_lookup_dependency
from tlo_version import DISPLAY_VERSION
from tlo_postprocess import postprocess_metadata_outputs
from walk_trees_lib import walk_trees


def _check_online_lookup_startup(config) -> None:
    if config is None:
        return
    apply_lookup_dependency(vars(config), mode="strict")
    etree_enabled = bool(getattr(config, "etree_lookup", False))
    setlistfm_enabled = bool(getattr(config, "setlistfm_lookup", False))
    if etree_enabled or setlistfm_enabled:
        console_print(
            config,
            "Online lookup enabled: etreeLookup=%s | setlist.fm=%s"
            % ("yes" if etree_enabled else "no", "yes" if setlistfm_enabled else "no"),
        )


def _build_number_from_version(version_text: str) -> str:
    version_text = str(version_text or "").strip()
    digits = ""
    for char in reversed(version_text):
        if char.isdigit():
            digits = char + digits
        elif digits:
            break
    return digits or version_text.lstrip("vV") or "0"


def _startup_banner(config) -> str:
    # Keep startup output stable and concise. Release-change summaries belong
    # in CHANGES files and documentation, not in the operational console.
    return f"Starting tlo-gi {DISPLAY_VERSION}"


def run_inventory(config) -> int:
    start_time = time.monotonic()
    exit_code = 0
    clear_cancel_request()
    apply_process_priority(config)
    if config is not None:
        config.inventory_complete = False
        config.inventory_scanning_complete = False
        config.cancel_requested = False
    try:
        console_print(config, _startup_banner(config))
        _check_online_lookup_startup(config)
        setup_logging(config)
        if config is not None and (
            bool(getattr(config, "tag_during_inventory", False))
            or bool(getattr(config, "tag_copy_during_inventory", False))
            or bool(str(getattr(config, "tag_copy_and_delete_path", "") or "").strip())
        ):
            from tlo_tag_lib import ensure_corrupt_flacs_log

            ensure_corrupt_flacs_log(config)
        validate_required_databases(config)
        walk_trees(config)
        config.inventory_scanning_complete = True
        console_print(config, "Inventory phase complete; cleanup, aggregation, and output generation still need to run.")
        postprocess_metadata_outputs(config)
        console_print(config, "Cleanup, aggregation, and output generation complete.")
        if config is not None:
            config.inventory_complete = True
    except KeyboardInterrupt:
        exit_code = 130
        if config is not None:
            config.cancel_requested = True
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
            tokens = getattr(config, "newly_allocated_log_tokens", [])
            delete_logs_for_tokens(config.TLOHome, tokens)
        else:
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
    except Exception as exc:
        exit_code = 1
        if config is None or not getattr(config, "silent", False):
            if config is not None:
                console_print(config, f"ERROR: {exc}", error=True)
            else:
                console_emit(f"ERROR: {exc}", error=True)
    finally:
        elapsed_minutes = (time.monotonic() - start_time) / 60.0
        if config is None:
            console_emit(f"Elapsed time: {elapsed_minutes:.2f} minutes")
        elif not getattr(config, "silent", False):
            console_print(config, f"Elapsed time: {elapsed_minutes:.2f} minutes")
    return exit_code
