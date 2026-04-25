# Mobile app — SafeThread (`bitchat-amber`)

The user-side iOS / macOS slice of the amber-alert system. Forked from
[`permissionlesstech/bitchat`](https://github.com/permissionlesstech/bitchat) and stripped down to a focused hub-and-spoke amber-alert receiver with a 5-screen UI.

> **Full codebase + buildable project:** https://github.com/hidden-salmon/bitchat-amber/tree/amber-alert
>
> What lives in *this* folder is a curated copy of the **files we authored** plus the upstream-edit notes — enough to read the design and review the protocol additions without cloning the entire bitchat fork.

---

## Why it matters — the shortlist

- 🛰️ **Works with no internet.** Alerts arrive over Bluetooth mesh, hopping phone-to-phone for up to 7 relays. Sightings, photos, and messages travel the same way back to the NGO.
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
    ├── upstream-edits.md              ← notes on the 4 upstream files we patched
    ├── bitchat/
    │   ├── Models/AmberPackets.swift           ← TLV encoders for our 5 new payload types
    │   ├── Services/HubClient.swift            ← HTTP + WS client to the NGO hub
    │   ├── ViewModels/AlertsViewModel.swift    ← app state + observable
    │   └── Views/                              ← 9 SwiftUI files
    │       ├── AmberRootView.swift             ← onboarded? → TabView : OnboardingView
    │       ├── OnboardingView.swift            ← registration form + Skip link
    │       ├── AlertsListView.swift            ← inbound alerts + filter pills
    │       ├── SubmitInfoView.swift            ← per-case sighting modal (photo, voice, location)
    │       ├── MapView.swift                   ← location pinning + safe/unsafe + geohash
    │       ├── MessageNGOView.swift            ← free-form messages to NGO
    │       ├── ProfileView.swift               ← edit profile
    │       ├── SafeThreadBrand.swift           ← brand colors + wordmark
    │       └── DeliveryBadge.swift             ← inline delivery-status pill
    └── bitchatTests/
        └── AmberPacketsTests.swift             ← TLV round-trip + tolerant decode
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
