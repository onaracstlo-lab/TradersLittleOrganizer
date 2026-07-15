__version__ = "v336"
# TLO-GI package version: v336
__version_summary__ = 'Restricts standalone Tag to direct tagging and hides undocumented myTLO help.'
# TLO-GI version summary: Restricts standalone Tag to direct tagging and hides undocumented myTLO help.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
