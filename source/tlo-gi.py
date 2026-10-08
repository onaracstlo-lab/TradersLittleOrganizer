from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION
from tlo_diagnostics import debug_suppressed_exception
import multiprocessing
import os
import subprocess

if __name__ == "__main__":
    multiprocessing.freeze_support()

from inventory_parser_lib import build_config
from logging_lib import delete_logs_for_tokens
from tlo_main_lib import run_inventory
from tlo_run_settings import append_run_settings
from tlo_ux import operation_review_lines
from tlo_runtime_control import request_cancel_and_terminate_active_executor, terminate_all_children, flush_standard_streams


def _run_packaging_smoke_test() -> int:
    """Exercise dependencies that frozen tlo-gi needs for tagging and SHN conversion."""
    try:
        from mutagen.flac import FLAC  # noqa: F401 - import is the packaging probe
        from tlo_tag_lib import _bundled_ffmpeg_executable

        ffmpeg = _bundled_ffmpeg_executable()
        if not ffmpeg or not os.path.isfile(ffmpeg):
            print("TLO packaging smoke test failed: bundled ffmpeg is unavailable.", file=__import__("sys").stderr)
            return 2
        result = subprocess.run(
            [ffmpeg, "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
            check=False,
        )
        if result.returncode != 0:
            print("TLO packaging smoke test failed: bundled ffmpeg did not execute cleanly.", file=__import__("sys").stderr)
            return 2
        print("TLO packaging smoke test OK: mutagen and bundled ffmpeg are available.")
        return 0
    except Exception as exc:  # noqa: BLE001 - fail-closed packaging probe
        print(f"TLO packaging smoke test failed: {exc}", file=__import__("sys").stderr)
        return 2


def main() -> int:
    if os.environ.get("TLO_PACKAGING_SMOKE_TEST") == "1":
        return _run_packaging_smoke_test()
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
