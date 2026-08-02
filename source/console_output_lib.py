__version__ = "v352"
# TLO-GI package version: v352
__version_summary__ = 'Slows the GUI activity indicator animation to one-tenth of its previous speed.'
# TLO-GI version summary: Slows the GUI activity indicator animation to one-tenth of its previous speed.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
