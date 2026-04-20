const { Pool } = require("pg");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
  quiet: true,
  override: false,
});

const pool = new Pool({
  user: process.env.AUTH_DB_USER || process.env.DB_USER || "postgres",
  host: process.env.AUTH_DB_HOST || process.env.DB_HOST || "localhost",
  database: process.env.AUTH_DB_NAME || process.env.DB_NAME || "USERS",
  password:
    process.env.AUTH_DB_PASS ||
    process.env.AUTH_DB_PASSWORD ||
    process.env.DB_PASS ||
    process.env.DB_PASSWORD ||
    "123456",
  port: process.env.AUTH_DB_PORT || process.env.DB_PORT || 5432,
});

module.exports = pool;
