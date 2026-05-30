const express = require("express");
const cors = require("cors");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});
const { Pool } = require("pg");
const fetch =
  typeof globalThis.fetch === "function"
    ? globalThis.fetch.bind(globalThis)
    : (...args) =>
        import("node-fetch").then(({ default: fetchImpl }) =>
          fetchImpl(...args),
        );

const app = express();
const DEFAULT_PORT = 4102;
const NODE_ENV = process.env.NODE_ENV || "development";

// Fix syntax & freeze static configs to help V8 optimize memory layout
const CHARACTER_TABLE = Object.freeze("Decision_character");
const CHARACTER_TABLE_SQL = Object.freeze('"Decision_character"');
const BET_ODDS_TABLE = Object.freeze("bet_odds");
const ODDS_GENERATOR_SYNC_URL =
  process.env.ODDS_GENERATOR_SYNC_URL ||
  "http://127.0.0.1:9000/odds/api/sync/latest-odds/";
const ODDS_SYNC_TIMEOUT_MS = Math.max(
  1000,
  Number(process.env.ODDS_SYNC_TIMEOUT_MS || 12000),
);
const ODDS_SYNC_COOLDOWN_MS = Math.max(
  1000,
  Number(process.env.ODDS_SYNC_COOLDOWN_MS || 10000),
);

let characterColumns;
let betOddsColumns;
let latestCharactersCache = [];
const optionsBundleCache = new Map();
let oddsSyncState = {
  key: "",
  promise: null,
  startedAt: 0,
  finishedAt: 0,
  warnedAt: 0,
};

// RAM-optimized PostgreSQL pools
const characterPool = new Pool({
  user: process.env.DB_USER || process.env.GAME_DB_USER || "postgres",
  host: process.env.DB_HOST || process.env.GAME_DB_HOST || "localhost",
  database: process.env.DB_NAME || process.env.GAME_DB_NAME || "DECISIONAPP",
  password:
    process.env.DB_PASS ||
    process.env.DB_PASSWORD ||
    process.env.GAME_DB_PASS ||
    process.env.GAME_DB_PASSWORD ||
    "Software",
  port: Number(process.env.DB_PORT || process.env.GAME_DB_PORT || 5432),
  // Memory & connection optimizations
  max: 3,
  idleTimeoutMillis: 30000,
  maxUses: 5000,
  connectionTimeoutMillis: 5000,
});

const oddsPool = new Pool({
  user: process.env.ODDS_DB_USER || process.env.DB_USER || "postgres",
  host: process.env.ODDS_DB_HOST || process.env.DB_HOST || "localhost",
  database: process.env.ODDS_DB_NAME || "ODDSGENERATOR",
  password:
    process.env.ODDS_DB_PASS ||
    process.env.ODDS_DB_PASSWORD ||
    process.env.DB_PASS ||
    process.env.DB_PASSWORD ||
    "Software",
  port: Number(process.env.ODDS_DB_PORT || process.env.DB_PORT || 5432),
  // Memory & connection optimizations
  max: 3,
  idleTimeoutMillis: 30000,
  maxUses: 5000,
  connectionTimeoutMillis: 5000,
});

// Prevent unhandled pool errors from leaking memory on crash loops
characterPool.on("error", (err) =>
  console.error("CharacterPool Error:", err.message),
);
oddsPool.on("error", (err) => console.error("OddsPool Error:", err.message));

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

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeCharacter(row) {
  const rawName = String(row.name || "");
  const cleanName = rawName.split("_")[0] || rawName;
  return {
    id: Number(row.id),
    name: cleanName,
    stamina: toNumber(row.stamina),
    control: toNumber(row.control),
    power: toNumber(row.power),
  };
}

function cacheCharacters(characters) {
  latestCharactersCache = Array.isArray(characters)
    ? characters.map((character) => ({ ...character }))
    : [];
}

function readCachedCharacters(limit = 5) {
  const safeLimit = Number.isInteger(limit) ? Math.max(limit, 1) : 5;
  return latestCharactersCache.slice(0, safeLimit).map((character) => ({
    ...character,
  }));
}

function cacheOptionsBundle(bundle) {
  if (!bundle || !Number.isInteger(Number(bundle.characterId))) return;
  optionsBundleCache.set(Number(bundle.characterId), {
    ...bundle,
    payload: bundle.payload
      ? JSON.parse(JSON.stringify(bundle.payload))
      : bundle.payload,
  });
}

function readCachedOptionsBundle(characterId) {
  const cached = optionsBundleCache.get(Number(characterId));
  if (!cached) return null;
  return {
    ...cached,
    payload: cached.payload
      ? JSON.parse(JSON.stringify(cached.payload))
      : cached.payload,
  };
}

