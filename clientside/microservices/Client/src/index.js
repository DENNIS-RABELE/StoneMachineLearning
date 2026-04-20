const express = require("express");
const cors = require("cors");
const path = require("path");
const { createProxyMiddleware, fixRequestBody } = require("http-proxy-middleware");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});

const fetch =
  typeof globalThis.fetch === "function"
    ? globalThis.fetch.bind(globalThis)
    : (...args) =>
        import("node-fetch").then(({ default: fetchImpl }) => fetchImpl(...args));

const app = express();
const DEFAULT_PORT = 3000;
const STATIC_ROOT = path.join(__dirname, "..", "static");

const BETTOR_URL = process.env.BETTOR_URL || "http://localhost:4101";
const ODDS_URL = process.env.ODDS_URL || "http://localhost:4102";
const GAME_URL = process.env.GAME_URL || "http://localhost:4103";
const STATISTICS_URL = process.env.STATISTICS_URL || "http://localhost:4104";
const DEMOMONEY_URL = process.env.DEMOMONEY_URL || "http://localhost:4105";
const TIMER_URL = process.env.TIMER_URL || "http://localhost:4106";
const CLIENT_UPDATE_URL =
  process.env.CLIENT_UPDATE_URL || "http://localhost:4107";
const STATS_UI_URL = process.env.STATS_UI_URL || "http://localhost:4108";
const TRANSACTIONS_URL = process.env.TRANSACTIONS_URL || "http://localhost:4109";
const STONE_THROW_OUTCOMES_URL =
  process.env.STONE_THROW_OUTCOMES_URL || "http://localhost:4110";
const UNITY_URL = process.env.UNITY_URL || "http://localhost:9000/gameplay";
const UNITY_ROOT_URL = (() => {
  try {
    return new URL(UNITY_URL).origin;
  } catch {
    return UNITY_URL.replace(/\/+$/, "");
  }
})();

const NODE_ENV = process.env.NODE_ENV || "development";

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

function flattenOptions(payload) {
  if (!payload) return [];
  const singleDraw = payload?.single?.draw || [];
  const singleFloat = payload?.single?.float || [];
  const doubleBuckets = payload?.double || {};
  const doubles = Object.values(doubleBuckets).flat();
  return [...singleDraw, ...singleFloat, ...doubles].map((item) => item.key);
}

async function validateBetRequest(req, res, next) {
  const { option, characterId, stake } = req.body || {};

  if (!option || !characterId) {
    return res.status(400).json({ error: "option and characterId are required" });
  }

  let stakeValue = Number(
    stake === undefined || stake === null || stake === "" ? 1 : stake,
  );
  if (!Number.isFinite(stakeValue) || stakeValue <= 0) {
    stakeValue = 1;
  }
  req.body.stake = Number(stakeValue.toFixed(2));

  const characterIdNum = Number.parseInt(String(characterId), 10);
  if (!Number.isInteger(characterIdNum) || characterIdNum <= 0) {
    return res.status(400).json({ error: "characterId must be a positive integer" });
  }

  try {
    const characterRes = await fetch(`${ODDS_URL}/api/characters/${characterIdNum}`);
    if (!characterRes.ok) {
      return res.status(400).json({ error: "Invalid characterId" });
    }

    const optionsRes = await fetch(
      `${ODDS_URL}/api/options?characterId=${encodeURIComponent(characterIdNum)}`,
    );
    if (!optionsRes.ok) {
      return res.status(400).json({ error: "Could not validate bet option" });
    }
    const payload = await optionsRes.json().catch(() => null);
    const flattened = flattenOptions(payload);
    const allowed = new Set(flattened);
    if (!allowed.has(String(option))) {
      return res.status(400).json({ error: "Invalid bet option" });
    }
    const oddsEntry = [...(payload?.single?.draw || []), ...(payload?.single?.float || []), ...Object.values(payload?.double || {}).flat()]
      .find((item) => String(item.key) === String(option));
    if (oddsEntry?.odds) {
      req.body.odds = Number(oddsEntry.odds);
    }
  } catch (error) {
    console.error("Gateway validation failed:", error);
    return res.status(502).json({ error: "Gateway validation failed" });
  }

  return next();
}

