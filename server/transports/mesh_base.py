"""Mesh-transport adapter Protocol.

Mirrors the shape of `server/transports/sms_base.py` so the agent layer
can swap mesh transports the same way it swaps SMS providers. Two
implementations land in this branch:

  - `SimMeshTransport` — in-process, asyncio-queue-backed; used in tests
    and the simulator UI.
  - `BleMeshTransport`  — real BLE skeleton via `bleak`; not exercised
    in CI (requires hardware), but imports cleanly.

Inbound packets flow through a registered callback. The callback is
typed against `InboundEvent`; concrete `MeshTransport`s call
`_emit_inbound(event)` to fire it. The hub wires the callback to
`server.dtn.dispatcher.dispatch_bundle` for DTN payload types.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Awaitable, Callable, Optional, Protocol, runtime_checkable


@dataclass
class SendResult:
    """Outcome of an outbound mesh send attempt."""

    accepted: bool
    error: Optional[str] = None


@dataclass
class InboundEvent:
    """A mesh packet observed at the local node."""

    sender_pubkey: bytes  # 32B X25519 / Noise static key of the sender peer
    payload_type: int  # NoisePayloadType byte (e.g. 0x25 dtnBundle)
    payload: bytes  # raw payload bytes (no leading type byte)
    received_at: datetime  # UTC timestamp at observation


InboundCallback = Callable[[InboundEvent], Awaitable[None]]


@runtime_checkable
class MeshTransport(Protocol):
    """Async transport that joins the bitchat mesh and exchanges
    encrypted payloads with directly-connected peers.

    The `start()`/`stop()` lifecycle is managed by the hub process; the
    inbound callback is registered before `start()` and is fired from
    within the transport's own asyncio context.
    """

    def set_inbound_callback(self, callback: InboundCallback) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def send(
        self,
        peer_pubkey: bytes,
        payload_type: int,
        payload: bytes,
    ) -> SendResult: ...
