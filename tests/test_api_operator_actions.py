"""Tests for operator-initiated write endpoints.

Covers POST /api/alerts, POST /api/requests, POST /api/cases/{id}/messages.
Each must persist a ToolCall (decision_id NULL, decided_by=operator) plus
an OutboundMessage, and the case-message endpoint's outbound must surface
in /api/incidents/{id}/messages.
"""
from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from server.db.alerts import Alert
from server.db.decisions import ToolCall
from server.db.identity import NGO, Account
from server.db.outbound import OutboundMessage


@pytest.fixture(autouse=True)
def stub_llm(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")


@pytest.fixture
async def seeded_incident(test_session_maker):
    """Single NGO + Account + Alert; cleaned up after."""
    name = "OpActionsNGO"
    phone = "+972500003333"
    async with test_session_maker() as s:
        # Pre-purge any leftovers
        prior = (
            await s.execute(select(NGO.ngo_id).where(NGO.name == name))
        ).scalars().all()
        if prior:
            alert_ids = (
                await s.execute(select(Alert.alert_id).where(Alert.ngo_id.in_(prior)))
            ).scalars().all()
            if alert_ids:
                tc_ids = (
                    await s.execute(
                        select(ToolCall.call_id).where(
                            ToolCall.args["incident_id"].astext.in_(alert_ids)
                        )
                    )
                ).scalars().all()
                if tc_ids:
                    await s.execute(
                        delete(OutboundMessage).where(
                            OutboundMessage.tool_call_id.in_(tc_ids)
                        )
                    )
                    await s.execute(delete(ToolCall).where(ToolCall.call_id.in_(tc_ids)))
                await s.execute(delete(Alert).where(Alert.alert_id.in_(alert_ids)))
            await s.execute(delete(Account).where(Account.phone == phone))
            await s.execute(delete(NGO).where(NGO.ngo_id.in_(prior)))
            await s.commit()

        ngo = NGO(name=name)
        s.add(ngo)
        await s.flush()
        s.add(Account(phone=phone, ngo_id=ngo.ngo_id))
        alert = Alert(
            ngo_id=ngo.ngo_id,
            person_name="Yara",
            description="Test missing person",
            status="active",
        )
        s.add(alert)
        await s.flush()
        await s.commit()
        out = {"ngo_id": ngo.ngo_id, "alert_id": alert.alert_id, "phone": phone}

    yield out

    async with test_session_maker() as s:
        tc_ids = (
            await s.execute(
                select(ToolCall.call_id).where(
                    ToolCall.args["incident_id"].astext == out["alert_id"]
                )
            )
        ).scalars().all()
        if tc_ids:
            await s.execute(
                delete(OutboundMessage).where(OutboundMessage.tool_call_id.in_(tc_ids))
            )
            await s.execute(delete(ToolCall).where(ToolCall.call_id.in_(tc_ids)))
        await s.execute(delete(Alert).where(Alert.alert_id == out["alert_id"]))
        await s.execute(delete(Account).where(Account.phone == out["phone"]))
        await s.execute(delete(NGO).where(NGO.ngo_id == out["ngo_id"]))
        await s.commit()


async def test_post_alert_persists_toolcall_and_outbound(
    client, seeded_incident, test_session_maker
):
    resp = await client.post(
        "/api/alerts",
        headers={"X-Operator-Id": "op-senior"},
        json={
            "incidentId": seeded_incident["alert_id"],
            "audienceId": "all_recipients",
            "channels": "fallback",
            "region": "IRQ_BAGHDAD",
            "body": "Amber Alert test broadcast",
            "attachments": {},
        },
    )
    assert resp.status_code == 200, resp.text
    ack = resp.json()
    assert ack["ok"] is True
    assert ack["queued"] >= 1
    assert ack["channels"] == ["fallback"]

    async with test_session_maker() as s:
        tcs = (
            await s.execute(
                select(ToolCall).where(
                    ToolCall.args["incident_id"].astext == seeded_incident["alert_id"]
                )
            )
        ).scalars().all()
        assert len(tcs) == 1
        tc = tcs[0]
        assert tc.tool_name == "send"
        assert tc.decision_id is None
        assert tc.decided_by == "op-senior"
        assert tc.approval_status == "approved"
        assert tc.args["send_mode"] == "alert"

        outs = (
            await s.execute(
                select(OutboundMessage).where(OutboundMessage.tool_call_id == tc.call_id)
            )
        ).scalars().all()
        assert len(outs) == 1
        assert outs[0].channel == "fallback"
        assert outs[0].body == "Amber Alert test broadcast"


async def test_post_alert_blocks_junior_operators(client, seeded_incident):
    resp = await client.post(
        "/api/alerts",
        headers={"X-Operator-Id": "op-junior"},
        json={
            "incidentId": seeded_incident["alert_id"],
            "audienceId": "all_recipients",
            "channels": "fallback",
            "body": "should not go through",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"] == "permission"


async def test_post_request_persists_with_send_mode_request(
    client, seeded_incident, test_session_maker
):
    resp = await client.post(
        "/api/requests",
        headers={"X-Operator-Id": "op-senior"},
        json={
            "incidentId": seeded_incident["alert_id"],
            "audienceId": "medical_responders",
            "channels": "sms",
            "body": "Need insulin urgently in this region",
        },
    )
    assert resp.status_code == 200, resp.text
    async with test_session_maker() as s:
        tcs = (
            await s.execute(
                select(ToolCall).where(
                    ToolCall.args["incident_id"].astext == seeded_incident["alert_id"]
                )
            )
        ).scalars().all()
        assert any(tc.args.get("send_mode") == "request" for tc in tcs)


async def test_case_message_appears_in_incident_messages(
    client, seeded_incident, test_session_maker
):
    body_text = "Operator follow-up message"
    resp = await client.post(
        f"/api/cases/{seeded_incident['alert_id']}/messages",
        headers={"X-Operator-Id": "op-senior"},
        json={"body": body_text, "via": "app", "audienceId": "all_recipients"},
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["ok"] is True
    assert payload["broadcast"]["ok"] is True

    # Now /api/incidents/{id}/messages should include this outbound row.
    msgs_resp = await client.get(
        f"/api/incidents/{seeded_incident['alert_id']}/messages",
        headers={"X-Operator-Id": "op-senior"},
    )
    assert msgs_resp.status_code == 200
    msgs = msgs_resp.json()
    assert any(m.get("outbound") and m.get("body") == body_text for m in msgs)


async def test_unknown_audience_rejected(client, seeded_incident):
    resp = await client.post(
        "/api/alerts",
        headers={"X-Operator-Id": "op-senior"},
        json={
            "incidentId": seeded_incident["alert_id"],
            "audienceId": "does-not-exist",
            "channels": "app",
            "body": "x",
        },
    )
    assert resp.status_code == 400
