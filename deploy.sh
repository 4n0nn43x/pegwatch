#!/bin/sh
# Déploie sur le serveur : rsync du dépôt (sans secrets ni données), .env à part, build + up, reload Caddy.
set -eu
HOST=deploy@srv1186438.hstgr.cloud
APP=/home/deploy/apps/pegwatch
rsync -az --delete --include=FEEDBACK.md --exclude-from=.dockerignore --exclude=.env ./ "$HOST:$APP/"
scp -q .env "$HOST:$APP/.env"
ssh "$HOST" "chmod 600 $APP/.env && cd $APP && docker compose up -d --build --quiet-pull \
  && cp sites/pegwatch.caddy ~/apps/edge/sites/pegwatch.caddy \
  && cd ~/apps/edge && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile"
