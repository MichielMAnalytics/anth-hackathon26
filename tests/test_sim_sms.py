from server.transports.sim_sms import SimSmsProvider


async def test_sim_send_records_messages():
    sim = SimSmsProvider()
    r1 = await sim.send(to="+972500000001", body="hello", idempotency_key="k1")
    r2 = await sim.send(to="+972500000002", body="bonjour", idempotency_key="k2")

    assert r1.provider_msg_id and r2.provider_msg_id
    assert len(sim.sent) == 2
    assert sim.sent[0].to == "+972500000001"
    assert sim.sent[0].body == "hello"


async def test_sim_send_idempotency_returns_same_id():
    sim = SimSmsProvider()
    r1 = await sim.send(to="+972500000001", body="hi", idempotency_key="k1")
    r2 = await sim.send(to="+972500000001", body="hi", idempotency_key="k1")

    assert r1.provider_msg_id == r2.provider_msg_id
    assert len(sim.sent) == 1   # second call deduped


async def test_sim_inbound_handler_returns_none():
    # SimSmsProvider drives inbound through its own UI / API, not via webhook.
    sim = SimSmsProvider()
    assert sim.inbound_handler() is None
