const express = require("express");
const cors = require("cors");
const redis = require("redis");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});

const app = express();
const DEFAULT_PORT = 4106;
const NODE_ENV = process.env.NODE_ENV || "development";

function parseBooleanEnv(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return undefined;
}

const REDIS_REQUIRED =
  parseBooleanEnv(process.env.REDIS_REQUIRED) ?? NODE_ENV === "production";
let hasLoggedRedisUnavailable = false;

function isRedisConnectionRefused(err) {
  if (!err) return false;
  if (err.code === "ECONNREFUSED") return true;
  if (Array.isArray(err.errors)) {
    return err.errors.some((item) => item?.code === "ECONNREFUSED");
  }
  return /ECONNREFUSED/i.test(String(err.message || err));
}

function logRedisUnavailableOnce(prefix) {
  if (hasLoggedRedisUnavailable) return;
  hasLoggedRedisUnavailable = true;
  console.warn(
    `${prefix} Redis is unavailable; continuing without Redis. Set REDIS_REQUIRED=true to fail fast instead.`,
  );
}

// Freeze static configs to help V8 optimize memory layout
const LIVE_STREAM_INTERVAL_MS = Object.freeze(
  Math.max(500, Number(process.env.LIVE_STREAM_INTERVAL_MS || 1500)),
);
const BET_UPDATES_LIMIT = Object.freeze(
  Math.max(1, Number(process.env.BET_UPDATES_LIMIT || 20)),
);
const REDIS_RECENT_BETS_KEY = "round:recent:bets";
const HEARTBEAT_INTERVAL_MS = 15000;

// RAM-optimized Redis configuration
function buildRedisOptions() {
  const redisUrl = process.env.REDIS_URL;
  const reconnectStrategy = REDIS_REQUIRED
    ? (retries) => Math.min(retries * 100, 3000)
    : false;
  if (redisUrl) {
    const parsedUrl = new URL(redisUrl);
    return {
      socket: {
        host: parsedUrl.hostname || process.env.REDIS_HOST || "127.0.0.1",
        port: Number(parsedUrl.port || process.env.REDIS_PORT || 6379),
        keepAlive: 5000,
        noDelay: true,
      },
      username:
        decodeURIComponent(parsedUrl.username || "") ||
        process.env.REDIS_USERNAME ||
        undefined,
      password:
        decodeURIComponent(parsedUrl.password || "") ||
        process.env.REDIS_PASSWORD ||
        undefined,
      database: parsedUrl.pathname
        ? Number.parseInt(parsedUrl.pathname.replace("/", ""), 10) || 0
        : undefined,
      disableOfflineQueue: true,
      commandsQueueMaxLength: 0,
      pingInterval: 10000,
      reconnectStrategy,
    };
  }
  return {
    socket: {
      host: process.env.REDIS_HOST || "127.0.0.1",
      port: Number(process.env.REDIS_PORT || 6379),
      keepAlive: 5000,
      noDelay: true,
    },
    username: process.env.REDIS_USERNAME || undefined,
    password: process.env.REDIS_PASSWORD || undefined,
    disableOfflineQueue: true,
    commandsQueueMaxLength: 0,
    pingInterval: 10000,
    reconnectStrategy,
  };
}

const redisClient = redis.createClient(buildRedisOptions());
redisClient.on("error", (err) => {
  if (!REDIS_REQUIRED && isRedisConnectionRefused(err)) {
    logRedisUnavailableOnce("[Timer]");
    return;
  }
  console.error("Redis Error:", err?.message || err);
});

let isRedisReady = false;

function parseCorsOrigins() {
  const origin = process.env.CORS_ORIGIN;
  if (!origin) {
    return NODE_ENV === "production"
      ? []
      : [
          "http://127.0.0.1:5500",
          "http://localhost:5500",
          "http://localhost:10000",
        ];
  }
  return origin
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

// Optimized parser: single-pass, avoids intermediate objects
function safeParseEntry(raw) {
  if (!raw || typeof raw !== "string") return null;

  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;

    // Inline validation to avoid object spread overhead
    const bettorName = String(parsed.bettorName || "").trim() || "Bettor";
    const optionCode = String(parsed.optionCode || "").trim() || "N/A";
    const amountRaw = Number(parsed.amount);
    const amount = Number.isFinite(amountRaw) ? amountRaw : null;
    const placedAt = parsed.placedAt || null;

    return { bettorName, optionCode, amount, placedAt };
  } catch {
    return null;
  }
}

// RAM-optimized: single-pass fetch and parse
async function fetchRecentBets(limit = BET_UPDATES_LIMIT) {
  if (!redisClient?.isReady) return [];

  const safeLimit = Number.isInteger(limit)
    ? Math.max(1, limit)
    : BET_UPDATES_LIMIT;
  const raw = await redisClient.lRange(REDIS_RECENT_BETS_KEY, 0, safeLimit - 1);

  if (!raw || raw.length === 0) return [];

  // Single-pass parse and filter
  const result = [];
  for (let i = 0; i < raw.length; i += 1) {
    const entry = safeParseEntry(raw[i]);
    if (entry) result.push(entry);
  }

  return result;
}

