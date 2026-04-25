"""In-process mesh transport for tests and the simulator UI.

Two `SimMeshTransport` instances connected to the same `SimMeshNetwork`
exchange `InboundEvent`s via an asyncio queue. No BLE radio involved.

Used by:
- `tests/transports/test_sim_mesh.py` (transport-level smoke)
- `tests/transports/test_mesh_dispatch.py` (end-to-end into dispatch_bundle)
- The hackathon simulator UI's mesh column (when one's wired up)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from server.transports.mesh_base import (
    InboundCallback,
    InboundEvent,
    MeshTransport,
    SendResult,
)


class SimMeshNetwork:
    """A trivial broadcast bus shared by all `SimMeshTransport` peers
    attached to it. A real BLE mesh would run TTL=7 hop-by-hop relay;
    this is the simplest possible substitute that's faithful enough for
    integration tests."""

    def __init__(self) -> None:
        self._peers: dict[bytes, "SimMeshTransport"] = {}

    def attach(self, peer: "SimMeshTransport") -> None:
        self._peers[peer.local_pubkey] = peer

    def detach(self, peer: "SimMeshTransport") -> None:
        self._peers.pop(peer.local_pubkey, None)

    async def deliver(
        self,
        sender: "SimMeshTransport",
        recipient_pubkey: bytes,
        payload_type: int,
        payload: bytes,
    ) -> SendResult:
        target = self._peers.get(recipient_pubkey)
        if target is None or target is sender:
            return SendResult(accepted=False, error="peer_not_attached")
        await target._inbound.put(
            InboundEvent(
                sender_pubkey=sender.local_pubkey,
                payload_type=payload_type,
                payload=payload,
                received_at=datetime.now(timezone.utc),
            )
        )
        return SendResult(accepted=True)


class SimMeshTransport(MeshTransport):
    def __init__(self, network: SimMeshNetwork, local_pubkey: bytes) -> None:
        if len(local_pubkey) != 32:
            raise ValueError("local_pubkey must be 32 bytes")
        self.network = network
        self.local_pubkey = local_pubkey
        self._inbound: asyncio.Queue[InboundEvent] = asyncio.Queue()
        self._callback: Optional[InboundCallback] = None
        self._task: Optional[asyncio.Task[None]] = None
        self._stopped = asyncio.Event()

    def set_inbound_callback(self, callback: InboundCallback) -> None:
        self._callback = callback

    async def start(self) -> None:
        self.network.attach(self)
        self._stopped.clear()
        self._task = asyncio.create_task(self._dispatch_loop(), name="sim-mesh-dispatch")

    async def stop(self) -> None:
        self.network.detach(self)
        self._stopped.set()
        if self._task is not None:
            # Wake the loop so it observes _stopped.
            await self._inbound.put(_SENTINEL)
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def send(
        self,
        peer_pubkey: bytes,
        payload_type: int,
        payload: bytes,
    ) -> SendResult:
        if len(peer_pubkey) != 32:
            return SendResult(accepted=False, error="peer_pubkey_wrong_size")
        return await self.network.deliver(self, peer_pubkey, payload_type, payload)

    async def _dispatch_loop(self) -> None:
        while not self._stopped.is_set():
            event = await self._inbound.get()
            if event is _SENTINEL:
                break
            if self._callback is not None:
                await self._callback(event)


# Marker put on the queue when stop() is called; not a real event.
_SENTINEL: InboundEvent = InboundEvent(
    sender_pubkey=b"\x00" * 32,
    payload_type=0,
    payload=b"",
    received_at=datetime.fromtimestamp(0, tz=timezone.utc),
)
