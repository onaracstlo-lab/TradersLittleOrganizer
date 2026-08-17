__version__ = "v372"
# TLO-GI package version: v372
__version_summary__ = 'Research accepts the full canonical TLO date grammar, and the public application version advances to 1.4.'
# TLO-GI version summary: Research accepts the full canonical TLO date grammar, and the public application version advances to 1.4.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
