const express = require("express");
const cors = require("cors");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});
const { Pool } = require("pg");

const DEFAULT_PORT = 4104;
const NODE_ENV = process.env.NODE_ENV || "development";
const CHARACTER_TABLE =
  process.env.STATS_CHARACTER_TABLE ||
  process.env.CHARACTER_TABLE ||
  "Decision_character";
const ROUND_TABLE =
  process.env.STATS_ROUND_TABLE ||
  process.env.ROUND_TABLE ||
  "Decision_gameround";
const DECISION_ROUND_TABLE = process.env.STATS_DECISION_ROUND_TABLE || "rounds";
const RESOLVED_OUTCOME_TABLE =
  process.env.STATS_RESOLVED_OUTCOME_TABLE || "round_market_outcome";
const OUTCOME_TABLE = process.env.STATS_OUTCOME_TABLE || "outcomes";

const pool = new Pool({
  user: process.env.DB_USER || "postgres",
  host: process.env.DB_HOST || "localhost",
  database: process.env.DB_NAME || "DECISIONAPP",
  password:
    process.env.DB_PASS || process.env.DB_PASSWORD || process.env.DB_PASS || "123456",
  port: Number(process.env.DB_PORT || 5432),
});

let characterColumns;
let roundColumns;

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

function displayCharacterName(rawName) {
  const name = String(rawName || "").trim();
  if (!name) return "Unknown";
  const [clean] = name.split("_", 1);
  return clean || name;
}

function quoteIdentifier(name) {
  return `"${String(name).replace(/"/g, '""')}"`;
}

function quoteTableIdentifier(name) {
  const raw = String(name || "").trim();
  if (!raw) return quoteIdentifier("Decision_character");
  const parts = raw.split(".");
  return parts.map(quoteIdentifier).join(".");
}

function pickCharacterColumn(columnMap, label, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) {
      return columnMap.get(candidate);
    }
  }

  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token))) {
      return actualName;
    }
  }

  const available = Array.from(columnMap.values()).join(", ");
  throw new Error(
    `Missing ${label} column on ${CHARACTER_TABLE}. Available columns: ${available}`,
  );
}

function pickOptionalCharacterColumn(columnMap, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) {
      return columnMap.get(candidate);
    }
  }

  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token))) {
      return actualName;
    }
  }

  return null;
}

async function resolveCharacterColumns() {
  if (characterColumns) {
    return characterColumns;
  }

  const { rows } = await pool.query(
    `SELECT column_name
     FROM information_schema.columns
     WHERE table_schema = current_schema()
       AND table_name = $1`,
    [CHARACTER_TABLE],
  );

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
    createdAt: pickOptionalCharacterColumn(
      columnMap,
      ["created_at", "createdat", "created"],
      ["created", "timestamp", "date"],
    ),
  };

  return characterColumns;
}

function pickRequiredColumn(columnMap, label, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) {
      return columnMap.get(candidate);
    }
  }

  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token))) {
      return actualName;
    }
  }

  const available = Array.from(columnMap.values()).join(", ");
  throw new Error(`Missing ${label} column on ${ROUND_TABLE}. Available columns: ${available}`);
}

async function resolveRoundColumns() {
  if (roundColumns) {
    return roundColumns;
  }

  const { rows } = await pool.query(
    `SELECT column_name
     FROM information_schema.columns
     WHERE table_schema = current_schema()
       AND table_name = $1`,
    [ROUND_TABLE],
  );

  const columnMap = new Map(
    rows.map((row) => [String(row.column_name).toLowerCase(), row.column_name]),
  );

  roundColumns = {
    id: pickRequiredColumn(columnMap, "id", ["id"], ["id"]),
    roundId: pickRequiredColumn(
      columnMap,
      "round_id",
      ["round_id", "roundid"],
      ["round_id", "roundid", "round"],
    ),
    status: pickOptionalCharacterColumn(
      columnMap,
      ["status"],
      ["status"],
    ),
    startTime: pickOptionalCharacterColumn(
      columnMap,
      ["start_time", "starttime"],
      ["start", "start_time"],
    ),
    endTime: pickOptionalCharacterColumn(
      columnMap,
      ["end_time", "endtime"],
      ["end", "end_time"],
    ),
    createdAt: pickOptionalCharacterColumn(
      columnMap,
      ["created_at", "createdat", "created"],
      ["created", "timestamp", "date"],
    ),
  };

  return roundColumns;
}

async function getCharacterHistory(limit = 200) {
  const columns = await resolveCharacterColumns();
  const safeLimit = Number.isInteger(limit) ? Math.max(1, Math.min(limit, 500)) : 200;
  const createdAtColumn = columns.createdAt
    ? `c.${quoteIdentifier(columns.createdAt)}`
    : null;
  const orderBy = createdAtColumn ? createdAtColumn : "c.id";
  const selectCreatedAt = createdAtColumn
    ? `${createdAtColumn} AS created_at`
    : "NULL AS created_at";

  const query = `
    SELECT c.id, c.name,
      c.${quoteIdentifier(columns.stamina)} AS stamina,
      c.${quoteIdentifier(columns.control)} AS control,
      c.${quoteIdentifier(columns.power)} AS power,
      ${selectCreatedAt}
    FROM ${quoteTableIdentifier(CHARACTER_TABLE)} c
    ORDER BY ${orderBy} DESC
    LIMIT $1
  `;

  const { rows } = await pool.query(query, [safeLimit]);
  return rows.map((row) => ({
    id: Number(row.id),
    name: row.name,
    stamina: toNumber(row.stamina),
    control: toNumber(row.control),
    power: toNumber(row.power),
    created_at: row.created_at,
  }));
}

