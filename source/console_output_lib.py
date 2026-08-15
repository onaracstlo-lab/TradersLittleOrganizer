__version__ = "v363"
# TLO-GI package version: v363
__version_summary__ = 'Adds tlo-deleteDupes for safe recursive cleanup of copy-suffixed duplicate folders via the platform Trash/Recycle Bin.'
# TLO-GI version summary: Adds tlo-deleteDupes for safe recursive cleanup of copy-suffixed duplicate folders via the platform Trash/Recycle Bin.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
