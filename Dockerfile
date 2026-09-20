# syntax=docker/dockerfile:1
# pegwatch : python (collecteurs, fixing) + pm2 (cron + serveur statique de data/), même modèle que radar-remote.
# Bases épinglées par digest (python:3.12-slim-bookworm, node:22-bookworm-slim).
FROM node@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS pm2
RUN npm install -g pm2@7.0.4 && npm cache clean --force

FROM python@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254
WORKDIR /app

COPY --from=pm2 /usr/local/bin/node /usr/local/bin/node
COPY --from=pm2 /usr/local/lib/node_modules/pm2 /usr/local/lib/node_modules/pm2
RUN ln -s /usr/local/lib/node_modules/pm2/bin/pm2-runtime /usr/local/bin/pm2-runtime

COPY pyproject.toml ./
COPY pegwatch ./pegwatch
RUN pip install --no-cache-dir ".[agent]" && rm -rf build

COPY ecosystem.config.cjs wrappers.yaml countries.yaml ./
COPY web ./web
COPY FEEDBACK.md ./web/

# Non-root ; data est un volume, créé ici pour hériter du bon propriétaire.
RUN useradd -r -u 1000 -d /app pegwatch && mkdir -p data && chown -R pegwatch:pegwatch /app
USER pegwatch
ENV PYTHONUNBUFFERED=1 PM2_HOME=/tmp/.pm2
EXPOSE 8080 8081
# data/ est un volume : la page statique y est recopiée à chaque démarrage, à côté des JSON générés.
CMD ["sh", "-c", "cp -r web/. data/ && exec pm2-runtime ecosystem.config.cjs"]
