"""End-to-end dispatcher test.

Builds a sealed bundle in-memory, runs `dispatch_bundle`, asserts an
`InboundMessage` row appears with the correct channel/body. Also covers
duplicate detection via `SeenStore` and expired-bundle rejection.

Requires the test Postgres DB (uses the standard `db` fixture). The
account `bitchat_pubkey` migration is applied as part of the alembic
revision shipped in this PR.
"""

from datetime import UTC, datetime, timedelta

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import select

from server.db.identity import NGO, Account
from server.db.messages import InboundMessage
from server.dtn.amber import GeneralMessagePayload, SightingPayload
from server.dtn.dispatcher import dispatch_bundle
from server.dtn.packets import VERSION, DTNBundle, InnerType
from server.dtn.seal import seal
from server.dtn.store import SeenStore


def _hub_keypair() -> tuple[bytes, bytes]:
    priv = X25519PrivateKey.generate()
    pub = priv.public_key().public_bytes(
        encoding=Encoding.Raw, format=PublicFormat.Raw
    )
    return priv.private_bytes_raw(), pub


def _build_sighting_bundle(
    *, hub_pub: bytes, expires_at: int
) -> tuple[DTNBundle, SightingPayload]:
    inner = SightingPayload(
        case_id="c-2026-0481",
        client_msg_id="cm-dtn-1",
        free_text="saw her near the bus station",
        observed_at=1_745_600_000,
    )
    sealed = seal(inner.encode(), hub_pubkey_raw=hub_pub)
    bundle = DTNBundle(
        bundle_id=b"\x01" * 16,
        hub_pubkey=hub_pub,
        expires_at=expires_at,
        copies_remaining=10,
        inner_type=InnerType.SIGHTING,
        ephemeral_pubkey=sealed.ephemeral_pubkey,
        nonce=sealed.nonce,
        ciphertext=sealed.ciphertext,
        sig=b"\x99" * 64,
    )
    return bundle, inner


async def test_dispatch_inserts_inbound_message_row(db):
    priv, pub = _hub_keypair()
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(
        phone="+963500000001",
        ngo_id=ngo.ngo_id,
        bitchat_pubkey="aa" * 32,
        language="ar",
    )
    db.add(acc)
    await db.flush()

    expires_at = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    bundle, inner = _build_sighting_bundle(hub_pub=pub, expires_at=expires_at)

    result = await dispatch_bundle(
        bundle.encode(),
        db=db,
        hub_private_key=priv,
        source_channel="dtn",
        ngo_id=ngo.ngo_id,
        sender_phone=acc.phone,
    )
    assert result.ok
    assert result.duplicate is False
    assert result.inserted_msg_id is not None
    assert result.inner_type == InnerType.SIGHTING

    rows = (
        await db.execute(
            select(InboundMessage).where(InboundMessage.msg_id == result.inserted_msg_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    msg = rows[0]
    assert msg.channel == "dtn"
    assert msg.body == inner.free_text
    assert msg.in_reply_to_alert_id == inner.case_id
    assert msg.raw["kind"] == "sighting"
    assert msg.raw["client_msg_id"] == inner.client_msg_id


async def test_dispatch_general_message(db):
    priv, pub = _hub_keypair()
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+963500000002", ngo_id=ngo.ngo_id, bitchat_pubkey="bb" * 32)
    db.add(acc)
    await db.flush()

    expires_at = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    inner = GeneralMessagePayload(
        client_msg_id="cm-dtn-2",
        body="need water at block 4",
        sent_at=1_745_600_000,
    )
    sealed = seal(inner.encode(), hub_pubkey_raw=pub)
    bundle = DTNBundle(
        bundle_id=b"\x02" * 16,
        hub_pubkey=pub,
        expires_at=expires_at,
        copies_remaining=10,
        inner_type=InnerType.GENERAL_MESSAGE,
        ephemeral_pubkey=sealed.ephemeral_pubkey,
        nonce=sealed.nonce,
        ciphertext=sealed.ciphertext,
        sig=b"\x99" * 64,
    )

    result = await dispatch_bundle(
        bundle.encode(),
        db=db,
        hub_private_key=priv,
        source_channel="mesh",
        ngo_id=ngo.ngo_id,
        sender_phone=acc.phone,
    )
    assert result.ok
    rows = (
        await db.execute(
            select(InboundMessage).where(InboundMessage.msg_id == result.inserted_msg_id)
        )
    ).scalars().all()
    assert rows[0].channel == "mesh"
    assert rows[0].body == "need water at block 4"


async def test_dispatch_rejects_malformed_bytes(db):
    priv, _ = _hub_keypair()
    result = await dispatch_bundle(
        b"\x99" * 200,
        db=db,
        hub_private_key=priv,
        source_channel="dtn",
        ngo_id="01HX" + "0" * 22,
        sender_phone="+963500000099",
    )
    assert not result.ok
    assert result.error == "malformed_bundle"


async def test_dispatch_rejects_expired_bundle(db):
    priv, pub = _hub_keypair()
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+963500000003", ngo_id=ngo.ngo_id, bitchat_pubkey="cc" * 32)
    db.add(acc)
    await db.flush()

    bundle, _ = _build_sighting_bundle(hub_pub=pub, expires_at=1_000_000_000)
    result = await dispatch_bundle(
        bundle.encode(),
        db=db,
        hub_private_key=priv,
        source_channel="dtn",
        ngo_id=ngo.ngo_id,
        sender_phone=acc.phone,
    )
    assert result.error == "expired"


async def test_dispatch_rejects_decrypt_failure(db):
    _, pub = _hub_keypair()
    other_priv, _ = _hub_keypair()
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+963500000004", ngo_id=ngo.ngo_id, bitchat_pubkey="dd" * 32)
    db.add(acc)
    await db.flush()

    expires_at = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    bundle, _ = _build_sighting_bundle(hub_pub=pub, expires_at=expires_at)

    result = await dispatch_bundle(
        bundle.encode(),
        db=db,
        hub_private_key=other_priv,  # wrong key
        source_channel="dtn",
        ngo_id=ngo.ngo_id,
        sender_phone=acc.phone,
    )
    assert result.error is not None and result.error.startswith("decrypt_failed")


async def test_seen_store_short_circuits_duplicates(db):
    priv, pub = _hub_keypair()
    ngo = NGO(name="Warchild")
    db.add(ngo)
    await db.flush()
    acc = Account(phone="+963500000005", ngo_id=ngo.ngo_id, bitchat_pubkey="ee" * 32)
    db.add(acc)
    await db.flush()

    expires_at = int((datetime.now(UTC) + timedelta(hours=1)).timestamp())
    bundle, _ = _build_sighting_bundle(hub_pub=pub, expires_at=expires_at)
    seen = SeenStore(db)

    first = await dispatch_bundle(
        bundle.encode(),
        db=db,
        hub_private_key=priv,
        source_channel="dtn",
        ngo_id=ngo.ngo_id,
        sender_phone=acc.phone,
        seen_store=seen,
    )
    assert first.ok and not first.duplicate

    # Second call with the same bundle_id should be flagged as a duplicate.
    second = await dispatch_bundle(
        bundle.encode(),
        db=db,
        hub_private_key=priv,
        source_channel="dtn",
        ngo_id=ngo.ngo_id,
        sender_phone=acc.phone,
        seen_store=seen,
    )
    assert second.duplicate is True
    assert second.inserted_msg_id is None


def test_version_constant_matches_swift_layout():
    # Smoke check the constant didn't drift.
    assert VERSION == 0x01
