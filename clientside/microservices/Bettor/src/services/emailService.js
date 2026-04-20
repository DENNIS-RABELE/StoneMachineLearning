const nodemailer = require("nodemailer");

function getSmtpConfig() {
  if (String(process.env.SMTP_SKIP || "").toLowerCase() === "true") {
    return null;
  }
  const timeoutMs = Number(process.env.SMTP_TIMEOUT_MS || 10000);
  const port = Number(process.env.SMTP_PORT || 587);
  const secure =
    String(process.env.SMTP_SECURE || "").toLowerCase() === "true" ||
    port === 465;

  const host = process.env.SMTP_HOST;
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;

  if (!host || !user || !pass) {
    throw new Error(
      "SMTP configuration is missing. Set SMTP_HOST, SMTP_USER and SMTP_PASS.",
    );
  }

  return {
    host,
    port,
    secure,
    auth: { user, pass },
    connectionTimeout: timeoutMs,
    greetingTimeout: timeoutMs,
    socketTimeout: timeoutMs,
    logger: true,
    debug: true,
  };
}

function getTransporter() {
  if (String(process.env.SMTP_SKIP || "").toLowerCase() === "true") {
    return null;
  }
  const config = getSmtpConfig();
  const safeConfig = {
    host: config.host,
    port: config.port,
    secure: config.secure,
    user: config.auth?.user,
    hasPass: Boolean(config.auth?.pass),
    connectionTimeout: config.connectionTimeout,
    greetingTimeout: config.greetingTimeout,
    socketTimeout: config.socketTimeout,
  };
  console.log("[SMTP] config:", safeConfig);
  return nodemailer.createTransport(config);
}

exports.sendVerificationEmail = async (toEmail, code) => {
  if (String(process.env.SMTP_SKIP || "").toLowerCase() === "true") {
    console.log(`[SMTP_SKIP] Verification code for ${toEmail}: ${code}`);
    return;
  }
  const transporter = getTransporter();
  const appName = process.env.APP_NAME || "Stone Odds";
  const from = process.env.SMTP_FROM || process.env.SMTP_USER;

  if (!from) {
    throw new Error("SMTP_FROM or SMTP_USER must be configured.");
  }

  const started = Date.now();
  try {
    await transporter.sendMail({
      from,
      to: toEmail,
      subject: `${appName} verification code`,
      text: `Your ${appName} verification code is ${code}. It expires in 10 minutes.`,
      html: `<p>Your <strong>${appName}</strong> verification code is:</p><h2>${code}</h2><p>This code expires in 10 minutes.</p>`,
    });
    console.log(`[SMTP] verification email sent to ${toEmail} in ${Date.now() - started}ms`);
  } catch (error) {
    console.error("[SMTP] verification email failed:", error);
    throw error;
  }
};

exports.sendPasswordResetEmail = async (toEmail, code) => {
  if (String(process.env.SMTP_SKIP || "").toLowerCase() === "true") {
    console.log(`[SMTP_SKIP] Password reset code for ${toEmail}: ${code}`);
    return;
  }
  const transporter = getTransporter();
  const appName = process.env.APP_NAME || "Stone Odds";
  const from = process.env.SMTP_FROM || process.env.SMTP_USER;

  if (!from) {
    throw new Error("SMTP_FROM or SMTP_USER must be configured.");
  }

  const started = Date.now();
  try {
    await transporter.sendMail({
      from,
      to: toEmail,
      subject: `${appName} password reset code`,
      text: `Your ${appName} password reset code is ${code}. It expires in 10 minutes.`,
      html: `<p>You requested to reset your <strong>${appName}</strong> password.</p><h2>${code}</h2><p>This code expires in 10 minutes.</p>`,
    });
    console.log(`[SMTP] password reset email sent to ${toEmail} in ${Date.now() - started}ms`);
  } catch (error) {
    console.error("[SMTP] password reset email failed:", error);
    throw error;
  }
};
