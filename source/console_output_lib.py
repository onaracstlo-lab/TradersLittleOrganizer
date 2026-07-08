__version__ = "v324"
# TLO-GI package version: v324
__version_summary__ = 'Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.'
# TLO-GI version summary: Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