async function getRoundHistory(limit = 50) {
  const columns = await resolveRoundColumns();
  const safeLimit = Number.isInteger(limit) ? Math.max(1, Math.min(limit, 50)) : 50;
  const createdAtColumn = columns.createdAt
    ? `r.${quoteIdentifier(columns.createdAt)}`
    : null;
  const orderBy = createdAtColumn ? createdAtColumn : `r.${quoteIdentifier(columns.id)}`;
  const selectCreatedAt = createdAtColumn
    ? `${createdAtColumn} AS created_at`
    : "NULL AS created_at";
  const selectStatus = columns.status
    ? `r.${quoteIdentifier(columns.status)} AS status`
    : "NULL AS status";
  const selectStart = columns.startTime
    ? `r.${quoteIdentifier(columns.startTime)} AS start_time`
    : "NULL AS start_time";
  const selectEnd = columns.endTime
    ? `r.${quoteIdentifier(columns.endTime)} AS end_time`
    : "NULL AS end_time";

  const query = `
    SELECT r.${quoteIdentifier(columns.id)} AS id,
      r.${quoteIdentifier(columns.roundId)} AS round_id,
      ${selectStatus},
      ${selectStart},
      ${selectEnd},
      ${selectCreatedAt}
    FROM ${quoteTableIdentifier(ROUND_TABLE)} r
    ORDER BY ${orderBy} DESC
    LIMIT $1
  `;

  const { rows } = await pool.query(query, [safeLimit]);
  return rows.map((row) => ({
    id: Number(row.id),
    round_id: row.round_id !== null && row.round_id !== undefined ? Number(row.round_id) : null,
    status: row.status,
    start_time: row.start_time,
    end_time: row.end_time,
    created_at: row.created_at,
  }));
}

async function getCharacterPerformanceHistory(limit = 50) {
  const safeLimit = Number.isInteger(limit) ? Math.max(1, Math.min(limit, 200)) : 50;
  const { rows } = await pool.query(
    `SELECT
       rmo.client_round_id,
       rmo.character_id,
       c.name AS character_name,
       rmo.phase_number,
       o.code AS outcome_code,
       dr.status AS decision_round_status
     FROM ${quoteTableIdentifier(RESOLVED_OUTCOME_TABLE)} rmo
     INNER JOIN ${quoteTableIdentifier(DECISION_ROUND_TABLE)} dr
       ON dr.id = rmo.decision_round_id
     INNER JOIN ${quoteTableIdentifier(CHARACTER_TABLE)} c
       ON c.id = rmo.character_id
     LEFT JOIN ${quoteTableIdentifier(OUTCOME_TABLE)} o
       ON o.id = rmo.outcome_id
     WHERE dr.status = 'RESOLVED'
     ORDER BY rmo.client_round_id ASC, rmo.character_id ASC, rmo.phase_number ASC`,
  );

  const byCharacter = new Map();
  for (const row of rows) {
    const roundNumber = Number(row.client_round_id);
    const characterId = Number(row.character_id);
    const phaseNumber = Number(row.phase_number);
    const outcomeCode = String(row.outcome_code || "").toUpperCase();
    const characterName = displayCharacterName(row.character_name) || `Character #${characterId}`;

    if (!Number.isInteger(roundNumber) || roundNumber <= 0) continue;
    if (!Number.isInteger(characterId) || characterId <= 0) continue;

    if (!byCharacter.has(characterName)) {
      byCharacter.set(characterName, {
        characterId,
        name: characterName,
        rounds: [],
      });
    }

    const characterEntry = byCharacter.get(characterName);
    let roundEntry = characterEntry.rounds.find(
      (entry) => Number(entry.roundNumber) === roundNumber,
    );

    if (!roundEntry) {
      roundEntry = {
        roundNumber,
        roundStatus: String(row.decision_round_status || ""),
        score: 0,
        cumulativeScore: 0,
        betCount: 0,
        wins: 0,
        losses: 0,
        pending: 0,
        optionCodes: [],
        placedAt: null,
        drownPhase: null,
      };
      characterEntry.rounds.push(roundEntry);
    }

    roundEntry.betCount += 1;
    if (outcomeCode === "DROWN" && Number.isInteger(phaseNumber) && phaseNumber > 0) {
      if (roundEntry.drownPhase === null || phaseNumber < Number(roundEntry.drownPhase)) {
        roundEntry.drownPhase = phaseNumber;
      }
    }
  }

  const summary = { wins: 0, losses: 0, pending: 0, totalRounds: 0 };
  const characters = Array.from(byCharacter.values())
    .map((characterEntry) => {
      let cumulativeScore = 0;
      characterEntry.rounds.sort((a, b) => Number(a.roundNumber || 0) - Number(b.roundNumber || 0));
      characterEntry.rounds = characterEntry.rounds.slice(-safeLimit).map((roundEntry) => {
        const drownPhase = Number(roundEntry.drownPhase);
        if (Number.isInteger(drownPhase) && drownPhase >= 1 && drownPhase <= 3) {
          roundEntry.score = -1;
          roundEntry.losses = 1;
        } else if (Number.isInteger(drownPhase) && drownPhase >= 4 && drownPhase <= 5) {
          roundEntry.score = 1;
          roundEntry.wins = 1;
        } else {
          roundEntry.score = 0;
          roundEntry.pending = 1;
        }
        cumulativeScore += Number(roundEntry.score || 0);
        const normalized = {
          ...roundEntry,
          cumulativeScore,
        };
        summary.wins += Number(normalized.wins || 0);
        summary.losses += Number(normalized.losses || 0);
        summary.pending += Number(normalized.pending || 0);
        summary.totalRounds += 1;
        return normalized;
      });
      return characterEntry;
    })
    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")));

  return {
    generatedAt: new Date().toISOString(),
    characters,
    summary,
  };
}