function quoteIdentifier(name) {
  return `"${String(name).replace(/"/g, '""')}"`;
}

function pickCharacterColumn(columnMap, label, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) return columnMap.get(candidate);
  }
  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token)))
      return actualName;
  }
  const available = Array.from(columnMap.values()).join(", ");
  throw new Error(
    `Missing ${label} column on ${CHARACTER_TABLE}. Available columns: ${available}`,
  );
}

async function resolveCharacterColumns() {
  if (characterColumns) return characterColumns;
  let rows = [];
  try {
    ({ rows } = await characterPool.query(
      `SELECT table_schema, column_name
         FROM information_schema.columns
        WHERE table_name = $1
           OR table_name = LOWER($1)
        ORDER BY table_schema, ordinal_position`,
      [CHARACTER_TABLE],
    ));
    if (!rows.length) {
      ({ rows } = await characterPool.query(
        `SELECT c.relname AS table_name, n.nspname AS table_schema
               , a.attname AS column_name
           FROM pg_catalog.pg_class c
           JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
           JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
          WHERE c.relkind = 'r'
            AND a.attnum > 0
            AND NOT a.attisdropped
            AND c.relname = $1
          ORDER BY n.nspname, a.attnum`,
        [CHARACTER_TABLE],
      ));
    }
  } catch (error) {
    console.error(
      "[Odds API] resolveCharacterColumns failed:",
      error.stack || error.message || error,
    );
    throw error;
  }

  if (!rows.length) {
    throw new Error(`Could not resolve columns for ${CHARACTER_TABLE}`);
  }

  const columnMap = new Map(
    rows.map((row) => [String(row.column_name).toLowerCase(), row.column_name]),
  );
  characterColumns = {
    stamina: pickCharacterColumn(
      columnMap,
      "stamina",
      ["stamina"],
      ["stamina", "stam"],
    ),
    control: pickCharacterColumn(
      columnMap,
      "control",
      ["control"],
      ["control", "ctrl"],
    ),
    power: pickCharacterColumn(
      columnMap,
      "power",
      ["power", "powe"],
      ["power", "powe"],
    ),
  };
  return characterColumns;
}

async function resolveBetOddsColumns() {
  if (betOddsColumns) return betOddsColumns;
  const { rows } = await oddsPool.query(
    `SELECT column_name
       FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND table_name = $1
      ORDER BY ordinal_position`,
    [BET_ODDS_TABLE],
  );
  betOddsColumns = rows.map((row) => row.column_name);
  return betOddsColumns;
}

function toOddsNumber(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) return 1.0;
  return Number(parsed.toFixed(2));
}

function toImpliedProbability(odds) {
  const value = Number(odds);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return Number((1 / value).toFixed(6));
}

// RAM-optimized: avoids intermediate array creation during odds mapping
function mapBetOddsRowToOptions(row) {
  const singleDraw = [];
  for (let i = 1; i <= 5; i++) {
    const odds = toOddsNumber(row[`drn${i}`]);
    singleDraw.push({
      key: `D${i}`,
      odds,
      probability: toImpliedProbability(odds),
    });
  }

  const singleFloat = [];
  for (let i = 1; i <= 5; i++) {
    const odds = toOddsNumber(row[`flt${i}`]);
    singleFloat.push({
      key: `F${i}`,
      odds,
      probability: toImpliedProbability(odds),
    });
  }

  const doublesByFloat = {
    F1: [
      { key: "F1andD2", column: "flt1_and_drn2" },
      { key: "F1andD3", column: "flt1_and_drn3" },
      { key: "F1andD4", column: "flt1_and_drn4" },
      { key: "F1andD5", column: "flt1_and_drn5" },
    ],
    F2: [
      { key: "F2andD3", column: "flt2_and_drn3" },
      { key: "F2andD4", column: "flt2_and_drn4" },
      { key: "F2andD5", column: "flt2_and_drn5" },
    ],
    F3: [
      { key: "F3andD4", column: "flt3_and_drn4" },
      { key: "F3andD5", column: "flt3_and_drn5" },
    ],
    F4: [{ key: "F4andD5", column: "flt4_and_drn5" }],
    F5: [],
  };

  for (const bucket in doublesByFloat) {
    const arr = doublesByFloat[bucket];
    for (let i = 0; i < arr.length; i++) {
      const item = arr[i];
      const odds = toOddsNumber(row[item.column]);
      arr[i] = { key: item.key, odds, probability: toImpliedProbability(odds) };
    }
  }

  return {
    single: { draw: singleDraw, float: singleFloat },
    double: doublesByFloat,
  };
}

