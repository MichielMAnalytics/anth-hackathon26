# Deploy to boxd.sh

The app is one Docker image built from the repo root. boxd VMs ship with Docker pre-installed.

## One-time

```bash
# install the boxd CLI (macOS arm64 / Linux x86_64 + arm64)
curl -fsSL https://boxd.sh/downloads/cli/install.sh | sh

# authenticate (opens browser)
~/.local/bin/boxd login
~/.local/bin/boxd whoami     # sanity check
```

Add `~/.local/bin` to your PATH if you want to call `boxd` directly.

## Deploy

```bash
./deploy/boxd-up.sh ngo-hub
```

That script:
1. Creates a VM `ngo-hub` if it doesn't exist (`boxd new --name=ngo-hub`).
2. Points the default subdomain proxy at port 8080 (`boxd proxy set-port`).
3. Clones / pulls the repo on the VM and runs `docker compose up -d --build`.

App is live at: **`https://ngo-hub.boxd.sh`**.

## Update after a code change

```bash
git push                     # push to GitHub
./deploy/boxd-up.sh ngo-hub  # re-runs git pull + compose up --build on the VM
```

## Sanity check

```bash
curl https://ngo-hub.boxd.sh/api/incidents | head
```

Should return seeded incidents JSON.

## Misc

```bash
boxd connect ngo-hub                          # interactive SSH
boxd exec ngo-hub -- 'docker compose logs -f' # tail logs
boxd destroy ngo-hub -y                       # tear it down
```
