// pm2 dans le conteneur : le planificateur des batchs, un serveur statique sur data/, le serveur MCP HTTP.
//   pm2-runtime ecosystem.config.cjs
// Les horaires des batchs vivent dans pegwatch/cron.py : le cron_restart de pm2 gelait une app dont le batch tournait encore.
const py = (name, args, env = {}) => ({
  name, script: "/usr/local/bin/python3", args, interpreter: "none", autorestart: true, time: true, env,
});
module.exports = {
  apps: [
    py("cron", "-m pegwatch.cron"),
    { name: "web", script: "serve", env: { PM2_SERVE_PATH: "data", PM2_SERVE_PORT: 8080 } },
    // MCP Streamable HTTP on :8081/mcp (Caddy routes pegwatch.fyra.fun/mcp here); reads the site's own JSON over :8080.
    py("mcp", "-m pegwatch.mcp_server --http", { PEGWATCH_URL: "http://127.0.0.1:8080" }),
  ],
};
