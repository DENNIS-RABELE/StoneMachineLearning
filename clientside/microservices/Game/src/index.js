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
const authenticateToken = require("./middleware/authenticateToken");
const {
  incrementBet,
  incrementCategorizedBet,
  getCurrentBets,
  pushRecentBet,
} = require("./lib/betQueue");
const { board } = require("./lib/oddsBoard");
const {
  getRecentRoundResults,
  verifyDbConnection,
  closeDbConnection,
  pool,
} = require("./lib/dbFlush");
const {
  client: redisClient,
  connectRedis,
  disconnectRedis,
  isRedisReady,
} = require("./lib/redisClient");

const app = express();
const DEFAULT_PORT = 4103;
const NODE_ENV = process.env.NODE_ENV || "development";
const CHARACTER_TABLE = "Decision_character";
const CHARACTER_TABLE_SQL = '"Decision_character"';
const BET_ODDS_TABLE = "bet_odds";
const CLIENT_ROUND_TABLE = '"Decision_gameround"';
const CLIENT_OUTCOME_TABLE = "client_outcome";
const CLIENT_BET_TABLE = "client_bet";
const CLIENT_BET_OUTCOME_TABLE = "client_bet_outcome";
const CLIENT_SLIP_TABLE = "client_slip";
const CLIENT_SLIP_ITEM_TABLE = "client_slip_item";
const GATEWAY_URL = process.env.GATEWAY_URL || "http://127.0.0.1:9006";
const BETDATA_SYNC_PATH =
  process.env.BETDATA_SYNC_PATH || "/api/bettor/betdata/api/bets/sync-status/";

// Freeze static configs to prevent mutation & help V8 optimize memory layout
const ALLOWED_BET_OPTIONS = new Set(board.allOptions);
const ROUND_STATUS = Object.freeze({
  OPEN: "OPEN",
  CLOSED: "CLOSED",
});
const BET_STATUS = Object.freeze({
  OPEN: "OPEN",
  CLOSED: "CLOSED",
});
const ROUND_DURATION_SECONDS = Math.max(
  1,
  Number(process.env.ROUND_DURATION_SECONDS || 200),
);
const LIVE_STREAM_INTERVAL_MS = Math.max(
  1000,
  Number(process.env.LIVE_STREAM_INTERVAL_MS || 1000),
);
const LATEST_RESULT_CACHE_TTL_MS = Math.max(
  LIVE_STREAM_INTERVAL_MS,
  Number(process.env.LIVE_LATEST_RESULT_CACHE_TTL_MS || 3000),
);

let characterColumns;
let betOddsColumns;
let isDbReady = false;
let isCharacterSchemaReady = false;
let isOddsSchemaReady = false;
let server;
let latestRoundResultCache = null;
let latestRoundResultFetchedAt = 0;
let latestRoundResultPromise = null;
const REDIS_BETS_KEY = "round:current:bets";
const REDIS_ROUND_TIMER_KEY = "round:timer:state";

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      return value;
    }
  }
  return undefined;
}

function firstDbDefined(...values) {
  return firstDefined(...values);
}

// RAM-optimized PostgreSQL pool for bets
const betPool = new Pool({
  user: firstDbDefined(
    process.env.BETS_DB_USER,
    process.env.DB_USER,
    process.env.BETTING_DB_USER,
    process.env.GAME_DB_USER,
    "postgres",
  ),
  host: firstDbDefined(
    process.env.BETS_DB_HOST,
    process.env.DB_HOST,
    process.env.BETTING_DB_HOST,
    process.env.GAME_DB_HOST,
    "localhost",
  ),
  database: firstDbDefined(
    process.env.BETS_DB_NAME,
    process.env.DB_NAME,
    process.env.BETTING_DB_NAME,
    process.env.GAME_DB_NAME,
    "betting",
  ),
  password: firstDbDefined(
    process.env.BETS_DB_PASS,
    process.env.BETS_DB_PASSWORD,
    process.env.DB_PASS,
    process.env.DB_PASSWORD,
    process.env.BETTING_DB_PASS,
    process.env.BETTING_DB_PASSWORD,
    process.env.GAME_DB_PASS,
    process.env.GAME_DB_PASSWORD,
    "123456",
  ),
  port: Number(
    firstDbDefined(
      process.env.BETS_DB_PORT,
      process.env.DB_PORT,
      process.env.BETTING_DB_PORT,
      process.env.GAME_DB_PORT,
      5432,
    ),
  ),
  // Memory & connection optimizations
  max: parseInt(process.env.DB_POOL_MAX || "3", 10),
  idleTimeoutMillis: 30000,
  maxUses: 5000,
  connectionTimeoutMillis: 5000,
  allowExitOnIdle: false,
});

// Prevent unhandled pool errors from leaking memory on crash loops
betPool.on("error", (err) => {
  console.error("Unexpected betPool error:", err.message);
});

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

function validateRuntimeConfig() {
  const hasDbUser = Boolean(
    process.env.DB_USER ||
    process.env.BETTING_DB_USER ||
    process.env.GAME_DB_USER,
  );
  const hasDbHost = Boolean(
    process.env.DB_HOST ||
    process.env.BETTING_DB_HOST ||
    process.env.GAME_DB_HOST,
  );
  const hasDbName = Boolean(
    process.env.DB_NAME ||
    process.env.BETTING_DB_NAME ||
    process.env.GAME_DB_NAME,
  );
  const hasDbPort = Boolean(
    process.env.DB_PORT ||
    process.env.BETTING_DB_PORT ||
    process.env.GAME_DB_PORT,
  );
  const hasDbPassword = Boolean(
    process.env.DB_PASS ||
    process.env.DB_PASSWORD ||
    process.env.BETTING_DB_PASS ||
    process.env.BETTING_DB_PASSWORD ||
    process.env.GAME_DB_PASS ||
    process.env.GAME_DB_PASSWORD,
  );
  const hasRedisUrl = Boolean(process.env.REDIS_URL);
  const hasRedisHostPort = Boolean(
    process.env.REDIS_HOST && process.env.REDIS_PORT,
  );
  if (!hasRedisUrl && !hasRedisHostPort) {
    throw new Error(
      "Missing required env vars: REDIS_URL or REDIS_HOST+REDIS_PORT",
    );
  }
  const missingVars = [];
  if (!hasDbUser) missingVars.push("DB_USER/BETTING_DB_USER/GAME_DB_USER");
  if (!hasDbHost) missingVars.push("DB_HOST/BETTING_DB_HOST/GAME_DB_HOST");
  if (!hasDbName) missingVars.push("DB_NAME/BETTING_DB_NAME/GAME_DB_NAME");
  if (!hasDbPort) missingVars.push("DB_PORT/BETTING_DB_PORT/GAME_DB_PORT");
  if (!hasDbPassword) {
    missingVars.push(
      "DB_PASS|DB_PASSWORD|BETTING_DB_PASS|BETTING_DB_PASSWORD|GAME_DB_PASS|GAME_DB_PASSWORD",
    );
  }
  if (missingVars.length > 0) {
    throw new Error(`Missing required env vars: ${missingVars.join(", ")}`);
  }
}

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