function proxyTo(target) {
  return createProxyMiddleware({
    target,
    changeOrigin: true,
    onProxyReq: fixRequestBody,
    proxyTimeout: 30000,
    timeout: 30000,
    onError(err, req, res) {
      console.error("Gateway proxy error:", err?.message || err);
      if (!res.headersSent) {
        res.status(502).json({ error: "Upstream service unavailable" });
      }
    },
  });
}

function proxyWebsocket(target) {
  return createProxyMiddleware({
    target,
    changeOrigin: true,
    ws: true,
    onError(err, req, res) {
      console.error("Unity websocket proxy error:", err?.message || err);
      if (!res.headersSent) {
        res.status(502).json({ error: "Unity websocket unavailable" });
      }
    },
  });
}

function proxyUnity(targetRoot, basePath) {
  return createProxyMiddleware({
    target: targetRoot,
    changeOrigin: true,
    pathRewrite: (path, req) => {
      // When mounted at /games, Express can pass either "/games/..." or just
      // the trimmed remainder ("/...") depending on middleware internals.
      // Rebuild from the original URL so the embed route always targets the
      // gameplay service path, e.g. /games/embed/ -> /gameplay/embed/.
      const originalPath = req?.originalUrl || path || "/";
      const trimmedPath = originalPath.startsWith("/games")
        ? originalPath.slice("/games".length) || "/"
        : path || "/";
      const normalizedBasePath = (basePath || "/").replace(/\/+$/, "");
      const normalizedTail = trimmedPath.startsWith("/") ? trimmedPath : `/${trimmedPath}`;
      return `${normalizedBasePath}${normalizedTail}`;
    },
    onProxyReq: fixRequestBody,
    proxyTimeout: 30000,
    timeout: 30000,
    onProxyRes(proxyRes) {
      if (proxyRes?.headers) {
        delete proxyRes.headers["x-frame-options"];
        delete proxyRes.headers["X-Frame-Options"];
        const location = proxyRes.headers.location;
        if (typeof location === "string" && location.startsWith("/")) {
          proxyRes.headers.location = `/games${location}`;
        }
      }
    },
    onError(err, req, res) {
      console.error("Unity proxy error:", err?.message || err);
      if (!res.headersSent) {
        res.status(502).json({ error: "Unity service unavailable" });
      }
    },
  });
}

function normalizeUnityPath(pathname, basePath) {
  const normalizedBasePath = (basePath || "/").replace(/\/+$/, "");
  const normalizedPath = pathname.startsWith("/") ? pathname : `/${pathname}`;

  if (normalizedPath.startsWith(`${normalizedBasePath}/`)) {
    return normalizedPath;
  }

  if (normalizedPath.startsWith("/embed/") || normalizedPath === "/embed") {
    return `${normalizedBasePath}${normalizedPath}`;
  }

  if (
    normalizedPath.startsWith("/embed-meta/") ||
    normalizedPath === "/embed-meta"
  ) {
    return `${normalizedBasePath}${normalizedPath}`;
  }

  return normalizedPath;
}

function proxyUnityCompat(targetRoot, basePath) {
  return createProxyMiddleware({
    target: targetRoot,
    changeOrigin: true,
    pathRewrite: (path, req) => {
      const originalPath = req?.originalUrl || path || "/";
      return normalizeUnityPath(originalPath, basePath);
    },
    onProxyReq: fixRequestBody,
    proxyTimeout: 30000,
    timeout: 30000,
    onProxyRes(proxyRes) {
      if (proxyRes?.headers) {
        delete proxyRes.headers["x-frame-options"];
        delete proxyRes.headers["X-Frame-Options"];
      }
    },
    onError(err, req, res) {
      console.error("Unity compatibility proxy error:", err?.message || err);
      if (!res.headersSent) {
        res.status(502).json({ error: "Unity service unavailable" });
      }
    },
  });
}

function validateDemoMoneyAllocate(req, res, next) {
  const bettorId = Number(req.body?.bettorId);
  const amount = req.body?.amount;
  if (!Number.isInteger(bettorId) || bettorId <= 0) {
    return res.status(400).json({ error: "bettorId must be a positive integer" });
  }
  if (amount !== undefined) {
    const numeric = Number(amount);
    if (!Number.isFinite(numeric) || numeric < 0) {
      return res.status(400).json({ error: "amount must be a non-negative number" });
    }
  }
  return next();
}

