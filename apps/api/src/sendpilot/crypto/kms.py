"""KMS abstraction for envelope encryption (PRD §6.2).

The KMS only ever sees *data keys*, never tokens. In production this is a cloud
KMS (AWS/GCP); locally it's an in-process :class:`LocalKMS` that wraps data keys
under a master key derived from ``KMS_MASTER_KEY``. The on-disk format and the
calling code are identical, so swapping to a real KMS is a config change.
"""

from __future__ import annotations

import hashlib
import os
from typing import Protocol

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ..config import settings


class KMS(Protocol):
    """Thin interface over a cloud KMS."""

    def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        """Return ``(plaintext_data_key, wrapped_data_key)``."""
        ...

    def decrypt_data_key(self, key_id: str, wrapped: bytes) -> bytes:
        """Unwrap and return the plaintext data key."""
        ...


class LocalKMS:
    """In-process KMS for local dev. NOT for production secrets."""

    def __init__(self, master_secret: str) -> None:
        # Derive a stable 32-byte master key from whatever secret is configured.
        self._master = hashlib.sha256(master_secret.encode()).digest()

    def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:
        data_key = os.urandom(32)
        nonce = os.urandom(12)
        ct = AESGCM(self._master).encrypt(nonce, data_key, key_id.encode())
        return data_key, nonce + ct

    def decrypt_data_key(self, key_id: str, wrapped: bytes) -> bytes:
        nonce, ct = wrapped[:12], wrapped[12:]
        return AESGCM(self._master).decrypt(nonce, ct, key_id.encode())


class CloudKMS:
    """Placeholder for a real KMS (AWS KMS / GCP KMS).

    Wire ``boto3`` ``kms.generate_data_key`` / ``kms.decrypt`` here. Not
    implemented in the v1 scaffold — local dev and CI use :class:`LocalKMS`.
    """

    def generate_data_key(self, key_id: str) -> tuple[bytes, bytes]:  # pragma: no cover
        raise NotImplementedError("CloudKMS is not wired in the v1 scaffold")

    def decrypt_data_key(self, key_id: str, wrapped: bytes) -> bytes:  # pragma: no cover
        raise NotImplementedError("CloudKMS is not wired in the v1 scaffold")


def get_kms() -> KMS:
    if settings.use_local_kms:
        return LocalKMS(settings.kms_master_key or settings.session_secret)
    return CloudKMS()