async function syncBetStatusWithGateway() {
  const base = String(GATEWAY_URL || "").replace(/\/+$/, "");
  const path = String(
    BETDATA_SYNC_PATH || "/api/bettor/betdata/api/bets/sync-status/",
  );
  const url = `${base}${path.startsWith("/") ? "" : "/"}${path}`;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 3000);
  try {
    const res = await fetch(url, { method: "GET", signal: controller.signal });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      console.warn("[Game API] Bet sync failed:", res.status, text);
    }
  } catch (error) {
    console.warn("[Game API] Bet sync unavailable:", error?.message || error);
  } finally {
    clearTimeout(timeout);
  }
}

async function verifyBetDbConnection() {
  await betPool.query("SELECT 1");
}

function normalizeCharacter(row) {
  return {
    id: Number(row.id),
    name: row.name,
    stamina: toNumber(row.stamina),
    control: toNumber(row.control),
    power: toNumber(row.power),
    created_at: row.created_at,
  };
}

function displayCharacterName(rawName) {
  const name = String(rawName || "").trim();
  if (!name) return "Unknown";
  const [clean] = name.split("_");
  return clean || name;
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

function pickClientBetColumn(columnMap, label, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) return columnMap.get(candidate);
  }
  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token)))
      return actualName;
  }
  const available = Array.from(columnMap.values()).join(", ");
  throw new Error(
    `Missing ${label} column on ${CLIENT_BET_TABLE}. Available columns: ${available}`,
  );
}

function pickOutcomeColumn(columnMap, label, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) return columnMap.get(candidate);
  }
  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token)))
      return actualName;
  }
  const available = Array.from(columnMap.values()).join(", ");
  throw new Error(
    `Missing ${label} column on ${CLIENT_OUTCOME_TABLE}. Available columns: ${available}`,
  );
}

let clientBetColumns;
let outcomeColumns;

