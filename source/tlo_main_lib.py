"""Command-line inventory orchestration: startup checks, scan execution, postprocess, cleanup, and timing output."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import time

from console_output_lib import console_emit, console_print
from logging_lib import delete_logs_for_tokens, setup_logging
from tlo_runtime_control import (
    clear_cancel_request,
    request_cancel_and_terminate_active_executor,
    terminate_all_children,
    apply_process_priority,
    acquire_inventory_lock,
    release_inventory_lock,
)
from tlo_db_validation import optional_database_status, validate_required_databases
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
            "Online lookup enabled: etreeLookup=%s | setlist.fm=%s | thoroughSetlistMatching=%s"
            % (
                "yes" if etree_enabled else "no",
                "yes" if setlistfm_enabled else "no",
                "yes" if bool(getattr(config, "thorough_setlist_matching", False)) else "no",
            ),
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


def _preflight_cross_root_show_identities(config) -> None:
    """Never modify the first root before finding a collision in a later root.

    The existing GUI preview uses isolated temporary discovery logs and resolves
    album identities without committing media changes. Only run this additional
    (potentially expensive) pass when multiple roots can mutate files. A
    failed/incomplete preflight is a safe refusal, not permission to proceed.
    """
    from tlo_ux import _inventory_roots, preview_operation

    roots = _inventory_roots(config)
    if len(roots) < 2:
        return
    mutating = any(bool(getattr(config, field, False)) for field in (
        'tag_during_inventory', 'tag_copy_during_inventory',
        'rename_compliantly', 'convert_shn',
    )) or bool(str(getattr(config, 'tag_copy_and_delete_path', '') or '').strip()) or any(
        mode in ('copy', 'copy-delete') for _root, mode, _destination in roots
    )
    if not mutating:
        return
    preview = preview_operation(config, operation='Full Inventory', sample_limit=None)
    errors = [issue for issue in preview.issues if issue.severity == 'error']
    if errors or preview.truncated:
        detail = errors[0].message if errors else 'preview results were truncated'
        raise RuntimeError('Multi-root mutation preflight incomplete: ' + detail)
    identities = {}
    for item in preview.samples:
        show = ' '.join((item.show_name or '').split()).casefold()
        if not show:
            continue  # Unresolved names are already refused by the normal mutation guard.
        path = __import__('os').path.normcase(__import__('os').path.abspath(item.path))
        previous = identities.setdefault(show, path)
        if previous != path:
            raise RuntimeError(
                'SHOW_IDENTITY_COLLISION across search paths: %s | %s and %s. '
                'No folder was tagged, renamed, transferred or converted; disambiguate first.'
                % (item.show_name, previous, path)
            )


def run_inventory(config) -> int:
    start_time = time.monotonic()
    exit_code = 0
    clear_cancel_request()
    inventory_lock = None
    if config is not None:
        config.inventory_complete = False
        config.inventory_scanning_complete = False
        config.cancel_requested = False
    try:
        inventory_lock = acquire_inventory_lock(getattr(config, "TLOHome", ""))
        # Fail before scanning, folder renames, or tag writes.
        from tlo_bootlist_volume_policy import validate_bootlist_utf8
        validate_bootlist_utf8(getattr(config, "TLOHome", ""))
        apply_process_priority(config)
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
        for message in optional_database_status(config):
            console_print(config, message)
        _preflight_cross_root_show_identities(config)
        config.storage_identity_enabled = True
        walk_trees(config)
        config.inventory_scanning_complete = True
        console_print(config, "Inventory phase complete; cleanup, aggregation, and output generation still need to run.")
        postprocess_metadata_outputs(config)
        from tlo_inventory_guard import retire_previous_logs
        try:
            retire_previous_logs(config)
        except OSError as exc:
            console_print(config, f"WARNING: older metadata logs could not be retired: {exc}", error=True)
        console_print(config, "Cleanup, aggregation, and output generation complete.")
        if config is not None:
            config.inventory_complete = True
    except KeyboardInterrupt:
        exit_code = 130
        if config is not None:
            config.cancel_requested = True
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
            if getattr(config, "storage_identity_enabled", False):
                from tlo_inventory_guard import preserve_aborted_logs
                preserve_aborted_logs(config)
            else:
                tokens = getattr(config, "newly_allocated_log_tokens", [])
                delete_logs_for_tokens(config.TLOHome, tokens)
        else:
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
    except Exception as exc:
        exit_code = 1
        if config is not None and getattr(config, "storage_identity_enabled", False) and not getattr(config, "inventory_complete", False):
            from tlo_inventory_guard import preserve_aborted_logs
            try:
                preserve_aborted_logs(config)
            except OSError as cleanup_error:
                console_print(config, f"Unable to archive incomplete scan logs: {cleanup_error}", error=True)
        if config is None or not getattr(config, "silent", False):
            if config is not None:
                console_print(config, f"ERROR: {exc}", error=True)
            else:
                console_emit(f"ERROR: {exc}", error=True)
    finally:
        release_inventory_lock(inventory_lock)
        elapsed_minutes = (time.monotonic() - start_time) / 60.0
        if config is None:
            console_emit(f"Elapsed time: {elapsed_minutes:.2f} minutes")
        elif not getattr(config, "silent", False):
            console_print(config, f"Elapsed time: {elapsed_minutes:.2f} minutes")
    return exit_code