function computeVersion(items) {
  if (!items || items.length === 0) return "0:0";
  return `${items.length}:${items[0]?.optionCode || "na"}`;
}

function writeSseEvent(res, event, payload) {
  // Check if response is still writable before allocating memory
  if (res.writableEnded) return false;
  try {
    res.write(`event: ${event}\n`);
    res.write(`data: ${JSON.stringify(payload)}\n\n`);
    return true;
  } catch {
    return false;
  }
}

// Express setup
app.disable("x-powered-by");
app.use(express.json({ limit: "16kb" }));
app.use(cors({ origin: parseCorsOrigins() }));

app.get("/health", (req, res) => {
  res.status(isRedisReady ? 200 : 503).json({
    ok: isRedisReady,
    env: NODE_ENV,
    services: {
      redis: isRedisReady ? "up" : "down",
    },
  });
});

app.get("/api/bettor-updates/snapshot", async (req, res) => {
  try {
    const items = await fetchRecentBets();
    res.json({ version: computeVersion(items), items });
  } catch (error) {
    console.error("Could not fetch bettor updates:", error.message);
    res.status(503).json({ error: "Bettor updates unavailable" });
  }
});

app.get("/api/bettor-updates/stream", async (req, res) => {
  // Set headers for SSE
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders?.();

  let closed = false;
  let lastVersion = null;
  let intervalId = null;
  let heartbeatId = null;

  // Cleanup function to prevent memory leaks
  const cleanup = () => {
    if (closed) return;
    closed = true;
    if (intervalId) clearInterval(intervalId);
    if (heartbeatId) clearInterval(heartbeatId);
    intervalId = null;
    heartbeatId = null;
  };

  const pushSnapshot = async () => {
    if (closed || res.writableEnded) {
      cleanup();
      return;
    }

    try {
      const items = await fetchRecentBets();
      const version = computeVersion(items);

      if (version !== lastVersion) {
        lastVersion = version;
        const success = writeSseEvent(res, "snapshot", { version, items });
        if (!success) cleanup();
      }
    } catch (error) {
      // Don't send error events on every failure to reduce memory pressure
      if (Math.random() < 0.1) {
        // 10% chance to report error
        writeSseEvent(res, "error", { error: "Bettor updates unavailable" });
      }
    }
  };

  // Heartbeat to keep connection alive
  heartbeatId = setInterval(() => {
    if (closed || res.writableEnded) {
      cleanup();
      return;
    }
    res.write(": heartbeat\n\n");
  }, HEARTBEAT_INTERVAL_MS);

  // Main polling interval
  intervalId = setInterval(pushSnapshot, LIVE_STREAM_INTERVAL_MS);

  // Initial snapshot
  pushSnapshot();

  // Handle client disconnect
  req.on("close", cleanup);
  req.on("end", cleanup);
  res.on("finish", cleanup);
  res.on("error", cleanup);
});

app.use((req, res) => {
  res.status(404).json({ error: "Not found" });
});

app.use((err, req, res, next) => {
  // Truncate error messages to prevent memory bloat
  const message = String(err?.message || "Internal error").slice(0, 500);
  console.error("Unhandled request error:", message);
  res.status(500).json({ error: "Internal server error" });
});

function createApp() {
  return app;
}

async function init() {
  try {
    if (!redisClient.isOpen) {
      await redisClient.connect();
    }
    isRedisReady = redisClient.isReady;
  } catch (error) {
    if (!REDIS_REQUIRED && isRedisConnectionRefused(error)) {
      logRedisUnavailableOnce("[Timer]");
    } else {
      console.warn("[Timer] Redis not ready:", error?.message || error);
    }
    isRedisReady = false;
  }
}

async function close() {
  if (redisClient?.isOpen) {
    try {
      await redisClient.quit();
    } catch {
      // Ignore quit errors during shutdown
    }
  }
}

async function start(options = {}) {
  const effectivePort = Number(
    options.port ?? process.env.PORT ?? DEFAULT_PORT,
  );
  await init();
  return app.listen(effectivePort, options.host, () => {
    console.log(`ClientUpdate service listening on port ${effectivePort}`);
  });
}

async function shutdown(signal) {
  console.log(`${signal} received. Shutting down...`);

  await close();

  process.exit(0);
}

module.exports = { createApp, init, start, close };

if (require.main === module) {
  start().catch((err) => {
    console.error("Startup failed:", err?.message || err);
    process.exit(1);
  });

  process.on("SIGINT", () => shutdown("SIGINT"));
  process.on("SIGTERM", () => shutdown("SIGTERM"));
  process.on("uncaughtException", (err) => {
    console.error("Uncaught exception:", err?.message || err);
    shutdown("uncaughtException");
  });
  process.on("unhandledRejection", (err) => {
    console.error("Unhandled rejection:", err?.message || err);
    shutdown("unhandledRejection");
  });
}
