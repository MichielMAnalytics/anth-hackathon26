"""Sealed-box round trip + tamper detection.

These tests guarantee wire compat with the iOS `DTNSeal` (X25519 + HKDF-
SHA256, info=b"safethread-dtn-v1" + ChaCha20-Poly1305). If the HKDF info
string changes here, mobileapp must change too.
"""

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from server.dtn.seal import open as seal_open
from server.dtn.seal import public_bytes, seal


def _hub_keypair() -> tuple[bytes, bytes]:
    priv = X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=Encoding.Raw, format=PublicFormat.Raw
    )
    return priv.private_bytes_raw(), pub


def test_seal_open_round_trip():
    priv, pub = _hub_keypair()
    plaintext = b"hello hub, this is a sighting"
    sealed = seal(plaintext, hub_pubkey_raw=pub)
    decrypted = seal_open(
        sealed.ephemeral_pubkey,
        sealed.nonce,
        sealed.ciphertext,
        priv,
    )
    assert decrypted == plaintext


def test_seal_open_round_trip_empty_payload():
    priv, pub = _hub_keypair()
    sealed = seal(b"", hub_pubkey_raw=pub)
    assert seal_open(sealed.ephemeral_pubkey, sealed.nonce, sealed.ciphertext, priv) == b""


def test_open_rejects_wrong_private_key():
    _, pub = _hub_keypair()
    other_priv, _ = _hub_keypair()
    sealed = seal(b"secret", hub_pubkey_raw=pub)
    with pytest.raises(InvalidTag):
        seal_open(sealed.ephemeral_pubkey, sealed.nonce, sealed.ciphertext, other_priv)


def test_open_rejects_tampered_ciphertext():
    priv, pub = _hub_keypair()
    sealed = seal(b"important", hub_pubkey_raw=pub)
    flipped = bytearray(sealed.ciphertext)
    flipped[0] ^= 0xFF
    with pytest.raises(InvalidTag):
        seal_open(sealed.ephemeral_pubkey, sealed.nonce, bytes(flipped), priv)


def test_seal_validates_pubkey_length():
    with pytest.raises(ValueError):
        seal(b"x", hub_pubkey_raw=b"\x00" * 31)


def test_open_validates_input_lengths():
    priv, _ = _hub_keypair()
    with pytest.raises(ValueError):
        seal_open(b"\x00" * 31, b"\x00" * 12, b"\x00" * 16, priv)
    with pytest.raises(ValueError):
        seal_open(b"\x00" * 32, b"\x00" * 11, b"\x00" * 16, priv)
    with pytest.raises(ValueError):
        seal_open(b"\x00" * 32, b"\x00" * 12, b"", priv)


def test_public_bytes_matches_x25519():
    priv, pub_expected = _hub_keypair()
    assert public_bytes(priv) == pub_expected
