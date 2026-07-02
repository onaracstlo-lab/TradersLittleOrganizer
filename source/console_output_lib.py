__version__ = "v318"
# TLO-GI package version: v318
__version_summary__ = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
# TLO-GI version summary: Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
