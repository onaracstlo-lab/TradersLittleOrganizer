__version__ = "v367"
# TLO-GI package version: v367
__version_summary__ = 'Moves qualifying duplicate folders into a partition-root duplicates holding folder instead of Trash/Recycle Bin.'
# TLO-GI version summary: Moves qualifying duplicate folders into a partition-root duplicates holding folder instead of Trash/Recycle Bin.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
