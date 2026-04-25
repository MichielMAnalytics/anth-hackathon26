"""End-to-end smoke test: verifies the entire foundation works as one piece."""
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from server.auth.ngo import create_operator_token, verify_operator_token
from server.db.alerts import Alert
from server.db.identity import NGO, Account
from server.db.messages import Bucket
from server.transports.sim_sms import SimSmsProvider


async def test_health_endpoint_responds(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "db": "ok"}


async def test_full_data_round_trip_through_test_db(db):
    # Insert an NGO, an alert, a recipient, and a synthetic bucket.
    ngo = NGO(name="Warchild", region_geohash_prefix="sv")
    db.add(ngo)
    await db.flush()

    acc = Account(
        phone="+972500000001",
        ngo_id=ngo.ngo_id,
        language="he",
        home_geohash="sv8d6q",
    )
    alert = Alert(
        ngo_id=ngo.ngo_id,
        person_name="Maya",
        last_seen_geohash="sv8d6",
        status="active",
        category="missing_child",
        urgency_tier="high",
        urgency_score=0.9,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add_all([acc, alert])
    await db.flush()

    b = Bucket(
        bucket_key=f"{alert.alert_id}|sv8d|hb1",
        ngo_id=ngo.ngo_id,
        alert_id=alert.alert_id,
        geohash_prefix_4="sv8d",
        window_start=datetime.now(UTC),
    )
    db.add(b)
    await db.flush()

    # Hot-path index check: a prefix LIKE query for region recipients.
    rows = (
        await db.execute(
            select(Account).where(Account.home_geohash.like("sv8d%"))
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_pgvector_query_runs(db):
    # Sanity: the pgvector cosine-distance operator is callable.
    result = (
        await db.execute(
            text("SELECT '[1,0,0]'::vector <=> '[0,1,0]'::vector AS d")
        )
    ).scalar()
    assert 0.0 < float(result) < 2.0


async def test_auth_token_round_trip():
    tok = create_operator_token(operator_id="op-1", ngo_id="ngo-x")
    payload = verify_operator_token(tok)
    assert payload["ngo_id"] == "ngo-x"


async def test_sim_sms_provider_records_send():
    sim = SimSmsProvider()
    r = await sim.send(to="+972500000099", body="ping", idempotency_key="i1")
    assert r.provider_msg_id.startswith("sim-")
    assert sim.sent[0].body == "ping"
