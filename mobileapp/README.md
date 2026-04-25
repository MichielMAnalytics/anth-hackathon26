# Mobile app — SafeThread (`bitchat-amber`)

The user-side iOS / macOS slice of the amber-alert system. Forked from
[`permissionlesstech/bitchat`](https://github.com/permissionlesstech/bitchat) and stripped down to a focused hub-and-spoke amber-alert receiver with a 5-screen UI.

> **Full codebase + buildable project:** https://github.com/hidden-salmon/bitchat-amber/tree/amber-alert
>
> What lives in *this* folder is a curated copy of the **files we authored** plus the upstream-edit notes — enough to read the design and review the protocol additions without cloning the entire bitchat fork.

---

## Why it matters — the shortlist

- 🛰️ **Works with no internet.** Alerts arrive over Bluetooth mesh, hopping phone-to-phone for up to 7 relays. Sightings, photos, and messages travel the same way back to the NGO.
- 🐢 **Carries your message across time, not just space.** A delay-tolerant store-and-forward layer: if no path to the hub exists right now, your sighting is wrapped as a sealed bundle that any nearby phone persists for up to 48h and gossipps onward whenever new peers appear. Spray-and-wait copy budget (L=10) and summary-vector exchange keep BLE airtime bounded — no exponential flooding.
- 🌐 **Three independent paths to the NGO.** Direct internet (HTTPS + WebSocket), bitchat mesh (BLE), and Nostr relays (censorship-resistant). The app uses whichever is up; the user never picks.
- 🛡️ **Hub-and-spoke by construction.** Users can only ever message the NGO — never each other. Enforced at the protocol layer, not a UI guideline.
- 🔐 **End-to-end encrypted.** Every payload rides bitchat's Noise XX channel with forward secrecy. Triple-tap emergency wipe inherited from bitchat.
- 🗺️ **Locations as 7-char codes.** Pin a spot on the map → get a geohash like `SY3R6X4` you can speak over a voice call, scrawl on paper, or send as SMS. Anyone with the app can paste it back to find the same place.
- 📷 **Multi-modal sightings.** Free-text + optional photo (auto-compressed JPEG) + optional voice note (AAC).
- ✓ **Delivery confirmations.** "sending → sent → received by NGO" badges so reporters know their tip actually landed.
- 🧱 **Tiny, focused surface.** Five screens total. No chat, no peer list, no settings rabbit hole.
- 🧪 **Demo-able with no backend.** A "Skip" link in onboarding bootstraps sample alerts so the app is fully clickable on a phone or simulator before the hub is even up.
- ♻️ **Forward-compatible wire format.** TLV envelopes silently skip unknown fields, so either side of the protocol can evolve without breaking older clients.

## What's in this folder

```
mobileapp/
├── README.md                          ← this file
└── src/
    ├── upstream-edits.md              ← notes on the 6 upstream files we patched
    ├── bitchat/
    │   ├── Models/
    │   │   ├── AmberPackets.swift              ← TLV encoders for the 5 amber payload types
    │   │   └── DTNPackets.swift                ← bundle/receipt/summary wire format + sealed-box
    │   ├── Services/
    │   │   ├── HubClient.swift                 ← HTTP + WS client to the NGO hub
    │   │   ├── DTNStore.swift                  ← disk-backed bundle storage + quotas (512KB / 15 / 48h)
    │   │   └── DTNRelay.swift                  ← spray-and-wait gossip + summary-vector anti-entropy
    │   ├── ViewModels/AlertsViewModel.swift    ← app state + observable + DTN fallback
    │   └── Views/                              ← 9 SwiftUI files
    │       ├── AmberRootView.swift             ← onboarded? → TabView : OnboardingView
    │       ├── OnboardingView.swift            ← registration form + Skip link
    │       ├── AlertsListView.swift            ← inbound alerts + filter pills
    │       ├── SubmitInfoView.swift            ← per-case sighting modal (photo, voice, location)
    │       ├── MapView.swift                   ← location pinning + safe/unsafe + geohash
    │       ├── MessageNGOView.swift            ← free-form messages to NGO
    │       ├── ProfileView.swift               ← edit profile
    │       ├── SafeThreadBrand.swift           ← brand colors + wordmark
    │       └── DeliveryBadge.swift             ← inline delivery-status pill (incl. "queued (mesh)")
    └── bitchatTests/
        ├── AmberPacketsTests.swift             ← TLV round-trip + tolerant decode
        └── DTNTests.swift                      ← bundle/receipt/summary round-trip,
                                                  store quotas + eviction priority,
                                                  spray-and-wait halving, sealed-box round-trip
```

## How it talks to the hub

```
                  ┌─────────────────────────┐
                  │      THE APP            │
                  └────┬───────────────┬────┘
                       │               │
              ┌────────┘               └─────────┐
              │ Pipe 1:                Pipe 2:   │
              │ INTERNET               BITCHAT   │
              │ (HTTPS + WS)           MESH (BLE)│
              ▼                                  ▼
       ┌─────────────┐                 ┌─────────────────┐
       │  /v1/...    │                 │  encrypted      │
       │  endpoints  │                 │  bitchat        │
       │  + WS push  │                 │  packets        │
       └──────┬──────┘                 └────────┬────────┘
              │                                 │
              │                                 │  (via mesh hops, eventually
              │                                 │   reaching a phone with
              │                                 │   internet OR the hub's
              │                                 │   pybitchat node)
              ▼                                 ▼
                ┌─────────────────────────────┐
                │           NGO HUB           │
                │  FastAPI + PostgreSQL +     │
                │  pybitchat node             │
                └─────────────────────────────┘
```

The app **never** touches SMS — that's the hub's separate dispatch module reaching dumbphones who don't have the app.

## Hub-side contract (what teammates need to implement)

```
POST /v1/register           { name, phone_number, profession?, language, bitchat_pubkey, apns_token? }
POST /v1/sighting           { case_id, free_text, location?, client_msg_id, observed_at }
                            (or multipart/form-data with photo / voice attachments)
POST /v1/profile            { name, phone_number, profession?, language }
POST /v1/message            { body, client_msg_id, sent_at }
POST /v1/location_report    { client_msg_id, lat, lng, safety: "safe"|"unsafe", note, observed_at }
GET  /v1/alerts/active      → { alerts: [ { case_id, title, summary, issued_at, version, photo_url?, category } ] }
WS   /v1/stream             → events: ALERT_ISSUED | STATUS_UPDATE | ACK
```

Plus a `pybitchat` node on the hub side that joins the mesh, broadcasts `alert` (0x20) payloads signed with the NGO key, and listens for `sighting` (0x21) / `locationReport` (0x22) / `generalMessage` (0x23) / `profileUpdate` (0x24) addressed to its key.

## Delay-tolerant networking (DTN) — store-and-forward across time

The mesh as it ships only forwards packets *currently in flight*. If at the moment your sighting hits the mesh there's no continuous path to the hub, it drops. That's a real gap for war-zone scenarios where any given person might be in a connectivity dead zone for hours or days.

The DTN layer fixes that. When the internet path fails, the app wraps the inner amber payload as a sealed bundle and stores it on disk. Nearby phones gossip these bundles peer-to-peer until one of them lands on a phone with internet — that phone POSTs to the hub and the hub broadcasts a signed receipt that flushes the bundle from every carrier.

**Wire format — three new payload types** (`bitchat/Models/DTNPackets.swift`):

```
0x25 dtnBundle   — { bundle_id (16B), hub_pubkey (32B), expires_at, copies_remaining,
                     inner_type, ephemeral_pubkey (32B), nonce (12B), ciphertext, sig (64B) }
0x26 dtnReceipt  — { bundle_id, hub_pubkey, signed_at, sig }   ← signed by hub Ed25519 key
0x27 dtnSummary  — { count, bundle_ids[] }                     ← anti-entropy summary vector
```

The inner payload is sealed to the hub's X25519 key (ephemeral X25519 + HKDF-SHA256 + ChaChaPoly), so carriers see metadata but never the contents. The bundle itself is signed by the originating reporter's Ed25519 key.

**How flooding is bounded — three mitigations stacked:**

1. **Anti-entropy summary vectors.** When two phones meet, they swap a `dtnSummary` (just the IDs they hold) before sending any bundles. Each side then transmits *only* what the other is missing. In a dense cluster this dedup dominates — most pairs exchange zero bundles.
2. **Spray-and-wait.** Each new bundle starts with `copies_remaining = 10`. On hand-off, the sender keeps `ceil(n/2)` and the recipient gets `floor(n/2)`. Once a phone holds the last copy it only delivers direct to the hub, never gossipps. Total carriers in the network ≤ 10.
3. **Receipt-driven eviction.** When the hub gets the bundle it broadcasts a signed `dtnReceipt`. The receipt floods the same way and every carrier evicts the matching bundle.

**Per-phone cost — kept deliberately low for war-zone hardware** (`DTNConfig` in `DTNPackets.swift`):

| Knob | Value | Why |
|---|---|---|
| `storeMaxBytes` | 512 KB | Storage-starved phones |
| `storeMaxBundles` | 15 | Hard cap independent of byte budget |
| `bundleTTLSeconds` | 48 h | Long enough for delivery, short enough to bound carry |
| `initialCopiesRemaining` | 10 | Spray-and-wait L; trades coverage for traffic |
| `perBundlePeerCooldownSeconds` | 60 min | Don't re-gossip same bundle to same peer |
| `perPeerGossipCooldownSeconds` | 10 min | Limit summary-exchange frequency |
| `purgeIntervalSeconds` | 10 min | Drop expired bundles |

Eviction order when full: expired first, then oldest-first across foreign (carry-for-someone-else) bundles. Bundles you originated locally are evicted last — the user's *own* sighting/message is what we most want to deliver.

**Hub-side contract (additional, not yet implemented by teammates):**

```
POST /v1/dtn/deliver        body: raw dtnBundle bytes
                            on accept: hub broadcasts dtnReceipt to mesh + Nostr
GET  /v1/dtn/seen           query: ?ids=<csv>  → { unseen_ids: [...] }
                            (carriers with internet can probe before flooding)
```

The `pybitchat` node also needs to: accept inbound `dtnBundle` packets, decrypt the ciphertext using the hub Noise/X25519 key, dispatch by `inner_type` to the existing `/v1/sighting` / `/v1/message` / `/v1/location_report` / `/v1/profile` handlers, and emit signed `dtnReceipt` packets back onto the mesh.

## How to run / build

See the full README at https://github.com/hidden-salmon/bitchat-amber for the buildable project. Quick reference:

```bash
git clone https://github.com/hidden-salmon/bitchat-amber.git
cd bitchat-amber
# macOS:
xcodebuild -project bitchat.xcodeproj -scheme "bitchat (macOS)" \
  -destination "platform=macOS" -derivedDataPath /tmp/bca \
  CODE_SIGNING_ALLOWED=NO build
open /tmp/bca/Build/Products/Debug/bitchat.app
# iOS Simulator (boots a populated demo via the --demo launch flag):
SIM=$(xcrun simctl create "Amber Demo" "com.apple.CoreSimulator.SimDeviceType.iPhone-16-Pro" "com.apple.CoreSimulator.SimRuntime.iOS-26-4")
xcrun simctl boot "$SIM" && open -a Simulator
xcodebuild -project bitchat.xcodeproj -scheme "bitchat (iOS)" \
  -destination "id=$SIM" -derivedDataPath /tmp/bca-ios CODE_SIGNING_ALLOWED=NO build
APP=$(find /tmp/bca-ios/Build/Products -name bitchat.app -type d | head -1)
xcrun simctl install "$SIM" "$APP"
xcrun simctl launch "$SIM" chat.bitchat --demo
```
