#!/usr/bin/env bash
# One-shot deploy/update for the NGO Hub on boxd.sh.
# Usage: ./deploy/boxd-up.sh [machine-name]
# Assumes the boxd CLI is installed and authenticated.
set -euo pipefail

NAME="${1:-ngo-hub}"
REPO_URL="${REPO_URL:-https://github.com/MichielMAnalytics/anth-hackathon26.git}"

if ! command -v boxd >/dev/null; then
  echo "boxd CLI not found. Install: curl -fsSL https://boxd.sh/install | sh" >&2
  exit 1
fi

if ! boxd machines list 2>/dev/null | grep -q "$NAME"; then
  echo ">> creating machine $NAME"
  boxd machines create --name "$NAME"
fi

echo ">> deploying to $NAME"
boxd ssh "$NAME" <<EOF
  set -e
  if ! command -v git >/dev/null; then sudo apt-get update && sudo apt-get install -y git; fi
  if [ ! -d anth-hackathon26 ]; then
    git clone "$REPO_URL"
  fi
  cd anth-hackathon26
  git pull
  docker compose up -d --build
EOF

echo ">> done. expose port 8080 on $NAME via the boxd dashboard or:"
echo "   boxd proxy add $NAME --port 8080"
