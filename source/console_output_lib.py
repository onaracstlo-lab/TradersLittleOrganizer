__version__ = "v373"
# TLO-GI package version: v373
__version_summary__ = 'Strengthen non-compliant artist resolution using DB-backed tag, path, and setlist filename evidence.'
# TLO-GI version summary: Strengthen non-compliant artist resolution using DB-backed tag, path, and setlist filename evidence.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
