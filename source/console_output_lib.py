__version__ = "v328"
# TLO-GI package version: v328
__version_summary__ = 'Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.'
# TLO-GI version summary: Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
