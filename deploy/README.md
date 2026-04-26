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

# 5. Set the Anthropic key — see "Set the Anthropic secret" below.
#    Quickest path:
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

## Set the Anthropic secret

The agent worker reads `ANTHROPIC_API_KEY` from its container environment.
With it set, the triage worker uses Haiku and the agent uses Sonnet 4.5.
Without it, both fall back to deterministic stubs — the demo still runs,
but `decision.model == "stub"` and `cost_usd == 0`.

`docker-compose.yml` already declares the pass-through:

```yaml
environment:
  ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY:-}
```

So the container sees whatever the **host shell** sees when you run
`docker compose up`. Three ways to set it on the VM:

### Option A — `.env` file (recommended)

Create a `.env` file at the repo root on the VM. Docker Compose reads it
automatically before substitution.

```bash
cd anth-hackathon26
cat > .env <<'EOF'
ANTHROPIC_API_KEY=sk-ant-...your-key-here...
EOF
chmod 600 .env             # readable only by you

docker compose up -d --build
```

`.env` is in the repo's `.gitignore`, so it won't accidentally get
committed if someone runs `git add -A` on the VM.

### Option B — export in the shell session

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
docker compose up -d --build
```

The downside: it dies when you log out, so a `docker compose restart` in
a fresh shell will lose the secret. Fine for one-shot tests, not for a
long-running deploy.

### Option C — inline on the command line

```bash
ANTHROPIC_API_KEY="sk-ant-..." docker compose up -d --build
```

Same caveat as Option B, plus the key may end up in your shell history.

### Verify it's in the container

```bash
# 1. Container env should show the key (masked here for safety):
docker compose exec app sh -c 'echo $ANTHROPIC_API_KEY' | head -c 20
echo

# 2. Trigger one decision and confirm it ran in real mode:
curl -X POST http://localhost:8080/api/sim/replay/start?intervalSec=4
sleep 8
curl -X POST http://localhost:8080/api/sim/replay/stop
curl -s http://localhost:8080/api/decisions/recent?limit=1 \
  -H "X-Operator-Id: op-senior" | python3 -m json.tool | head -20
```

If `model` reads `claude-sonnet-4-5` and `costUsd > 0`, you're real-mode.
If it reads `stub` and `costUsd == 0`, the key didn't reach the container.

### Where to get the key

[console.anthropic.com → Settings → API keys](https://console.anthropic.com/settings/keys).
Create a key, copy it once (the console won't show it again), drop it
into `.env`. Rotate after the demo.

### Security checklist

- `.env` lives only on the VM, never in git.
- The key never appears in commits, logs, or the README — verify with
  `git log -p --all -S "sk-ant-"` before pushing.
- Don't echo the key over a shared screen-share without masking.

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
