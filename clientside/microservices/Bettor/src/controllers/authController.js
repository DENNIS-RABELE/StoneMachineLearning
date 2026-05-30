const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");
const fetch =
  typeof globalThis.fetch === "function"
    ? globalThis.fetch.bind(globalThis)
    : (...args) =>
        import("node-fetch").then(({ default: fetchImpl }) => fetchImpl(...args));
const authPool = require("../lib/database");
const { pool: bettingPool } = require("../lib/dbFlush");
const { recordActivityEvent } = require("../lib/activityStore");
const {
  sendVerificationEmail,
  sendPasswordResetEmail,
} = require("../services/emailService");
const BETTORS_TABLE = "\"Bettors_bettors\"";
const SUPPORT_ENQUIRY_TABLE = "portal_support_enquiry";
const DEMO_MONEY_TABLE = "demonstration_money";
const CLIENT_PLAYER_WALLET_TABLE = "client_player_wallet";
const DEFAULT_DEMO_BALANCE = 1000;
const DEFAULT_PLAYER_BALANCE = Number(
  process.env.DEFAULT_PLAYER_WALLET_BALANCE || DEFAULT_DEMO_BALANCE,
);
const CLIENT_GATEWAY_URL = process.env.CLIENT_GATEWAY_URL || "http://localhost:3000";

const pendingRegistrations = new Map();
const pendingPasswordResets = new Map();
const VERIFICATION_TTL_MS = 10 * 60 * 1000;
const PASSWORD_RESET_TTL_MS = 10 * 60 * 1000;
const SUPPORT_CATEGORIES = new Set([
  "account",
  "betting",
  "payment",
  "complaint",
  "suggestion",
  "other",
]);

