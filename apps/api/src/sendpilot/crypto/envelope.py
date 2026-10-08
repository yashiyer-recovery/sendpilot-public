"""Envelope encryption of OAuth tokens (PRD §6.2).

Each token blob is encrypted with a per-record AES-256-GCM data key; the data
key is itself wrapped by KMS. Only the KMS-wrapped data key and the ciphertext
are persisted — the plaintext data key is never stored and is zeroed after use.

Blob layout::

    [2-byte wrapped-key length][wrapped key][12-byte nonce][ciphertext]
"""

from __future__ import annotations

import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .kms import KMS


def encrypt_tokens(kms: KMS, key_id: str, tokens: dict) -> bytes:
    plaintext_key, wrapped_key = kms.generate_data_key(key_id)
    try:
        aes = AESGCM(plaintext_key)
        nonce = os.urandom(12)
        ct = aes.encrypt(nonce, json.dumps(tokens).encode(), key_id.encode())
    finally:
        # Drop the plaintext data key reference promptly.
        del plaintext_key
    return len(wrapped_key).to_bytes(2, "big") + wrapped_key + nonce + ct


def decrypt_tokens(kms: KMS, key_id: str, blob: bytes) -> dict:
    wlen = int.from_bytes(blob[:2], "big")
    wrapped_key = blob[2 : 2 + wlen]
    nonce = blob[2 + wlen : 2 + wlen + 12]
    ct = blob[2 + wlen + 12 :]
    plaintext_key = kms.decrypt_data_key(key_id, wrapped_key)
    aes = AESGCM(plaintext_key)
    return json.loads(aes.decrypt(nonce, ct, key_id.encode()))