async function nextTableId(dbRunner, tableName) {
  const seqRes = await dbRunner.query(
    `SELECT pg_get_serial_sequence($1, 'id') AS sequence_name`,
    [tableName],
  );
  const sequenceName = seqRes.rows[0]?.sequence_name || null;
  if (sequenceName) {
    const safeSequenceName = String(sequenceName).replace(/'/g, "''");
    const maxRes = await dbRunner.query(
      `SELECT MAX(id) AS max_id FROM ${tableName}`,
    );
    const maxId = Number(maxRes.rows[0]?.max_id);
    if (Number.isFinite(maxId) && maxId > 0) {
      await dbRunner.query(
        `SELECT setval('${safeSequenceName}', ${maxId}, true)`,
      );
    } else {
      await dbRunner.query(`SELECT setval('${safeSequenceName}', 1, false)`);
    }
    const nextRes = await dbRunner.query(
      `SELECT nextval('${safeSequenceName}') AS next_id`,
    );
    return Number(nextRes.rows[0]?.next_id);
  }
  const fallbackRes = await dbRunner.query(
    `SELECT COALESCE(MAX(id), 0) + 1 AS next_id FROM ${tableName}`,
  );
  return Number(fallbackRes.rows[0]?.next_id);
}

async function resolveClientBetColumns() {
  if (clientBetColumns) return clientBetColumns;
  const { rows } = await betPool.query(
    `SELECT column_name
       FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND table_name = $1
      ORDER BY ordinal_position`,
    [CLIENT_BET_TABLE],
  );
  const columnMap = new Map(
    rows.map((row) => [String(row.column_name).toLowerCase(), row.column_name]),
  );
  clientBetColumns = {
    character: pickClientBetColumn(
      columnMap,
      "character",
      ["character_id", "character"],
      ["character"],
    ),
    gameRound: pickClientBetColumn(
      columnMap,
      "game round",
      ["game_round_id", "game_round"],
      ["game_round", "round"],
    ),
    slipId: columnMap.get("slip_id") || null,
  };
  return clientBetColumns;
}

async function resolveOutcomeColumns(dbRunner) {
  if (outcomeColumns) return outcomeColumns;
  const { rows } = await dbRunner.query(
    `SELECT column_name
       FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND table_name = $1
      ORDER BY ordinal_position`,
    [CLIENT_OUTCOME_TABLE],
  );
  const columnMap = new Map(
    rows.map((row) => [String(row.column_name).toLowerCase(), row.column_name]),
  );
  outcomeColumns = {
    externalOutcomeId: pickOutcomeColumn(
      columnMap,
      "external outcome id",
      [
        "external_outcome_id",
        "external_outcome",
        "outcome_external_id",
        "external_id",
      ],
      ["external", "outcome"],
    ),
    id: pickOutcomeColumn(columnMap, "id", ["id"], ["id"]),
    phaseId: pickOutcomeColumn(
      columnMap,
      "phase id",
      ["phase_id", "phase"],
      ["phase"],
    ),
    kind: pickOutcomeColumn(
      columnMap,
      "kind",
      ["kind", "type"],
      ["kind", "type"],
    ),
    code: pickOutcomeColumn(columnMap, "code", ["code"], ["code"]),
    label: pickOutcomeColumn(
      columnMap,
      "label",
      ["label", "name"],
      ["label", "name"],
    ),
  };
  return outcomeColumns;
}

async function ensureOutcomeSeedRows(dbRunner, externalIds) {
  const columns = await resolveOutcomeColumns(dbRunner);
  const externalColumn = quoteIdentifier(columns.externalOutcomeId);
  const idColumn = columns.id ? quoteIdentifier(columns.id) : null;
  const phaseColumn = columns.phaseId ? quoteIdentifier(columns.phaseId) : null;
  const kindColumn = columns.kind ? quoteIdentifier(columns.kind) : null;
  const codeColumn = columns.code ? quoteIdentifier(columns.code) : null;
  const labelColumn = columns.label ? quoteIdentifier(columns.label) : null;

  const { rows: requiredRows } = await dbRunner.query(
    `SELECT column_name
       FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND is_nullable = 'NO'
        AND table_name = $1
        AND column_default IS NULL
      ORDER BY ordinal_position`,
    [CLIENT_OUTCOME_TABLE],
  );
  const requiredExtras = requiredRows
    .map((row) => String(row.column_name))
    .filter(
      (name) => name.toLowerCase() !== columns.externalOutcomeId.toLowerCase(),
    );

  const supported = new Set(
    [columns.id, columns.phaseId, columns.kind, columns.code, columns.label]
      .filter(Boolean)
      .map((name) => String(name).toLowerCase()),
  );
  const unsupported = requiredExtras.filter(
    (name) => !supported.has(String(name).toLowerCase()),
  );
  if (unsupported.length > 0) {
    throw new Error(
      `Outcome seed rows are missing and ${CLIENT_OUTCOME_TABLE} requires columns without defaults: ${unsupported.join(", ")}. Run client_bet_data migrations.`,
    );
  }

  const { rows } = await dbRunner.query(
    `SELECT ${externalColumn} AS external_outcome_id FROM ${CLIENT_OUTCOME_TABLE} WHERE ${externalColumn} = ANY($1::int[])`,
    [externalIds],
  );
  const found = new Set(rows.map((row) => Number(row.external_outcome_id)));
  const missing = externalIds.filter((id) => !found.has(Number(id)));
  if (!missing.length) return;

  let sequenceName = null;
  if (columns.id) {
    const sequenceNameQuery = await dbRunner.query(
      `SELECT pg_get_serial_sequence($1, $2) AS sequence_name`,
      [CLIENT_OUTCOME_TABLE, columns.id],
    );
    sequenceName = sequenceNameQuery.rows[0]?.sequence_name || null;
    if (sequenceName) {
      const safeSequenceName = String(sequenceName).replace(/'/g, "''");
      const maxIdRes = await dbRunner.query(
        `SELECT MAX(${idColumn}) AS max_id FROM ${CLIENT_OUTCOME_TABLE}`,
      );
      const maxId = Number(maxIdRes.rows[0]?.max_id);
      if (Number.isFinite(maxId) && maxId > 0) {
        await dbRunner.query(
          `SELECT setval('${safeSequenceName}', ${maxId}, true)`,
        );
      } else {
        await dbRunner.query(`SELECT setval('${safeSequenceName}', 1, false)`);
      }
    }
  }

  const insertColumns = [externalColumn];
  const selectColumns = ["x.external_id"];
  const needsId = requiredExtras.some(
    (name) =>
      String(name).toLowerCase() === String(columns.id || "").toLowerCase(),
  );
  if (needsId && idColumn) {
    insertColumns.unshift(idColumn);
    if (sequenceName) {
      const escapedSequenceName = String(sequenceName).replace(/'/g, "''");
      selectColumns.unshift(`nextval('${escapedSequenceName}')`);
    } else {
      selectColumns.unshift(
        "max_ids.max_id + ROW_NUMBER() OVER (ORDER BY x.external_id)",
      );
    }
  }
  if (phaseColumn) {
    insertColumns.push(phaseColumn);
    selectColumns.push("((x.external_id + 1) / 2)");
  }
  if (kindColumn) {
    insertColumns.push(kindColumn);
    selectColumns.push(
      "CASE WHEN (x.external_id % 2) = 1 THEN 'FLOAT' ELSE 'DROWN' END",
    );
  }
  if (codeColumn) {
    insertColumns.push(codeColumn);
    selectColumns.push(
      "CASE WHEN (x.external_id % 2) = 1 THEN 'F' || ((x.external_id + 1) / 2) ELSE 'D' || (x.external_id / 2) END",
    );
  }
  if (labelColumn) {
    insertColumns.push(labelColumn);
    selectColumns.push(
      "CASE WHEN (x.external_id % 2) = 1 THEN 'Float ' || ((x.external_id + 1) / 2) ELSE 'Drown ' || (x.external_id / 2) END",
    );
  }

  const maxIdCte =
    needsId && idColumn && !sequenceName
      ? `WITH max_ids AS (SELECT COALESCE(MAX(${idColumn}), 0) AS max_id FROM ${CLIENT_OUTCOME_TABLE})`
      : " ";
  const maxIdJoin =
    needsId && idColumn && !sequenceName ? "CROSS JOIN max_ids " : " ";

  await dbRunner.query(
    `${maxIdCte} INSERT INTO ${CLIENT_OUTCOME_TABLE} (${insertColumns.join(", ")}) SELECT ${selectColumns.join(", ")} FROM UNNEST($1::int[]) AS x(external_id) ${maxIdJoin} WHERE NOT EXISTS ( SELECT 1 FROM ${CLIENT_OUTCOME_TABLE} t WHERE t.${externalColumn} = x.external_id )`,
    [missing],
  );
}

async function resolveCharacterColumns() {
  if (characterColumns) return characterColumns;
  const { rows } = await pool.query(
    `SELECT column_name
       FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND table_name = $1
      ORDER BY ordinal_position`,
    [CHARACTER_TABLE],
  );
  const columnMap = new Map(
    rows.map((row) => [String(row.column_name).toLowerCase(), row.column_name]),
  );
  characterColumns = {
    stamina: pickCharacterColumn(
      columnMap,
      "stamina",
      ["stamina "],
      ["stamina ", "stam "],
    ),
    control: pickCharacterColumn(
      columnMap,
      "control",
      ["control "],
      ["control ", "ctrl "],
    ),
    power: pickCharacterColumn(
      columnMap,
      "power",
      ["power ", "powe "],
      ["power ", "powe "],
    ),
  };
  isCharacterSchemaReady = true;
  return characterColumns;
}

async function resolveBetOddsColumns() {
  if (betOddsColumns) return betOddsColumns;
  const { rows } = await pool.query(
    `SELECT column_name
       FROM information_schema.columns
      WHERE table_schema = current_schema()
        AND table_name = $1
      ORDER BY ordinal_position`,
    [BET_ODDS_TABLE],
  );
  betOddsColumns = rows.map((row) => row.column_name);
  isOddsSchemaReady = true;
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

function mapBetOddsRowToOptions(row) {
  const singleDraw = ["D1", "D2", "D3", "D4", "D5"].map((key, idx) => {
    const odds = toOddsNumber(row[`drn${idx + 1}`]);
    return { key, odds, probability: toImpliedProbability(odds) };
  });
  const singleFloat = ["F1", "F2", "F3", "F4", "F5"].map((key, idx) => {
    const odds = toOddsNumber(row[`flt${idx + 1}`]);
    return { key, odds, probability: toImpliedProbability(odds) };
  });
  const doublesByFloat = {
    F1: [
      { key: "F1andD2 ", column: "flt1_and_drn2 " },
      { key: "F1andD3 ", column: "flt1_and_drn3 " },
      { key: "F1andD4 ", column: "flt1_and_drn4 " },
      { key: "F1andD5 ", column: "flt1_and_drn5 " },
    ],
    F2: [
      { key: "F2andD3 ", column: "flt2_and_drn3 " },
      { key: "F2andD4 ", column: "flt2_and_drn4 " },
      { key: "F2andD5 ", column: "flt2_and_drn5 " },
    ],
    F3: [
      { key: "F3andD4 ", column: "flt3_and_drn4 " },
      { key: "F3andD5 ", column: "flt3_and_drn5 " },
    ],
    F4: [{ key: "F4andD5 ", column: "flt4_and_drn5 " }],
    F5: [],
  };
  for (const bucket of Object.keys(doublesByFloat)) {
    doublesByFloat[bucket] = doublesByFloat[bucket].map((item) => {
      const odds = toOddsNumber(row[item.column]);
      return { key: item.key, odds, probability: toImpliedProbability(odds) };
    });
  }
  return {
    single: { draw: singleDraw, float: singleFloat },
    double: doublesByFloat,
  };
}

function flattenMappedOptions(mapped) {
  const out = [];
  if (mapped?.single?.draw) out.push(...mapped.single.draw);
  if (mapped?.single?.float) out.push(...mapped.single.float);
  if (mapped?.double) {
    for (const bucket of Object.values(mapped.double)) out.push(...bucket);
  }
  return out;
}

function parseBetSelection(option) {
  const raw = String(option || "").trim();
  const single = raw.match(/^([FD])([1-5])$/i);
  if (single) {
    const side = single[1].toUpperCase();
    const phase = Number.parseInt(single[2], 10);
    const outcomeExternalId = side === "F" ? phase * 2 - 1 : phase * 2;
    return {
      optionCode: raw,
      betType: "SINGLE",
      phaseStart: phase,
      phaseEnd: null,
      outcomeExternalIds: [outcomeExternalId],
    };
  }
  const combo = raw.match(/^F([1-5])andD([1-5])$/i);
  if (combo) {
    const floatPhase = Number.parseInt(combo[1], 10);
    const drawPhase = Number.parseInt(combo[2], 10);
    if (drawPhase <= floatPhase)
      throw new Error("Invalid DOUBLE option phase order");
    return {
      optionCode: raw,
      betType: "DOUBLE",
      phaseStart: floatPhase,
      phaseEnd: drawPhase,
      outcomeExternalIds: [floatPhase * 2 - 1, drawPhase * 2],
    };
  }
  throw new Error("Unsupported option format");
}

function asEpochMs(value) {
  if (!value) return Date.now();
  if (value instanceof Date) return value.getTime();
  const parsed = Date.parse(String(value));
  return Number.isFinite(parsed) ? parsed : Date.now();
}

function normalizeRoundRow(row) {
  if (!row) return null;
  return {
    id: Number(row.id),
    roundId: Number(row.round_id),
    startTime: row.start_time ? new Date(row.start_time) : new Date(),
    endTime: row.end_time ? new Date(row.end_time) : null,
    status: row.status || ROUND_STATUS.OPEN,
  };
}

function computeSecondsRemaining({
  startTimeMs,
  durationSeconds = ROUND_DURATION_SECONDS,
  nowMs = Date.now(),
}) {
  const safeDuration = Math.max(
    1,
    Number(durationSeconds) || ROUND_DURATION_SECONDS,
  );
  const elapsed = Math.max(0, Math.floor((nowMs - startTimeMs) / 1000));
  return Math.max(0, safeDuration - elapsed);
}

async function getCurrentOpenRound(dbRunner) {
  let rows;
  try {
    ({ rows } = await dbRunner.query(
      `SELECT id, round_id, start_time, end_time, status FROM ${CLIENT_ROUND_TABLE} WHERE status = $1 ORDER BY round_id DESC LIMIT 1`,
      [ROUND_STATUS.OPEN],
    ));
  } catch (error) {
    if (
      error?.code === "42P01" &&
      String(error?.message || "").includes("Decision_gameround")
    ) {
      console.warn(
        "[Game API] Round table not ready yet; continuing without cached round state.",
      );
      return null;
    }
    throw error;
  }
  if (!rows.length) return null;
  return normalizeRoundRow(rows[0]);
}

async function requireOpenRound(dbRunner) {
  const openRound = await getCurrentOpenRound(dbRunner);
  if (openRound) return openRound;
  throw new Error(
    "No OPEN round available. Round lifecycle must be driven by Django/Celery.",
  );
}

async function readRoundTimerStateFromRedis() {
  if (!redisClient?.isReady) return null;
  const payload = await redisClient.hGetAll(REDIS_ROUND_TIMER_KEY);
  if (!payload || Object.keys(payload).length === 0) return null;
  const roundId = Number.parseInt(String(payload.roundId || ""), 10);
  const startTimeMs = Number.parseInt(String(payload.startTimeMs || ""), 10);
  const durationSeconds = Number.parseInt(
    String(payload.durationSeconds || ROUND_DURATION_SECONDS),
    10,
  );
  const endTimeMs = Number.parseInt(String(payload.endTimeMs || ""), 10);
  const secondsRemaining = Number.parseInt(String(payload.secondsRemaining || ""), 10);
  const secondsElapsed = Number.parseInt(String(payload.secondsElapsed || ""), 10);
  const serverTimeMs = Number.parseInt(String(payload.serverTimeMs || ""), 10);
  if (
    !Number.isFinite(roundId) ||
    roundId <= 0 ||
    !Number.isFinite(startTimeMs)
  )
    return null;
  return {
    roundId,
    status: payload.status || ROUND_STATUS.OPEN,
    startTimeMs,
    endTimeMs: Number.isFinite(endTimeMs) ? endTimeMs : null,
    durationSeconds: Number.isFinite(durationSeconds)
      ? Math.max(1, durationSeconds)
      : ROUND_DURATION_SECONDS,
    secondsRemaining: Number.isFinite(secondsRemaining)
      ? Math.max(0, secondsRemaining)
      : null,
    secondsElapsed: Number.isFinite(secondsElapsed)
      ? Math.max(0, secondsElapsed)
      : null,
    serverTimeMs: Number.isFinite(serverTimeMs) ? serverTimeMs : null,
  };
}

async function ensureRoundTimerState() {
  const cached = await readRoundTimerStateFromRedis();
  if (cached && cached.status === ROUND_STATUS.OPEN) return cached;
  throw new Error(
    "Round timer not initialized in Redis. Decision service is the only timer writer.",
  );
}

function buildRoundTimerSnapshot(state) {
  const serverTimeMs = Date.now();
  let secondsRemaining = null;
  let secondsElapsed = null;
  const computedEndTimeMs =
    Number.isFinite(Number(state.endTimeMs)) && Number(state.endTimeMs) > 0
      ? Number(state.endTimeMs)
      : Number(state.startTimeMs) + Number(state.durationSeconds) * 1000;

  if (Number.isFinite(computedEndTimeMs) && computedEndTimeMs > 0) {
    secondsRemaining = Math.max(
      0,
      Math.floor((computedEndTimeMs - serverTimeMs) / 1000),
    );
  } else {
    secondsRemaining = computeSecondsRemaining({
      startTimeMs: state.startTimeMs,
      durationSeconds: state.durationSeconds,
      nowMs: serverTimeMs,
    });
  }

  secondsElapsed = Math.max(0, state.durationSeconds - secondsRemaining);
  return {
    roundId: state.roundId,
    status: state.status,
    durationSeconds: state.durationSeconds,
    secondsRemaining,
    secondsElapsed,
    startTimeMs: state.startTimeMs,
    endTimeMs: computedEndTimeMs,
    serverTimeMs,
    source: "redis",
  };
}

async function getOutcomePkByExternalIds(dbRunner, externalIds) {
  await ensureOutcomeSeedRows(dbRunner, externalIds);
  const columns = await resolveOutcomeColumns(dbRunner);
  const externalColumn = quoteIdentifier(columns.externalOutcomeId);
  const { rows } = await dbRunner.query(
    `SELECT id, ${externalColumn} AS external_outcome_id FROM ${CLIENT_OUTCOME_TABLE} WHERE ${externalColumn} = ANY($1::int[])`,
    [externalIds],
  );
  if (rows.length !== externalIds.length) {
    throw new Error(
      "Outcome seed rows are missing. Run client_bet_data migrations.",
    );
  }
  const map = new Map(
    rows.map((row) => [Number(row.external_outcome_id), Number(row.id)]),
  );
  return externalIds.map((id) => map.get(Number(id)));
}

async function ensureClientSlip(dbRunner, { playerId, gameRoundId, placedAt }) {
  const slipId = await nextTableId(dbRunner, CLIENT_SLIP_TABLE);
  const { rows } = await dbRunner.query(
    `INSERT INTO ${CLIENT_SLIP_TABLE} (id, player_id, game_round, status, total_stake, total_possible_win, placed_at, updated_at)
     VALUES ($1, $2, $3, 'OPEN', 0, 0, $4, NOW())
     ON CONFLICT (player_id, game_round)
     DO UPDATE SET updated_at = NOW()
     RETURNING id`,
    [slipId, playerId, gameRoundId, placedAt],
  );
  return Number(rows[0].id);
}

async function attachClientBetToSlip(
  dbRunner,
  {
    playerId,
    gameRoundId,
    betId,
    characterId,
    selection,
    stake,
    odds,
    placedAt,
  },
) {
  const slipId = await ensureClientSlip(dbRunner, {
    playerId,
    gameRoundId,
    placedAt,
  });
  const slipItemId = await nextTableId(dbRunner, CLIENT_SLIP_ITEM_TABLE);
  const possibleWin = Number((Number(stake) * Number(odds)).toFixed(2));
  await dbRunner.query(
    `INSERT INTO ${CLIENT_SLIP_ITEM_TABLE} (id, slip_id, bet_id, character, bet_type, option_code, phase_start, phase_end, stake, odds, possible_win, placed_at, created_at) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW())`,
    [
      slipItemId,
      slipId,
      betId,
      characterId,
      selection.betType,
      selection.optionCode,
      selection.phaseStart,
      selection.phaseEnd,
      stake,
      odds,
      possibleWin,
      placedAt,
    ],
  );
  await dbRunner.query(
    `UPDATE ${CLIENT_SLIP_TABLE} SET total_stake = COALESCE(agg.total_stake, 0), total_possible_win = COALESCE(agg.total_possible_win, 0), updated_at = NOW() FROM ( SELECT slip_id, SUM(stake) AS total_stake, SUM(possible_win) AS total_possible_win FROM ${CLIENT_SLIP_ITEM_TABLE} WHERE slip_id = $1 GROUP BY slip_id ) AS agg WHERE ${CLIENT_SLIP_TABLE}.id = $1`,
    [slipId],
  );
}

async function resolveOptionOdds(characterId, option) {
  const optionsBundle = await getOptionsBundleByCharacterId(characterId);
  if (!optionsBundle) throw new Error("Odds not found for selected character");
  const item = flattenMappedOptions(optionsBundle.mapped).find(
    (entry) => entry.key === option,
  );
  if (!item) throw new Error("Option odds could not be resolved");
  return Number(item.odds);
}

async function getOptionsBundleByCharacterId(characterId) {
  if (!isCharacterSchemaReady || !isOddsSchemaReady) return null;
  const safeCharacterId = Number.parseInt(String(characterId || ""), 10);
  if (!Number.isInteger(safeCharacterId) || safeCharacterId <= 0) return null;
  const activeCharacter = await getCharacterById(safeCharacterId);
  if (!activeCharacter) return null;
  await resolveBetOddsColumns();

  try {
    const { rows } = await pool.query(
      `SELECT * FROM ${BET_ODDS_TABLE} WHERE character_id = $1 LIMIT 1`,
      [safeCharacterId],
    );
    if (!rows.length) return null;
    const row = rows[0];
    const mapped = mapBetOddsRowToOptions(row);
    const oddsUpdatedAtMs = row.updated_at
      ? Date.parse(String(row.updated_at))
      : null;
    const version = `${safeCharacterId}:${Number.isFinite(oddsUpdatedAtMs) ? oddsUpdatedAtMs : "na"}`;
    return {
      characterId: safeCharacterId,
      version,
      payload: { character: activeCharacter, ...mapped },
      mapped,
    };
  } catch (error) {
    // Gracefully handle missing bet_odds table (common in local development)
    // Table doesn't exist in decision_service schema; odds will be unavailable
    if (error.code === "42P01" || error.message?.includes("does not exist")) {
      console.warn(
        `[Game API] Odds table unavailable; character ${safeCharacterId} loaded without odds data`,
      );
      return null;
    }
    throw error;
  }
}

async function getLatestRoundResult() {
  if (
    latestRoundResultCache &&
    Date.now() - latestRoundResultFetchedAt <= LATEST_RESULT_CACHE_TTL_MS
  ) {
    return { ...latestRoundResultCache };
  }

  if (latestRoundResultPromise) return latestRoundResultPromise;

  latestRoundResultPromise = (async () => {
    try {
      const rows = await getRecentRoundResults(1);
      if (!rows.length) {
        latestRoundResultCache = null;
        latestRoundResultFetchedAt = Date.now();
        return null;
      }
      const latest = rows[0];
      const payload = {
        id: Number(latest.id),
        drawOption: latest.result_zone,
        createdAt: latest.created_at,
      };
      latestRoundResultCache = payload;
      latestRoundResultFetchedAt = Date.now();
      return { ...payload };
    } catch (error) {
      if (latestRoundResultCache) {
        console.warn(
          `[Game API] Using cached latest result after DB failure: ${error.message}`,
        );
        latestRoundResultFetchedAt = Date.now();
        return { ...latestRoundResultCache };
      }
      throw error;
    } finally {
      latestRoundResultPromise = null;
    }
  })();

  return latestRoundResultPromise;
}

function computeBetsChecksum(bets) {
  const entries = Object.entries(bets || {}).sort(([a], [b]) =>
    a.localeCompare(b),
  );
  let totalStake = 0;
  for (const [, count] of entries) totalStake += Number(count) || 0;
  return `${entries.length}:${totalStake}`;
}

async function buildLiveSnapshot({ characterId = null } = {}) {
  const timerState = await ensureRoundTimerState();
  const timer = buildRoundTimerSnapshot(timerState);
  const [betsResult, latestResultResult, optionsBundleResult] =
    await Promise.allSettled([
      getCurrentBets(),
      getLatestRoundResult(),
      getOptionsBundleByCharacterId(characterId),
    ]);

  if (betsResult.status === "rejected") {
    console.warn(
      `[Game API] Could not load live bets for snapshot: ${betsResult.reason?.message || betsResult.reason}`,
    );
  }
  if (latestResultResult.status === "rejected") {
    console.warn(
      `[Game API] Could not load latest result for snapshot: ${latestResultResult.reason?.message || latestResultResult.reason}`,
    );
  }
  if (optionsBundleResult.status === "rejected") {
    console.warn(
      `[Game API] Could not load options bundle for snapshot: ${optionsBundleResult.reason?.message || optionsBundleResult.reason}`,
    );
  }

  const bets = betsResult.status === "fulfilled" ? betsResult.value : {};
  const latestResult =
    latestResultResult.status === "fulfilled"
      ? latestResultResult.value
      : latestRoundResultCache
        ? { ...latestRoundResultCache }
        : null;
  const optionsBundle =
    optionsBundleResult.status === "fulfilled" ? optionsBundleResult.value : null;
  const optionsVersion = optionsBundle?.version || "none";
  const latestResultId = latestResult?.id || 0;
  const betsChecksum = computeBetsChecksum(bets);
  const version = [
    timer.roundId,
    timer.secondsRemaining,
    latestResultId,
    optionsVersion,
    betsChecksum,
  ].join(":");
  return {
    version,
    serverTimeMs: timer.serverTimeMs,
    timer,
    bets,
    latestResult,
    options: optionsBundle
      ? {
          characterId: optionsBundle.characterId,
          version: optionsBundle.version,
          payload: optionsBundle.payload,
        }
      : null,
  };
}

function writeSseEvent(res, event, payload) {
  res.write(`event: ${event}\n`);
  res.write(`data: ${JSON.stringify(payload)}\n\n`);
}

async function persistClientBet({
  playerId,
  characterId,
  option,
  stake,
  oddsOverride,
  gameRoundIdOverride,
  placedAt = new Date(),
  slipId = null,
}) {
  syncBetStatusWithGateway();
  const selection = parseBetSelection(option);
  const odds = Number(oddsOverride);
  if (!Number.isFinite(odds) || odds <= 0)
    throw new Error("Invalid odds provided by gateway");

  let currentRoundNumber = null;
  let gameRoundId = Number(gameRoundIdOverride);
  if (!Number.isInteger(gameRoundId) || gameRoundId <= 0) {
    const openRound = await requireOpenRound(pool);
    currentRoundNumber = openRound.roundId;
    gameRoundId = openRound.roundId;
  }

  const dbClient = await betPool.connect();
  try {
    await dbClient.query("BEGIN");
    const betColumns = await resolveClientBetColumns();
    const betCharacterColumn = quoteIdentifier(betColumns.character);
    const betGameRoundColumn = quoteIdentifier(betColumns.gameRound);

    if (!currentRoundNumber) {
      const openRound = await requireOpenRound(pool);
      currentRoundNumber = openRound.roundId;
    }

    const outcomeIds = await getOutcomePkByExternalIds(
      dbClient,
      selection.outcomeExternalIds,
    );
    const insertColumns = [
      "player_id ",
      betCharacterColumn,
      betGameRoundColumn,
      "status ",
      "bet_type ",
      "option_code ",
      "phase_start ",
      "phase_end ",
      "stake ",
      "odds ",
      "placed_at ",
    ];
    const insertValues = [
      playerId,
      characterId,
      gameRoundId,
      BET_STATUS.OPEN,
      selection.betType,
      selection.optionCode,
      selection.phaseStart,
      selection.phaseEnd,
      stake,
      odds,
      placedAt,
    ];

    if (betColumns.slipId && slipId) {
      insertColumns.splice(3, 0, quoteIdentifier(betColumns.slipId));
      insertValues.splice(3, 0, slipId);
    }

    const valueSlots = insertValues.map((_, idx) => `$${idx + 1}`);
    insertColumns.push("created_at ");
    valueSlots.push("NOW() ");

    const insertBetResult = await dbClient.query(
      `INSERT INTO ${CLIENT_BET_TABLE} (${insertColumns.join(", ")}) VALUES (${valueSlots.join(", ")}) RETURNING id`,
      insertValues,
    );
    const betId = Number(insertBetResult.rows[0].id);

    for (let idx = 0; idx < outcomeIds.length; idx += 1) {
      await dbClient.query(
        `INSERT INTO ${CLIENT_BET_OUTCOME_TABLE} (bet_id, outcome_id, selection_order) VALUES ($1, $2, $3)`,
        [betId, outcomeIds[idx], idx + 1],
      );
    }

    await attachClientBetToSlip(dbClient, {
      playerId,
      gameRoundId,
      betId,
      characterId,
      selection,
      stake,
      odds,
      placedAt,
    });
    await dbClient.query("COMMIT");

    return {
      betId,
      roundId: currentRoundNumber,
      betType: selection.betType,
      optionCode: selection.optionCode,
      phaseStart: selection.phaseStart,
      phaseEnd: selection.phaseEnd,
      odds,
      stake,
      outcomeExternalIds: selection.outcomeExternalIds,
      playerBalance: null,
      houseBalance: null,
    };
  } catch (error) {
    await dbClient.query("ROLLBACK");
    throw error;
  } finally {
    dbClient.release();
  }
}

// RAM-optimized: replaces .map().filter().reduce() chains with single-pass loops
async function getCurrentBetsForPlayer(playerId) {
  const safePlayerId = Number(playerId);
  if (!Number.isInteger(safePlayerId) || safePlayerId <= 0) return [];

  const openRoundRows = await pool.query(
    `SELECT id FROM ${CLIENT_ROUND_TABLE} WHERE status = $1 ORDER BY id DESC LIMIT 50`,
    [ROUND_STATUS.OPEN],
  );
  const openRoundIds = [];
  for (const row of openRoundRows.rows) {
    const id = Number(row.id);
    if (Number.isInteger(id) && id > 0) openRoundIds.push(id);
  }
  if (!openRoundIds.length) return [];

  const betColumns = await resolveClientBetColumns();
  const betCharacterColumn = quoteIdentifier(betColumns.character);
  const betGameRoundColumn = quoteIdentifier(betColumns.gameRound);
  const betSlipColumn = betColumns.slipId
    ? quoteIdentifier(betColumns.slipId)
    : null;

  const { rows } = await betPool.query(
    `SELECT b.${betCharacterColumn} AS character_id, b.${betGameRoundColumn} AS game_round_id, ${betSlipColumn ? `b.${betSlipColumn} AS slip_id,` : "NULL AS slip_id,"} b.option_code, COALESCE(SUM(b.stake), 0) AS stake_total, COALESCE(AVG(b.odds), 0) AS odds_value FROM ${CLIENT_BET_TABLE} b WHERE b.player_id = $1 AND b.status = $2 AND b.${betGameRoundColumn} = ANY($3::int[]) GROUP BY b.${betCharacterColumn}, b.${betGameRoundColumn}, b.option_code${betSlipColumn ? `, b.${betSlipColumn}` : ""} ORDER BY b.${betGameRoundColumn} DESC, stake_total DESC`,
    [safePlayerId, BET_STATUS.OPEN, openRoundIds],
  );

  const characterIdSet = new Set();
  for (const row of rows) {
    const id = Number(row.character_id);
    if (Number.isInteger(id) && id > 0) characterIdSet.add(id);
  }

  let nameById = new Map();
  if (characterIdSet.size) {
    const characterRows = await pool.query(
      `SELECT id, name FROM ${CHARACTER_TABLE} WHERE id = ANY($1::int[])`,
      [Array.from(characterIdSet)],
    );
    for (const row of characterRows.rows) {
      nameById.set(Number(row.id), String(row.name || ""));
    }
  }

  const slipsByKey = new Map();
  for (const row of rows) {
    const characterId = Number(row.character_id);
    const gameRoundId = Number(row.game_round_id);
    const slipIdRaw = row.slip_id ? String(row.slip_id) : "";
    const characterNameRaw = String(nameById.get(characterId) || "").trim();
    const characterLabel = characterNameRaw
      ? displayCharacterName(characterNameRaw)
      : `Character #${characterId}`;
    const optionCode = String(row.option_code || "").trim();
    if (!optionCode) continue;

    const stakeTotal = Number(row.stake_total) || 0;
    const oddsValue = Number(row.odds_value) || 0;
    const slipKey = slipIdRaw
      ? `slip:${slipIdRaw}`
      : `round:${gameRoundId}:char:${characterId}:opt:${optionCode}`;

    if (!slipsByKey.has(slipKey)) {
      slipsByKey.set(slipKey, {
        slipId: slipIdRaw || null,
        gameRoundId,
        items: [],
        totalStake: 0,
      });
    }
    const slip = slipsByKey.get(slipKey);
    slip.items.push({
      characterId,
      characterLabel,
      optionCode,
      stakeTotal,
      oddsValue,
    });
    slip.totalStake += stakeTotal;
  }

  return Array.from(slipsByKey.values());
}

async function getCharacters(limit = 5) {
  if (!isCharacterSchemaReady || !isOddsSchemaReady) return [];
  const columns = await resolveCharacterColumns();
  await resolveBetOddsColumns();
  const safeLimit = Number.isInteger(limit) ? Math.max(limit, 1) : 5;
  try {
    const query = `SELECT c.id, c.name, c.${quoteIdentifier(columns.stamina)} AS stamina, c.${quoteIdentifier(columns.control)} AS control, c.${quoteIdentifier(columns.power)} AS power, c.created_at FROM ${CHARACTER_TABLE_SQL} c INNER JOIN ${BET_ODDS_TABLE} bo ON bo.character_id = c.id ORDER BY c.id DESC LIMIT $1`;
    const { rows } = await pool.query(query, [safeLimit]);
    const out = [];
    for (let i = rows.length - 1; i >= 0; i--)
      out.push(normalizeCharacter(rows[i]));
    return out;
  } catch (error) {
    console.error("[Game API] Database query failed:", error.message);
    return [];
  }
}

async function getCharacterById(characterId) {
  if (!isCharacterSchemaReady) return null;
  const safeCharacterId = Number(characterId);
  if (!Number.isInteger(safeCharacterId) || safeCharacterId <= 0) return null;
  try {
    const columns = await resolveCharacterColumns();
    const query = `SELECT id, name, ${quoteIdentifier(columns.stamina)} AS stamina, ${quoteIdentifier(columns.control)} AS control, ${quoteIdentifier(columns.power)} AS power, created_at FROM ${CHARACTER_TABLE_SQL} WHERE id = $1 LIMIT 1`;
    const { rows } = await pool.query(query, [safeCharacterId]);
    return rows.length === 0 ? null : normalizeCharacter(rows[0]);
  } catch (error) {
    console.error("[Game API] Database query failed:", error.message);
    return null;
  }
}

// RAM-optimized: avoids intermediate object creation during migration
async function migrateLegacyBetKeys() {
  if (!redisClient?.isReady) return;
  const items = await redisClient.hGetAll(REDIS_BETS_KEY);
  const entries = Object.entries(items || {});
  if (!entries.length) return;

  for (const [key, rawCount] of entries) {
    const match = String(key).match(/^C(\d+):(.+)$/);
    if (!match) continue;
    const characterId = Number(match[1]);
    const option = match[2];
    const totalStake = Number(rawCount);
    if (!Number.isFinite(totalStake) || totalStake <= 0) continue;

    const character = await getCharacterById(characterId);
    if (!character) continue;

    const cleanName = displayCharacterName(character.name);
    const newKey = `${cleanName}:${option}`;

    await redisClient.hIncrByFloat(REDIS_BETS_KEY, newKey, totalStake);
    await redisClient.hDel(REDIS_BETS_KEY, key);
  }
}

// Express setup
app.disable("x-powered-by");
app.use(express.json({ limit: "16kb" }));
app.use(cors({ origin: parseCorsOrigins() }));

app.get("/health", async (req, res) => {
  const redisReady = isRedisReady();
  let betsReady = false;
  try {
    await verifyBetDbConnection();
    betsReady = true;
  } catch (error) {
    betsReady = false;
  }
  const ok = redisReady && isDbReady && betsReady;
  res.status(ok ? 200 : 503).json({
    ok,
    env: NODE_ENV,
    services: {
      redis: redisReady ? "up" : "down",
      postgres: isDbReady ? "up" : "down",
      bets_postgres: betsReady ? "up" : "down",
    },
  });
});

app.post("/api/bet", authenticateToken, async (req, res) => {
  if (!req.body || typeof req.body !== "object") {
    return res.status(400).json({ error: "Request body is required" });
  }
  const {
    option,
    characterId,
    characterName,
    odds: oddsOverride,
    gameRoundId,
    slipId,
    bettorName,
  } = req.body;
  const stakeRaw = req.body?.stake;

  if (!ALLOWED_BET_OPTIONS.has(option))
    return res.status(400).json({ error: "Invalid bet option" });
  const stake = Number(stakeRaw ?? 1);
  if (!Number.isFinite(stake) || stake <= 0)
    return res.status(400).json({ error: "stake must be a positive number" });
  const oddsValue = Number(oddsOverride);
  if (!Number.isFinite(oddsValue) || oddsValue <= 0)
    return res.status(400).json({ error: "Missing or invalid odds" });
  const playerId = Number(req.user?.userId);
  if (!Number.isInteger(playerId) || playerId <= 0)
    return res.status(401).json({ error: "Invalid authenticated player" });

  let betKey = option;
  let safeCharacterId = null;
  let characterDisplayName = null;

  if (
    characterId !== undefined &&
    characterId !== null &&
    characterId !== " "
  ) {
    const parsedCharacterId = Number.parseInt(String(characterId), 10);
    if (!Number.isInteger(parsedCharacterId) || parsedCharacterId <= 0) {
      return res
        .status(400)
        .json({ error: "characterId must be a positive integer" });
    }
    safeCharacterId = parsedCharacterId;
    if (characterName)
      characterDisplayName = displayCharacterName(characterName);
    if (isCharacterSchemaReady) {
      const character = await getCharacterById(parsedCharacterId);
      if (character)
        characterDisplayName = displayCharacterName(character.name);
    }
    if (!characterDisplayName)
      characterDisplayName = `Character #${parsedCharacterId}`;
    betKey = `${characterDisplayName}:${option}`;
  } else {
    return res.status(400).json({ error: "characterId is required" });
  }

  try {
    const persisted = await persistClientBet({
      playerId,
      characterId: safeCharacterId,
      option,
      stake,
      oddsOverride: oddsValue,
      gameRoundIdOverride: gameRoundId,
      slipId,
      placedAt: new Date().toISOString(),
    });

    await incrementBet(betKey, stake);
    if (safeCharacterId) {
      try {
        if (persisted.betType === "SINGLE") {
          const kind = String(persisted.optionCode || "")
            .toUpperCase()
            .startsWith("F")
            ? "FLOAT"
            : "DROWN";
          await incrementCategorizedBet({
            characterId: safeCharacterId,
            characterName: characterDisplayName,
            kind,
            phase: persisted.phaseStart,
            stake,
            odds: persisted.odds,
          });
        } else if (persisted.betType === "DOUBLE") {
          await incrementCategorizedBet({
            characterId: safeCharacterId,
            characterName: characterDisplayName,
            kind: "FLOAT",
            phase: persisted.phaseStart,
            stake,
            odds: persisted.odds,
          });
          await incrementCategorizedBet({
            characterId: safeCharacterId,
            characterName: characterDisplayName,
            kind: "DROWN",
            phase: persisted.phaseEnd,
            stake,
            odds: persisted.odds,
          });
        }
      } catch (error) {
        console.warn(
          "[Game API] Categorized bet update failed: ",
          error?.message || error,
        );
      }
    }

    try {
      await pushRecentBet({
        bettorName,
        optionCode: persisted.optionCode || option,
        amount: stake,
        placedAt: new Date(),
      });
    } catch (error) {
      console.warn(
        "[Game API] Recent bet push failed: ",
        error?.message || error,
      );
    }

    res.json({
      message: "Bet placed",
      option,
      characterId: safeCharacterId,
      roundId: persisted.roundId,
      betType: persisted.betType,
      optionCode: persisted.optionCode,
      phaseStart: persisted.phaseStart,
      phaseEnd: persisted.phaseEnd,
      stake: persisted.stake,
      odds: persisted.odds,
      outcomes: persisted.outcomeExternalIds,
      playerBalance: persisted.playerBalance,
      houseBalance: persisted.houseBalance,
    });
  } catch (error) {
    console.error("Persist bet failed: ", error);
    if (String(error?.message || "").includes("Insufficient wallet balance")) {
      return res.status(400).json({ error: "Insufficient wallet balance" });
    }
    if (String(error?.message || "").includes("No OPEN round available")) {
      return res
        .status(503)
        .json({ error: "Round lifecycle is not initialized yet." });
    }
    res.status(500).json({ error: "Could not persist bet data" });
  }
});

app.get("/api/bets", async (req, res) => {
  res.json(await getCurrentBets());
});

app.get("/api/bets/me", authenticateToken, async (req, res) => {
  const playerId = Number(req.user?.userId);
  if (!Number.isInteger(playerId) || playerId <= 0)
    return res.status(401).json({ error: "Invalid authenticated player" });
  try {
    res.json(await getCurrentBetsForPlayer(playerId));
  } catch (error) {
    console.error("Could not load player bets:", error);
    res.status(500).json({ error: "Could not load current bets" });
  }
});

app.get("/api/results", async (req, res) => {
  const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
  res.json(await getRecentRoundResults(limit));
});

app.get("/api/round-timer", async (req, res) => {
  try {
    const state = await ensureRoundTimerState();
    return res.json(buildRoundTimerSnapshot(state));
  } catch (error) {
    console.error("Could not load round timer:", error);
    return res.status(503).json({ error: "Round timer unavailable" });
  }
});

app.get("/api/live/snapshot", async (req, res) => {
  try {
    const characterId = Number.parseInt(
      String(req.query.characterId || ""),
      10,
    );
    const payload = await buildLiveSnapshot({
      characterId:
        Number.isInteger(characterId) && characterId > 0 ? characterId : null,
    });
    return res.json(payload);
  } catch (error) {
    console.error("Could not build live snapshot:", error);
    return res.status(503).json({ error: "Live snapshot unavailable" });
  }
});

app.get("/api/live/stream", async (req, res) => {
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache, no-transform");
  res.setHeader("Connection", "keep-alive");
  res.setHeader("X-Accel-Buffering", "no");
  res.flushHeaders?.();

  const characterId = Number.parseInt(String(req.query.characterId || ""), 10);
  const safeCharacterId =
    Number.isInteger(characterId) && characterId > 0 ? characterId : null;
  let closed = false;
  let lastVersion = null;
  let intervalId = null;

  const cleanup = () => {
    if (closed) return;
    closed = true;
    if (intervalId) clearInterval(intervalId);
    intervalId = null;
  };

  const pushSnapshot = async () => {
    if (closed || res.writableEnded) {
      cleanup();
      return;
    }

    try {
      const snapshot = await buildLiveSnapshot({
        characterId: safeCharacterId,
      });
      if (snapshot.version !== lastVersion) {
        lastVersion = snapshot.version;
        writeSseEvent(res, "snapshot", snapshot);
      }
    } catch (error) {
      writeSseEvent(res, "error", {
        error: String(error?.message || "Live snapshot unavailable"),
      });
    }
  };

  intervalId = setInterval(pushSnapshot, LIVE_STREAM_INTERVAL_MS);
  pushSnapshot();

  req.on("close", cleanup);
  req.on("end", cleanup);
  res.on("finish", cleanup);
  res.on("error", cleanup);
});

app.get("/api/rounds/open", async (req, res) => {
  try {
    const openRound = await getCurrentOpenRound(pool);
    if (!openRound)
      return res.status(404).json({ error: "No open round available" });
    return res.json({
      id: openRound.id,
      round_id: openRound.roundId,
      status: openRound.status,
      start_time: openRound.startTime,
      end_time: openRound.endTime,
    });
  } catch (error) {
    console.error("Could not load open round:", error);
    return res.status(500).json({ error: "Could not load open round" });
  }
});

app.post("/api/close-round", async (req, res) => {
  res.status(403).json({
    error:
      "Round closure is server-driven by Django/Celery. Client-triggered closure is disabled.",
  });
});

app.use((req, res) => res.status(404).json({ error: "Not found" }));
app.use((err, req, res, next) => {
  if (err?.type === "request.aborted" || err?.code === "ECONNABORTED") return;
  console.error("Unhandled request error:", err);
  res.status(500).json({ error: "Internal server error" });
});

function createApp() {
  return app;
}

async function init() {
  if (isDbReady) return;

  validateRuntimeConfig();
  const effectiveDbName =
    process.env.DB_NAME ||
    process.env.BETTING_DB_NAME ||
    process.env.GAME_DB_NAME;
  const effectiveDbHost =
    process.env.DB_HOST ||
    process.env.BETTING_DB_HOST ||
    process.env.GAME_DB_HOST;
  const effectiveDbPort =
    process.env.DB_PORT ||
    process.env.BETTING_DB_PORT ||
    process.env.GAME_DB_PORT;
  console.log(
    `[Game API] Using DB ${effectiveDbName}@${effectiveDbHost}:${effectiveDbPort} for characters and odds`,
  );

  const effectiveBetDbName =
    process.env.BETS_DB_NAME ||
    process.env.BETTING_DB_NAME ||
    process.env.GAME_DB_NAME ||
    process.env.DB_NAME;
  const effectiveBetDbHost =
    process.env.BETS_DB_HOST ||
    process.env.BETTING_DB_HOST ||
    process.env.GAME_DB_HOST ||
    process.env.DB_HOST;
  const effectiveBetDbPort =
    process.env.BETS_DB_PORT ||
    process.env.BETTING_DB_PORT ||
    process.env.GAME_DB_PORT ||
    process.env.DB_PORT;
  console.log(
    `[Game API] Using DB ${effectiveBetDbName}@${effectiveBetDbHost}:${effectiveBetDbPort} for bets`,
  );

  await connectRedis();
  await verifyDbConnection();
  await verifyBetDbConnection();

  try {
    await resolveCharacterColumns();
    await resolveBetOddsColumns();
  } catch (error) {
    isCharacterSchemaReady = false;
    isOddsSchemaReady = false;
    console.warn(
      "[Game API] Character/odds tables not ready; continuing without enforcing schema.",
    );
  }

  const openRound = await getCurrentOpenRound(pool);
  // Round timer state is managed by Decision service (serverside)
  await migrateLegacyBetKeys();

  isDbReady = true;
}

async function start(options = {}) {
  const effectivePort = Number(
    options.port ?? process.env.PORT ?? DEFAULT_PORT,
  );
  await init();
  server = app.listen(effectivePort, options.host, () =>
    console.log(`Game service listening on port ${effectivePort}`),
  );
  return server;
}

async function close() {
  await Promise.allSettled([disconnectRedis(), closeDbConnection()]);
  await betPool.end().catch(() => null);
}

async function shutdown(signal) {
  console.log(`${signal} received. Shutting down...`);
  if (server) await new Promise((resolve) => server.close(resolve));
  await close();
  process.exit(0);
}

module.exports = { createApp, init, start, close };

if (require.main === module) {
  start().catch((err) => {
    console.error("Startup failed:", err.message);
    process.exit(1);
  });

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
