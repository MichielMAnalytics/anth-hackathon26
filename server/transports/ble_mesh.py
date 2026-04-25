"""Real BLE mesh transport — hardware path, not exercised by hackathon CI.

Requires a host with a BLE radio (a Linux server with a USB BLE dongle, or
a Raspberry Pi). Not used by the demo: the hackathon mesh story is told
end-to-end via real BLE *between phones* + an internet-bearing carrier
POSTing the resulting bundles into `/app/dtn/deliver`. Standing up a
BLE-capable hub is a production roadmap item.

This module is a scaffold:
- It imports cleanly so test runs don't break.
- Raises `NotImplementedError` from the lifecycle methods if ever
  invoked, with a clear message pointing here.
- Marks every wire-protocol gap with `# TODO(bitchat-protocol):` so a
  future implementer can grep for the work.

Wire-protocol references:
  https://github.com/permissionlesstech/bitchat
  bitchat's GATT service UUID, characteristic UUIDs, Noise XX handshake,
  TTL=7 multi-hop relay, and fragmentation rules all live in the
  upstream Swift/Kotlin implementations. A Python port would need:

  1. A BLE central+peripheral via `bleak` (scan, connect, subscribe).
  2. A Noise XX state machine (cryptography lib + careful nonce handling).
  3. Packet fragmentation/reassembly (BLE MTU is ~512B; bitchat packets
     can run kilobytes for media).
  4. Dedup + relay bookkeeping (TTL=7 hop counter).
  5. Identity persistence (load/save Noise static key + peer
     fingerprints).

For the hub case, we'd run only as a peripheral that accepts inbound
from phones and forwards inbound DTN payloads to the dispatcher.
Outbound (e.g. broadcasting `dtnReceipt`) requires central role.
"""

from __future__ import annotations

from typing import Optional

from server.transports.mesh_base import (
    InboundCallback,
    MeshTransport,
    SendResult,
)


class BleMeshTransport(MeshTransport):
    """Real BLE bitchat mesh transport. Requires a host with a BLE radio."""

    # bitchat advertises this 128-bit GATT service UUID. Confirm against
    # upstream before relying on it (the value below is illustrative).
    # TODO(bitchat-protocol): pin to upstream's authoritative UUID.
    BITCHAT_SERVICE_UUID = "F47B5E2D-4A9E-4C5A-9B3F-8E1D2C3A4B5C"

    def __init__(self, identity_keypair: tuple[bytes, bytes]) -> None:
        """`identity_keypair` is (private, public) for the local Noise
        static key. The hub-side identity is meant to be persistent —
        peers learn it once and trust it for the lifetime of the install.
        """
        priv, pub = identity_keypair
        if len(priv) != 32 or len(pub) != 32:
            raise ValueError("identity_keypair must be (32B priv, 32B pub)")
        self._priv = priv
        self._pub = pub
        self._callback: Optional[InboundCallback] = None

    def set_inbound_callback(self, callback: InboundCallback) -> None:
        self._callback = callback

    async def start(self) -> None:
        # TODO(bitchat-protocol): scan for the bitchat service UUID,
        # accept inbound peripheral connections, run Noise XX handshakes
        # for each accepted central, and subscribe to the data
        # characteristic. See upstream BLEService.swift for the full
        # state machine.
        raise NotImplementedError(
            "BleMeshTransport requires hardware (BLE radio) and is not "
            "wired in the hackathon build. Use SimMeshTransport for "
            "tests; real BLE is a production roadmap item."
        )

    async def stop(self) -> None:
        # TODO(bitchat-protocol): tear down the BLE central/peripheral,
        # close all Noise sessions, persist identity state.
        raise NotImplementedError(
            "BleMeshTransport.stop() requires hardware-backed runtime."
        )

    async def send(
        self,
        peer_pubkey: bytes,
        payload_type: int,
        payload: bytes,
    ) -> SendResult:
        # TODO(bitchat-protocol): encrypt with Noise XX, fragment to fit
        # BLE MTU, prepend 1-byte payload_type, write to peer's data
        # characteristic, await ack/NACK with the upstream framing.
        return SendResult(
            accepted=False,
            error="BleMeshTransport.send not implemented (requires hardware)",
        )
