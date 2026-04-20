document.addEventListener("DOMContentLoaded", () => {
  initVerificationInputs();
  setAuthContainerVisible(false);
  initializeProfileCard();
  updateLogoutButtonVisibility();
  updateDashboardPanelVisibility();
});
const API_BASE =
  window.location.protocol === "file:" || window.location.port !== "3000"
    ? "http://localhost:3000"
    : "";
let pendingVerificationEmail = "";
let pendingPasswordResetEmail = "";
let currentUserProfile = null;
let currentAccountMode = "demo";

function formatCurrency(value) {
  const numeric = Number(value || 0);
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
  }).format(Number.isFinite(numeric) ? numeric : 0);
}

async function authFetch(path, options = {}) {
  const token = localStorage.getItem("token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  const raw = await response.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { error: raw || "Unexpected server response" };
  }

  return { response, data };
}

function updateProfileCardUI(user) {
  const card = document.getElementById("profileCard");
  const nameEl = document.getElementById("profileName");
  const emailEl = document.getElementById("profileEmail");
  const balanceEl = document.getElementById("profileBalance");

  if (!card || !nameEl || !emailEl || !balanceEl) return;

  if (!user || currentAccountMode !== "demo") {
    card.style.display = "none";
    return;
  }

  const fullName = `${user.firstname || ""} ${user.lastname || ""}`.trim();
  nameEl.textContent = fullName || "Bettor";
  emailEl.textContent = user.email || "";
  balanceEl.textContent = formatCurrency(user.demo_balance);
  card.style.display = "block";
}

function updateLogoutButtonVisibility() {
  const logoutBtn = document.getElementById("headerLogoutBtn");
  if (!logoutBtn) return;

  const token = localStorage.getItem("token");
  logoutBtn.style.display = token ? "inline-flex" : "none";
}

function updateDashboardPanelVisibility() {
  const panel = document.getElementById("dashboardPanel");
  if (!panel) return;

  const token = localStorage.getItem("token");
  panel.style.display = token ? "block" : "none";
}

async function initializeProfileCard() {
  const modeSelect = document.getElementById("accountModeSelect");
  if (modeSelect) currentAccountMode = modeSelect.value || "demo";

  const token = localStorage.getItem("token");
  if (!token) {
    updateProfileCardUI(null);
    return;
  }

  await loadProfileCard();
}

async function loadProfileCard() {
  try {
    const { response, data } = await authFetch("/api/user/profile", {
      method: "GET",
    });

    if (!response.ok) {
      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem("token");
      }
      updateProfileCardUI(null);
      return;
    }

    currentUserProfile = data.user || null;
    updateProfileCardUI(currentUserProfile);
    updateLogoutButtonVisibility();
    updateDashboardPanelVisibility();
  } catch (error) {
    console.error("Profile load failed:", error);
    updateProfileCardUI(null);
    updateLogoutButtonVisibility();
    updateDashboardPanelVisibility();
  }
}

function getCodeInputs() {
  return Array.from(document.querySelectorAll(".code-input"));
}

function clearCodeInputs() {
  const inputs = getCodeInputs();
  inputs.forEach((input) => {
    input.value = "";
  });
}

function focusFirstCodeInput() {
  const inputs = getCodeInputs();
  if (inputs.length > 0) {
    inputs[0].focus();
  }
}

function initVerificationInputs() {
  const inputs = getCodeInputs();

  inputs.forEach((input, index) => {
    input.addEventListener("keydown", (event) => {
      if (event.key === "Backspace" && !input.value && index > 0) {
        inputs[index - 1].focus();
      }
    });

    input.addEventListener("paste", (event) => {
      event.preventDefault();
      const pasted = (event.clipboardData?.getData("text") || "")
        .replace(/\D/g, "")
        .slice(0, inputs.length);

      pasted.split("").forEach((char, i) => {
        if (inputs[i]) {
          inputs[i].value = char;
        }
      });

      const focusIndex = Math.min(pasted.length, inputs.length - 1);
      if (inputs[focusIndex]) {
        inputs[focusIndex].focus();
      }
    });
  });
}

// 👇 Make these GLOBAL (important!)
function setAuthContainerVisible(isVisible) {
  const container = document.querySelector(".auth-container");
  if (!container) return;
  container.classList.toggle("open", Boolean(isVisible));
}

function closeAuthModal() {
  setAuthContainerVisible(false);
}

