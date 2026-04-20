const fs = require("fs");
const path = require("path");
const dotenv = require("dotenv");

// Cache path resolutions to avoid repeated computation
const repoRootEnv = path.resolve(__dirname, "..", ".env");
const repoRootEnvLocal = path.resolve(__dirname, "..", ".env.local");

// Load environment variables efficiently - check existence once, load in order
const envFiles = [
  { path: fs.existsSync(repoRootEnv) && repoRootEnv, override: false },
  { path: fs.existsSync(repoRootEnvLocal) && repoRootEnvLocal, override: true },
].filter(({ path: p }) => p);

for (const { path: envPath, override } of envFiles) {
  dotenv.config({ path: envPath, quiet: true, override });
}

// Optimized: use == null to catch both undefined/null, minimize String() calls
function setDefaultEnv(name, value) {
  const current = process.env[name];
  if (current == null || current === "") {
    if (value != null && String(value) !== "") {
      process.env[name] = String(value);
    }
  }
}

// Optimized: cache String() conversions, avoid redundant operations
function setDefaultUrlFromHostport(name, hostport, pathSuffix = "") {
  if (!hostport) return;
  const pathStr = String(pathSuffix);
  const normalizedPath =
    pathStr && !pathStr.startsWith("/") ? `/${pathStr}` : pathStr;
  setDefaultEnv(name, `http://${hostport}${normalizedPath}`);
}

// Local dev convenience: mirror compose-style POSTGRES_* into DB_* env vars
setDefaultEnv("DB_USER", process.env.POSTGRES_USER);
setDefaultEnv("DB_PASSWORD", process.env.POSTGRES_PASSWORD);
setDefaultEnv("DB_HOST", process.env.POSTGRES_HOST);
setDefaultEnv("DB_PORT", process.env.POSTGRES_PORT);

// Reasonable defaults matching `docker-compose.yml` service env.
setDefaultEnv("DB_NAME", "DECISIONAPP");
setDefaultEnv("BETS_DB_NAME", "CLIENTBETDATA");
setDefaultEnv("BETTING_DB_NAME", "CLIENTBETDATA");
setDefaultEnv("ODDS_DB_NAME", "ODDSGENERATOR");
setDefaultEnv("DEMO_DB_NAME", "DEMOMONEY");
setDefaultEnv("AUTH_DB_NAME", "BETTORS");
setDefaultEnv("DECISION_DB_NAME", "DECISIONAPP");
setDefaultEnv("CLIENT_GATEWAY_URL", process.env.CLIENT_GATEWAY_PUBLIC_URL);
setDefaultUrlFromHostport("GATEWAY_URL", process.env.GATEWAY_HOSTPORT);
setDefaultUrlFromHostport("UNITY_URL", process.env.UNITY_HOSTPORT);
setDefaultUrlFromHostport(
  "ODDS_GENERATOR_SYNC_URL",
  process.env.ODDS_GENERATOR_SYNC_HOSTPORT,
  "/odds/api/sync/latest-odds/",
);
// Fallback default for ODDS_GENERATOR_SYNC_URL
setDefaultEnv(
  "ODDS_GENERATOR_SYNC_URL",
  "http://127.0.0.1:9000/odds/api/sync/latest-odds/",
);
setDefaultUrlFromHostport(
  "DECISION_CHARACTERS_URL",
  process.env.ADMIN_PORTAL_HOSTPORT,
  "/api/decision/api/characters/latest/?limit=5",
);
setDefaultUrlFromHostport(
  "RESULTS_API_URL",
  process.env.CLIENT_GATEWAY_HOSTPORT,
  "/api/results?limit=1",
);
setDefaultUrlFromHostport(
  "RESULTS_API_URL",
  process.env.PORT ? `127.0.0.1:${process.env.PORT}` : "",
  "/api/results?limit=1",
);

