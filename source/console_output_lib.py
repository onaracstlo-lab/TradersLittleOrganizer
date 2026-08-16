__version__ = "v370"
# TLO-GI package version: v370
__version_summary__ = 'Compares duplicate copies with each other using content-equivalence clusters and preferred keepers.'
# TLO-GI version summary: Compares duplicate copies with each other using content-equivalence clusters and preferred keepers.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
