const express = require("express");
const authenticateToken = require("../middleware/authenticateToken");
const demoMoneyController = require("../controllers/demoMoneyController");

const router = express.Router();

router.patch("/user/demo-money", authenticateToken, demoMoneyController.updateDemoMoney);
router.post(
  "/user/demo-money/deduct",
  authenticateToken,
  demoMoneyController.deductDemoMoney,
);
router.get("/wallet/me", authenticateToken, demoMoneyController.getWalletSnapshot);
router.post("/demo-money/allocate", demoMoneyController.allocateDemoMoney);

module.exports = router;
