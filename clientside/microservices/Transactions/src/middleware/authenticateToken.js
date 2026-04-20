const jwt = require("jsonwebtoken");

module.exports = function authenticateToken(req, res, next) {
  const authHeader = req.headers.authorization;
  const token = authHeader && authHeader.split(" ")[1];

  if (!token) {
    return res.status(401).json({ error: "Access token required" });
  }

  // Keep fallback secret consistent with the rest of the clientside services
  // so local dev works even without a .env.
  jwt.verify(token, process.env.JWT_SECRET || "your-secret-key", (err, user) => {
    if (err) {
      return res.status(403).json({ error: "Invalid token" });
    }
    req.user = user;
    return next();
  });
};
