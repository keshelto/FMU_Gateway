"""Utilities for hashing and signing FMU binaries."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import BinaryIO


def compute_sha256(data: bytes) -> str:
    """Return the hexadecimal SHA-256 digest for ``data``."""

    digest = hashlib.sha256()
    digest.update(data)
    return digest.hexdigest()


def compute_sha256_stream(stream: BinaryIO) -> tuple[str, int]:
    """Hash a stream and return ``(digest, size_bytes)``."""

    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(8192):
        digest.update(chunk)
        size += len(chunk)
    return digest.hexdigest(), size


def sign_digest(hash_hex: str, private_key_path: str | None = None) -> str:
    """Sign the digest using the configured private key.

    The production service uses an ECDSA key stored in a secrets manager.  For
    local development the private key path can be omitted and a deterministic
    placeholder signature is returned.  ``cryptography`` is imported lazily so
    unit tests can run without optional dependencies.
    """

    key_path = private_key_path or os.getenv("SIGNING_PRIVATE_KEY_PATH")
    if not key_path or not Path(key_path).exists():
        # Deterministic fallback allows unit tests to assert on behaviour without
        # accessing the production key material.
        return compute_sha256(f"dev-signature:{hash_hex}".encode())

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
    except ImportError as exc:  # pragma: no cover - optional dependency path
        raise RuntimeError("cryptography package required for signing") from exc

    with open(key_path, "rb") as handle:
        private_key = load_pem_private_key(handle.read(), password=None)

    signature = private_key.sign(bytes.fromhex(hash_hex), ec.ECDSA(hashes.SHA256()))
    return signature.hex()


def build_metadata(tooling: dict[str, str] | None = None, **extra: str) -> dict:
    """Create an SBOM-like metadata payload stored alongside the FMU."""

    metadata = {
        "fmi_version": extra.get("fmi_version", "2.0"),
        "tool_versions": tooling or {},
        "platforms": extra.get("platforms", ["linux-x86_64", "windows-x86_64"]),
    }
    metadata.update({k: v for k, v in extra.items() if v is not None})
    return metadata


def metadata_to_json(metadata: dict) -> str:
    """Serialise metadata deterministically for hashing or storage."""

    return json.dumps(metadata, sort_keys=True)


__all__ = ["compute_sha256", "compute_sha256_stream", "sign_digest", "build_metadata", "metadata_to_json"]

