__version__ = "v318"
# TLO-GI package version: v318
__version_summary__ = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
# TLO-GI version summary: Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()

from inventory_parser_lib import build_config
from tlo_main_lib import run_inventory


def main() -> int:
    config = build_config()
    try:
        return run_inventory(config)
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
