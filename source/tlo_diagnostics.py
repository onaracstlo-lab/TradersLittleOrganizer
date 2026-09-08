"""Low-noise diagnostics for intentionally suppressed best-effort exceptions."""
from __future__ import annotations

__version__ = "v446"

import logging

_LOGGER = logging.getLogger("tlo.suppressed")

def debug_suppressed_exception(context: str, exc: BaseException) -> None:
    """Record an intentionally suppressed exception at debug level."""
    _LOGGER.debug("suppressed exception in %s: %s", context, exc, exc_info=(type(exc), exc, exc.__traceback__))
