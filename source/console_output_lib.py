__version__ = "v347"
# TLO-GI package version: v347
__version_summary__ = 'Uses one main-window Dry run setting inherited live by Tag and Add Shows.'
# TLO-GI version summary: Uses one main-window Dry run setting inherited live by Tag and Add Shows.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
