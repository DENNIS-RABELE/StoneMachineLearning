const express = require("express");
const cors = require("cors");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});

const app = express();
const DEFAULT_PORT = 4108;
const NODE_ENV = process.env.NODE_ENV || "development";
const STATIC_ROOT = path.join(__dirname, "..");
const RESULTS_API_URL =
  process.env.RESULTS_API_URL || "http://127.0.0.1:4100/api/results?limit=1";
const DECISION_CHARACTERS_URL =
  process.env.DECISION_CHARACTERS_URL ||
  "http://127.0.0.1:9006/api/decision/api/characters/latest/?limit=5";

// Freeze static configs to help V8 optimize memory layout
const CORS_DEFAULTS = Object.freeze([
  "http://127.0.0.1:5500",
  "http://localhost:5500",
  "http://localhost:10000",
]);
const PHASES_FLOAT = Object.freeze([
  "FLOAT",
  "FLOAT",
  "FLOAT",
  "FLOAT",
  "FLOAT",
]);
const PHASES_DROWN = Object.freeze(["DROWN", null, null, null, null]);
const PHASES_NULL = Object.freeze([null, null, null, null, null]);

// Pre-compiled regex patterns (avoid re-compilation on every call)
const REGEX_FLOAT_AND_DROWN = /^F(\d)ANDD(\d)$/;
const REGEX_DIRECT = /^(FLOAT|DROWN)(\d)$/;

// RAM-optimized cache for post-game stats (10-second TTL)
let statsCache = null;
let statsCacheTimestamp = 0;
const STATS_CACHE_TTL_MS = 10000;

function parseCorsOrigins() {
  const origin = process.env.CORS_ORIGIN;
  if (!origin) {
    return NODE_ENV === "production" ? [] : CORS_DEFAULTS;
  }
  // Single-pass loop to avoid intermediate arrays
  const origins = [];
  const parts = origin.split(",");
  for (let i = 0; i < parts.length; i++) {
    const trimmed = parts[i].trim();
    if (trimmed) origins.push(trimmed);
  }
  return origins;
}

function normalizeText(value) {
  return String(value || "").trim();
}

function cleanCharacterName(name, fallbackIndex) {
  const raw = normalizeText(name);
  if (!raw) return `CHAR ${fallbackIndex + 1}`;
  const [clean] = raw.split("_");
  return clean || raw;
}

function parseResultPath(resultZone) {
  const raw = normalizeText(resultZone).toUpperCase();

  const floatMatch = REGEX_FLOAT_AND_DROWN.exec(raw);
  if (floatMatch) {
    return buildPhasesFromThreshold(
      Number(floatMatch[1]),
      Number(floatMatch[2]),
    );
  }

  const directMatch = REGEX_DIRECT.exec(raw);
  if (directMatch) {
    if (directMatch[1] === "FLOAT") {
      const floatPhase = Number(directMatch[2]);
      return buildPhasesFromThreshold(floatPhase, Math.min(floatPhase + 1, 5));
    }
    return buildPhasesFromThreshold(
      Math.max(Number(directMatch[2]) - 1, 0),
      Number(directMatch[2]),
    );
  }

  if (raw === "FLOAT") return PHASES_FLOAT;
  if (raw === "DROWN") return PHASES_DROWN;
  return PHASES_NULL;
}

function buildPhasesFromThreshold(floatPhaseCount, drownPhase) {
  const phases = new Array(5);
  for (let phase = 1; phase <= 5; phase++) {
    if (phase <= floatPhaseCount) {
      phases[phase - 1] = "FLOAT";
    } else if (phase === drownPhase) {
      phases[phase - 1] = "DROWN";
    } else {
      phases[phase - 1] = null;
    }
  }
  return phases;
}

async function fetchJson(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const response = await fetch(url, {
      headers: { Accept: "application/json" },
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`Request failed (${response.status}) for ${url}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

// Cached loader with TTL
async function loadPostGameStats() {
  const now = Date.now();
  if (statsCache && now - statsCacheTimestamp < STATS_CACHE_TTL_MS) {
    return statsCache;
  }

  // Use Promise.allSettled to handle partial failures gracefully
  const [resultsRes, charactersRes] = await Promise.allSettled([
    fetchJson(RESULTS_API_URL),
    fetchJson(DECISION_CHARACTERS_URL),
  ]);

  const resultsPayload =
    resultsRes.status === "fulfilled" ? resultsRes.value : null;
  const charactersPayload =
    charactersRes.status === "fulfilled" ? charactersRes.value : null;

  const latestResult = Array.isArray(resultsPayload?.results)
    ? resultsPayload.results[0]
    : Array.isArray(resultsPayload)
      ? resultsPayload[0]
      : resultsPayload?.rows?.[0] || {};

  const resultZone = normalizeText(
    latestResult?.result_zone ||
      latestResult?.round_result ||
      latestResult?.drawOption ||
      latestResult?.result ||
      "",
  );

  // Pre-compute phases once, reuse for all characters
  const phases = parseResultPath(resultZone);

  const characters = Array.isArray(charactersPayload?.results)
    ? charactersPayload.results
    : Array.isArray(charactersPayload?.characters)
      ? charactersPayload.characters
      : [];

  const payload = {
    result_zone: resultZone,
    generated_at: new Date().toISOString(),
    characters: characters.map((entry, index) => ({
      id: Number(entry.id),
      name: cleanCharacterName(entry.name, index),
      power: Number(entry.power || 0),
      control: Number(entry.control || 0),
      stamina: Number(entry.stamina || 0),
      phases, // Reuse same frozen array reference
    })),
  };

  statsCache = payload;
  statsCacheTimestamp = now;
  return payload;
}

// Express setup
app.disable("x-powered-by");
app.use(cors({ origin: parseCorsOrigins() }));
app.use(express.static(STATIC_ROOT, { maxAge: "1d", immutable: true }));

app.get("/", (req, res) => {
  res.sendFile(path.join(STATIC_ROOT, "index.html"));
});

app.get("/health", (req, res) => {
  res.json({
    service: "stats-ui",
    status: "ok",
    timestamp: new Date().toISOString(),
  });
});

app.get("/api/post-game-stats", async (req, res) => {
  try {
    const payload = await loadPostGameStats();
    res.json(payload);
  } catch (error) {
    const msg = String(error?.message || error).slice(0, 256);
    console.error("Could not load post-game stats:", msg);
    res.status(503).json({
      error: "post_game_stats_unavailable",
      detail: msg,
    });
  }
});

app.use((req, res) => {
  res.status(404).send("Not found");
});

app.use((err, req, res, next) => {
  if (err?.type === "request.aborted" || err?.code === "ECONNABORTED") return;
  const msg = String(err?.message || "Internal error").slice(0, 256);
  console.error("Unhandled error:", msg);
  res.status(500).json({ error: "Internal server error" });
});

let server;

function createApp() {
  return app;
}

function start(options = {}) {
  const effectivePort = Number(
    options.port ?? process.env.PORT ?? DEFAULT_PORT,
  );
  server = app.listen(effectivePort, options.host, () => {
    console.log(`Stats UI listening on port ${effectivePort}`);
  });
  return server;
}

// Graceful shutdown
async function shutdown(signal) {
  console.log(`${signal} received. Shutting down...`);
  if (server) await new Promise((resolve) => server.close(resolve));
  statsCache = null;
  process.exit(0);
}

module.exports = { createApp, start };

if (require.main === module) {
  start();
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