function showLogin() {
  setAuthContainerVisible(true);
  document.getElementById("auth-container").innerHTML = getLogin();
}

function showRegister() {
  setAuthContainerVisible(true);
  document.getElementById("auth-container").innerHTML = getRegister();
}

function showForgotPassword() {
  setAuthContainerVisible(true);
  document.getElementById("auth-container").innerHTML = getForgotPassword();
}

function getRegister() {
  return `<div id="signupForm" class="auth-form active">
                <form id="signupFormElement">
                    <div class="form-group">
                        <label for="firstname">Firstname</label>
                        <div class="input-with-icon">
                            <i class="fas fa-user"></i>
                            <input name="firstName" type="text" id="firstname" class="form-control" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="lastname">Lastname</label>
                        <div class="input-with-icon">
                            <i class="fas fa-user"></i>
                            <input name="lastName" type="text" id="lastname" class="form-control" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="signupEmail">Email Address</label>
                        <div class="input-with-icon">
                            <i class="fas fa-envelope"></i>
                            <input name="signupEmail" type="email" id="signupEmail" class="form-control" placeholder="Enter your email" required>
                        </div>
                    </div>

                     <div class="form-group">
                        <label for="date_of_birth">Date of Birth</label>
                        <input name="date_of_birth" type="date" id="date_of_birth" class="form-control" required>
                    </div>

                    <div class="form-group">
                        <label for="nationality">Nationality</label>
                        <div class="input-with-icon">
                            <i class="fas fa-globe"></i>
                            <input name="nationality" type="text" id="nationality", class="form-control">
                        </div>
                    </div>

                     <div class="form-group">
                        <label for="id_number">ID number</label>
                        <input name="id_number" type="number" id="id_number", class="form-control">
                    </div>


                      <div class="form-group">
                        <label for="physical_address">Physical Address</label>
                        <input name="physical_address" type="text" id="physical_address", class="form-control">
                    </div>

                    <div class="form-group">
                        <label for="signupPassword">Password</label>
                        <div class="input-with-icon">
                            <i class="fas fa-lock"></i>
                            <input name="signupPassword" type="password" id="signupPassword" class="form-control" placeholder="Create a password (min. 8 characters)" required minlength="8">
                            <span class="password-toggle" onclick="togglePassword('signupPassword')">
                            </span>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="confirmPassword">Confirm Password</label>
                        <div class="input-with-icon">
                            <i class="fas fa-lock"></i>
                            <input name="confirmPassword" type="password" id="confirmPassword" class="form-control" required>
                        </div>
                    </div>

                    <div class="checkbox-group">
                        <input type="checkbox" id="terms" required>
                        <label for="terms">I agree to the <a href="#" onclick="showTerms()">Terms of Service</a> and <a href="#" onclick="showPrivacy()">Privacy Policy</a></label>
                    </div>

                    <button type="button" id="signupSubmitBtn" class="btn" onclick="handleSignup(event)">Create Account</button>

                    <p style="text-align: center; margin-top: 20px; color: #aaa;">
                        Already have an account? 
                        <a href="#" onclick="showLogin()"; style="color: #00d4ff; text-decoration: none;">Sign in here</a>
                    </p>
                </form>
            </div>`;
}

function setSignupLoading(isLoading) {
  const button = document.getElementById("signupSubmitBtn");
  if (!button) return;

  if (isLoading) {
    if (!button.dataset.originalText) {
      button.dataset.originalText = button.textContent || "Create Account";
    }
    button.disabled = true;
    button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending code...';
    return;
  }

  button.disabled = false;
  button.textContent = button.dataset.originalText || "Create Account";
}