async function getCharacters(limit = 5) {
  const columns = await resolveCharacterColumns();
  const safeLimit = Number.isInteger(limit) ? Math.max(limit, 1) : 5;
  const query = `SELECT c.id, c.name, c.${quoteIdentifier(columns.stamina)} AS stamina, c.${quoteIdentifier(columns.control)} AS control, c.${quoteIdentifier(columns.power)} AS power FROM ${CHARACTER_TABLE_SQL} c ORDER BY c.id DESC LIMIT $1`;
  const { rows } = await characterPool.query(query, [safeLimit]);
  const characters = rows.map(normalizeCharacter);
  cacheCharacters(characters);

  // Prewarm odds for the active board once so /api/options does not fan out
  // into one sync request per character.
  if (characters.length && safeLimit <= 5) {
    requestOddsSync({
        limit: characters.length,
        characterIds: characters.map((character) => character.id),
      }).catch(() => {
        // /api/options will retry against the shared sync state if needed.
      });
  }

  return characters;
}

function normalizeSyncCharacterIds(characterIds) {
  if (!Array.isArray(characterIds) || characterIds.length === 0) return [];
  return Array.from(
    new Set(
      characterIds
        .map((value) => Number.parseInt(String(value), 10))
        .filter((value) => Number.isInteger(value) && value > 0),
    ),
  ).sort((a, b) => a - b);
}

function buildOddsSyncKey({ limit = 5, characterIds = null } = {}) {
  const normalizedIds = normalizeSyncCharacterIds(characterIds);
  return normalizedIds.length
    ? `ids:${normalizedIds.join(",")}`
    : `limit:${Math.max(1, Number(limit) || 1)}`;
}

async function requestOddsSync({ limit = 5, characterIds = null } = {}) {
  const normalizedIds = normalizeSyncCharacterIds(characterIds);
  const safeLimit = Math.max(1, Number(limit) || 1);
  const key = buildOddsSyncKey({ limit: safeLimit, characterIds: normalizedIds });
  const now = Date.now();

  if (oddsSyncState.promise && oddsSyncState.key === key) {
    return oddsSyncState.promise;
  }
  if (
    oddsSyncState.key === key &&
    oddsSyncState.finishedAt &&
    now - oddsSyncState.finishedAt < ODDS_SYNC_COOLDOWN_MS
  ) {
    return null;
  }

  const url = new URL(ODDS_GENERATOR_SYNC_URL);
  url.searchParams.set("limit", String(safeLimit));
  if (normalizedIds.length) {
    url.searchParams.set("character_ids", normalizedIds.join(","));
  }
  oddsSyncState.key = key;
  oddsSyncState.startedAt = now;
  oddsSyncState.promise = (async () => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), ODDS_SYNC_TIMEOUT_MS);
    try {
      const response = await fetch(url, {
        method: "GET",
        signal: controller.signal,
      });
      if (!response.ok) {
        throw new Error(`Odds sync failed with status ${response.status}`);
      }
      return await response.json().catch(() => ({}));
    } finally {
      clearTimeout(timeout);
    }
  })();

  try {
    return await oddsSyncState.promise;
  } catch (error) {
    const isAbort = error?.name === "AbortError";
    if (Date.now() - oddsSyncState.warnedAt > ODDS_SYNC_COOLDOWN_MS) {
      oddsSyncState.warnedAt = Date.now();
      console.warn(
        isAbort
          ? "Odds sync timed out; serving cached odds if available."
          : `Odds sync failed: ${error?.message || error}`,
      );
    }
    throw error;
  } finally {
    oddsSyncState.promise = null;
    oddsSyncState.finishedAt = Date.now();
  }
}

async function getCharacterById(characterId) {
  const safeCharacterId = Number(characterId);
  if (!Number.isInteger(safeCharacterId) || safeCharacterId <= 0) return null;
  try {
    const cached =
      latestCharactersCache.find(
        (character) => Number(character.id) === safeCharacterId,
      ) || null;
    if (cached) return { ...cached };

    const columns = await resolveCharacterColumns();
    const query = `SELECT id, name, ${quoteIdentifier(columns.stamina)} AS stamina, ${quoteIdentifier(columns.control)} AS control, ${quoteIdentifier(columns.power)} AS power FROM ${CHARACTER_TABLE_SQL} WHERE id = $1 LIMIT 1`;
    const { rows } = await characterPool.query(query, [safeCharacterId]);
    if (!rows.length) return null;
    const normalized = normalizeCharacter(rows[0]);
    const existingIndex = latestCharactersCache.findIndex(
      (character) => Number(character.id) === safeCharacterId,
    );
    if (existingIndex >= 0) {
      latestCharactersCache.splice(existingIndex, 1, { ...normalized });
    } else {
      latestCharactersCache.unshift({ ...normalized });
    }
    return normalized;
  } catch (error) {
    const cached =
      latestCharactersCache.find(
        (character) => Number(character.id) === safeCharacterId,
      ) || null;
    if (cached) return { ...cached };
    throw error;
  }
}