async function getCharacterPerformanceDebug(characterName, limit = 50) {
  const payload = await getCharacterPerformanceHistory(limit);
  const normalizedFilter = String(characterName || "").trim().toLowerCase();
  const characters = Array.isArray(payload.characters) ? payload.characters : [];
  const simplified = characters
    .filter((character) => {
      if (!normalizedFilter) return true;
      return String(character?.name || "").trim().toLowerCase() === normalizedFilter;
    })
    .map((character) => ({
      character: String(character?.name || "Unknown"),
      bars: (Array.isArray(character?.rounds) ? character.rounds : []).map((round) => ({
        roundNumber: Number(round?.roundNumber || 0),
        drownPhase:
          round?.drownPhase === null || round?.drownPhase === undefined
            ? null
            : Number(round.drownPhase),
        barScore: Number(round?.score || 0),
      })),
    }));

  if (normalizedFilter) {
    return simplified[0]?.bars || [];
  }
  return simplified;
}

function createApp() {
  const app = express();

  app.disable("x-powered-by");
  app.use(express.json({ limit: "16kb" }));
  app.use(cors({ origin: parseCorsOrigins() }));

  app.get("/health", (req, res) => {
    res.json({
      service: "Statistics",
      status: "ok",
      timestamp: new Date().toISOString(),
    });
  });

  app.get("/api/stats/character-history", async (req, res) => {
    const limit = Number.parseInt(String(req.query.limit || "200"), 10);
    try {
      const history = await getCharacterHistory(limit);
      res.json(history);
    } catch (error) {
      console.error("Could not load character history:", error);
      res.status(500).json({ error: "Could not load character history" });
    }
  });

  app.get("/api/stats/rounds", async (req, res) => {
    const limit = Number.parseInt(String(req.query.limit || "50"), 10);
    try {
      const rounds = await getRoundHistory(limit);
      res.json(rounds);
    } catch (error) {
      console.error("Could not load round history:", error);
      res.status(500).json({ error: "Could not load round history" });
    }
  });

  app.get("/api/stats/performance/characters", async (req, res) => {
    const limit = Number.parseInt(String(req.query.limit || "50"), 10);
    try {
      const payload = await getCharacterPerformanceHistory(limit);
      res.json(payload);
    } catch (error) {
      console.error("Could not load character performance history:", error);
      res.status(500).json({
        error: "Could not load character performance history",
      });
    }
  });

  app.get("/api/stats/performance/debug", async (req, res) => {
    const limit = Number.parseInt(String(req.query.limit || "50"), 10);
    try {
      const payload = await getCharacterPerformanceDebug(
        req.query.character,
        limit,
      );
      res.json(payload);
    } catch (error) {
      console.error("Could not load character performance debug payload:", error);
      res
        .status(500)
        .json({ error: "Could not load character performance debug payload" });
    }
  });

  // Compatibility endpoint for stats readiness.
  app.get("/api/stats", (req, res) => {
    res.json({
      message: "Statistics service is ready.",
      endpoints: [
        "/api/stats/character-history",
        "/api/stats/rounds",
        "/api/stats/performance/characters",
        "/api/stats/performance/debug",
      ],
    });
  });

  app.use((req, res) => {
    res.status(404).json({ error: "Not found" });
  });

  app.use((err, req, res, next) => {
    console.error("Unhandled request error:", err);
    res.status(500).json({ error: "Internal server error" });
  });

  return app;
}

function start(options = {}) {
  const effectivePort = Number(
    options.port ?? process.env.PORT ?? DEFAULT_PORT,
  );
  const app = createApp();
  return app.listen(effectivePort, options.host, () => {
    console.log(`Statistics service listening on port ${effectivePort}`);
  });
}

module.exports = { createApp, start };

if (require.main === module) {
  start();
}
