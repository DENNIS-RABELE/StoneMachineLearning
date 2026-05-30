const express = require("express");
const rateLimiter = require("../middleware/rateLimiter");
const authenticateToken = require("../middleware/authenticateToken");
const authController = require("../controllers/authController");

const router = express.Router();

router.post("/register", rateLimiter, authController.register);
router.post("/verify-email", rateLimiter, authController.verifyEmail);
router.post("/login", rateLimiter, authController.login);
router.post("/forgot-password", rateLimiter, authController.forgotPassword);
router.post("/reset-password", rateLimiter, authController.resetPassword);
router.post(
  "/resend-verification",
  rateLimiter,
  authController.resendVerification,
);
router.get("/user/profile", authenticateToken, authController.getProfile);
router.post("/logout", authenticateToken, authController.logout);
router.post("/activity", authenticateToken, authController.trackActivity);
router.get("/support/enquiries", authenticateToken, authController.listSupportEnquiries);
router.post("/support/enquiries", authenticateToken, authController.createSupportEnquiry);

module.exports = router;


