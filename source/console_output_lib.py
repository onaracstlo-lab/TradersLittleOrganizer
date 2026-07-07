__version__ = "v322"
# TLO-GI package version: v322
__version_summary__ = 'Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.'
# TLO-GI version summary: Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
