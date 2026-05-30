const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, 'clientside/microservices/Odds/.env'), quiet: true, override: false });
const { Pool } = require('pg');
function quoteIdentifier(name) {
  return '"' + String(name).replace(/"/g, '""') + '"';
}
function pickCharacterColumn(columnMap, label, exactCandidates, fuzzyTokens) {
  for (const candidate of exactCandidates) {
    if (columnMap.has(candidate)) return columnMap.get(candidate);
  }
  for (const [lowerName, actualName] of columnMap.entries()) {
    if (fuzzyTokens.some((token) => lowerName.includes(token))) return actualName;
  }
  throw new Error(`Missing ${label} column on Decision_character. Available columns: ${Array.from(columnMap.values()).join(', ')}`);
}
async function resolveCharacterColumns(pool) {
  const { rows } = await pool.query(
    `SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = $1 ORDER BY ordinal_position`,
    ['Decision_character'],
  );
  const columnMap = new Map(rows.map((row) => [String(row.column_name).toLowerCase(), row.column_name]));
  return {
    stamina: pickCharacterColumn(columnMap, 'stamina', ['stamina'], ['stamina', 'stam']),
    control: pickCharacterColumn(columnMap, 'control', ['control'], ['control', 'ctrl']),
    power: pickCharacterColumn(columnMap, 'power', ['power'], ['power', 'powe']),
  };
}
(async () => {
  const pool = new Pool({
    user: process.env.DB_USER || process.env.GAME_DB_USER || 'postgres',
    host: process.env.DB_HOST || process.env.GAME_DB_HOST || 'localhost',
    database: process.env.DB_NAME || process.env.GAME_DB_NAME || 'DECISIONAPP',
    password:
      process.env.DB_PASS ||
      process.env.DB_PASSWORD ||
      process.env.GAME_DB_PASS ||
      process.env.GAME_DB_PASSWORD ||
      'Software',
    port: Number(process.env.DB_PORT || process.env.GAME_DB_PORT || 5432),
    max: 3,
    idleTimeoutMillis: 30000,
    maxUses: 5000,
    connectionTimeoutMillis: 5000,
  });
  try {
    const cols = await resolveCharacterColumns(pool);
    console.log('columns:', cols);
    const { rows } = await pool.query(
      `SELECT c.id, c.name, c.${quoteIdentifier(cols.stamina)} AS stamina, c.${quoteIdentifier(cols.control)} AS control, c.${quoteIdentifier(cols.power)} AS power FROM "Decision_character" c ORDER BY c.id DESC LIMIT $1`,
      [5],
    );
    console.log('rows:', rows);
  } catch (err) {
    console.error('ERROR', err && err.stack ? err.stack : err);
  } finally {
    await pool.end();
  }
})();
