# SafeThread — P2P amber alerts for warzones

When NGOs need to find missing people in places where the cell network is down or
censored, **SafeThread** lets them broadcast an alert and collect sightings from
civilians whose phones have no internet — by piggybacking on
[bitchat](https://github.com/permissionlesstech/bitchat)'s Bluetooth mesh.

> Hackathon submission, Anthropic 2026.

## How it works

```
   ┌──────────────┐                              ┌────────────────────────┐
   │   NGO Hub    │  WebSocket + REST            │      Civilian Phone    │
   │  (web app)   │ ─────────────────────────►   │  SafeThread iOS app    │
   │              │                              │  (fork of bitchat)     │
   │ - compose    │                              │                        │
   │   alerts     │     Three independent paths: │  - receive alert       │
   │ - live feed  │     ① HTTPS + WS             │  - submit sighting     │
   │   of tips    │     ② BLE mesh (bitchat)     │    (text/photo/voice)  │
   │ - map view   │     ③ Nostr relay fallback   │  - geohash location    │
   │ - dispatch   │                              │  - delivery receipts   │
   │   broadcasts │                              │                        │
   └──────────────┘                              └────────────────────────┘
```

The user never picks a transport — the app uses whichever pipe is up. Alerts
hop phone-to-phone over Bluetooth (up to 7 relays), end-to-end encrypted via
the Noise XX channel, with Nostr as the online fallback when any node has
internet. Sightings travel back the same way.

**Hub-and-spoke is enforced at the protocol layer**, not the UI: civilians can
only ever message the NGO, never each other. Less surface, less abuse.

## The cool tech

- 🛰️ **Works with no internet.** [bitchat](https://github.com/permissionlesstech/bitchat) BLE mesh, 7-hop TTL, store-and-forward.
- 🔐 **End-to-end encrypted.** Noise Protocol XX with forward secrecy; triple-tap emergency wipe inherited from bitchat.
- 🌐 **Three transports, one app.** HTTPS+WS / BLE mesh / Nostr relays, picked automatically.
- 🗺️ **Geohash locations.** 7-char codes (`SY3R6X4`) you can speak over a voice call or send as SMS.
- 📷 **Multi-modal sightings.** Free-text + JPEG photo + AAC voice note, all chunked into TLV packets.
- ♻️ **Forward-compatible wire format.** TLV envelopes silently skip unknown fields, so the protocol can evolve without breaking older clients.
- 📲 **SMS fallback for dumbphones.** Hub dispatches broadcasts to phones that don't run the app.
- ⚡ **One-command deploy.** `./deploy/boxd-up.sh ngo-hub` → live on `https://ngo-hub.boxd.sh`.

## Repo layout

| Path          | What it is                                                           |
|---------------|----------------------------------------------------------------------|
| `server/`     | FastAPI NGO hub — incidents, messages, audiences, WS stream, seed DB |
| `web/`        | React + Vite + Tailwind operator dashboard                           |
| `mobileapp/`  | Swift/iOS app (fork of bitchat). See [`mobileapp/README.md`](./mobileapp/README.md) |
| `deploy/`     | boxd.sh deploy script. See [`deploy/README.md`](./deploy/README.md) |
| `visuals/`    | Demo assets / screenshots                                            |

## Quick start

```bash
# Backend + frontend, locally
pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9"
SEED_ON_STARTUP=1 uvicorn server.main:app --reload --port 8080

cd web && npm install && npm run dev    # http://localhost:5173
```

Or with Docker:

```bash
docker compose up --build               # http://localhost:8080
```

iOS app: see [`mobileapp/README.md`](./mobileapp/README.md). Buildable Xcode
project lives at https://github.com/hidden-salmon/bitchat-amber.

## Routing-agent contract

The routing agent POSTs each parsed civilian message to `POST /api/ingest`
(schema: `IngestEvent` in [`server/schemas.py`](./server/schemas.py)). The UI
subscribes to `WS /ws/stream` for live updates.

## References

- bitchat (Swift): https://github.com/permissionlesstech/bitchat
- Our bitchat fork (buildable): https://github.com/hidden-salmon/bitchat-amber
- pybitchat (Python BLE): https://pypi.org/project/pybitchat/