function forwardInternalJson(reqLike, targetBase) {
  return new Promise((resolve) => {
    forwardRequest(
      reqLike,
      {
        status(code) {
          this.statusCode = code;
          return this;
        },
        setHeader() {},
        send(payload) {
          try {
            const parsed =
              typeof payload === "string" ? JSON.parse(payload) : payload;
            resolve({
              status: this.statusCode || 200,
              payload: parsed,
            });
          } catch {
            resolve({
              status: this.statusCode || 200,
              payload,
            });
          }
        },
        json(payload) {
          resolve({
            status: this.statusCode || 200,
            payload,
          });
        },
      },
      targetBase,
    );
  });
}

async function forwardRequest(req, res, targetBase) {
  const url = `${targetBase}${req.originalUrl}`;
  const headers = { ...req.headers };
  delete headers.host;
  delete headers["content-length"];
  delete headers["content-length".toLowerCase()];

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {
    const body =
      req.method === "GET" || req.method === "HEAD" ? undefined : JSON.stringify(req.body || {});
    if (body !== undefined) {
      headers["content-type"] = headers["content-type"] || "application/json";
    }

    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body,
      signal: controller.signal,
    });

    const text = await upstream.text();
    if (upstream.headers.get("content-type")) {
      res.setHeader("content-type", upstream.headers.get("content-type"));
    }
    return res.status(upstream.status).send(text);
  } catch (error) {
    console.error("Gateway forward error:", error?.message || error);
    return res.status(502).json({ error: "Upstream service unavailable" });
  } finally {
    clearTimeout(timeout);
  }
}

app.disable("x-powered-by");
app.use(express.json({ limit: "16kb" }));
app.use(cors({ origin: parseCorsOrigins() }));

// Serve static assets on both paths for compatibility with old UI.
app.use("/static", express.static(STATIC_ROOT));
app.use("/clientside/static", express.static(STATIC_ROOT));

app.get("/", (req, res) => {
  res.sendFile(path.join(STATIC_ROOT, "html", "index.html"));
});

app.get("/dashboard", (req, res) => {
  res.sendFile(path.join(STATIC_ROOT, "html", "dashboard.html"));
});

// Extract Unity base path from UNITY_URL
const UNITY_BASE_PATH = (() => {
  try {
    const url = new URL(UNITY_URL);
    return url.pathname || "/gameplay";
  } catch {
    const match = UNITY_URL.match(/\/[^/]+/);
    return match ? match[0] : "/gameplay";
  }
})();

// Proxy Unity embed so it loads from the same origin as the dashboard.
app.use("/games", proxyUnity(UNITY_ROOT_URL, UNITY_BASE_PATH));
app.use("/gameplay/embed-meta", proxyUnityCompat(UNITY_ROOT_URL, UNITY_BASE_PATH));
app.use("/gameplay/embed", proxyUnityCompat(UNITY_ROOT_URL, UNITY_BASE_PATH));
app.use("/gameplay", proxyTo(UNITY_ROOT_URL));
app.use("/game2", proxyTo(UNITY_ROOT_URL));
app.use("/ws", proxyWebsocket(UNITY_ROOT_URL));
// Proxy Stats UI embed so it loads from the same origin as the dashboard.
app.use("/stats", proxyTo(STATS_UI_URL));

app.get("/health", (req, res) => {
  res.json({
    service: "Client",
    status: "ok",
    timestamp: new Date().toISOString(),
  });
});

app.get("/api/health", async (req, res) => {
  const checks = await Promise.allSettled([
    fetch(`${BETTOR_URL}/health`),
    fetch(`${ODDS_URL}/health`),
    fetch(`${GAME_URL}/health`),
    fetch(`${STATISTICS_URL}/health`),
    fetch(`${DEMOMONEY_URL}/health`),
    fetch(`${TIMER_URL}/health`),
    fetch(`${CLIENT_UPDATE_URL}/health`),
    fetch(`${STATS_UI_URL}/health`),
    fetch(`${TRANSACTIONS_URL}/health`),
    fetch(`${STONE_THROW_OUTCOMES_URL}/health`),
  ]);

  const names = [
    "bettor",
    "odds",
    "game",
    "statistics",
    "demomoney",
    "timer",
    "clientupdate",
    "stats-ui",
    "transactions",
    "stone-throw-outcomes",
  ];
  const services = {};
  checks.forEach((result, idx) => {
    services[names[idx]] = result.status === "fulfilled" && result.value.ok ? "up" : "down";
  });

  const ok = Object.values(services).every((state) => state === "up");
  res.status(ok ? 200 : 503).json({ ok, env: NODE_ENV, services });
});

