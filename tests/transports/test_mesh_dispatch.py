"""End-to-end: a sim mesh peer receives a DTN bundle payload, the
adapter forwards it to the dispatcher, and an InboundMessage row lands
with channel='mesh'.

Requires the test Postgres DB.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select

from server.db.identity import NGO, Account
from server.db.messages import InboundMessage
from server.dtn.amber import GeneralMessagePayload
from server.dtn.dispatcher import dispatch_bundle
from server.dtn.packets import DTNBundle, InnerType
from server.dtn.seal import seal
from server.transports.mesh_base import InboundEvent
from server.transports.sim_mesh import SimMeshNetwork, SimMeshTransport


def _hub_keypair() -> tuple[bytes, bytes]:
    priv = X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=Encoding.Raw, format=PublicFormat.Raw
    )
    return priv.private_bytes_raw(), pub


def _pubkey(seed: int) -> bytes:
    return bytes([seed]) * 32


async def test_inbound_dtn_bundle_lands_as_inbound_message_row(db):
    priv, pub = _hub_keypair()
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+963500001000", ngo_id=ngo.ngo_id, bitchat_pubkey="ff" * 32)
    db.add(acc)
    await db.flush()

    # Build a sealed bundle from "phone A" to the hub.
    expires_at = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    inner = GeneralMessagePayload(
        client_msg_id="cm-mesh-1",
        body="message via mesh",
        sent_at=1_745_600_000,
    )
    sealed = seal(inner.encode(), hub_pubkey_raw=pub)
    bundle = DTNBundle(
        bundle_id=b"\x42" * 16,
        hub_pubkey=pub,
        expires_at=expires_at,
        copies_remaining=10,
        inner_type=InnerType.GENERAL_MESSAGE,
        ephemeral_pubkey=sealed.ephemeral_pubkey,
        nonce=sealed.nonce,
        ciphertext=sealed.ciphertext,
        sig=b"\x99" * 64,
    )

    network = SimMeshNetwork()
    phone_a = SimMeshTransport(network, local_pubkey=_pubkey(0xA1))
    hub = SimMeshTransport(network, local_pubkey=_pubkey(0xBB))

    async def on_hub_inbound(event: InboundEvent) -> None:
        # Real hub would parse `payload_type` and route. For DTN bundle
        # types (0x25), we hand the raw bytes to the dispatcher.
        if event.payload_type != 0x25:
            return
        await dispatch_bundle(
            event.payload,
            db=db,
            hub_private_key=priv,
            source_channel="mesh",
            ngo_id=ngo.ngo_id,
            sender_phone=acc.phone,  # in real life, resolved from event.sender_pubkey
        )

    hub.set_inbound_callback(on_hub_inbound)
    await phone_a.start()
    await hub.start()

    try:
        result = await phone_a.send(
            peer_pubkey=hub.local_pubkey,
            payload_type=0x25,
            payload=bundle.encode(),
        )
        assert result.accepted

        # Wait for the dispatch loop + DB insert to land.
        for _ in range(50):
            rows = (
                await db.execute(select(InboundMessage).where(InboundMessage.channel == "mesh"))
            ).scalars().all()
            if rows:
                break
            await asyncio.sleep(0.02)
        assert len(rows) == 1
        assert rows[0].body == "message via mesh"
        assert rows[0].sender_phone == acc.phone
    finally:
        await phone_a.stop()
        await hub.stop()
