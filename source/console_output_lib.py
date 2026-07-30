__version__ = "v351"
# TLO-GI package version: v351
__version_summary__ = 'Uses normal dark text for donation details and corrects the About contact wording.'
# TLO-GI version summary: Uses normal dark text for donation details and corrects the About contact wording.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
