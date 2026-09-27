// pm2 dans le conteneur : des batchs sur cron, un serveur statique sur data/, le serveur MCP HTTP.
//   pm2-runtime ecosystem.config.cjs
// Chaque batch tourne une fois au démarrage puis à son horaire (UTC). autorestart:false = un batch se termine.
const py = (name, mod, cron, limit = 280) => ({
  // timeout: a batch that outlives its slot kills itself; pm2 failed to kill a stuck p2p on 2026-09-26 and froze its cron
  name, script: "/usr/bin/timeout", args: `-k 10 ${limit} /usr/local/bin/python3 -m ${mod}`, interpreter: "none",
  autorestart: false, cron_restart: cron, time: true,
});
module.exports = {
  apps: [
    py("p2p", "pegwatch.p2p", "*/5 * * * *"),
    py("collect", "pegwatch.collect", "*/5 * * * *"),
    py("ref", "pegwatch.ref", "*/5 * * * *"),
    py("premiums", "pegwatch.premiums", "2-59/5 * * * *"),
    py("ladder", "pegwatch.ladder", "3-59/5 * * * *"),
    py("fixing", "pegwatch.fixing", "1-59/5 * * * *"),
    { ...py("fixing-daily", "pegwatch.fixing", "0 12 * * *"), args: "-k 10 280 /usr/local/bin/python3 -m pegwatch.fixing --daily" },
    py("monday", "pegwatch.monday", "0 14 * * *", 1800),   // after the 13:30 UTC NYSE open; rebuilds every weekend on disk
    py("archive", "pegwatch.archive", "17 3 * * *", 3000), // gzip closed daily JSONL files, the archive would fill the disk otherwise
    { name: "web", script: "serve", env: { PM2_SERVE_PATH: "data", PM2_SERVE_PORT: 8080 } },
    // MCP Streamable HTTP on :8081/mcp (Caddy routes pegwatch.fyra.fun/mcp here); reads the site's own JSON over :8080.
    { name: "mcp", script: "/usr/local/bin/python3", args: "-m pegwatch.mcp_server --http", interpreter: "none",
      autorestart: true, time: true, env: { PEGWATCH_URL: "http://127.0.0.1:8080" } },
  ],
};