// Gateway validation for FK-like references + wallet deduction.
app.post("/api/bet", validateBetRequest, async (req, res) => {
  try {
    const headers = { ...req.headers };
    delete headers.host;
    delete headers["content-length"];
    delete headers["content-length".toLowerCase()];
    delete headers["transfer-encoding"];
    delete headers["Transfer-Encoding"];

    const stake = Number(req.body?.stake ?? 1);
    console.log("[Gateway bet] payload", {
      option: req.body?.option,
      characterId: req.body?.characterId,
      stake,
      hasAuth: Boolean(req.headers?.authorization),
    });

    if (!req.body?.gameRoundId) {
      const roundRes = await fetch(`${GAME_URL}/api/rounds/open`, {
        method: "GET",
      });
      const roundPayload = await roundRes.json().catch(() => ({}));
      if (!roundRes.ok) {
        return res
          .status(roundRes.status)
          .json({ error: roundPayload?.error || "No open round available" });
      }
      const roundIdValue = Number(roundPayload?.round_id);
      if (!Number.isInteger(roundIdValue) || roundIdValue <= 0) {
        return res.status(500).json({ error: "Invalid open round id" });
      }
      req.body.gameRoundId = roundIdValue;
    }
    const deductReq = {
      ...req,
      method: "POST",
      originalUrl: "/api/user/demo-money/deduct",
      headers: { ...(req.headers || {}) },
      body: { amount: stake },
    };
    const deductRes = await forwardInternalJson(deductReq, DEMOMONEY_URL);
    const deductPayload = deductRes.payload || {};
    console.log("[Gateway bet] demomoney response", {
      status: deductRes.status,
      payload: deductPayload,
    });
    if (deductRes.status >= 400) {
      return res
        .status(deductRes.status)
        .json({ error: deductPayload?.error || "Could not deduct demo balance" });
    }

    const betPayload = { ...(req.body || {}) };
    const betBody = JSON.stringify(betPayload);
    const forwardHeaders = {
      Authorization: req.headers?.authorization,
      "Content-Type": "application/json",
    };
    const betRes = await fetch(`${GAME_URL}/api/bet`, {
      method: "POST",
      headers: {
        ...forwardHeaders,
      },
      body: betBody,
    });
    const betResponse = await betRes.json().catch(() => ({}));
    if (!betRes.ok) {
      const deductedBalance = Number(deductPayload?.demo_balance);
      if (Number.isFinite(deductedBalance)) {
        const restoreReq = {
          ...req,
          method: "PATCH",
          originalUrl: "/api/user/demo-money",
          headers: { ...(req.headers || {}) },
          body: { amount: Number((deductedBalance + stake).toFixed(2)) },
        };
        try {
          const restoreRes = await forwardInternalJson(restoreReq, DEMOMONEY_URL);
          if (restoreRes.status >= 400) {
            console.error("[Gateway bet] refund failed", {
              status: restoreRes.status,
              payload: restoreRes.payload,
            });
          }
        } catch (refundError) {
          console.error("[Gateway bet] refund error", refundError);
        }
      }
      return res.status(betRes.status).json(betResponse);
    }

    return res.json({
      ...betResponse,
      playerBalance: Number(deductPayload?.demo_balance ?? betResponse?.playerBalance ?? 0),
    });
  } catch (error) {
    console.error("Gateway bet flow failed:", error);
    return res.status(502).json({ error: "Upstream service unavailable" });
  }
});

// Bettor service routes (registration/auth/profile).
app.use(
  [
    "/api/register",
    "/api/verify-email",
    "/api/login",
    "/api/forgot-password",
    "/api/reset-password",
    "/api/resend-verification",
    "/api/logout",
  ],
  (req, res) => forwardRequest(req, res, BETTOR_URL),
);

