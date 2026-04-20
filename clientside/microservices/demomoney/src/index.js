const express = require("express");
const cors = require("cors");
const path = require("path");
require("dotenv").config({
  path: path.resolve(__dirname, "../.env"),
  quiet: true,
  override: false,
});

const demoMoneyRoutes = require("./routes/demoMoneyRoutes");

const DEFAULT_PORT = 4105;
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

function createApp() {
  const app = express();

  app.disable("x-powered-by");
  app.use(express.json({ limit: "16kb" }));
  app.use(cors({ origin: parseCorsOrigins() }));

  app.get("/health", (req, res) => {
    res.json({
      service: "demomoney",
      status: "ok",
      timestamp: new Date().toISOString(),
    });
  });

  app.use("/api", demoMoneyRoutes);

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
    console.log(`demomoney service listening on port ${effectivePort}`);
  });
}

module.exports = { createApp, start };

if (require.main === module) {
  start();
}
