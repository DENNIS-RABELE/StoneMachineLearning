const express = require("express");
const cors = require("cors");
const { Pool } = require("pg");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});

const DEFAULT_PORT = 4110;
const NODE_ENV = process.env.NODE_ENV || "development";

const ROUND_TABLE = "\"Decision_gameround\"";
const CHARACTER_TABLE = "\"Decision_character\"";
const RESOLVED_OUTCOME_TABLE = "round_market_outcome";
const OUTCOME_TABLE = "outcomes";

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      return value;
    }
  }
  return undefined;
}

const pool = new Pool({
  user: firstDefined(
    process.env.DECISION_DB_USER,
    process.env.GAME_DB_USER,
    process.env.DB_USER,
    "postgres",
  ),
  host: firstDefined(
    process.env.DECISION_DB_HOST,
    process.env.GAME_DB_HOST,
    process.env.DB_HOST,
    "localhost",
  ),
  database: firstDefined(
    process.env.DECISION_DB_NAME,
    process.env.GAME_DB_NAME,
    process.env.DB_NAME,
    "DECISIONAPP",
  ),
  password: firstDefined(
    process.env.DECISION_DB_PASS,
    process.env.DECISION_DB_PASSWORD,
    process.env.GAME_DB_PASS,
    process.env.GAME_DB_PASSWORD,
    process.env.DB_PASS,
    process.env.DB_PASSWORD,
    "Software",
  ),
  port: Number(
    firstDefined(
      process.env.DECISION_DB_PORT,
      process.env.GAME_DB_PORT,
      process.env.DB_PORT,
      5432,
    ),
  ),
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

function displayCharacterName(rawName) {
  const name = String(rawName || "").trim();
  if (!name) return "Unknown";
  const [clean] = name.split("_", 1);
  return clean || name;
}

async function getResolvedOutcomes(roundLimit = 2) {
  const safeRoundLimit = Number.isInteger(roundLimit)
    ? Math.max(1, Math.min(roundLimit, 2))
    : 2;

  const { rows } = await pool.query(
    `SELECT gr.round_id,
            rmo.generated_at,
            rmo.market_id,
            rmo.phase_number,
            c.id AS character_id,
            c.name AS character_name,
            o.code AS outcome_code
     FROM ${RESOLVED_OUTCOME_TABLE} rmo
     JOIN ${ROUND_TABLE} gr
       ON gr.id = rmo.client_round_id
     JOIN ${CHARACTER_TABLE} c
       ON c.id = rmo.character_id
     LEFT JOIN ${OUTCOME_TABLE} o
       ON o.id = rmo.outcome_id
     WHERE rmo.client_round_id IN (
       SELECT rr.client_round_id
       FROM ${RESOLVED_OUTCOME_TABLE} rr
       INNER JOIN ${ROUND_TABLE} closed_gr
         ON closed_gr.id = rr.client_round_id
       WHERE closed_gr.status = 'CLOSED'
       GROUP BY rr.client_round_id, closed_gr.round_id
       ORDER BY closed_gr.round_id DESC
       LIMIT $1
     )
     ORDER BY gr.round_id DESC, c.name ASC, rmo.phase_number ASC`,
    [safeRoundLimit],
  );

  return rows.map((row) => ({
    roundId: Number(row.round_id),
    generatedAt: row.generated_at,
    marketId: Number(row.market_id),
    phaseNumber: Number(row.phase_number),
    characterId: Number(row.character_id),
    characterName: displayCharacterName(row.character_name),
    outcomeCode: row.outcome_code,
  }));
}

async function getLatestResolvedRoundRows() {
  const latestRound = await pool.query(
    `SELECT gr.id, gr.round_id
     FROM ${ROUND_TABLE} gr
     WHERE gr.status = 'CLOSED'
       AND EXISTS (
         SELECT 1
         FROM ${RESOLVED_OUTCOME_TABLE} rmo
         WHERE rmo.client_round_id = gr.id
       )
     ORDER BY gr.round_id DESC
     LIMIT 1`,
  );

  if (!latestRound.rows.length) {
    return { roundId: null, rows: [] };
  }

  const decisionRoundId = Number(latestRound.rows[0].id);
  const clientRoundNumber = Number(latestRound.rows[0].round_id);
  const rows = await pool.query(
    `SELECT
       rmo.client_round_id,
       rmo.character_id,
       rmo.phase_number,
       c.name AS character_name,
       c.stamina,
       c.control,
       c.power,
       o.code AS outcome_code
     FROM ${RESOLVED_OUTCOME_TABLE} rmo
     INNER JOIN ${CHARACTER_TABLE} c
       ON c.id = rmo.character_id
     LEFT JOIN ${OUTCOME_TABLE} o
       ON o.id = rmo.outcome_id
     WHERE rmo.client_round_id = $1
     ORDER BY c.name ASC, rmo.phase_number ASC`,
    [decisionRoundId],
  );

  return { roundId: clientRoundNumber, rows: rows.rows };
}

async function getPostGameStats() {
  const payload = await getLatestResolvedRoundRows();
  if (!payload.rows.length) {
    return { roundId: null, characters: [] };
  }

  const order = [];
  const byCharacter = new Map();

  for (const row of payload.rows) {
    const characterId = Number(row.character_id);
    if (!byCharacter.has(characterId)) {
      byCharacter.set(characterId, {
        characterId,
        name: displayCharacterName(row.character_name),
        stamina: Number(row.stamina || 0),
        control: Number(row.control || 0),
        power: Number(row.power || 0),
        phases: [null, null, null, null, null],
      });
      order.push(characterId);
    }

    const phaseIndex = Math.max(1, Number(row.phase_number || 0)) - 1;
    if (phaseIndex >= 0 && phaseIndex < 5) {
      byCharacter.get(characterId).phases[phaseIndex] =
        String(row.outcome_code || "").toUpperCase() || null;
    }
  }

  return {
    roundId: payload.roundId,
    characters: order.map((characterId) => byCharacter.get(characterId)),
  };
}

function createApp() {
  const app = express();

  app.disable("x-powered-by");
  app.use(express.json({ limit: "16kb" }));
  app.use(cors({ origin: parseCorsOrigins() }));

  app.get("/health", async (req, res) => {
    try {
      await pool.query("SELECT 1");
      res.json({
        ok: true,
        service: "StoneThrowOutcomes",
        timestamp: new Date().toISOString(),
      });
    } catch (error) {
      res.status(503).json({
        ok: false,
        service: "StoneThrowOutcomes",
        error: "database_unavailable",
        timestamp: new Date().toISOString(),
      });
    }
  });

  app.get("/api/outcomes", async (req, res) => {
    try {
      const roundLimit = Number.parseInt(
        String(req.query.roundLimit || "2"),
        10,
      );
      const payload = await getResolvedOutcomes(roundLimit);
      res.json(payload);
    } catch (error) {
      console.error("Could not load resolved outcomes:", error);
      res.status(500).json({ error: "Could not load outcomes" });
    }
  });

  app.get("/api/post-game-stats", async (req, res) => {
    try {
      const payload = await getPostGameStats();
      res.json(payload);
    } catch (error) {
      console.error("Could not load post-game stats:", error);
      res.status(500).json({ error: "Could not load post-game stats." });
    }
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
    console.log(`StoneThrowOutcomes service listening on port ${effectivePort}`);
  });
}

module.exports = { createApp, start };

if (require.main === module) {
  start();
}
