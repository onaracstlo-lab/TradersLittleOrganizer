__version__ = "v361"
# TLO-GI package version: v361
__version_summary__ = 'Refines copy verification so same-partition Copy/Delete uses a size-free directory move while every real copy is verified by file size.'
# TLO-GI version summary: Refines copy verification so same-partition Copy/Delete uses a size-free directory move while every real copy is verified by file size.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
