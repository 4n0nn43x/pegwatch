#!/bin/sh
# Déploie sur le serveur : rsync du dépôt (sans secrets ni données), .env à part, build + up, reload Caddy.
set -eu
HOST=${PEGWATCH_HOST:?set PEGWATCH_HOST=user@server}
APP=${PEGWATCH_APP:-apps/pegwatch}
rsync -az --delete --include=FEEDBACK.md --exclude-from=.dockerignore --exclude=.env ./ "$HOST:$APP/"
scp -q .env "$HOST:$APP/.env"
ssh "$HOST" "chmod 600 $APP/.env && cd $APP && docker compose up -d --build --quiet-pull \
  && cp sites/pegwatch.caddy ~/apps/edge/sites/pegwatch.caddy \
  && cd ~/apps/edge && docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile"
