__version__ = "v369"
# TLO-GI package version: v369
__version_summary__ = 'Adds Research log lookup by artist/date, venue, or date in the CLI and Inventory GUI.'
# TLO-GI version summary: Adds Research log lookup by artist/date, venue, or date in the CLI and Inventory GUI.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
