"""DTN (Delay-Tolerant Networking) decoder + dispatcher.

Wire format and crypto are mirrored from the iOS app's
`mobileapp/src/bitchat/Models/DTNPackets.swift`. Phones gossip sealed
bundles peer-to-peer over the bitchat mesh until one reaches internet
and POSTs them to the hub; the hub decrypts, dispatches by inner type
into the same `InboundMessage` ingestion path other channels use.

Public surface:
- `packets`: DTNBundle / DTNReceipt / DTNSummary fixed-binary codecs.
- `seal`:    sealed-box helpers (X25519 + HKDF-SHA256 + ChaCha20Poly1305).
- `amber`:   tolerant TLV decoders for the four inner amber payload types.
- `dispatcher.dispatch_bundle`: the high-level entry point a hub adapter
  (HTTP route or pybitchat node) calls with raw bundle bytes.
- `store.SeenStore`: idempotency cache for `bundle_id`s the hub already
  acknowledged.

The `/app/dtn/*` HTTP endpoints are not in this module — a teammate owns
the API tier. This module is library code only.
"""

from server.dtn.amber import (
    GeneralMessagePayload,
    LocationReportPayload,
    ProfileUpdatePayload,
    SightingPayload,
)
from server.dtn.dispatcher import DispatchResult, dispatch_bundle
from server.dtn.packets import DTNBundle, DTNReceipt, DTNSummary, InnerType
from server.dtn.seal import open as seal_open
from server.dtn.seal import seal as seal_seal
from server.dtn.store import SeenStore

__all__ = [
    "DTNBundle",
    "DTNReceipt",
    "DTNSummary",
    "InnerType",
    "SightingPayload",
    "LocationReportPayload",
    "GeneralMessagePayload",
    "ProfileUpdatePayload",
    "seal_open",
    "seal_seal",
    "dispatch_bundle",
    "DispatchResult",
    "SeenStore",
]
