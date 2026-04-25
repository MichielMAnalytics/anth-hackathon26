"""Sealed-box helpers for DTN bundles.

One-shot encryption to the hub's X25519 public key:

    ephemeral X25519 keypair  →  shared secret with hub
    →  HKDF(SHA256, info=b"safethread-dtn-v1")  →  symmetric key
    →  ChaCha20-Poly1305 seal

Mirrors the iOS `DTNSeal` enum. The HKDF info string MUST match across
sides verbatim.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HKDF_INFO: bytes = b"safethread-dtn-v1"
NONCE_LEN: int = 12
TAG_LEN: int = 16
KEY_LEN: int = 32


@dataclass
class Sealed:
    """Outputs of a `seal()` call — serialise into a DTNBundle directly."""

    ephemeral_pubkey: bytes  # 32B X25519 raw public key
    nonce: bytes  # 12B
    ciphertext: bytes  # plaintext-len + 16B Poly1305 tag


def _derive_key(shared_secret: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_LEN,
        salt=b"",
        info=HKDF_INFO,
    ).derive(shared_secret)


def seal(plaintext: bytes, hub_pubkey_raw: bytes) -> Sealed:
    """Encrypt `plaintext` to the hub's 32-byte X25519 public key.

    Generates a fresh ephemeral keypair per call.
    """
    if len(hub_pubkey_raw) != 32:
        raise ValueError("hub_pubkey_raw must be 32 bytes")
    hub_pub = X25519PublicKey.from_public_bytes(hub_pubkey_raw)
    ephem_priv = X25519PrivateKey.generate()
    ephem_pub_raw = _x25519_public_bytes(ephem_priv)
    shared = ephem_priv.exchange(hub_pub)
    key = _derive_key(shared)
    nonce = os.urandom(NONCE_LEN)
    ct = ChaCha20Poly1305(key).encrypt(nonce, plaintext, associated_data=None)
    return Sealed(ephemeral_pubkey=ephem_pub_raw, nonce=nonce, ciphertext=ct)


def open(  # noqa: A001  (mirror Swift's `DTNSeal.open(...)`)
    ephemeral_pubkey: bytes,
    nonce: bytes,
    ciphertext: bytes,
    hub_private_key: bytes,
) -> bytes:
    """Decrypt the inner payload of a DTN bundle.

    `hub_private_key` is 32 raw bytes (X25519 private key).
    Raises `cryptography.exceptions.InvalidTag` on tamper; ValueError on
    malformed input lengths.
    """
    if len(ephemeral_pubkey) != 32:
        raise ValueError("ephemeral_pubkey must be 32 bytes")
    if len(nonce) != NONCE_LEN:
        raise ValueError(f"nonce must be {NONCE_LEN} bytes")
    if len(ciphertext) < TAG_LEN:
        raise ValueError("ciphertext too short to contain Poly1305 tag")
    if len(hub_private_key) != 32:
        raise ValueError("hub_private_key must be 32 bytes")

    hub_priv = X25519PrivateKey.from_private_bytes(hub_private_key)
    ephem_pub = X25519PublicKey.from_public_bytes(ephemeral_pubkey)
    shared = hub_priv.exchange(ephem_pub)
    key = _derive_key(shared)
    return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, associated_data=None)


def _x25519_public_bytes(priv: X25519PrivateKey) -> bytes:
    """Extract a raw 32-byte X25519 public key from a private key."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    return priv.public_key().public_bytes(
        encoding=Encoding.Raw,
        format=PublicFormat.Raw,
    )


def public_bytes(private_key: bytes) -> bytes:
    """Public companion to `_x25519_public_bytes`. Given a 32-byte X25519
    private key, return the corresponding 32-byte raw public key. Useful
    for the API tier when emitting the hub's pubkey on /app/register.
    """
    if len(private_key) != 32:
        raise ValueError("private_key must be 32 bytes")
    return _x25519_public_bytes(X25519PrivateKey.from_private_bytes(private_key))
