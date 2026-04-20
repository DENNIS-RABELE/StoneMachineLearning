const path = require('path');
require('dotenv').config({ path: path.resolve(__dirname, '../.env'), quiet: true, override: false });
const { Pool } = require('pg');
(async () => {
  const pool = new Pool({
    user: process.env.DB_USER || process.env.GAME_DB_USER || 'postgres',
    host: process.env.DB_HOST || process.env.GAME_DB_HOST || 'localhost',
    database: process.env.GAME_DB_NAME || 'DECISIONAPP',
    password: process.env.DB_PASS || process.env.DB_PASSWORD || process.env.GAME_DB_PASS || process.env.GAME_DB_PASSWORD || '123456',
    port: Number(process.env.DB_PORT || process.env.GAME_DB_PORT || 5432),
  });
  try {
    console.log('env DB_USER', process.env.DB_USER);
    console.log('env DB_HOST', process.env.DB_HOST);
    console.log('env DB_NAME', process.env.DB_NAME);
    console.log('env GAME_DB_NAME', process.env.GAME_DB_NAME);
    console.log('search_path debug');
    const { rows: searchRows } = await pool.query('show search_path');
    console.log(searchRows);
    const { rows } = await pool.query("SELECT column_name FROM information_schema.columns WHERE table_schema = current_schema() AND table_name = $1 ORDER BY ordinal_position", ['Decision_character']);
    console.log('rows1', rows);
    const { rows: rows2 } = await pool.query("SELECT column_name FROM information_schema.columns WHERE table_name = $1 ORDER BY table_schema, ordinal_position", ['Decision_character']);
    console.log('rows2', rows2);
  } catch (err) {
    console.error('err', err);
  } finally {
    await pool.end();
  }
})();