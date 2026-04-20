const redis = require("redis");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../../.env"),
  quiet: true,
  override: false,
});

function parseBooleanEnv(value) {
  const normalized = String(value || "")
    .trim()
    .toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  if (["0", "false", "no", "off"].includes(normalized)) return false;
  return undefined;
}

const REDIS_REQUIRED =
  parseBooleanEnv(process.env.REDIS_REQUIRED) ??
  (process.env.NODE_ENV || "development") === "production";

let hasLoggedRedisUnavailable = false;

function isRedisConnectionRefused(err) {
  if (!err) return false;
  if (err.code === "ECONNREFUSED") return true;
  if (Array.isArray(err.errors)) {
    return err.errors.some((item) => item?.code === "ECONNREFUSED");
  }
  return /ECONNREFUSED/i.test(String(err.message || err));
}

function logRedisUnavailableOnce(prefix) {
  if (hasLoggedRedisUnavailable) return;
  hasLoggedRedisUnavailable = true;
  console.warn(
    `${prefix} Redis is unavailable; continuing without Redis. Set REDIS_REQUIRED=true to fail fast instead.`,
  );
}

function buildRedisOptions() {
  const redisUrl = process.env.REDIS_URL;
  const reconnectStrategy = REDIS_REQUIRED
    ? (retries) => Math.min(retries * 100, 3000)
    : false;

  if (redisUrl) {
    const parsedUrl = new URL(redisUrl);
    return {
      socket: {
        host: parsedUrl.hostname || process.env.REDIS_HOST || "127.0.0.1",
        port: Number(parsedUrl.port || process.env.REDIS_PORT || 6379),
        keepAlive: 5000,
        noDelay: true,
      },
      username:
        decodeURIComponent(parsedUrl.username || "") ||
        process.env.REDIS_USERNAME ||
        undefined,
      password:
        decodeURIComponent(parsedUrl.password || "") ||
        process.env.REDIS_PASSWORD ||
        undefined,
      database: parsedUrl.pathname
        ? Number.parseInt(parsedUrl.pathname.replace("/", ""), 10) || 0
        : undefined,
      disableOfflineQueue: true,
      commandsQueueMaxLength: 0,
      pingInterval: 10000,
      reconnectStrategy,
    };
  }
  return {
    socket: {
      host: process.env.REDIS_HOST || "127.0.0.1",
      port: Number(process.env.REDIS_PORT || 6379),
      keepAlive: 5000,
      noDelay: true,
    },
    username: process.env.REDIS_USERNAME || undefined,
    password: process.env.REDIS_PASSWORD || undefined,
    disableOfflineQueue: true,
    commandsQueueMaxLength: 0,
    pingInterval: 10000,
    reconnectStrategy,
  };
}

const client = redis.createClient(buildRedisOptions());
client.on("error", (err) => {
  if (!REDIS_REQUIRED && isRedisConnectionRefused(err)) {
    logRedisUnavailableOnce("[Timer Redis]");
    return;
  }
  console.error("Redis Error:", err?.message || err);
});

async function connectRedis() {
  if (!client.isOpen) {
    try {
      await client.connect();
    } catch (error) {
      if (!REDIS_REQUIRED && isRedisConnectionRefused(error)) {
        logRedisUnavailableOnce("[Timer Redis]");
        return;
      }
      throw error;
    }
  }
}

async function disconnectRedis() {
  if (client.isOpen) await client.quit();
}

function isRedisReady() {
  return client.isReady;
}

module.exports = { client, connectRedis, disconnectRedis, isRedisReady };
