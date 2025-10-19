"""Abstractions for storing FMU binaries and generating signed URLs."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from pathlib import Path
from fastapi import UploadFile


STORAGE_ROOT = Path(os.getenv("OBJECT_STORAGE_ROOT", "./data/object_storage"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def save_fmu_bytes(data: bytes, file_key: str) -> str:
    """Persist the provided FMU bytes to disk.

    Production deployments plug into S3 or another object store via the same
    file key interface.  For the reference implementation we store the payloads
    locally so tests can execute end-to-end.
    """

    target = STORAGE_ROOT / file_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return file_key


def save_upload(upload: UploadFile, file_key: str) -> str:
    """Stream an :class:`UploadFile` to storage."""

    data = upload.file.read()
    save_fmu_bytes(data, file_key)
    return file_key


def load_bytes(file_key: str) -> bytes:
    """Return the raw bytes for ``file_key``."""

    target = STORAGE_ROOT / file_key
    return target.read_bytes()


def generate_signed_url(file_key: str, ttl_sec: int = 120) -> str:
    """Return a signed URL with an embedded expiry timestamp.

    The URL uses a deterministic HMAC signature so that downstream services can
    verify authenticity.  The ``OBJECT_STORAGE_SIGNING_SECRET`` environment
    variable should be populated with a random value in production.  The URL is
    not tied to any specific storage backend which keeps testing simple while
    still enforcing short-lived download links.
    """

    secret = os.getenv("OBJECT_STORAGE_SIGNING_SECRET", "development-secret").encode()
    expires = int(time.time()) + int(ttl_sec)
    payload = f"{file_key}:{expires}".encode()
    digest = hmac.new(secret, payload, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    bucket = os.getenv("OBJECT_STORAGE_BUCKET", "fmu-registry")
    return f"https://storage.local/{bucket}/{file_key}?expires={expires}&token={token}"


__all__ = ["save_upload", "generate_signed_url", "save_fmu_bytes", "load_bytes"]

