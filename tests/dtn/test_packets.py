"""Wire-format round trips for DTN bundles, receipts, and summary vectors.

These tests exercise the same byte layouts the iOS app uses
(`mobileapp/src/bitchatTests/DTNTests.swift`). If a value changes here,
the iOS test fixtures must change too — they share the wire.
"""

import pytest

from server.dtn.packets import (
    MAX_SUMMARY_BUNDLE_IDS,
    VERSION,
    DTNBundle,
    DTNReceipt,
    DTNSummary,
    InnerType,
)


def _make_bundle(*, copies: int = 10, ciphertext_size: int = 64) -> DTNBundle:
    return DTNBundle(
        bundle_id=bytes(range(16)),
        hub_pubkey=bytes(range(32)),
        expires_at=1_745_600_000,
        copies_remaining=copies,
        inner_type=InnerType.SIGHTING,
        ephemeral_pubkey=bytes(range(0x40, 0x60)),
        nonce=bytes(range(0x70, 0x7C)),
        ciphertext=b"\xAB" * ciphertext_size,
        sig=bytes(range(0x80, 0xC0)),
    )


def test_dtn_bundle_round_trip():
    bundle = _make_bundle()
    encoded = bundle.encode()
    assert encoded[0] == VERSION
    decoded = DTNBundle.decode(encoded)
    assert decoded == bundle


def test_dtn_bundle_round_trip_empty_ciphertext():
    bundle = _make_bundle(ciphertext_size=0)
    decoded = DTNBundle.decode(bundle.encode())
    assert decoded == bundle


def test_dtn_bundle_canonical_signing_excludes_sig():
    bundle = _make_bundle()
    canonical = bundle.canonical_bytes_for_signing()
    encoded = bundle.encode()
    assert canonical == encoded[:-64]


def test_dtn_bundle_decode_rejects_short_input():
    assert DTNBundle.decode(b"\x01" * 100) is None


def test_dtn_bundle_decode_rejects_bad_version():
    bundle = _make_bundle()
    bad = bytearray(bundle.encode())
    bad[0] = 0x99
    assert DTNBundle.decode(bytes(bad)) is None


def test_dtn_bundle_validates_field_sizes():
    with pytest.raises(ValueError):
        DTNBundle(
            bundle_id=b"\x00" * 8,  # wrong size
            hub_pubkey=bytes(32),
            expires_at=0,
            copies_remaining=1,
            inner_type=0,
            ephemeral_pubkey=bytes(32),
            nonce=bytes(12),
            ciphertext=b"",
            sig=bytes(64),
        )


def test_dtn_receipt_round_trip():
    r = DTNReceipt(
        bundle_id=bytes(16),
        hub_pubkey=bytes(32),
        signed_at=1_745_590_320,
        sig=bytes(64),
    )
    decoded = DTNReceipt.decode(r.encode())
    assert decoded == r
    assert r.canonical_bytes_for_signing() == r.encode()[:-64]


def test_dtn_receipt_decode_rejects_short_input():
    assert DTNReceipt.decode(b"\x01" * 50) is None


def test_dtn_summary_round_trip():
    ids = [bytes([i]) * 16 for i in range(5)]
    summary = DTNSummary(bundle_ids=ids)
    decoded = DTNSummary.decode(summary.encode())
    assert decoded == summary


def test_dtn_summary_round_trip_empty():
    summary = DTNSummary(bundle_ids=[])
    decoded = DTNSummary.decode(summary.encode())
    assert decoded == summary


def test_dtn_summary_rejects_oversize_input():
    with pytest.raises(ValueError):
        DTNSummary(bundle_ids=[bytes(16)] * (MAX_SUMMARY_BUNDLE_IDS + 1))


def test_dtn_summary_decode_rejects_truncated():
    summary = DTNSummary(bundle_ids=[bytes(16), bytes(16)])
    truncated = summary.encode()[:-1]
    assert DTNSummary.decode(truncated) is None
