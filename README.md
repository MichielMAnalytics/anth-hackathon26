# P2P Amber Alert Network over Bitchat

## Quick start (NGO Hub UI)

```bash
# backend
pip install "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9"
SEED_ON_STARTUP=1 uvicorn server.main:app --reload --port 8080

# frontend (separate terminal)
cd web && npm install && npm run dev
# open http://localhost:5173
```

Or with Docker:

```bash
docker compose up --build
# open http://localhost:8080
```

Deploy to boxd.sh: see `deploy/README.md`.

## Routing-agent contract

The teammate's routing agent POSTs each parsed message to `/api/ingest`. See the schema in `server/schemas.py` (`IngestEvent`). The UI subscribes to `WS /ws/stream` and updates live.

## Context

NGOs operating in warzones need to broadcast missing-person ("amber") alerts to civilians whose phones often have no working cellular or internet. **Bitchat** (Jack Dorsey's BLE mesh app, with Nostr fallback) gives those phones a way to talk to each other without infrastructure: messages hop phone-to-phone over Bluetooth (up to 7 hops), end-to-end encrypted via the Noise Protocol, and fall back to Nostr relays whenever any node has internet.

This project layers a structured **AMBER alert protocol** on top of bitchat:

- An **NGO operator** composes an alert (name, photo, last-seen location, description) from a web dashboard.
- The alert is broadcast into the bitchat mesh as a typed message; every node within hop-range receives it and re-broadcasts it.
- A **civilian recipient** sees the alert on their phone (or in the demo, a simulated phone in the browser) and can reply *"I saw them"* with free-text notes.
- Sightings are routed back through the mesh to the NGO node and aggregated on a **map/dashboard** in real time.

The repo (`anth-hackathon26`) is currently empty, so this is greenfield. The prototype runs as a **browser-based simulator** for the hackathon demo, with a clean adapter boundary so the same alert/sighting protocol can later run over real BLE via `pybitchat` or `bitchat-python`, or over Nostr for online fallback.

## Goals & non-goals

**Goals**
- End-to-end demo: NGO sends alert → multiple simulated phones receive it via mesh hops → one replies with a sighting + notes → NGO sees it on their dashboard with the relay path.
- Protocol that is bitchat-compatible *in shape* (TTL-bounded multi-hop relay, message-id dedup, signed payloads), so swapping the simulated transport for real BLE is a transport swap, not a redesign.
- Privacy by default: sightings are encrypted to the NGO's pubkey; relays only see ciphertext + routing envelope.

**Non-goals (for hackathon)**
- Shipping an actual iOS/Android client. We piggyback on the real bitchat app conceptually but demo with a web simulator.
- Real BLE in the demo. We provide the adapter interface; a `pybitchat` implementation is a stretch goal.
- Production-grade key management (we use ephemeral in-memory keypairs).

## Architecture

```
┌──────────────┐   WebSocket   ┌──────────────────────────────┐   Adapter   ┌──────────────────┐
│  NGO Web UI  │ ─────────────►│  Orchestrator (FastAPI/Py)   │ ──────────► │ MeshTransport    │
│  (React)     │ ◄─────────────│  - alert/sighting protocol   │ ◄────────── │  - SimMesh (demo)│
└──────────────┘               │  - SQLite store              │             │  - BitchatBLE    │
                               └──────────────────────────────┘             │    (stretch)     │
┌──────────────┐   WebSocket                                                └──────────────────┘
│ Phone Sim ×N │ ◄─────────────► same orchestrator, one WS per simulated phone node
└──────────────┘
```

- **Orchestrator** (Python, FastAPI) is the only server. It owns the protocol, the SQLite DB, and a WebSocket hub.
- **NGO dashboard** and **phone simulator** are both React pages talking to the orchestrator over WS. Each simulated phone is a tab/window.
- **MeshTransport** is an interface. `SimMesh` ships first: an in-process graph of nodes with configurable BLE-range adjacency, hop-by-hop store-and-forward, TTL=7, message-id dedup, and a tunable per-hop delay so the demo *looks* like a mesh propagating. `BitchatBLE` (stretch) wraps `pybitchat` to talk to real bitchat phones.

## Protocol

All messages are JSON envelopes signed by the sender's ed25519 key:

```json
{
  "id": "uuid",            // for dedup
  "type": "ALERT" | "SIGHTING" | "ACK",
  "ttl": 7,                // decremented per hop, dropped at 0
  "origin": "<pubkey>",
  "to": "<pubkey>" | "*",  // * = broadcast
  "ts": 1735000000,
  "payload": { ...type-specific... },
  "sig": "<ed25519 sig over the above>"
}
```

- `ALERT.payload`: `{ alertId, personName, ageRange, photoUrl, lastSeenAt, lastSeenGeohash, description, ngoPubkey, ngoContact }`. Broadcast (`to: "*"`).
- `SIGHTING.payload`: `{ alertId, sightingId, observerGeohash, notes, photoUrl?, confidence }`. Encrypted to `ngoPubkey`, addressed to NGO; relayed by intermediate nodes blindly.
- `ACK.payload`: `{ refId }` so the NGO confirms receipt back to the sighter (best-effort).

Relay rule on every node: if `id` already seen → drop; else store, decrement TTL, re-broadcast to all neighbors except sender. This matches bitchat's relay semantics.

## Data model (SQLite, via SQLModel)

- `Alert(alertId, ngoPubkey, personName, photoUrl, lastSeenGeohash, description, createdAt, status)`
- `Sighting(sightingId, alertId, observerPubkey, observerGeohash, notes, photoUrl?, receivedAt, hopPath JSON)`
- `Node(pubkey, label, lastSeenAt)` — for the simulator, also `x, y` so we can render a graph
- `MessageLog(id, type, fromPubkey, toPubkey, hop, ts)` — for the relay-path visualization

## UX

**NGO dashboard** (`/ngo`)
- "New alert" form: name, photo upload, last-seen location (map pin → geohash), description.
- Live feed of incoming sightings, each showing: notes, observer geohash on map, hop path, time, "Acknowledge" button.
- Topology view: live graph of all phone nodes the NGO has heard from, with edges flashing as messages relay.

**Phone simulator** (`/phone?id=<n>`)
- Looks like an SMS thread.
- Receives ALERT → renders as a card with photo + "I saw them" CTA.
- "I saw them" opens a reply composer (notes field + optional photo + auto-attach geohash from a draggable pin).
- Reply round-trips back to NGO via mesh.
- Operator-only debug panel on each sim phone: list of neighbors (toggle BLE-range adjacency live), TTL counter on inbound messages.

**Sim controls** (`/sim`)
- Spawn N phone nodes in a grid; drag to reposition; BLE adjacency auto-derived from distance.
- Inject failures: kill a node, sever an edge, throttle a hop. Used to demo resilience.

## Critical files to create

```
anth-hackathon26/
├── README.md
├── pyproject.toml                       # uv/poetry, ruff config
├── server/
│   ├── main.py                          # FastAPI app, WS endpoints
│   ├── protocol.py                      # envelope build/verify, ed25519, encrypt/decrypt
│   ├── transport/
│   │   ├── base.py                      # MeshTransport ABC
│   │   ├── sim_mesh.py                  # in-process gossip mesh w/ TTL+dedup
│   │   └── bitchat_ble.py               # STRETCH: pybitchat adapter
│   ├── orchestrator.py                  # alert/sighting routing, dedup table, ACK
│   ├── store.py                         # SQLModel models + queries
│   └── ws_hub.py                        # per-node WS fanout
├── web/                                 # Vite + React + Tailwind
│   ├── src/pages/Ngo.tsx
│   ├── src/pages/Phone.tsx
│   ├── src/pages/Sim.tsx
│   ├── src/components/MeshGraph.tsx     # d3-force topology view
│   ├── src/components/AlertCard.tsx
│   └── src/lib/wsClient.ts
└── tests/
    ├── test_protocol.py                 # envelope sign/verify, dedup, TTL
    ├── test_sim_mesh.py                 # 5-node line: ALERT reaches end, SIGHTING returns
    └── test_orchestrator.py             # ACK, idempotency, encryption to NGO
```

## Build sequence

1. **Skeleton** — FastAPI app, React app via Vite, single WS echo round-trip working.
2. **Protocol module** — envelope, signing, dedup. Unit tests first.
3. **SimMesh** — node graph, TTL relay, configurable adjacency. Unit test: 5-node line propagation in both directions.
4. **Orchestrator** — wire transport ↔ store ↔ WS hub. ALERT broadcast and SIGHTING return path.
5. **NGO dashboard** — compose alert + sighting feed (no map yet; geohash text is fine).
6. **Phone simulator** — receive card, reply with notes.
7. **Sim controls page** — spawn/move/kill nodes, mesh graph viz with relay flashes. **This is the demo money shot** — invest here.
8. **Polish** — map (Leaflet) for geohash, photo uploads, ACK round-trip.
9. **Stretch: `BitchatBLE`** — wrap `pybitchat`, run NGO orchestrator on a laptop with BLE, send a real alert to a phone running bitchat. Ship if Steps 1–8 are solid 4 hours before demo.

## Verification

- `pytest tests/` — protocol round-trip, mesh propagation across 5-node line, dedup correctness, encryption opacity to relays.
- Manual demo script (record this for judges):
  1. Open `/sim`, spawn 8 phones in a rough line, no NGO-to-far-phone direct edge.
  2. Open `/ngo` in another tab, compose alert with photo + last-seen pin.
  3. Watch graph: alert flashes hop-by-hop until far phones light up.
  4. On `/phone?id=7`, click "I saw them", drop a pin, type "saw a girl matching photo near the bakery, walking south, scared but unhurt", send.
  5. Sighting flashes back along reverse path; appears on `/ngo` feed within ~2s; NGO clicks Acknowledge.
  6. Kill node 4 mid-broadcast; show that the gossip finds an alternate path.
- Stretch verification: real bitchat phone running in BLE range receives the alert and replies, sighting shows in `/ngo`.

## Open questions to resolve during build

- Photos in bitchat: real bitchat is text-oriented; for the demo we'll send photos as a URL pointer (orchestrator hosts), and document that real BLE deployment would need chunked binary or a Nostr-relay drop.
- Geohash precision: default 6 chars (~1.2 km) — good privacy/utility tradeoff for civilians reporting in a warzone.

## References

- bitchat (Swift, official): https://github.com/permissionlesstech/bitchat
- pybitchat (Python, protocol-compatible BLE): https://pypi.org/project/pybitchat/
- bitchat-python (Python, protocol-compatible BLE CLI): https://github.com/kaganisildak/bitchat-python
- bitchat-cli (Python CLI): https://github.com/dearabhin/bitchat-cli