async function main() {
  // Freeze ports object to prevent accidental mutation (minor engine optimization)
  const ports = Object.freeze({
    bettor: Number(process.env.BETTOR_PORT || 4101),
    odds: Number(process.env.ODDS_PORT || 4102),
    game: Number(process.env.GAME_PORT || 4103),
    statistics: Number(process.env.STATISTICS_PORT || 4104),
    demomoney: Number(process.env.DEMOMONEY_PORT || 4105),
    timer: Number(process.env.TIMER_PORT || 4106),
    clientupdate: Number(process.env.CLIENTUPDATE_PORT || 4107),
    statsUi: Number(process.env.STATS_UI_PORT || 4108),
    transactions: Number(process.env.TRANSACTIONS_PORT || 4109),
    stoneOutcomes: Number(process.env.STONE_THROW_OUTCOMES_PORT || 4110),
    gateway: Number(process.env.CLIENT_GATEWAY_PORT || 3000),
  });

  const servers = [];

  // Keep individual requires to preserve module variable references for shutdown logic
  const bettor = require("./microservices/Bettor/src/index.js");
  const odds = require("./microservices/Odds/src/index.js");
  const game = require("./microservices/Game/src/index.js");
  const statistics = require("./microservices/Statistics/src/index.js");
  const demomoney = require("./microservices/demomoney/src/index.js");
  const timer = require("./microservices/Timer/src/index.js");
  const clientupdate = require("./microservices/clientupdate/src/index.js");
  const statsUi = require("./microservices/stats/src/index.js");
  const transactions = require("./microservices/Transactions/src/index.js");
  const stoneOutcomes = require("./microservices/StoneThrowOutcomes/src/index.js");
  const gateway = require("./microservices/Client/src/index.js");

  function track(server, name) {
    if (!server) return;
    servers.push({ name, server });
  }

  // Optimized startup: handle async/sync start() uniformly with minimal overhead
  // Using Promise.resolve() ensures consistent handling without unnecessary awaits
  await Promise.all([
    Promise.resolve(bettor.start({ port: ports.bettor })).then((s) =>
      track(s, "bettor"),
    ),
    Promise.resolve(odds.start({ port: ports.odds })).then((s) =>
      track(s, "odds"),
    ),
    Promise.resolve(game.start({ port: ports.game })).then((s) =>
      track(s, "game"),
    ),
    Promise.resolve(statistics.start({ port: ports.statistics })).then((s) =>
      track(s, "statistics"),
    ),
    Promise.resolve(demomoney.start({ port: ports.demomoney })).then((s) =>
      track(s, "demomoney"),
    ),
    Promise.resolve(timer.start({ port: ports.timer })).then((s) =>
      track(s, "timer"),
    ),
    Promise.resolve(clientupdate.start({ port: ports.clientupdate })).then(
      (s) => track(s, "clientupdate"),
    ),
    Promise.resolve(statsUi.start({ port: ports.statsUi })).then((s) =>
      track(s, "stats-ui"),
    ),
    Promise.resolve(transactions.start({ port: ports.transactions })).then(
      (s) => track(s, "transactions"),
    ),
    Promise.resolve(stoneOutcomes.start({ port: ports.stoneOutcomes })).then(
      (s) => track(s, "stone-outcomes"),
    ),
    Promise.resolve(gateway.start({ port: ports.gateway })).then((s) =>
      track(s, "client-gateway"),
    ),
  ]);

  let shuttingDown = false;

  // Optimized: promisify callback-based close without unnecessary try/catch
  // Promise.allSettled already handles rejections gracefully
  const promisifyClose = (server) =>
    new Promise((resolve) => {
      if (typeof server?.close === "function") {
        server.close(resolve);
      } else {
        resolve();
      }
    });

  async function shutdown(signal) {
    if (shuttingDown) return;
    shuttingDown = true;
    console.log(`${signal} received. Shutting down...`);

    // Close all tracked server instances in parallel
    const serverCloses = servers.map(({ server }) => promisifyClose(server));

    // Close modules with additional cleanup logic (preserve original behavior)
    // Filter out falsy values before passing to Promise.allSettled for efficiency
    const moduleCloses = [
      typeof game.close === "function" && game.close(),
      typeof odds.close === "function" && odds.close(),
      typeof timer.close === "function" && timer.close(),
      typeof clientupdate.close === "function" && clientupdate.close(),
    ].filter(Boolean);

    await Promise.allSettled([...serverCloses, ...moduleCloses]);

    process.exit(0);
  }

  // Register shutdown handlers
  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("uncaughtException", (err) => {
    console.error("Uncaught exception:", err);
    shutdown("uncaughtException");
  });
  process.on("unhandledRejection", (err) => {
    console.error("Unhandled rejection:", err);
    shutdown("unhandledRejection");
  });
}

main().catch((err) => {
  console.error("Clientside monolith startup failed:", err?.message || err);
  process.exit(1);
});
