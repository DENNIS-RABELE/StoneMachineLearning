const { Pool } = require("pg");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
  quiet: true,
  override: false,
});

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
    process.env.DB_USER,
    process.env.BETTING_DB_USER,
    process.env.GAME_DB_USER,
    "postgres",
  ),
  host: firstDefined(
    process.env.DB_HOST,
    process.env.BETTING_DB_HOST,
    process.env.GAME_DB_HOST,
    "localhost",
  ),
  database: firstDefined(
    process.env.DB_NAME,
    process.env.BETTING_DB_NAME,
    process.env.GAME_DB_NAME,
    "betting",
  ),
  password: firstDefined(
    process.env.DB_PASS,
    process.env.DB_PASSWORD,
    process.env.BETTING_DB_PASS,
    process.env.BETTING_DB_PASSWORD,
    process.env.GAME_DB_PASS,
    process.env.GAME_DB_PASSWORD,
    "123456",
  ),
  port: Number(
    firstDefined(
      process.env.DB_PORT,
      process.env.BETTING_DB_PORT,
      process.env.GAME_DB_PORT,
      5432,
    ),
  ),
  // RAM & Connection Optimizations
  max: parseInt(process.env.DB_POOL_MAX || "3", 10),
  idleTimeoutMillis: 30000,
  maxUses: 5000,
  connectionTimeoutMillis: 5000,
  allowExitOnIdle: false,
});

// Prevent unhandled pool errors from leaking memory on crash loops
pool.on("error", (err) => {
  console.error("Unexpected PostgreSQL pool error:", err.message);
});

const RESULTS_TABLE = "round_market_outcome";
const ROUND_TABLE = '"Decision_gameround"';
const CHARACTER_TABLE = '"Decision_character"';
const OUTCOME_TABLE = "outcomes";

async function saveRoundResult(result) {
  throw new Error(
    `${RESULTS_TABLE} is a resolved-outcomes table. Results are written by the decision service, not the Game microservice.`,
  );
}

async function getRecentRoundResults(limit = 20) {
  const safeLimit = Number.isInteger(limit) ? limit : 20;
  const { rows } = await pool.query(
    `SELECT
       rmo.id,
       gr.round_id,
       rmo.phase_number,
       c.name AS character_name,
       o.code AS result_zone,
       rmo.generated_at AS created_at
     FROM ${RESULTS_TABLE} rmo
     INNER JOIN ${ROUND_TABLE} gr
       ON gr.id = rmo.client_round_id
     INNER JOIN ${CHARACTER_TABLE} c
       ON c.id = rmo.character_id
     LEFT JOIN ${OUTCOME_TABLE} o
       ON o.id = rmo.outcome_id
     WHERE gr.status = 'CLOSED'
       AND o.code IS NOT NULL
     ORDER BY gr.round_id DESC, rmo.generated_at DESC, rmo.id DESC
     LIMIT $1`,
    [safeLimit],
  );
  return rows;
}

async function verifyDbConnection() {
  await pool.query("SELECT 1");
}

async function closeDbConnection() {
  await pool.end();
}

module.exports = {
  saveRoundResult,
  getRecentRoundResults,
  verifyDbConnection,
  closeDbConnection,
  pool,
};
