"""Bounded network response reads for small TLO metadata/API payloads."""
from __future__ import annotations

__version__ = "v433"

MAX_METADATA_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ERROR_RESPONSE_BYTES = 64 * 1024


class ResponseTooLargeError(ValueError):
    pass


def read_bounded_bytes(response, max_bytes: int, *, label: str = "network response") -> bytes:
    limit = max(1, int(max_bytes))
    data = response.read(limit + 1)
    if len(data) > limit:
        raise ResponseTooLargeError(f"{label} exceeds {limit} bytes")
    return data


def read_bounded_text(response, max_bytes: int, *, label: str = "network response", errors: str = "replace") -> str:
    return read_bounded_bytes(response, max_bytes, label=label).decode("utf-8", errors=errors)
