const authPool = require("./database");

const ACTIVITY_TABLE = "bettor_activity_event";
const ALLOWED_EVENT_TYPES = new Set([
  "registered",
  "login",
  "logout",
  "profile_view",
  "odds_view",
  "market_view",
  "sport_view",
  "betslip_created",
  "betslip_abandoned",
  "bet_placed",
  "failed_bet",
]);

function normalizeEventType(eventType) {
  const normalized = String(eventType || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_]+/g, "_")
    .replace(/^_+|_+$/g, "");

  return ALLOWED_EVENT_TYPES.has(normalized) ? normalized : null;
}

function normalizeMetadata(metadata) {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return {};
  }

  const normalized = {};
  Object.entries(metadata).forEach(([key, value]) => {
    const safeKey = String(key || "")
      .trim()
      .slice(0, 64);
    if (!safeKey) return;

    if (
      value === null ||
      ["string", "number", "boolean"].includes(typeof value)
    ) {
      normalized[safeKey] = value;
    }
  });
  return normalized;
}

async function recordActivityEvent({ bettorId, eventType, metadata = {} }) {
  const safeBettorId = Number(bettorId);
  if (!Number.isInteger(safeBettorId) || safeBettorId <= 0) {
    return { recorded: false, reason: "invalid_bettor_id" };
  }

  const safeEventType = normalizeEventType(eventType);
  if (!safeEventType) {
    return { recorded: false, reason: "invalid_event_type" };
  }

  try {
    const result = await authPool.query(
      `
      INSERT INTO ${ACTIVITY_TABLE} (bettor_id, event_type, metadata, created_at)
      VALUES ($1, $2, $3::jsonb, NOW())
      RETURNING id, bettor_id, event_type, created_at
      `,
      [safeBettorId, safeEventType, JSON.stringify(normalizeMetadata(metadata))],
    );
    return { recorded: true, event: result.rows[0] };
  } catch (error) {
    if (error?.code === "42P01" || error?.code === "42703") {
      console.warn(
        "[Bettor Activity] Activity table is not migrated yet; event skipped.",
      );
      return { recorded: false, reason: "activity_table_missing" };
    }
    throw error;
  }
}

module.exports = {
  ALLOWED_EVENT_TYPES,
  normalizeEventType,
  recordActivityEvent,
};
