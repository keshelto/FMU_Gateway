"""Utility functions for the FMU Gateway SDK."""
from __future__ import annotations

from pathlib import Path


def read_binary_file(path: str | Path) -> bytes:
    """Read a file as bytes to support FMU uploads."""
    return Path(path).expanduser().resolve().read_bytes()
