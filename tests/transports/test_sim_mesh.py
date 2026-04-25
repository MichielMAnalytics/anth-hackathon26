"""Transport-level smoke for SimMeshTransport — independent of dispatcher / DB."""

import asyncio
from datetime import datetime, timezone

import pytest

from server.transports.mesh_base import InboundEvent
from server.transports.sim_mesh import SimMeshNetwork, SimMeshTransport


def _pubkey(seed: int) -> bytes:
    return bytes([seed]) * 32


async def test_two_peers_round_trip_a_payload():
    network = SimMeshNetwork()
    a = SimMeshTransport(network, local_pubkey=_pubkey(0xAA))
    b = SimMeshTransport(network, local_pubkey=_pubkey(0xBB))

    received: list[InboundEvent] = []

    async def on_b_inbound(event: InboundEvent) -> None:
        received.append(event)

    b.set_inbound_callback(on_b_inbound)
    await a.start()
    await b.start()

    try:
        result = await a.send(
            peer_pubkey=b.local_pubkey,
            payload_type=0x25,  # dtnBundle
            payload=b"hello",
        )
        assert result.accepted, result.error

        # Give the dispatch loop one tick.
        for _ in range(20):
            if received:
                break
            await asyncio.sleep(0.01)

        assert len(received) == 1
        event = received[0]
        assert event.sender_pubkey == a.local_pubkey
        assert event.payload_type == 0x25
        assert event.payload == b"hello"
        assert isinstance(event.received_at, datetime)
        assert event.received_at.tzinfo is timezone.utc
    finally:
        await a.stop()
        await b.stop()


async def test_send_to_unknown_peer_is_rejected():
    network = SimMeshNetwork()
    a = SimMeshTransport(network, local_pubkey=_pubkey(0xAA))
    await a.start()
    try:
        result = await a.send(
            peer_pubkey=_pubkey(0xCC),  # nobody attached
            payload_type=0x25,
            payload=b"x",
        )
        assert not result.accepted
        assert result.error == "peer_not_attached"
    finally:
        await a.stop()


async def test_send_to_self_is_rejected():
    network = SimMeshNetwork()
    a = SimMeshTransport(network, local_pubkey=_pubkey(0xAA))
    await a.start()
    try:
        result = await a.send(
            peer_pubkey=a.local_pubkey,
            payload_type=0x25,
            payload=b"x",
        )
        assert not result.accepted
    finally:
        await a.stop()


async def test_pubkey_validation():
    network = SimMeshNetwork()
    with pytest.raises(ValueError):
        SimMeshTransport(network, local_pubkey=b"\x00" * 16)


async def test_send_validates_peer_pubkey_size():
    network = SimMeshNetwork()
    a = SimMeshTransport(network, local_pubkey=_pubkey(0xAA))
    await a.start()
    try:
        result = await a.send(
            peer_pubkey=b"\x00" * 16,  # too short
            payload_type=0x25,
            payload=b"x",
        )
        assert not result.accepted
        assert result.error == "peer_pubkey_wrong_size"
    finally:
        await a.stop()


async def test_stop_drains_pending_inbound():
    """Sanity: stopping a peer with queued inbound shouldn't hang."""
    network = SimMeshNetwork()
    a = SimMeshTransport(network, local_pubkey=_pubkey(0xAA))
    b = SimMeshTransport(network, local_pubkey=_pubkey(0xBB))
    b.set_inbound_callback(lambda _evt: asyncio.sleep(0))  # no-op
    await a.start()
    await b.start()
    try:
        await a.send(b.local_pubkey, 0x25, b"x")
    finally:
        await a.stop()
        await asyncio.wait_for(b.stop(), timeout=2.0)
