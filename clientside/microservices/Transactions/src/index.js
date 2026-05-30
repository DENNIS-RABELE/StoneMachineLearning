const express = require("express");
const cors = require("cors");
const { Pool } = require("pg");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});

const authenticateToken = require("./middleware/authenticateToken");

const DEFAULT_PORT = 4109;
const NODE_ENV = process.env.NODE_ENV || "development";

const BETTING_SLIP_TABLE = "client_slip";
const BETTING_SLIP_ITEM_TABLE = "client_slip_item";
const BETTING_SLIP_GAME_ROUND_COLUMN = "game_round";
const BETTING_SLIP_ITEM_CHARACTER_COLUMN = "character";
const DEMO_MONEY_TABLE = "demo_money";
const DECISION_ROUND_TABLE = "\"Decision_gameround\"";
const DECISION_CHARACTER_TABLE = "\"Decision_character\"";
const DECISION_RESOLVED_OUTCOME_TABLE = "round_market_outcome";
const DECISION_OUTCOME_TABLE = "outcomes";
const DEFAULT_PLAYER_BALANCE = Number(process.env.DEFAULT_PLAYER_WALLET_BALANCE || 1000);

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      return value;
    }
  }
  return undefined;
}

function normalizeStatus(value) {
  return String(value || "").trim().toUpperCase();
}

const bettingPool = new Pool({
  user: firstDefined(
    process.env.BETS_DB_USER,
    process.env.BETTING_DB_USER,
    process.env.GAME_DB_USER,
    process.env.DB_USER,
    "postgres",
  ),
  host: firstDefined(
    process.env.BETS_DB_HOST,
    process.env.BETTING_DB_HOST,
    process.env.GAME_DB_HOST,
    process.env.DB_HOST,
    "localhost",
  ),
  database: firstDefined(
    process.env.BETS_DB_NAME,
    process.env.BETTING_DB_NAME,
    process.env.GAME_DB_NAME,
    process.env.DB_NAME,
    "CLIENTBETDATA",
  ),
  password: firstDefined(
    process.env.BETS_DB_PASS,
    process.env.BETS_DB_PASSWORD,
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
      process.env.BETS_DB_PORT,
      process.env.BETTING_DB_PORT,
      process.env.GAME_DB_PORT,
      process.env.DB_PORT,
      5432,
    ),
  ),
});

console.log(
  `[Transactions] Using betting DB ${firstDefined(
    process.env.BETS_DB_NAME,
    process.env.BETTING_DB_NAME,
    process.env.GAME_DB_NAME,
    process.env.DB_NAME,
    "CLIENTBETDATA",
  )}@${firstDefined(
    process.env.BETS_DB_HOST,
    process.env.BETTING_DB_HOST,
    process.env.GAME_DB_HOST,
    process.env.DB_HOST,
    "localhost",
  )}:${Number(
    firstDefined(
      process.env.BETS_DB_PORT,
      process.env.BETTING_DB_PORT,
      process.env.GAME_DB_PORT,
      process.env.DB_PORT,
      5432,
    ),
  )}`,
);