function generateVerificationCode() {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

function normalizeEmail(email) {
  return String(email || "").trim().toLowerCase();
}

function serializeSupportEnquiry(row) {
  return {
    id: Number(row.id),
    category: row.category,
    subject: row.subject,
    message: row.message,
    status: row.status,
    supportResponse: row.support_response || "",
    respondedAt: row.responded_at,
    createdAt: row.created_at,
    updatedAt: row.updated_at,
  };
}

async function upsertDemoMoneyForUser(userId, amount = DEFAULT_DEMO_BALANCE) {
  try {
    await bettingPool.query(
      `
      INSERT INTO ${CLIENT_PLAYER_WALLET_TABLE} (player_id, balance, created_at, updated_at)
      VALUES ($1, $2, NOW(), NOW())
      ON CONFLICT (player_id) DO NOTHING
      `,
      [userId, DEFAULT_PLAYER_BALANCE],
    );

    const walletRes = await bettingPool.query(
      `SELECT balance FROM ${CLIENT_PLAYER_WALLET_TABLE} WHERE player_id = $1 LIMIT 1`,
      [userId],
    );
    const syncedAmount = Number(walletRes.rows[0]?.balance ?? amount);

    const result = await bettingPool.query(
      `
      INSERT INTO ${DEMO_MONEY_TABLE} (bettor_id, amount, created_at, updated_at)
      VALUES ($1, $2, NOW(), NOW())
      ON CONFLICT (bettor_id)
      DO UPDATE SET
        amount = EXCLUDED.amount,
        updated_at = NOW()
      RETURNING bettor_id, amount
      `,
      [userId, syncedAmount],
    );
    return result.rows[0];
  } catch (error) {
    // Demo-money tables may not exist yet; allow verification to succeed.
    if (error?.code === "42P01" || error?.code === "3D000") {
      return { bettor_id: userId, amount: null };
    }
    throw error;
  }
}

exports.register = async (req, res) => {
  try {
    const {
      firstname,
      lastname,
      email: rawEmail,
      dateOfBirth,
      nationality,
      idNumber,
      physicalAddress,
      password,
    } = req.body;

    if (
      !firstname ||
      !lastname ||
      !rawEmail ||
      !dateOfBirth ||
      !nationality ||
      !idNumber ||
      !physicalAddress ||
      !password
    )
      return res.status(400).json({ error: "Missing fields" });

    const email = normalizeEmail(rawEmail);
    if (!email) return res.status(400).json({ error: "Valid email is required" });

    // DB READ: check whether the email already exists.
    const existing = await authPool.query(
      `SELECT id FROM ${BETTORS_TABLE} WHERE email = $1`,
      [email],
    );

    if (existing.rows.length > 0)
      return res.status(409).json({ error: "Email already exists" });

    const passwordHash = await bcrypt.hash(password, 10);
    const code = generateVerificationCode();
    const expiresAt = Date.now() + VERIFICATION_TTL_MS;

    pendingRegistrations.set(email, {
      firstname,
      lastname,
      email,
      dateOfBirth,
      nationality,
      idNumber,
      physicalAddress,
      passwordHash,
      code,
      expiresAt,
    });

    try {
      await sendVerificationEmail(email, code);
    } catch (mailError) {
      pendingRegistrations.delete(email);
      console.error("Email send failed:", mailError);
      return res.status(500).json({
        error:
          "Could not send verification email. Check SMTP settings and try again.",
      });
    }

    res.status(201).json({
      message: "Verification code sent. Complete verification to create account.",
      email,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Server error" });
  }
};

exports.login = async (req, res) => {
  try {
    const { email: rawEmail, password } = req.body;
    const email = normalizeEmail(rawEmail);

    // DB READ: load user credentials for login validation.
    const result = await authPool.query(
      `SELECT id, email, password_hash FROM ${BETTORS_TABLE} WHERE email = $1`,
      [email],
    );

    if (result.rows.length === 0)
      return res.status(401).json({ error: "Invalid credentials" });

    const user = result.rows[0];

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) return res.status(401).json({ error: "Invalid credentials" });

    recordActivityEvent({
      bettorId: user.id,
      eventType: "login",
      metadata: { source: "bettor_auth" },
    }).catch((error) =>
      console.warn("[Bettor Activity] Login event failed:", error.message),
    );

    const token = jwt.sign(
      { userId: user.id, email: user.email },
      process.env.JWT_SECRET || "your-secret-key",
      { expiresIn: "24h" },
    );

    res.json({
      message: "Login successful",
      token,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Server error" });
  }
};

exports.forgotPassword = async (req, res) => {
  try {
    const { email: rawEmail } = req.body;
    const email = normalizeEmail(rawEmail);

    if (!email) return res.status(400).json({ error: "Email is required" });

    const result = await authPool.query(
      `SELECT id FROM ${BETTORS_TABLE} WHERE email = $1`,
      [email],
    );

    if (result.rows.length === 0) {
      return res.json({
        message: "If this email exists, a password reset code was sent.",
      });
    }

    const code = generateVerificationCode();
    const expiresAt = Date.now() + PASSWORD_RESET_TTL_MS;
    pendingPasswordResets.set(email, { code, expiresAt });

    try {
      await sendPasswordResetEmail(email, code);
    } catch (mailError) {
      pendingPasswordResets.delete(email);
      console.error("Password reset email send failed:", mailError);
      return res.status(500).json({
        error:
          "Could not send password reset email. Check SMTP settings and try again.",
      });
    }

    return res.json({
      message: "If this email exists, a password reset code was sent.",
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};

exports.resetPassword = async (req, res) => {
  try {
    const { email: rawEmail, code, newPassword } = req.body;
    const email = normalizeEmail(rawEmail);

    if (!email || !code || !newPassword) {
      return res
        .status(400)
        .json({ error: "Email, code and new password are required" });
    }

    if (String(newPassword).length < 8) {
      return res
        .status(400)
        .json({ error: "New password must be at least 8 characters" });
    }

    const pending = pendingPasswordResets.get(email);
    if (!pending) {
      return res.status(404).json({ error: "No pending password reset found" });
    }

    if (Date.now() > pending.expiresAt) {
      pendingPasswordResets.delete(email);
      return res.status(400).json({ error: "Password reset code expired" });
    }

    if (pending.code !== String(code)) {
      return res.status(400).json({ error: "Invalid password reset code" });
    }

    const passwordHash = await bcrypt.hash(newPassword, 10);
    const updateResult = await authPool.query(
      `UPDATE ${BETTORS_TABLE} SET password_hash = $1 WHERE email = $2 RETURNING id`,
      [passwordHash, email],
    );

    pendingPasswordResets.delete(email);

    if (updateResult.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }

    return res.json({ message: "Password reset successful. Please log in." });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};

exports.verifyEmail = async (req, res) => {
  const { email: rawEmail, code } = req.body;
  const email = normalizeEmail(rawEmail);

  if (!email || !code)
    return res.status(400).json({ error: "Email and code are required" });

  const pending = pendingRegistrations.get(email);
  if (!pending)
    return res.status(404).json({ error: "No pending registration found" });

  if (Date.now() > pending.expiresAt) {
    pendingRegistrations.delete(email);
    return res.status(400).json({ error: "Verification code expired" });
  }

  if (pending.code !== String(code))
    return res.status(400).json({ error: "Invalid verification code" });

  try {
    // DB WRITE: create user only after successful email verification.
    const result = await authPool.query(
      `INSERT INTO ${BETTORS_TABLE}
       (firstname, lastname, email, date_of_birth, nationality, id_number, physical_address, password_hash)
       VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
       RETURNING id, firstname, lastname, email, date_of_birth, nationality, id_number, physical_address`,
      [
        pending.firstname,
        pending.lastname,
        pending.email,
        pending.dateOfBirth,
        pending.nationality,
        pending.idNumber,
        pending.physicalAddress,
        pending.passwordHash,
      ],
    );

    const user = result.rows[0];

    try {
      await fetch(`${CLIENT_GATEWAY_URL}/api/demo-money/allocate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          bettorId: user.id,
          amount: DEFAULT_DEMO_BALANCE,
        }),
      });
    } catch (allocationError) {
      console.error("Demo money allocation failed:", allocationError);
    }

    const token = jwt.sign(
      { userId: user.id, email: user.email },
      process.env.JWT_SECRET || "your-secret-key",
      { expiresIn: "24h" },
    );

    pendingRegistrations.delete(email);

    recordActivityEvent({
      bettorId: user.id,
      eventType: "registered",
      metadata: { source: "email_verification" },
    }).catch((error) =>
      console.warn("[Bettor Activity] Registration event failed:", error.message),
    );
    recordActivityEvent({
      bettorId: user.id,
      eventType: "login",
      metadata: { source: "email_verification" },
    }).catch((error) =>
      console.warn("[Bettor Activity] Verification login event failed:", error.message),
    );

    res.json({
      message: "Email verified and account created",
      token,
      user,
    });
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: "Server error" });
  }
};

exports.resendVerification = async (req, res) => {
  const { email: rawEmail } = req.body;
  const email = normalizeEmail(rawEmail);

  if (!email) return res.status(400).json({ error: "Email is required" });

  const pending = pendingRegistrations.get(email);
  if (!pending)
    return res.status(404).json({ error: "No pending registration found" });

  const code = generateVerificationCode();
  pending.code = code;
  pending.expiresAt = Date.now() + VERIFICATION_TTL_MS;
  pendingRegistrations.set(email, pending);

  try {
    await sendVerificationEmail(email, code);
  } catch (mailError) {
    console.error("Email resend failed:", mailError);
    return res.status(500).json({
      error: "Could not resend verification email. Check SMTP settings.",
    });
  }

  res.json({
    message: "Verification code resent",
  });
};

exports.getProfile = async (req, res) => {
  try {
    // DB READ: fetch profile details for the authenticated user + demo balance.
    const result = await authPool.query(
      `SELECT id, firstname, lastname, email FROM ${BETTORS_TABLE} WHERE id = $1`,
      [req.user.userId],
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }

    const user = result.rows[0];
    user.demo_balance = null;

    return res.json({ user });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Server error" });
  }
};

exports.logout = async (req, res) => {
  recordActivityEvent({
    bettorId: req.user?.userId,
    eventType: "logout",
    metadata: { source: "bettor_auth" },
  }).catch((error) =>
    console.warn("[Bettor Activity] Logout event failed:", error.message),
  );
  res.json({ message: "Logged out successfully" });
};

exports.trackActivity = async (req, res) => {
  try {
    const result = await recordActivityEvent({
      bettorId: req.user?.userId,
      eventType: req.body?.eventType,
      metadata: req.body?.metadata,
    });

    if (!result.recorded && result.reason === "invalid_event_type") {
      return res.status(400).json({ error: "Invalid activity event type" });
    }
    if (!result.recorded && result.reason === "invalid_bettor_id") {
      return res.status(401).json({ error: "Invalid authenticated bettor" });
    }

    return res.status(result.recorded ? 201 : 202).json(result);
  } catch (err) {
    console.error("Activity tracking failed:", err);
    return res.status(500).json({ error: "Could not track activity" });
  }
};

exports.createSupportEnquiry = async (req, res) => {
  try {
    const bettorId = Number(req.user?.userId);
    if (!Number.isFinite(bettorId) || bettorId <= 0) {
      return res.status(401).json({ error: "Invalid authenticated bettor" });
    }

    const category = SUPPORT_CATEGORIES.has(req.body?.category)
      ? req.body.category
      : "other";
    const subject = String(req.body?.subject || "").trim();
    const message = String(req.body?.message || "").trim();

    if (!subject || !message) {
      return res.status(400).json({ error: "Subject and message are required" });
    }

    const profile = await authPool.query(
      `SELECT email FROM ${BETTORS_TABLE} WHERE id = $1 LIMIT 1`,
      [bettorId],
    );
    const bettorEmail = profile.rows[0]?.email || req.user?.email || "";

    const result = await authPool.query(
      `INSERT INTO ${SUPPORT_ENQUIRY_TABLE}
       (bettor_id, bettor_email, category, subject, message, status, support_response, created_at, updated_at)
       VALUES ($1, $2, $3, $4, $5, 'open', '', NOW(), NOW())
       RETURNING id, category, subject, message, status, support_response, responded_at, created_at, updated_at`,
      [bettorId, bettorEmail, category, subject, message],
    );

    return res.status(201).json({ enquiry: serializeSupportEnquiry(result.rows[0]) });
  } catch (err) {
    console.error("Create support enquiry failed:", err);
    if (err?.code === "42P01") {
      return res.status(503).json({ error: "Support enquiry table is not ready" });
    }
    return res.status(500).json({ error: "Could not submit enquiry" });
  }
};

exports.listSupportEnquiries = async (req, res) => {
  try {
    const bettorId = Number(req.user?.userId);
    if (!Number.isFinite(bettorId) || bettorId <= 0) {
      return res.status(401).json({ error: "Invalid authenticated bettor" });
    }

    const result = await authPool.query(
      `SELECT id, category, subject, message, status, support_response, responded_at, created_at, updated_at
       FROM ${SUPPORT_ENQUIRY_TABLE}
       WHERE bettor_id = $1
       ORDER BY updated_at DESC, created_at DESC
       LIMIT 50`,
      [bettorId],
    );

    return res.json({ enquiries: result.rows.map(serializeSupportEnquiry) });
  } catch (err) {
    console.error("List support enquiries failed:", err);
    if (err?.code === "42P01") {
      return res.json({ enquiries: [] });
    }
    return res.status(500).json({ error: "Could not load enquiries" });
  }
};
