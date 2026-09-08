__version__ = "v446"
from tlo_diagnostics import debug_suppressed_exception
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

from inventory_parser_lib import build_config
from logging_lib import delete_logs_for_tokens
from tlo_main_lib import run_inventory
from tlo_run_settings import append_run_settings
from tlo_ux import operation_review_lines
from tlo_runtime_control import request_cancel_and_terminate_active_executor, terminate_all_children, flush_standard_streams


def main() -> int:
    config = None
    try:
        config = build_config()
        review_lines = operation_review_lines(
            config,
            operation="Full Inventory",
            dry_run=False,
        )
        append_run_settings(config.TLOHome, "Full Inventory", review_lines)
        return run_inventory(config)
    except KeyboardInterrupt:
        if config is not None:
            try:
                config.cancel_requested = True
            except Exception as exc:  # noqa: BLE001 - best-effort boundary
                debug_suppressed_exception(__name__, exc)
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
            try:
                tokens = getattr(config, "newly_allocated_log_tokens", [])
                delete_logs_for_tokens(config.TLOHome, tokens)
            except Exception as exc:  # noqa: BLE001 - best-effort boundary
                debug_suppressed_exception(__name__, exc)
        else:
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
        flush_standard_streams()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
