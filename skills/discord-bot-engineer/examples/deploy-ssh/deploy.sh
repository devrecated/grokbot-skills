#!/usr/bin/env bash
# Build locally, copy to any Linux host over SSH, install deps, restart the service.
# Usage: DEPLOY_HOST=<USER>@<HOST> ./deploy.sh
# One-time on the host: create user "discordbot", install Node 20+, put the env file at
# /etc/discord-bot-engineer.env (chmod 600), and copy the .service file to /etc/systemd/system/.
set -euo pipefail

: "${DEPLOY_HOST:?set DEPLOY_HOST=<USER>@<HOST>}"
APP_DIR="${APP_DIR:-/opt/discord-bot-engineer}"
SERVICE="discord-bot-engineer"

cd "$(dirname "$0")"
npm ci
npm run build

cp ../package.json dist/package.json  # marks dist/worker.js as ESM
rsync -az --delete dist package.json package-lock.json "$DEPLOY_HOST:$APP_DIR/"
# shellcheck disable=SC2029  # APP_DIR/SERVICE are meant to expand locally
ssh "$DEPLOY_HOST" "cd '$APP_DIR' && npm ci --omit=dev && sudo systemctl daemon-reload && sudo systemctl restart '$SERVICE' && sleep 2 && curl -fsS http://127.0.0.1:8787/health"
echo "deployed to $DEPLOY_HOST"