function getLogin() {
  return `<div id="loginForm" class="auth-form active">
                <div class="auth-header">
                    <h2>Welcome Back</h2>
                    <p>Sign in to your Stone Odds account</p>
                </div>

                <form id="loginFormElement" onsubmit="handleLogin(event)">
                    <div class="form-group">
                        <label for="loginEmail">Email Address</label>
                        <div class="input-with-icon">
                            <i class="fas fa-envelope"></i>
                            <input name="loginEmail"type="email" id="loginEmail" class="form-control" placeholder="Enter your email" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="loginPassword">Password</label>
                        <div class="input-with-icon">
                            <i class="fas fa-lock"></i>
                            <input type="password" id="loginPassword" class="form-control" placeholder="Enter your password" required>
                            <span class="password-toggle" onclick="togglePassword('loginPassword')">
                               
                            </span>
                        </div>
                    </div>

                    <div class="checkbox-group">
                        <input type="checkbox" id="rememberMe">
                        <label for="rememberMe">Remember me</label>
                        <a href="#" onclick="showForgotPassword()" style="margin-left: auto;">Forgot Password?</a>
                    </div>

                    <button type="submit" class="btn">Sign In</button>

                    <div class="divider">
                        <span>Or continue with</span>
                    </div>

                    <p style="text-align: center; margin-top: 20px; color: #aaa;">
                        Don't have an account? 
                        <a href="#" onclick="showRegister()";  style="color: #00d4ff; text-decoration: none;">Sign up here</a>
                    </p>
                </form>
            </div>`;
}

function getForgotPassword() {
  return `<div id="forgotPasswordForm" class="auth-form active">
                <div class="auth-header">
                    <h2>Reset Password</h2>
                    <p>Enter your email to receive a 6-digit reset code.</p>
                </div>

                <form id="forgotPasswordRequestForm" onsubmit="sendPasswordResetCode(event)">
                    <div class="form-group">
                        <label for="forgotEmail">Email Address</label>
                        <div class="input-with-icon">
                            <i class="fas fa-envelope"></i>
                            <input name="forgotEmail" type="email" id="forgotEmail" class="form-control" placeholder="Enter your email" required>
                        </div>
                    </div>

                    <button type="submit" class="btn">Send Reset Code</button>
                </form>

                <div id="resetStep" style="display: none; margin-top: 20px;">
                    <div class="form-group">
                        <label for="resetCode">Reset Code</label>
                        <input type="text" id="resetCode" class="form-control" maxlength="6" inputmode="numeric" pattern="[0-9]*" placeholder="Enter 6-digit code" required>
                    </div>

                    <div class="form-group">
                        <label for="newPassword">New Password</label>
                        <div class="input-with-icon">
                            <i class="fas fa-lock"></i>
                            <input type="password" id="newPassword" class="form-control" placeholder="New password (min. 8 characters)" minlength="8" required>
                        </div>
                    </div>

                    <div class="form-group">
                        <label for="confirmNewPassword">Confirm New Password</label>
                        <div class="input-with-icon">
                            <i class="fas fa-lock"></i>
                            <input type="password" id="confirmNewPassword" class="form-control" placeholder="Confirm new password" required>
                        </div>
                    </div>

                    <button type="button" class="btn" onclick="submitPasswordReset(event)">Reset Password</button>
                </div>

                <p id="forgotPasswordMessage" style="margin-top: 16px; color: #aaa;"></p>

                <p style="text-align: center; margin-top: 20px; color: #aaa;">
                    Remembered your password?
                    <a href="#" onclick="showLogin()" style="color: #00d4ff; text-decoration: none;">Sign in here</a>
                </p>
            </div>`;
}

