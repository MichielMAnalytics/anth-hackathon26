#!/usr/bin/env bash
# Deploy/update the NGO Hub on boxd.sh.
# Usage: ./deploy/boxd-up.sh [vm-name]
# Requires: boxd CLI installed and `boxd login` already run.
set -euo pipefail

NAME="${1:-ngo-hub}"
REPO_URL="${REPO_URL:-https://github.com/MichielMAnalytics/anth-hackathon26.git}"
APP_PORT=8080

BOXD="${BOXD_BIN:-boxd}"
if ! command -v "$BOXD" >/dev/null; then
  if [ -x "$HOME/.local/bin/boxd" ]; then
    BOXD="$HOME/.local/bin/boxd"
  else
    echo "boxd CLI not found. Install with:" >&2
    echo "  curl -fsSL https://boxd.sh/downloads/cli/install.sh | sh" >&2
    exit 1
  fi
fi

if ! "$BOXD" whoami >/dev/null 2>&1; then
  echo "Not logged in. Run: $BOXD login" >&2
  exit 1
fi

# create VM if it doesn't exist
if ! "$BOXD" list --json 2>/dev/null | grep -q "\"$NAME\""; then
  echo ">> creating VM: $NAME"
  "$BOXD" new --name="$NAME"
else
  echo ">> VM $NAME already exists"
fi

# point the default subdomain proxy at our app port
echo ">> setting proxy port to $APP_PORT"
"$BOXD" proxy set-port --vm="$NAME" --port="$APP_PORT" || true

# clone (or pull) the repo and bring up the container
echo ">> deploying code on $NAME"
"$BOXD" exec "$NAME" -- bash -lc "
  set -e
  if [ ! -d anth-hackathon26 ]; then
    git clone $REPO_URL
  fi
  cd anth-hackathon26
  git pull
  docker compose up -d --build
  docker compose ps
"

echo
echo ">> done. App is live at: https://${NAME}.boxd.sh"
