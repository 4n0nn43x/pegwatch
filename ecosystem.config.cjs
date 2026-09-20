// pm2 dans le conteneur : trois batchs sur cron + un serveur statique sur data/.
//   pm2-runtime ecosystem.config.cjs
// Chaque batch tourne une fois au démarrage puis à son horaire (UTC). autorestart:false = un batch se termine.
const py = (name, mod, cron) => ({
  name, script: "/usr/local/bin/python3", args: `-m ${mod}`, interpreter: "none",
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
    { ...py("fixing-daily", "pegwatch.fixing", "0 12 * * *"), args: "-m pegwatch.fixing --daily" },
    py("monday", "pegwatch.monday", "0 14 * * *"),   // after the 13:30 UTC NYSE open; rebuilds every weekend on disk
    { name: "web", script: "serve", env: { PM2_SERVE_PATH: "data", PM2_SERVE_PORT: 8080 } },
  ],
};
