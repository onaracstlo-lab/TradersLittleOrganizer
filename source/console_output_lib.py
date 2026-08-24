__version__ = "v394"
# TLO-GI package version: v394
__version_summary__ = 'Harden Linux CI regression tests so synthetic FLAC fixtures explicitly opt out of corruption removal; runtime behavior is unchanged.'
# TLO-GI version summary: Harden Linux CI regression tests so synthetic FLAC fixtures explicitly opt out of corruption removal; runtime behavior is unchanged.
import sys


def console_emit(message, error=False, silent=False, end="\n"):
    """Central console-output gate used by CLI helpers and config-aware callers."""
    if silent:
        return
    stream = sys.stderr if error else sys.stdout
    print(message, file=stream, end=end)


def console_print(config, message, error=False, end="\n"):
    console_emit(message, error=error, silent=getattr(config, "silent", False), end=end)
