const rateLimitTable = new Map();

const rateLimiter = (req, res, next) => {
  const ip = req.ip;
  const now = Date.now();
  const windowMs = 15 * 60 * 1000;
  const maxRequests = 100;

  if (!rateLimitTable.has(ip)) {
    rateLimitTable.set(ip, { count: 1, start: now });
    setTimeout(() => rateLimitTable.delete(ip), windowMs);
    return next();
  }

  const data = rateLimitTable.get(ip);

  if (now - data.start > windowMs) {
    rateLimitTable.set(ip, { count: 1, start: now });
    return next();
  }

  if (data.count >= maxRequests) {
    return res.status(429).json({ error: "Too many requests" });
  }

  data.count++;
  next();
};

module.exports = rateLimiter;
