# Deploy to boxd.sh

The app is a single Docker image built from the repo root.

## One-time

```bash
# install the boxd CLI (see https://docs.boxd.sh/)
curl -fsSL https://boxd.sh/install | sh
boxd auth login
```

## Provision + deploy

```bash
# 1. create a machine
boxd machines create --name ngo-hub

# 2. ssh in and pull the repo
boxd ssh ngo-hub <<'SH'
  set -e
  if ! command -v git >/dev/null; then sudo apt-get update && sudo apt-get install -y git; fi
  if [ ! -d anth-hackathon26 ]; then
    git clone https://github.com/MichielMAnalytics/anth-hackathon26.git
  fi
  cd anth-hackathon26
  git pull
  docker compose up -d --build
SH

# 3. expose on HTTPS
#    boxd auto-assigns <name>.boxd.sh -> the machine's public IP.
#    we just need traffic on :443 to reach :8080. exact CLI varies; one of:
boxd proxy add ngo-hub --port 8080
# or, if proxy is configured per-machine in the dashboard,
# point :443 -> :8080 there.
```

## Update after a code change

```bash
boxd ssh ngo-hub 'cd anth-hackathon26 && git pull && docker compose up -d --build'
```

## Sanity check

```bash
curl https://ngo-hub.boxd.sh/api/incidents | jq .
```

Should return an array of seeded incidents.
