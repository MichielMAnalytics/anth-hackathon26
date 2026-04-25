"""DTN wire-format codecs.

Mirrors `mobileapp/src/bitchat/Models/DTNPackets.swift`. Layouts are fixed
binary (not TLV) — DTN packets travel in volume across constrained mesh
links and a 50% smaller wire size noticeably reduces BLE radio time. A
1-byte version prefix gives forward-compat: clients drop unknown versions
silently.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Optional

VERSION: int = 0x01


class InnerType(IntEnum):
    """The inner amber payload type carried by a DTN bundle."""

    SIGHTING = 0x21
    LOCATION_REPORT = 0x22
    GENERAL_MESSAGE = 0x23
    PROFILE_UPDATE = 0x24


# ---------------------------------------------------------------------------
# DTNBundle
# ---------------------------------------------------------------------------


@dataclass
class DTNBundle:
    """Opaque envelope addressed to the hub, signed by the originating
    reporter, gossipped peer-to-peer until it reaches a phone with
    internet (or until the hub broadcasts a receipt that triggers
    eviction)."""

    bundle_id: bytes  # 16B random; also the dedup key
    hub_pubkey: bytes  # 32B X25519 — the destination
    expires_at: int  # unix seconds (uint64)
    copies_remaining: int  # spray-and-wait budget, mutated on hand-off
    inner_type: int  # original NoisePayloadType.rawValue (sighting, etc.)
    ephemeral_pubkey: bytes  # 32B X25519 ephemeral, for sealed-box
    nonce: bytes  # 12B for ChaCha20-Poly1305
    ciphertext: bytes  # sealed inner payload (includes 16B Poly1305 tag)
    sig: bytes  # 64B Ed25519 over canonical bytes, by reporter key

    # Minimum: 1 + 16 + 32 + 8 + 1 + 1 + 32 + 12 + 4 + 64 = 171 bytes.
    _MIN_BYTES = 171

    def __post_init__(self) -> None:
        if len(self.bundle_id) != 16:
            raise ValueError("bundle_id must be 16 bytes")
        if len(self.hub_pubkey) != 32:
            raise ValueError("hub_pubkey must be 32 bytes")
        if len(self.ephemeral_pubkey) != 32:
            raise ValueError("ephemeral_pubkey must be 32 bytes")
        if len(self.nonce) != 12:
            raise ValueError("nonce must be 12 bytes")
        if len(self.sig) != 64:
            raise ValueError("sig must be 64 bytes")
        if not (0 <= self.copies_remaining <= 0xFF):
            raise ValueError("copies_remaining must fit in a uint8")
        if not (0 <= self.inner_type <= 0xFF):
            raise ValueError("inner_type must fit in a uint8")
        if not (0 <= self.expires_at < 2**64):
            raise ValueError("expires_at must fit in a uint64")

    def encode(self) -> bytes:
        return (
            bytes([VERSION])
            + self.bundle_id
            + self.hub_pubkey
            + struct.pack("!Q", self.expires_at)
            + bytes([self.copies_remaining, self.inner_type])
            + self.ephemeral_pubkey
            + self.nonce
            + struct.pack("!I", len(self.ciphertext))
            + self.ciphertext
            + self.sig
        )

    def canonical_bytes_for_signing(self) -> bytes:
        """Bytes covered by `sig` — everything in the encoded packet
        except the trailing 64-byte signature."""
        return self.encode()[:-64]

    @classmethod
    def decode(cls, data: bytes) -> Optional["DTNBundle"]:
        if len(data) < cls._MIN_BYTES:
            return None
        if data[0] != VERSION:
            return None
        off = 1
        bundle_id = data[off : off + 16]
        off += 16
        hub_pubkey = data[off : off + 32]
        off += 32
        (expires_at,) = struct.unpack_from("!Q", data, off)
        off += 8
        copies_remaining = data[off]
        off += 1
        inner_type = data[off]
        off += 1
        ephemeral_pubkey = data[off : off + 32]
        off += 32
        nonce = data[off : off + 12]
        off += 12
        (clen,) = struct.unpack_from("!I", data, off)
        off += 4
        if off + clen + 64 > len(data):
            return None
        ciphertext = data[off : off + clen]
        off += clen
        sig = data[off : off + 64]
        return cls(
            bundle_id=bundle_id,
            hub_pubkey=hub_pubkey,
            expires_at=expires_at,
            copies_remaining=copies_remaining,
            inner_type=inner_type,
            ephemeral_pubkey=ephemeral_pubkey,
            nonce=nonce,
            ciphertext=ciphertext,
            sig=sig,
        )


# ---------------------------------------------------------------------------
# DTNReceipt
# ---------------------------------------------------------------------------


@dataclass
class DTNReceipt:
    """Hub-signed delivery confirmation. Floods the same way as bundles
    and triggers carriers to evict the matching bundle."""

    bundle_id: bytes  # 16B
    hub_pubkey: bytes  # 32B — also the verifier
    signed_at: int  # unix seconds (uint64)
    sig: bytes  # 64B Ed25519 by hub_pubkey

    # 1 + 16 + 32 + 8 + 64 = 121 bytes.
    _MIN_BYTES = 121

    def __post_init__(self) -> None:
        if len(self.bundle_id) != 16:
            raise ValueError("bundle_id must be 16 bytes")
        if len(self.hub_pubkey) != 32:
            raise ValueError("hub_pubkey must be 32 bytes")
        if len(self.sig) != 64:
            raise ValueError("sig must be 64 bytes")
        if not (0 <= self.signed_at < 2**64):
            raise ValueError("signed_at must fit in a uint64")

    def encode(self) -> bytes:
        return (
            bytes([VERSION])
            + self.bundle_id
            + self.hub_pubkey
            + struct.pack("!Q", self.signed_at)
            + self.sig
        )

    def canonical_bytes_for_signing(self) -> bytes:
        return self.encode()[:-64]

    @classmethod
    def decode(cls, data: bytes) -> Optional["DTNReceipt"]:
        if len(data) < cls._MIN_BYTES:
            return None
        if data[0] != VERSION:
            return None
        off = 1
        bundle_id = data[off : off + 16]
        off += 16
        hub_pubkey = data[off : off + 32]
        off += 32
        (signed_at,) = struct.unpack_from("!Q", data, off)
        off += 8
        sig = data[off : off + 64]
        return cls(
            bundle_id=bundle_id, hub_pubkey=hub_pubkey, signed_at=signed_at, sig=sig
        )


# ---------------------------------------------------------------------------
# DTNSummary (anti-entropy)
# ---------------------------------------------------------------------------

MAX_SUMMARY_BUNDLE_IDS: int = 256


@dataclass
class DTNSummary:
    """Anti-entropy summary vector — list of bundle_ids the sender
    already holds. Peers exchange these on connect; the receiver computes
    the diff and transfers only bundles the sender is missing."""

    bundle_ids: list[bytes]  # each 16B

    def __post_init__(self) -> None:
        if len(self.bundle_ids) > MAX_SUMMARY_BUNDLE_IDS:
            raise ValueError(
                f"too many bundle_ids (max {MAX_SUMMARY_BUNDLE_IDS})"
            )
        for bid in self.bundle_ids:
            if len(bid) != 16:
                raise ValueError("each bundle_id must be 16 bytes")

    def encode(self) -> bytes:
        return (
            bytes([VERSION])
            + struct.pack("!H", len(self.bundle_ids))
            + b"".join(self.bundle_ids)
        )

    @classmethod
    def decode(cls, data: bytes) -> Optional["DTNSummary"]:
        if len(data) < 3 or data[0] != VERSION:
            return None
        (n,) = struct.unpack_from("!H", data, 1)
        if n > MAX_SUMMARY_BUNDLE_IDS:
            return None
        if len(data) < 3 + n * 16:
            return None
        ids = [data[3 + i * 16 : 3 + (i + 1) * 16] for i in range(n)]
        return cls(bundle_ids=ids)
