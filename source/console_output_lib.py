__version__ = "v362"
# TLO-GI package version: v362
__version_summary__ = 'Classifies name collisions as copy only after exact recursive tree/content comparison; non-identical collisions are labeled alt.'
# TLO-GI version summary: Classifies name collisions as copy only after exact recursive tree/content comparison; non-identical collisions are labeled alt.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