async function getOptionsBundleByCharacterId(characterId) {
  const safeCharacterId = Number.parseInt(String(characterId || ""), 10);
  if (!Number.isInteger(safeCharacterId) || safeCharacterId <= 0) return null;
  const cachedBundle = readCachedOptionsBundle(safeCharacterId);
  try {
    const activeCharacter = await getCharacterById(safeCharacterId);
    if (!activeCharacter) return cachedBundle;
    await resolveBetOddsColumns();
    let { rows } = await oddsPool.query(
      `SELECT * FROM ${BET_ODDS_TABLE} WHERE character_id = $1 LIMIT 1`,
      [safeCharacterId],
    );
    if (!rows.length) {
      try {
        await requestOddsSync({ limit: 1, characterIds: [safeCharacterId] });
        ({ rows } = await oddsPool.query(
          `SELECT * FROM ${BET_ODDS_TABLE} WHERE character_id = $1 LIMIT 1`,
          [safeCharacterId],
        ));
      } catch {}
    }
    if (!rows.length) return cachedBundle;
    const row = rows[0];
    const mapped = mapBetOddsRowToOptions(row);
    const oddsUpdatedAtMs = row.updated_at
      ? Date.parse(String(row.updated_at))
      : null;
    const version = `${safeCharacterId}:${Number.isFinite(oddsUpdatedAtMs) ? oddsUpdatedAtMs : "na"}`;
    const bundle = {
      characterId: safeCharacterId,
      version,
      payload: { character: activeCharacter, ...mapped },
    };
    cacheOptionsBundle(bundle);
    return bundle;
  } catch (error) {
    if (cachedBundle) return cachedBundle;
    throw error;
  }
}

// Express setup
app.disable("x-powered-by");
app.use(express.json({ limit: "16kb" }));
app.use(cors({ origin: parseCorsOrigins() }));

app.get("/health", (req, res) => {
  res.json({
    service: "Odds",
    status: "ok",
    timestamp: new Date().toISOString(),
  });
});

app.get("/api/characters", async (req, res) => {
  try {
    const limit = Number.parseInt(String(req.query.limit || ""), 10);
    res.json(await getCharacters(limit));
  } catch (error) {
    console.error(
      "[Odds API] Could not load characters:",
      error.stack || error.message || error,
    );
    const limit = Number.parseInt(String(req.query.limit || ""), 10);
    const cachedCharacters = readCachedCharacters(limit);
    if (cachedCharacters.length) {
      return res.json(cachedCharacters);
    }
    const payload = { error: "Could not load characters" };
    if (process.env.NODE_ENV !== "production") {
      payload.details = String(error.message || error);
    }
    res.status(500).json(payload);
  }
});

app.get("/api/characters/:id", async (req, res) => {
  try {
    const character = await getCharacterById(req.params.id);
    if (!character)
      return res.status(404).json({ error: "Character not found" });
    return res.json(character);
  } catch (error) {
    console.error("Could not load character:", error.message);
    return res.status(500).json({ error: "Could not load character" });
  }
});

app.get("/api/options", async (req, res) => {
  const characterId = Number.parseInt(String(req.query.characterId || ""), 10);
  if (!Number.isInteger(characterId) || characterId <= 0) {
    return res.status(400).json({ error: "characterId is required." });
  }
  try {
    const optionsBundle = await getOptionsBundleByCharacterId(characterId);
    if (!optionsBundle)
      return res.status(404).json({ error: "Character not found" });
    return res.json(optionsBundle.payload);
  } catch (error) {
    console.error("Could not load options:", error.message);
    return res.status(500).json({ error: "Could not load options" });
  }
});

app.use((req, res) => res.status(404).json({ error: "Not found" }));
app.use((err, req, res, next) => {
  const message = String(err?.message || "Internal error").slice(0, 500);
  console.error("Unhandled request error:", message);
  res.status(500).json({ error: "Internal server error" });
});

let server;

function createApp() {
  return app;
}

async function close() {
  await Promise.allSettled([characterPool.end(), oddsPool.end()]);
}

function start(options = {}) {
  const effectivePort = Number(
    options.port ?? process.env.PORT ?? DEFAULT_PORT,
  );
  server = app.listen(effectivePort, options.host, () => {
    console.log(`Odds service listening on port ${effectivePort}`);
  });
  return server;
}

async function shutdown(signal) {
  console.log(`${signal} received. Shutting down...`);
  if (server) await new Promise((resolve) => server.close(resolve));
  await close();
  process.exit(0);
}

module.exports = { createApp, start, close };

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
