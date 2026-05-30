const { Pool } = require("pg");

const pool = new Pool({
  user: process.env.DEMO_DB_USER || process.env.DB_USER || "postgres",
  host: process.env.DEMO_DB_HOST || process.env.DB_HOST || "localhost",
  database: process.env.DEMO_DB_NAME || "DEMOMONEY",
  password:
    process.env.DEMO_DB_PASS ||
    process.env.DEMO_DB_PASSWORD ||
    process.env.DB_PASS ||
    process.env.DB_PASSWORD ||
    "Software",
  port: Number(process.env.DEMO_DB_PORT || process.env.DB_PORT || 5432),
});

const DEMO_MONEY_TABLE = "demo_money";
const DEFAULT_DEMO_BALANCE = 1000;

exports.updateDemoMoney = async (req, res) => {
  try {
    const amount = Number(req.body?.amount);
    if (!Number.isFinite(amount) || amount < 0) {
      return res
        .status(400)
        .json({ error: "Amount must be a non-negative number" });
    }

    const rounded = Number(amount.toFixed(2));
    const playerId = Number(req.user?.userId);
    if (!Number.isInteger(playerId) || playerId <= 0) {
      return res.status(401).json({ error: "Invalid authenticated player" });
    }

    const result = await pool.query(
      `INSERT INTO ${DEMO_MONEY_TABLE}
       (user_id, amount, created_at, updated_at)
       VALUES ($1, $2, NOW(), NOW())
       ON CONFLICT (user_id)
       DO UPDATE SET
         amount = EXCLUDED.amount,
         updated_at = NOW()
       RETURNING user_id, amount`,
      [playerId, rounded],
    );

    return res.json({
      message: "Demo balance updated",
      demo_balance: Number(result.rows[0].amount),
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};

exports.deductDemoMoney = async (req, res) => {
  try {
    const amount = Number(req.body?.amount);
    console.log("[demomoney] deduct request", {
      rawAmount: req.body?.amount,
      amount,
      hasAuth: Boolean(req.headers?.authorization),
    });
    if (!Number.isFinite(amount) || amount <= 0) {
      return res.status(400).json({ error: "Amount must be greater than zero" });
    }

    const rounded = Number(amount.toFixed(2));
    const playerId = Number(req.user?.userId);
    if (!Number.isInteger(playerId) || playerId <= 0) {
      return res.status(401).json({ error: "Invalid authenticated player" });
    }

    const currentRes = await pool.query(
      `SELECT amount
       FROM ${DEMO_MONEY_TABLE}
       WHERE user_id = $1
       LIMIT 1`,
      [playerId],
    );
    const currentAmount = Number(currentRes.rows[0]?.amount ?? DEFAULT_DEMO_BALANCE);
    if (currentAmount < rounded) {
      return res.status(400).json({ error: "Insufficient demo balance" });
    }
    const nextBalance = Number((currentAmount - rounded).toFixed(2));
    await pool.query(
      `INSERT INTO ${DEMO_MONEY_TABLE}
       (user_id, amount, created_at, updated_at)
       VALUES ($1, $2, NOW(), NOW())
       ON CONFLICT (user_id)
       DO UPDATE SET
         amount = EXCLUDED.amount,
         updated_at = NOW()`,
      [playerId, nextBalance],
    );

    return res.json({
      message: "Demo balance deducted",
      demo_balance: nextBalance,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};

exports.getWalletSnapshot = async (req, res) => {
  try {
    const playerId = Number(req.user?.userId);
    if (!Number.isInteger(playerId) || playerId <= 0) {
      return res.status(401).json({ error: "Invalid authenticated player" });
    }

    const result = await pool.query(
      `SELECT amount
       FROM ${DEMO_MONEY_TABLE}
       WHERE user_id = $1
       LIMIT 1`,
      [playerId],
    );
    const playerBalance = Number(result.rows[0]?.amount ?? DEFAULT_DEMO_BALANCE);
    return res.json({ playerBalance, houseBalance: 0 });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};

exports.allocateDemoMoney = async (req, res) => {
  try {
    const bettorId = Number(req.body?.bettorId);
    const amountRaw = req.body?.amount;
    const amount = Number(
      Number.isFinite(Number(amountRaw)) ? amountRaw : DEFAULT_DEMO_BALANCE,
    );

    if (!Number.isInteger(bettorId) || bettorId <= 0) {
      return res.status(400).json({ error: "bettorId must be a positive integer" });
    }
    if (!Number.isFinite(amount) || amount < 0) {
      return res.status(400).json({ error: "amount must be a non-negative number" });
    }

    const rounded = Number(amount.toFixed(2));
    const result = await pool.query(
      `INSERT INTO ${DEMO_MONEY_TABLE}
       (user_id, amount, created_at, updated_at)
       VALUES ($1, $2, NOW(), NOW())
       ON CONFLICT (user_id)
       DO UPDATE SET
         amount = EXCLUDED.amount,
         updated_at = NOW()
       RETURNING user_id, amount`,
      [bettorId, rounded],
    );

    return res.json({
      message: "Demo balance allocated",
      bettor_id: result.rows[0]?.user_id ?? bettorId,
      demo_balance: Number(result.rows[0]?.amount ?? rounded),
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};