// Merge profile with demo wallet balance from demomoney service.
app.get("/api/user/profile", async (req, res) => {
  try {
    const headers = { ...req.headers };
    delete headers.host;

    const profileRes = await fetch(`${BETTOR_URL}/api/user/profile`, {
      method: "GET",
      headers,
    });
    const profileText = await profileRes.text();
    if (!profileRes.ok) {
      return res.status(profileRes.status).send(profileText);
    }

    let profilePayload = {};
    try {
      profilePayload = profileText ? JSON.parse(profileText) : {};
    } catch {
      profilePayload = {};
    }

    const walletRes = await fetch(`${DEMOMONEY_URL}/api/wallet/me`, {
      method: "GET",
      headers,
    });
    let walletPayload = {};
    try {
      walletPayload = await walletRes.json();
    } catch {
      walletPayload = {};
    }

    const user = profilePayload.user || {};
    if (walletRes.ok && walletPayload && typeof walletPayload === "object") {
      user.demo_balance = walletPayload.playerBalance ?? user.demo_balance ?? null;
    }

    return res.json({ ...profilePayload, user });
  } catch (error) {
    console.error("Profile merge failed:", error);
    return res.status(502).json({ error: "Upstream service unavailable" });
  }
});

function validateDemoMoneyAmount(req, res, next) {
  const amount = req.body?.amount;
  if (amount === undefined) return next();
  const numeric = Number(amount);
  if (!Number.isFinite(numeric) || numeric < 0) {
    return res.status(400).json({ error: "amount must be a non-negative number" });
  }
  return next();
}

// Demo money service routes (validated at gateway).
app.patch(
  "/api/user/demo-money",
  validateDemoMoneyAmount,
  (req, res) => forwardRequest(req, res, DEMOMONEY_URL),
);
app.post(
  "/api/user/demo-money/deduct",
  validateDemoMoneyAmount,
  (req, res) => forwardRequest(req, res, DEMOMONEY_URL),
);
app.get("/api/wallet/me", (req, res) => forwardRequest(req, res, TRANSACTIONS_URL));
app.post(
  "/api/demo-money/allocate",
  validateDemoMoneyAllocate,
  (req, res) => forwardRequest(req, res, DEMOMONEY_URL),
);

// Odds service routes.
app.get("/api/characters", (req, res) => forwardRequest(req, res, ODDS_URL));
app.get("/api/characters/:id", (req, res) => forwardRequest(req, res, ODDS_URL));
app.get("/api/options", (req, res) => forwardRequest(req, res, ODDS_URL));

// Game service routes.
app.get("/api/bets", (req, res) => forwardRequest(req, res, GAME_URL));
app.get("/api/bets/me", (req, res) => forwardRequest(req, res, GAME_URL));
app.get("/api/results", (req, res) => forwardRequest(req, res, GAME_URL));
app.get("/api/slips/me", (req, res) => forwardRequest(req, res, TRANSACTIONS_URL));
app.get("/api/outcomes", (req, res) =>
  forwardRequest(req, res, STONE_THROW_OUTCOMES_URL),
);
app.get("/api/post-game-stats", (req, res) =>
  forwardRequest(req, res, STONE_THROW_OUTCOMES_URL),
);

// Live gameplay routes.
app.get("/api/round-timer", (req, res) => forwardRequest(req, res, GAME_URL));
app.get("/api/live/snapshot", (req, res) => forwardRequest(req, res, GAME_URL));
app.use("/api/live/stream", proxyTo(GAME_URL));

// Client update service routes.
app.get("/api/bettor-updates/snapshot", (req, res) =>
  forwardRequest(req, res, CLIENT_UPDATE_URL),
);
app.use("/api/bettor-updates/stream", proxyTo(CLIENT_UPDATE_URL));

// Statistics service routes.
app.use("/api/stats", (req, res) => forwardRequest(req, res, STATISTICS_URL));

app.use((req, res) => {
  res.status(404).json({ error: "Not found" });
});

app.use((err, req, res, next) => {
  console.error("Unhandled request error:", err);
  res.status(500).json({ error: "Internal server error" });
});

function createApp() {
  return app;
}

function start(options = {}) {
  const effectivePort = Number(
    options.port ?? process.env.PORT ?? DEFAULT_PORT,
  );
  return app.listen(effectivePort, options.host, () => {
    console.log(`Client gateway listening on port ${effectivePort}`);
  });
}

module.exports = { createApp, start };

if (require.main === module) {
  start();
}
