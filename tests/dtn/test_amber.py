"""Round-trip + tolerant decode for the four amber inner-payload types."""

from server.dtn.amber import (
    GeneralMessagePayload,
    LocationReportPayload,
    ProfileUpdatePayload,
    Safety,
    SightingPayload,
)


def test_sighting_round_trip_with_location():
    p = SightingPayload(
        case_id="c-2026-0481",
        client_msg_id="0c5b2a4e-1e0c-4b1c-8f3a-3d7d3a3e2c11",
        free_text="saw her at homs market wearing red",
        observed_at=1_745_600_000,
        location_lat=36.7233,
        location_lng=36.9923,
    )
    decoded = SightingPayload.decode(p.encode())
    assert decoded is not None
    assert decoded.case_id == p.case_id
    assert decoded.client_msg_id == p.client_msg_id
    assert decoded.free_text == p.free_text
    assert decoded.observed_at == p.observed_at
    assert decoded.location_lat is not None
    assert abs(decoded.location_lat - p.location_lat) < 1e-9
    assert decoded.location_lng is not None
    assert abs(decoded.location_lng - p.location_lng) < 1e-9


def test_sighting_round_trip_without_location():
    p = SightingPayload(
        case_id="c-2026-0481",
        client_msg_id="abc123",
        free_text="no location",
        observed_at=1_745_600_000,
    )
    decoded = SightingPayload.decode(p.encode())
    assert decoded is not None
    assert decoded.location_lat is None
    assert decoded.location_lng is None


def test_sighting_decoder_skips_unknown_tlv():
    p = SightingPayload(
        case_id="c-2026-0001",
        client_msg_id="x",
        free_text="y",
        observed_at=1,
    )
    bytes_with_unknown = p.encode() + bytes([0xFE, 1, 0xAA])
    decoded = SightingPayload.decode(bytes_with_unknown)
    assert decoded is not None
    assert decoded.case_id == p.case_id


def test_location_report_round_trip():
    p = LocationReportPayload(
        client_msg_id="cmid-1",
        lat=36.20,
        lng=37.16,
        safety=Safety.UNSAFE,
        note="checkpoint up ahead",
        observed_at=1_745_600_000,
    )
    decoded = LocationReportPayload.decode(p.encode())
    assert decoded is not None
    assert decoded.client_msg_id == p.client_msg_id
    assert abs(decoded.lat - p.lat) < 1e-9
    assert abs(decoded.lng - p.lng) < 1e-9
    assert decoded.safety == Safety.UNSAFE
    assert decoded.note == p.note
    assert decoded.observed_at == p.observed_at


def test_location_report_with_empty_note():
    p = LocationReportPayload(
        client_msg_id="cmid-2",
        lat=0.0,
        lng=0.0,
        safety=Safety.SAFE,
        note="",
        observed_at=1,
    )
    decoded = LocationReportPayload.decode(p.encode())
    assert decoded is not None
    assert decoded.note == ""


def test_general_message_round_trip():
    p = GeneralMessagePayload(
        client_msg_id="cmid-3",
        body="message to NGO",
        sent_at=1_745_600_000,
    )
    decoded = GeneralMessagePayload.decode(p.encode())
    assert decoded == p


def test_profile_update_round_trip():
    p = ProfileUpdatePayload(
        name="Hidde Kehrer",
        phone_number="+963 21 555 0142",
        language="en",
        profession="field worker",
    )
    decoded = ProfileUpdatePayload.decode(p.encode())
    assert decoded == p


def test_profile_update_round_trip_no_profession():
    p = ProfileUpdatePayload(
        name="Sara",
        phone_number="+963 21 555 0143",
        language="ar",
    )
    decoded = ProfileUpdatePayload.decode(p.encode())
    assert decoded is not None
    assert decoded.profession is None


def test_truncated_input_returns_none():
    p = SightingPayload(
        case_id="c-1", client_msg_id="x", free_text="y", observed_at=1
    )
    truncated = p.encode()[:5]  # keep only the first TLV header partial
    assert SightingPayload.decode(truncated) is None


def test_required_field_missing_returns_none():
    # Encode only the case_id TLV — missing client_msg_id, free_text, observed_at.
    only_case_id = bytes([0x01, 3]) + b"abc"
    assert SightingPayload.decode(only_case_id) is None
