const { Pool } = require("pg");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
  quiet: true,
  override: false,
});

// RAM-optimized: single-pass validation without intermediate arrays
function firstDefined(...values) {
  for (let i = 0; i < values.length; i += 1) {
    const value = values[i];
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      return value;
    }
  }
  return undefined;
}

// RAM-optimized PostgreSQL pool configuration
const pool = new Pool({
  user: firstDefined(
    process.env.BETTING_DB_USER,
    process.env.GAME_DB_USER,
    process.env.DB_USER,
    "postgres",
  ),
  host: firstDefined(
    process.env.BETTING_DB_HOST,
    process.env.GAME_DB_HOST,
    process.env.DB_HOST,
    "localhost",
  ),
  database: firstDefined(
    process.env.BETTING_DB_NAME,
    process.env.GAME_DB_NAME,
    process.env.DB_NAME,
    "betting",
  ),
  password: firstDefined(
    process.env.BETTING_DB_PASS,
    process.env.BETTING_DB_PASSWORD,
    process.env.GAME_DB_PASS,
    process.env.GAME_DB_PASSWORD,
    process.env.DB_PASS,
    process.env.DB_PASSWORD,
    "Software",
  ),
  port: Number(
    firstDefined(
      process.env.BETTING_DB_PORT,
      process.env.GAME_DB_PORT,
      process.env.DB_PORT,
      5432,
    ),
  ),
  // Memory & connection optimizations
  max: 3,
  idleTimeoutMillis: 30000,
  maxUses: 5000,
  connectionTimeoutMillis: 5000,
  allowExitOnIdle: false,
});

// Prevent unhandled pool errors from leaking memory on crash loops
pool.on("error", (err) => {
  console.error("Unexpected PostgreSQL pool error:", err.message);
});

const RESULTS_TABLE = Object.freeze("decision_app_bet_decision");

async function saveRoundResult(result) {
  await pool.query(`INSERT INTO ${RESULTS_TABLE} (round_result) VALUES ($1)`, [
    result,
  ]);
}

async function getRecentRoundResults(limit = 20) {
  const safeLimit = Number.isInteger(limit) ? limit : 20;
  const { rows } = await pool.query(
    `SELECT id, round_result AS result_zone, created_at FROM ${RESULTS_TABLE} ORDER BY id DESC LIMIT $1`,
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
