__version__ = "v361"
# TLO-GI package version: v361
__version_summary__ = 'Refines copy verification so same-partition Copy/Delete uses a size-free directory move while every real copy is verified by file size.'
# TLO-GI version summary: Refines copy verification so same-partition Copy/Delete uses a size-free directory move while every real copy is verified by file size.
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
            except Exception:
                pass
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
            try:
                tokens = getattr(config, "newly_allocated_log_tokens", [])
                delete_logs_for_tokens(config.TLOHome, tokens)
            except Exception:
                pass
        else:
            request_cancel_and_terminate_active_executor()
            terminate_all_children()
        flush_standard_streams()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