async function handleSignup(event) {
  event.preventDefault();
  event.stopPropagation(); // Add this line

  // Get form values
  const firstname = document.getElementById("firstname")?.value;
  const lastname = document.getElementById("lastname")?.value;
  const email = document.getElementById("signupEmail")?.value;
  const dateOfBirth = document.getElementById("date_of_birth")?.value;
  const nationality = document.getElementById("nationality")?.value;
  const idNumber = document.getElementById("id_number")?.value;
  const physicalAddress = document.getElementById("physical_address")?.value;
  const password = document.getElementById("signupPassword")?.value;
  const confirmPassword = document.getElementById("confirmPassword")?.value;

  const terms = document.getElementById("terms")?.checked;

  // Check if elements exist
  if (
    !firstname ||
    !lastname ||
    !email ||
    !dateOfBirth ||
    !nationality ||
    !idNumber ||
    !physicalAddress ||
    !password ||
    !confirmPassword
  ) {
    alert("Please fill in all required fields");
    return;
  }

  // Basic validation
  if (!terms) {
    alert("Please agree to the Terms of Service and Privacy Policy");
    return;
  }

  if (password !== confirmPassword) {
    alert("Passwords do not match!");
    return;
  }

  const payload = {
    firstname,
    lastname,
    email,
    dateOfBirth,
    nationality,
    idNumber,
    physicalAddress,
    password,
  };

  setSignupLoading(true);

  try {
    const response = await fetch(`${API_BASE}/api/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw || "Unexpected server response" };
    }

    if (!response.ok) {
      alert(data.error || "Registration failed");
      return;
    }

    pendingVerificationEmail = email.trim().toLowerCase();

    // Close auth modal before showing verification page
    setAuthContainerVisible(false);
  } catch (error) {
    console.error("Signup request failed:", error);
    alert("Could not connect to server");
    return;
  } finally {
    setSignupLoading(false);
  }

  // Show the verification page
  const verificationPage = document.getElementById("verificationPage");
  const mainContent = document.getElementById("mainContent");

  if (verificationPage && mainContent) {
    verificationPage.style.display = "flex";
    mainContent.style.display = "none";
  }
  clearCodeInputs();
  focusFirstCodeInput();

  // Show email in verification page
  const emailSpan = document.getElementById("verificationEmail");
  if (emailSpan) {
    emailSpan.textContent = `Verification code sent to: ${pendingVerificationEmail}`;
  }
}

async function handleLogin(event) {
  event.preventDefault();

  const email = document.getElementById("loginEmail")?.value;
  const password = document.getElementById("loginPassword")?.value;

  if (!email || !password) {
    alert("Please enter email and password");
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw || "Unexpected server response" };
    }

    if (!response.ok) {
      alert(data.error || "Login failed");
      return;
    }

    if (data.token) {
      localStorage.setItem("token", data.token);
    }

    await loadProfileCard();
    updateLogoutButtonVisibility();
    updateDashboardPanelVisibility();
    window.location.href = "/dashboard";
  } catch (error) {
    console.error("Login request failed:", error);
    alert("Could not connect to server");
  }
}

async function logout() {
  const token = localStorage.getItem("token");

  try {
    if (token) {
      await authFetch("/api/logout", { method: "POST" });
    }
  } catch (error) {
    console.error("Logout request failed:", error);
  } finally {
    localStorage.removeItem("token");
    currentUserProfile = null;
    updateProfileCardUI(null);
    updateLogoutButtonVisibility();
    updateDashboardPanelVisibility();

    const verificationPage = document.getElementById("verificationPage");
    const mainContent = document.getElementById("mainContent");
    if (verificationPage && mainContent) {
      verificationPage.style.display = "none";
      mainContent.style.display = "flex";
    }

    setAuthContainerVisible(false);
    alert("Logged out successfully");
  }
}

async function refreshProfileCard() {
  await loadProfileCard();
}

function handleAccountModeChange() {
  const modeSelect = document.getElementById("accountModeSelect");
  currentAccountMode = modeSelect?.value || "demo";

  if (currentAccountMode === "demo" && localStorage.getItem("token")) {
    loadProfileCard();
    return;
  }

  updateProfileCardUI(null);
}

function toggleSetAmount() {
  const controls = document.getElementById("setAmountControls");
  if (!controls) return;
  controls.style.display = controls.style.display === "none" ? "block" : "none";
}

async function setDemoBalance() {
  if (currentAccountMode !== "demo") {
    alert("Switch to Demo account to set demo amount");
    return;
  }

  const input = document.getElementById("demoAmountInput");
  const amount = Number(input?.value);

  if (!Number.isFinite(amount) || amount < 0) {
    alert("Enter a valid non-negative amount");
    return;
  }

  try {
    const { response, data } = await authFetch("/api/user/demo-money", {
      method: "PATCH",
      body: JSON.stringify({ amount }),
    });

    if (!response.ok) {
      alert(data.error || "Could not update demo balance");
      return;
    }

    if (currentUserProfile) {
      currentUserProfile.demo_balance = data.demo_balance;
      updateProfileCardUI(currentUserProfile);
    }
    const controls = document.getElementById("setAmountControls");
    if (controls) controls.style.display = "none";
    if (input) input.value = "";
  } catch (error) {
    console.error("Set demo balance failed:", error);
    alert("Could not connect to server");
  }
}

async function sendPasswordResetCode(event) {
  event.preventDefault();

  const email = document
    .getElementById("forgotEmail")
    ?.value?.trim()
    .toLowerCase();
  if (!email) {
    alert("Please enter your email");
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/forgot-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw || "Unexpected server response" };
    }

    if (!response.ok) {
      alert(data.error || "Could not send reset code");
      return;
    }

    pendingPasswordResetEmail = email;
    const resetStep = document.getElementById("resetStep");
    const message = document.getElementById("forgotPasswordMessage");
    if (resetStep) resetStep.style.display = "block";
    if (message) {
      message.textContent = "If the email exists, a reset code has been sent.";
      message.style.color = "#00d4ff";
    }
  } catch (error) {
    console.error("Forgot password request failed:", error);
    alert("Could not connect to server");
  }
}

async function submitPasswordReset(event) {
  if (event) event.preventDefault();

  const code = document
    .getElementById("resetCode")
    ?.value?.trim()
    .replace(/\D/g, "");
  const newPassword = document.getElementById("newPassword")?.value;
  const confirmNewPassword =
    document.getElementById("confirmNewPassword")?.value;

  if (!pendingPasswordResetEmail) {
    alert("Request a reset code first");
    return;
  }

  if (!code || code.length !== 6) {
    alert("Enter the 6-digit reset code");
    return;
  }

  if (!newPassword || newPassword.length < 8) {
    alert("New password must be at least 8 characters");
    return;
  }

  if (newPassword !== confirmNewPassword) {
    alert("Passwords do not match");
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: pendingPasswordResetEmail,
        code,
        newPassword,
      }),
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw || "Unexpected server response" };
    }

    if (!response.ok) {
      alert(data.error || "Password reset failed");
      return;
    }

    alert("Password reset successful. Please log in.");
    pendingPasswordResetEmail = "";
    setAuthContainerVisible(false);
  } catch (error) {
    console.error("Reset password request failed:", error);
    alert("Could not connect to server");
  }
}

function moveToNext(input, position) {
  if (!input) return;
  input.value = input.value.replace(/\D/g, "").slice(0, 1);
  if (input.value.length !== 1) return;
  const inputs = getCodeInputs();
  if (position < inputs.length) {
    inputs[position].focus();
  }
}

function goBackToSignup() {
  const verificationPage = document.getElementById("verificationPage");
  const mainContent = document.getElementById("mainContent");
  if (verificationPage && mainContent) {
    verificationPage.style.display = "none";
    mainContent.style.display = "flex";
  }
  showRegister();
}

function closeVerificationPage() {
  const verificationPage = document.getElementById("verificationPage");
  const mainContent = document.getElementById("mainContent");
  if (verificationPage && mainContent) {
    verificationPage.style.display = "none";
    mainContent.style.display = "flex";
  }
  clearCodeInputs();
}

async function verifyCode() {
  if (!pendingVerificationEmail) {
    alert("Please register first");
    return;
  }

  const code = getCodeInputs()
    .map((input) => input.value.trim())
    .join("")
    .replace(/\D/g, "");

  if (code.length !== 6) {
    alert("Enter the 6-digit verification code");
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: pendingVerificationEmail, code }),
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw || "Unexpected server response" };
    }

    if (!response.ok) {
      alert(data.error || "Email verification failed");
      return;
    }

    if (data.token) {
      localStorage.setItem("token", data.token);
    }

    alert("Email verified and account created. You can now log in.");
    pendingVerificationEmail = "";
    clearCodeInputs();
    goBackToSignup();
    setAuthContainerVisible(false);
  } catch (error) {
    console.error("Verify request failed:", error);
    alert("Could not connect to server");
  }
}

async function resendVerificationCode() {
  if (!pendingVerificationEmail) {
    alert("Please register first");
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/resend-verification`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: pendingVerificationEmail }),
    });

    const raw = await response.text();
    let data = {};
    try {
      data = raw ? JSON.parse(raw) : {};
    } catch {
      data = { error: raw || "Unexpected server response" };
    }

    if (!response.ok) {
      alert(data.error || "Could not resend code");
      return;
    }

    alert("Verification code resent");
  } catch (error) {
    console.error("Resend request failed:", error);
    alert("Could not connect to server");
  }
}

function navigateToDashboard() {
  window.location.href = "/dashboard";
}

function startBetting() {
  navigateToDashboard();
}

function navigateToHome() {
  window.location.href = "/";
}

function togglePassword(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === "password" ? "text" : "password";
}

function showTerms() {
  alert("Terms of Service will be available here.");
}

function showPrivacy() {
  alert("Privacy Policy will be available here.");
}

function showResponsibleGaming() {
  alert("Responsible Gaming information will be available here.");
}

function showContactSupport() {
  alert("Contact support at support@stoneodds.local");
}


