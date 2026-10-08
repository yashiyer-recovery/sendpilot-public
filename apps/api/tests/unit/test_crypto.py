"""Envelope encryption round-trip + tamper detection (PRD §6.2)."""

from __future__ import annotations

import pytest

from sendpilot.crypto.envelope import decrypt_tokens, encrypt_tokens
from sendpilot.crypto.kms import LocalKMS


def test_roundtrip():
    kms = LocalKMS("test-master-secret")
    tokens = {"access_token": "ya29.abc", "refresh_token": "1//rt", "expires_at": 123}
    blob = encrypt_tokens(kms, "local:dev", tokens)
    # The plaintext token must not appear in the ciphertext blob.
    assert b"ya29.abc" not in blob
    assert decrypt_tokens(kms, "local:dev", blob) == tokens


def test_tamper_is_rejected():
    kms = LocalKMS("test-master-secret")
    blob = bytearray(encrypt_tokens(kms, "local:dev", {"access_token": "x"}))
    blob[-1] ^= 0xFF  # flip a ciphertext bit
    with pytest.raises(Exception):
        decrypt_tokens(kms, "local:dev", bytes(blob))


def test_wrong_key_id_aad_fails():
    kms = LocalKMS("test-master-secret")
    blob = encrypt_tokens(kms, "key-a", {"access_token": "x"})
    # key_id is bound as AEAD associated data; a different id must fail.
    with pytest.raises(Exception):
        decrypt_tokens(kms, "key-b", blob)
