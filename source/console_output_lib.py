__version__ = "v327"
# TLO-GI package version: v327
__version_summary__ = 'Serializes same-physical-drive labeled volume work, fixes Add Shows delete backups, and restores read-only TLOHome GUI labels.'
# TLO-GI version summary: Serializes same-physical-drive labeled volume work, fixes Add Shows delete backups, and restores read-only TLOHome GUI labels.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
