const { client } = require("./redisClient");

const REDIS_BETS_KEY = "round:current:bets";
const REDIS_RECENT_BETS_KEY = "round:recent:bets";
const REDIS_BETS_BY_CHAR_KEY = "round:current:bets:by_character";
const REDIS_BETS_CHAR_NAMES_KEY = "round:current:bets:character_names";
const REDIS_BETS_BY_CHAR_COUNT_KEY = "round:current:bets:by_character:count";
const REDIS_BETS_BY_CHAR_ODDS_KEY = "round:current:bets:by_character:odds_sum";
const RECENT_BETS_MAX = Math.max(5, Number(process.env.RECENT_BETS_MAX || 50));

async function incrementBet(option, stake = 1) {
  const safeStake = Number(stake);
  if (!Number.isFinite(safeStake) || safeStake <= 0) {
    throw new Error("stake must be a positive number");
  }
  await client.hIncrByFloat(REDIS_BETS_KEY, option, safeStake);
}

async function getCurrentBets() {
  return await client.hGetAll(REDIS_BETS_KEY);
}

async function clearBets() {
  await client.del([
    REDIS_BETS_KEY,
    REDIS_RECENT_BETS_KEY,
    REDIS_BETS_BY_CHAR_KEY,
    REDIS_BETS_CHAR_NAMES_KEY,
    REDIS_BETS_BY_CHAR_COUNT_KEY,
    REDIS_BETS_BY_CHAR_ODDS_KEY,
  ]);
}

async function pushRecentBet({
  bettorName,
  optionCode,
  amount,
  placedAt = new Date(),
}) {
  const safeName = String(bettorName || "").trim();
  const safeOption = String(optionCode || "").trim();
  if (!safeName || !safeOption) return;

  const safeAmount = Number(amount);
  const entry = JSON.stringify({
    bettorName: safeName,
    optionCode: safeOption,
    amount: Number.isFinite(safeAmount) ? safeAmount : null,
    placedAt: placedAt instanceof Date ? placedAt.toISOString() : placedAt,
  });

  await client
    .multi()
    .lPush(REDIS_RECENT_BETS_KEY, entry)
    .lTrim(REDIS_RECENT_BETS_KEY, 0, RECENT_BETS_MAX - 1)
    .expire(REDIS_RECENT_BETS_KEY, 300)
    .exec();
}

async function incrementCategorizedBet({
  characterId,
  characterName,
  kind,
  phase,
  stake = 1,
  odds = null,
}) {
  const safeStake = Number(stake);
  if (!Number.isFinite(safeStake) || safeStake <= 0)
    throw new Error("stake must be a positive number");

  const safeCharacterId = Number(characterId);
  if (!Number.isInteger(safeCharacterId) || safeCharacterId <= 0)
    throw new Error("characterId must be a positive integer");

  const safePhase = Number(phase);
  if (!Number.isInteger(safePhase) || safePhase <= 0)
    throw new Error("phase must be a positive integer");

  const safeKind = String(kind || "").toUpperCase();
  if (!["FLOAT", "DROWN"].includes(safeKind))
    throw new Error("kind must be FLOAT or DROWN");

  const safeOdds = Number(odds);
  const charIdStr = String(safeCharacterId);
  const field = `C${charIdStr}:${safeKind}:${safePhase}`;
  const totalField = `C${charIdStr}:TOTAL`;
  const countField = `${field}:COUNT`;
  const totalCountField = `C${charIdStr}:TOTAL:COUNT`;

  const pipeline = client.multi();
  if (characterName)
    pipeline.hSet(REDIS_BETS_CHAR_NAMES_KEY, charIdStr, String(characterName));
  pipeline.hIncrByFloat(REDIS_BETS_BY_CHAR_KEY, field, safeStake);
  pipeline.hIncrByFloat(REDIS_BETS_BY_CHAR_KEY, totalField, safeStake);
  pipeline.hIncrBy(REDIS_BETS_BY_CHAR_COUNT_KEY, countField, 1);
  pipeline.hIncrBy(REDIS_BETS_BY_CHAR_COUNT_KEY, totalCountField, 1);

  if (Number.isFinite(safeOdds) && safeOdds > 0) {
    const oddsField = `${field}:ODDS`;
    const totalOddsField = `C${charIdStr}:TOTAL:ODDS`;
    pipeline.hIncrByFloat(REDIS_BETS_BY_CHAR_ODDS_KEY, oddsField, safeOdds);
    pipeline.hIncrByFloat(
      REDIS_BETS_BY_CHAR_ODDS_KEY,
      totalOddsField,
      safeOdds,
    );
  }

  await pipeline.exec();
}

module.exports = {
  incrementBet,
  incrementCategorizedBet,
  getCurrentBets,
  clearBets,
  pushRecentBet,
};
