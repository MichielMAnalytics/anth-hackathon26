# Deploy on boxd.sh

The full app (FastAPI + Postgres+pgvector + built React frontend) ships as
two Docker containers via the repo's `docker-compose.yml`. Only secret
needed at deploy time is `ANTHROPIC_API_KEY` — without it both LLM tiers
fall back to deterministic stubs (the demo still runs, just stub-mode).

## One-shot deploy

```bash
# 1. SSH into the boxd controller
ssh boxd.sh

# 2. Create a VM (name it whatever — 'ngo-hub' is the convention)
boxd new --name=ngo-hub

# 3. Open a shell on the VM
boxd connect ngo-hub
```

Now you're on the VM:

```bash
# 4. Clone the repo
git clone https://github.com/MichielMAnalytics/anth-hackathon26.git
cd anth-hackathon26

# 5. Drop your Anthropic key into a .env file (gitignored)
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env

# 6. Build + start the two containers (db + app)
#    The app entrypoint runs `alembic upgrade head` before uvicorn,
#    so the schema is in place before workers boot.
docker compose up -d --build

# 7. Seed the rich demo scene (8 alerts, ~30 historic decisions,
#    8 pending suggestions, etc.)
curl -X POST http://localhost:8080/api/sim/seed

# 8. (optional) start the live replay drip
curl -X POST "http://localhost:8080/api/sim/replay/start?intervalSec=4"
```

The app is reachable at `http://localhost:8080` on the VM and at
`https://<vm-name>.boxd.sh` once boxd's subdomain proxy is pointed at
port 8080 (boxd does this automatically for the default port).

## Re-deploy after a code change

```bash
boxd connect ngo-hub
cd anth-hackathon26
git pull
docker compose up -d --build
```

## Sanity check

```bash
curl https://<vm-name>.boxd.sh/health
curl https://<vm-name>.boxd.sh/api/incidents -H "X-Operator-Id: op-senior" | head
curl https://<vm-name>.boxd.sh/api/agent/stats -H "X-Operator-Id: op-senior"
```

## Tail logs / SSH / nuke

```bash
boxd connect ngo-hub                          # interactive shell
boxd exec ngo-hub -- 'docker compose logs -f' # tail logs
boxd destroy ngo-hub -y                       # tear it down
```

## Optional env knobs

All read by the app via `pydantic-settings`. Override in `.env` on the VM
(or in the compose file):

| Var | Default | Effect |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | enables real Haiku triage + Sonnet agent. Without it both fall back to deterministic stubs. |
| `JWT_SECRET` | `change-me` | NGO operator JWT signing (auth not yet enforced everywhere) |
| `HEARTBEAT_INTERVAL_SEC` | `300` | how often the heartbeat scheduler ticks each active alert. Drop to `60` for a livelier demo. |
| `HEARTBEAT_ENABLED` | `true` | set to `false` to skip the heartbeat task entirely |
