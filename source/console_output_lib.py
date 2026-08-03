__version__ = "v354"
# TLO-GI package version: v354
__version_summary__ = 'Prevents broad collection roots from being aggregated or renamed and preserves Artist in Album during full-inventory tagging.'
# TLO-GI version summary: Prevents broad collection roots from being aggregated or renamed and preserves Artist in Album during full-inventory tagging.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