const decisionPool = new Pool({
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

const demoPool = new Pool({
  user: firstDefined(
    process.env.DEMO_DB_USER,
    process.env.DB_USER,
    "postgres",
  ),
  host: firstDefined(
    process.env.DEMO_DB_HOST,
    process.env.DB_HOST,
    "localhost",
  ),
  database: firstDefined(
    process.env.DEMO_DB_NAME,
    "DEMOMONEY",
  ),
  password: firstDefined(
    process.env.DEMO_DB_PASS,
    process.env.DEMO_DB_PASSWORD,
    process.env.DB_PASS,
    process.env.DB_PASSWORD,
    "Software",
  ),
  port: Number(firstDefined(process.env.DEMO_DB_PORT, process.env.DB_PORT, 5432)),
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

function deriveSlipOutcomeResultsFromPhaseLookup(item, phaseLookup) {
  const optionCode = String(item?.optionCode || "").trim().toUpperCase();
  const safeLookup = phaseLookup instanceof Map ? phaseLookup : new Map();

  function resolveOutcomeForSelectedPhase(selectedPhaseNumber) {
    const directOutcomeCode = String(safeLookup.get(selectedPhaseNumber) || "").toUpperCase();
    if (directOutcomeCode) {
      return {
        resolvedOutcomeCode: directOutcomeCode,
        resolvedPhaseNumber: selectedPhaseNumber,
      };
    }

    let terminalDrownPhase = null;
    for (const [phaseNumberRaw, outcomeCodeRaw] of safeLookup.entries()) {
      const phaseNumber = Number(phaseNumberRaw);
      const outcomeCode = String(outcomeCodeRaw || "").toUpperCase();
      if (
        Number.isFinite(phaseNumber) &&
        phaseNumber <= selectedPhaseNumber &&
        outcomeCode === "DROWN" &&
        (terminalDrownPhase === null || phaseNumber < terminalDrownPhase)
      ) {
        terminalDrownPhase = phaseNumber;
      }
    }

    if (terminalDrownPhase !== null) {
      return {
        resolvedOutcomeCode: "DROWN",
        resolvedPhaseNumber: terminalDrownPhase,
      };
    }

    return {
      resolvedOutcomeCode: null,
      resolvedPhaseNumber: null,
    };
  }

  function buildEntry(selectedOutcomeCode, phaseNumber, label) {
    const resolved = resolveOutcomeForSelectedPhase(phaseNumber);
    const isWon =
      resolved.resolvedOutcomeCode === selectedOutcomeCode &&
      Number(resolved.resolvedPhaseNumber) === Number(phaseNumber);

    return {
      marketId: null,
      phaseNumber: Number(phaseNumber),
      label,
      selectedOutcomeCode,
      resolvedOutcomeCode: resolved.resolvedOutcomeCode,
      resolvedPhaseNumber: resolved.resolvedPhaseNumber,
      status: resolved.resolvedOutcomeCode ? (isWon ? "won" : "lost") : "pending",
    };
  }

  const singleMatch = optionCode.match(/^([FD])([1-5])$/);
  if (singleMatch) {
    const phaseNumber = Number.parseInt(singleMatch[2], 10);
    const selectedOutcomeCode = singleMatch[1] === "F" ? "FLOAT" : "DROWN";
    return [buildEntry(selectedOutcomeCode, phaseNumber, `${singleMatch[1]}${phaseNumber}`)];
  }

  const doubleMatch = optionCode.match(/^F([1-5])ANDD([1-5])$/);
  if (doubleMatch) {
    const floatPhase = Number.parseInt(doubleMatch[1], 10);
    const drownPhase = Number.parseInt(doubleMatch[2], 10);
    return [
      buildEntry("FLOAT", floatPhase, `F${floatPhase}`),
      buildEntry("DROWN", drownPhase, `D${drownPhase}`),
    ];
  }

  return [];
}

function scoreOutcomeResults(outcomeResults) {
  const entries = Array.isArray(outcomeResults) ? outcomeResults : [];
  if (!entries.length) {
    return 0;
  }
  if (entries.some((entry) => String(entry?.status || "") === "lost")) {
    return -1;
  }
  if (entries.every((entry) => String(entry?.status || "") === "won")) {
    return 1;
  }
  return 0;
}

async function getWalletSnapshot(playerId) {
  const safePlayerId = Number(playerId);
  if (!Number.isInteger(safePlayerId) || safePlayerId <= 0) {
    return null;
  }

  const result = await demoPool.query(
    `SELECT amount
     FROM ${DEMO_MONEY_TABLE}
     WHERE user_id = $1
     LIMIT 1`,
    [safePlayerId],
  );

  return {
    playerBalance: Number(result.rows[0]?.amount ?? DEFAULT_PLAYER_BALANCE),
    houseBalance: 0,
  };
}

async function getRoundMap(roundIds) {
  if (!roundIds.length) {
    return new Map();
  }

  const { rows } = await decisionPool.query(
    `SELECT id, round_id, status
     FROM ${DECISION_ROUND_TABLE}
     WHERE round_id = ANY($1::int[])`,
    [roundIds],
  );

  return new Map(
    rows.map((row) => [
      Number(row.round_id),
      {
        id: Number(row.id),
        roundNumber: Number(row.round_id),
        status: String(row.status || ""),
      },
    ]),
  );
}

async function getCharacterNameMap(characterIds) {
  if (!characterIds.length) {
    return new Map();
  }

  const { rows } = await decisionPool.query(
    `SELECT id, name
     FROM ${DECISION_CHARACTER_TABLE}
     WHERE id = ANY($1::int[])`,
    [characterIds],
  );

  return new Map(
    rows.map((row) => [Number(row.id), displayCharacterName(row.name)]),
  );
}

async function buildResolvedOutcomeLookup(roundIds, characterIds) {
  if (!roundIds.length || !characterIds.length) {
    return new Map();
  }

  const { rows } = await decisionPool.query(
    `SELECT
       rmo.client_round_id,
       rmo.character_id,
       rmo.phase_number,
       o.code AS outcome_code
     FROM ${DECISION_RESOLVED_OUTCOME_TABLE} rmo
     LEFT JOIN ${DECISION_OUTCOME_TABLE} o
       ON o.id = rmo.outcome_id
     WHERE rmo.client_round_id = ANY($1::int[])
       AND rmo.character_id = ANY($2::int[])
     ORDER BY rmo.client_round_id DESC, rmo.character_id ASC, rmo.phase_number ASC`,
    [roundIds, characterIds],
  );

  const lookup = new Map();
  for (const row of rows) {
    const key = `${Number(row.client_round_id)}:${Number(row.character_id)}`;
    if (!lookup.has(key)) {
      lookup.set(key, new Map());
    }
    const phaseNumber = Number(row.phase_number);
    const outcomeCode = String(row.outcome_code || "").toUpperCase();
    if (Number.isFinite(phaseNumber) && outcomeCode && !lookup.get(key).has(phaseNumber)) {
      lookup.get(key).set(phaseNumber, outcomeCode);
    }
  }
  return lookup;
}

async function getSlipItemsBySlipIds(slipIds) {
  if (!Array.isArray(slipIds) || !slipIds.length) {
    return new Map();
  }

  const { rows } = await bettingPool.query(
    `SELECT
       si.id,
       si.slip_id,
       si.${BETTING_SLIP_ITEM_CHARACTER_COLUMN} AS character_id,
       si.bet_type,
       si.option_code,
       si.stake,
       si.odds,
       si.possible_win,
       si.placed_at,
       si.phase_start,
       si.phase_end,
       s.${BETTING_SLIP_GAME_ROUND_COLUMN} AS game_round_id
     FROM ${BETTING_SLIP_ITEM_TABLE} si
     INNER JOIN ${BETTING_SLIP_TABLE} s
       ON s.id = si.slip_id
     WHERE si.slip_id = ANY($1::bigint[])
     ORDER BY si.placed_at DESC, si.id DESC`,
    [slipIds],
  );

  const grouped = new Map();
  const roundIds = new Set();
  const characterIds = new Set();

  for (const row of rows) {
    const slipId = Number(row.slip_id);
    const item = {
      id: Number(row.id),
      characterId: Number(row.character_id),
      characterName: "Unknown",
      betType: String(row.bet_type || ""),
      optionCode: String(row.option_code || ""),
      stake: Number(row.stake || 0),
      odds: Number(row.odds || 0),
      possibleWin: Number(row.possible_win || 0),
      phaseStart: Number(row.phase_start || 0),
      phaseEnd:
        row.phase_end === null || row.phase_end === undefined
          ? null
          : Number(row.phase_end),
      gameRoundId: Number(row.game_round_id),
      placedAt: row.placed_at,
      outcomeResults: [],
    };

    if (!grouped.has(slipId)) {
      grouped.set(slipId, []);
    }
    grouped.get(slipId).push(item);

    if (Number.isInteger(item.gameRoundId) && item.gameRoundId > 0) {
      roundIds.add(item.gameRoundId);
    }
    if (Number.isInteger(item.characterId) && item.characterId > 0) {
      characterIds.add(item.characterId);
    }
  }

  const [characterNameMap, resolvedLookup] = await Promise.all([
    getCharacterNameMap(Array.from(characterIds)),
    buildResolvedOutcomeLookup(Array.from(roundIds), Array.from(characterIds)),
  ]);

  grouped.forEach((items) => {
    items.forEach((item) => {
      item.characterName = characterNameMap.get(item.characterId) || "Unknown";
      const phaseLookup =
        resolvedLookup.get(`${Number(item.gameRoundId)}:${Number(item.characterId)}`) || new Map();
      item.outcomeResults = deriveSlipOutcomeResultsFromPhaseLookup(item, phaseLookup);
    });
  });

  return grouped;
}

async function getSlipActivityForPlayer(playerId) {
  const safePlayerId = Number(playerId);
  if (!Number.isInteger(safePlayerId) || safePlayerId <= 0) {
    return { currentSlip: null, pastSlips: [] };
  }

  const { rows } = await bettingPool.query(
    `SELECT
       id,
       player_id,
       status,
     total_stake,
     total_possible_win,
     placed_at,
     updated_at,
     ${BETTING_SLIP_GAME_ROUND_COLUMN} AS game_round_id
     FROM ${BETTING_SLIP_TABLE}
     WHERE player_id = $1
     ORDER BY placed_at DESC, id DESC`,
    [safePlayerId],
  );

  if (!rows.length) {
    return { currentSlip: null, pastSlips: [] };
  }

  let roundMap = new Map();
  let itemsBySlipId = new Map();
  try {
    const roundIds = Array.from(
      new Set(
        rows
          .map((row) => Number(row.game_round_id))
          .filter((value) => Number.isInteger(value) && value > 0),
      ),
    );
    roundMap = await getRoundMap(roundIds);
  } catch (error) {
    console.warn("Transactions round enrichment failed:", error?.message || error);
  }
  try {
    const slipIds = rows.map((row) => Number(row.id));
    itemsBySlipId = await getSlipItemsBySlipIds(slipIds);
  } catch (error) {
    console.warn("Transactions slip-item enrichment failed:", error?.message || error);
  }

  const mapped = rows.map((row) => {
    const round = roundMap.get(Number(row.game_round_id)) || {};
    const slipStatus = normalizeStatus(row.status);
    const roundStatus = normalizeStatus(round.status || row.status);
    return {
      id: Number(row.id),
      playerId: Number(row.player_id),
      status: slipStatus,
      totalStake: Number(row.total_stake || 0),
      totalPossibleWin: Number(row.total_possible_win || 0),
      placedAt: row.placed_at,
      updatedAt: row.updated_at,
      gameRoundId: Number(row.game_round_id),
      roundNumber: Number(round.roundNumber || 0),
      roundStatus,
      items: itemsBySlipId.get(Number(row.id)) || [],
    };
  });

  const currentSlip =
    mapped
      .filter((row) => row.roundStatus === "OPEN" || row.status === "OPEN")
      .sort(
        (a, b) =>
          Number(b.roundNumber || 0) - Number(a.roundNumber || 0) ||
          Date.parse(String(b.placedAt || "")) - Date.parse(String(a.placedAt || "")),
      )[0] || null;

  const pastSlips = mapped
    .filter((row) => row.roundStatus === "CLOSED")
    .sort(
      (a, b) =>
        Number(b.roundNumber || 0) - Number(a.roundNumber || 0) ||
        Date.parse(String(b.placedAt || "")) - Date.parse(String(a.placedAt || "")),
    );

  return { currentSlip, pastSlips };
}

async function getSlipActivityFallback(playerId) {
  const safePlayerId = Number(playerId);
  if (!Number.isInteger(safePlayerId) || safePlayerId <= 0) {
    return { currentSlip: null, pastSlips: [] };
  }

  const { rows } = await bettingPool.query(
    `SELECT
       id,
       player_id,
       status,
       total_stake,
       total_possible_win,
       placed_at,
       updated_at,
       ${BETTING_SLIP_GAME_ROUND_COLUMN} AS game_round_id
     FROM ${BETTING_SLIP_TABLE}
     WHERE player_id = $1
     ORDER BY placed_at DESC, id DESC`,
    [safePlayerId],
  );

  if (!rows.length) {
    return { currentSlip: null, pastSlips: [] };
  }

  const slipIds = rows.map((row) => Number(row.id));
  const itemRows = await bettingPool.query(
    `SELECT
       id,
       slip_id,
       ${BETTING_SLIP_ITEM_CHARACTER_COLUMN} AS character_id,
       bet_type,
       option_code,
       stake,
       odds,
       possible_win,
       placed_at,
       phase_start,
       phase_end
     FROM ${BETTING_SLIP_ITEM_TABLE}
     WHERE slip_id = ANY($1::bigint[])
     ORDER BY placed_at DESC, id DESC`,
    [slipIds],
  );

  const itemsBySlipId = new Map();
  for (const row of itemRows.rows) {
    const slipId = Number(row.slip_id);
    if (!itemsBySlipId.has(slipId)) {
      itemsBySlipId.set(slipId, []);
    }
    itemsBySlipId.get(slipId).push({
      id: Number(row.id),
      characterId: Number(row.character_id),
      characterName: `Character #${Number(row.character_id)}`,
      betType: String(row.bet_type || ""),
      optionCode: String(row.option_code || ""),
      stake: Number(row.stake || 0),
      odds: Number(row.odds || 0),
      possibleWin: Number(row.possible_win || 0),
      phaseStart: Number(row.phase_start || 0),
      phaseEnd:
        row.phase_end === null || row.phase_end === undefined
          ? null
          : Number(row.phase_end),
      placedAt: row.placed_at,
      outcomeResults: [],
    });
  }

  const mapped = rows.map((row) => ({
    id: Number(row.id),
    playerId: Number(row.player_id),
    status: normalizeStatus(row.status),
    totalStake: Number(row.total_stake || 0),
    totalPossibleWin: Number(row.total_possible_win || 0),
    placedAt: row.placed_at,
    updatedAt: row.updated_at,
    gameRoundId: Number(row.game_round_id),
    roundNumber: Number(row.game_round_id),
    roundStatus: normalizeStatus(row.status),
    items: itemsBySlipId.get(Number(row.id)) || [],
  }));

  const currentSlip =
    mapped.find((row) => row.status === "OPEN" || row.roundStatus === "OPEN") ||
    mapped[0] ||
    null;
  const pastSlips = mapped.filter((row) => row !== currentSlip);
  return { currentSlip, pastSlips };
}

function createApp() {
  const app = express();

  app.disable("x-powered-by");
  app.use(express.json({ limit: "16kb" }));
  app.use(cors({ origin: parseCorsOrigins() }));

  app.get("/health", async (req, res) => {
    const checks = await Promise.allSettled([
      bettingPool.query("SELECT 1"),
      decisionPool.query("SELECT 1"),
      demoPool.query("SELECT 1"),
    ]);

    const services = {
      betting_postgres: checks[0].status === "fulfilled" ? "up" : "down",
      decision_postgres: checks[1].status === "fulfilled" ? "up" : "down",
      demo_postgres: checks[2].status === "fulfilled" ? "up" : "down",
    };
    const ok = Object.values(services).every((state) => state === "up");

    return res.status(ok ? 200 : 503).json({
      ok,
      service: "Transactions",
      build: "slip-fallback-2026-04-08",
      timestamp: new Date().toISOString(),
      services,
    });
  });

  app.get("/api/wallet/me", authenticateToken, async (req, res) => {
    try {
      const playerId = Number(req.user?.userId);
      if (!Number.isInteger(playerId) || playerId <= 0) {
        return res.status(401).json({ error: "Invalid authenticated player" });
      }

      const snapshot = await getWalletSnapshot(playerId);
      return res.json(snapshot || {});
    } catch (error) {
      console.error("Could not load wallet snapshot:", error);
      return res.status(500).json({ error: "Could not load wallet balance" });
    }
  });

  app.get("/api/slips/me", authenticateToken, async (req, res) => {
    try {
      const playerId = Number(req.user?.userId);
      if (!Number.isInteger(playerId) || playerId <= 0) {
        return res.status(401).json({ error: "Invalid authenticated player" });
      }

      let payload;
      try {
        payload = await getSlipActivityForPlayer(playerId);
      } catch (error) {
        console.warn(
          "Transactions enriched slip activity failed, using fallback:",
          error?.message || error,
        );
        payload = await getSlipActivityFallback(playerId);
      }
      return res.json(payload);
    } catch (error) {
      console.error("Could not load slip activity:", error);
      return res.status(500).json({ error: "Could not load slip activity" });
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
    console.log(`Transactions service listening on port ${effectivePort}`);
  });
}

module.exports = { createApp, start };

if (require.main === module) {
  start();
}
