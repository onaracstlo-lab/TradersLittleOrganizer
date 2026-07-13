__version__ = "v335"
# TLO-GI package version: v335
__version_summary__ = 'Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.'
# TLO-GI version summary: Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
