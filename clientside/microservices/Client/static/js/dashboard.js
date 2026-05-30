function resolveApiBase() {
  const { hostname, port, protocol } = window.location;
  const isLocalHost = hostname === "localhost" || hostname === "127.0.0.1";

  // If dashboard is already served by the API process, use same-origin calls.
  if (port === "3000") {
    return "";
  }

  // For local static/dev servers (5500, 5501, 5633, 10000, etc.), point to game API.
  if (isLocalHost) {
    return `${protocol}//${hostname}:3000`;
  }

  return "";
}

const API_BASE = resolveApiBase();

const menuButtons = document.querySelectorAll(".menu-btn");
const dashboardViews = document.querySelectorAll(".dashboard-view");
const mainTitle = document.getElementById("mainTitle");
const mainSubtitle = document.getElementById("mainSubtitle");

const selectedCharacterMeta = document.getElementById("selectedCharacterMeta");
const oddsBoardGrid =
  document.getElementById("characterOddsBoard") ||
  document.getElementById("oddsBoardGrid");
const gameStage = document.getElementById("gameStage");
const gameStageCover = document.getElementById("gameStageCover");
const gameplayFrame = document.getElementById("unityGameplayFrame");
const roundCountdown = document.getElementById("roundCountdown");
const slipList = document.getElementById("slipList");
const slipEmpty = document.getElementById("slipEmpty");
const placeBetBtn = document.getElementById("placeBetBtn");
const roundResult = document.getElementById("roundResult");
const liveBets = document.getElementById("liveBets");
const pastSlipsList = document.getElementById("pastSlipsList");
const slipContainer = document.querySelector(".slip-container");
const dashboardLogoutBtn = document.getElementById("dashboardLogoutBtn");
const dashboardBalanceChip = document.getElementById("dashboardBalanceChip");
const dashboardBalanceValue = document.getElementById("dashboardBalanceValue");
const dashboardUserChip = document.getElementById("dashboardUserChip");
const dashboardUserName = document.getElementById("dashboardUserName");
const outcomesGroups = document.getElementById("outcomesGroups");
const outcomesLatestRound = document.getElementById("outcomesLatestRound");
const outcomesTotalCount = document.getElementById("outcomesTotalCount");
const outcomesCharacterCount = document.getElementById(
  "outcomesCharacterCount",
);
const outcomesMarketCount = document.getElementById("outcomesMarketCount");
const perfCharacterNav = document.getElementById("perfCharacterNav");
const characterPerfChart = document.getElementById("characterPerfChart");
const charChartScrollWrapper = document.getElementById(
  "charChartScrollWrapper",
);
const charChartRangeNote = document.getElementById("charChartRangeNote");
const charChartTitle = document.getElementById("charChartTitle");
const charChartButtons = document.querySelectorAll("[data-char-chart]");
const charFrameButtons = document.querySelectorAll("[data-char-frame]");
const generalChartButtons = document.querySelectorAll("[data-general-chart]");
const generalFrameButtons = document.querySelectorAll("[data-general-frame]");
const generalPieWrap = document.getElementById("generalPieWrap");
const generalLineWrap = document.getElementById("generalLineWrap");
const generalPie = document.getElementById("generalPie");
const lineCurrent = document.getElementById("lineCurrent");
const lineCompare = document.getElementById("lineCompare");
const comparePerfChart = document.getElementById("comparePerfChart");
const compareChartScrollWrapper = document.getElementById(
  "compareChartScrollWrapper",
);
const compareChartRangeNote = document.getElementById("compareChartRangeNote");
const compareChartTitle = document.getElementById("compareChartTitle");
const compareSeriesInfo = document.getElementById("compareSeriesInfo");
const compareChartButtons = document.querySelectorAll("[data-compare-chart]");
const compareFrameButtons = document.querySelectorAll("[data-compare-frame]");
const compareFrameControlGroup = document.getElementById(
  "compareFrameControlGroup",
);
const accountMenuBtn = document.getElementById("accountMenuBtn");
const accountSubmenu = document.getElementById("accountSubmenu");
const accountRealBtn = document.getElementById("accountRealBtn");
const accountDemoBtn = document.getElementById("accountDemoBtn");
const demoBalanceCard = document.getElementById("demoBalanceCard");
const demoUserName = document.getElementById("demoUserName");
const demoBalanceValue = document.getElementById("demoBalanceValue");
const demoBalanceSetBtn = document.getElementById("demoBalanceSetBtn");
const demoBalanceEditor = document.getElementById("demoBalanceEditor");
const demoBalanceInput = document.getElementById("demoBalanceInput");
const demoBalanceSaveBtn = document.getElementById("demoBalanceSaveBtn");
const demoBalanceMessage = document.getElementById("demoBalanceMessage");
const slipStakeInput = document.getElementById("slipStakeInput");
const slipPossibleWinnings = document.getElementById("slipPossibleWinnings");
const globalGameplayState = document.getElementById("globalGameplayState");
const supportEnquiryForm = document.getElementById("supportEnquiryForm");
const supportCategory = document.getElementById("supportCategory");
const supportSubject = document.getElementById("supportSubject");
const supportMessage = document.getElementById("supportMessage");
const supportStatus = document.getElementById("supportStatus");
const supportThreadList = document.getElementById("supportThreadList");

const betSlip = [];
let characters = [];
let selectedCharacterId = null;
let isUserLoggedIn = false;
const defaultGameplaySrc =
  gameplayFrame?.dataset.defaultSrc || gameplayFrame?.getAttribute("src") || "";
const BETTING_VIEW_ID = "view-betting";
const performanceFrameConfig = {
  "5min": { step: 5, unit: "m" },
  "1hr": { step: 1, unit: "h" },
  "2hr": { step: 2, unit: "h" },
};
const PERFORMANCE_SCORE_STEP = 0.1;
const performanceFrameRoundLimits = {
  "5min": 50,
  "1hr": 50,
  "2hr": 50,
};
const historyBarsCount = 50;
let selectedCharChart = "divergence";
let selectedCharFrame = "5min";
let selectedGeneralChart = "pie";
let selectedGeneralFrame = "6hrs";
let selectedCompareChart = "divergence";
let selectedCompareFrame = "5min";
let selectedAnalysisCharacterId = null;
let divergenceChart = null;
let compareBarsChart = null;
let performanceControlsBound = false;
const performanceData = {};
let characterHistoryByName = {};
let currentUserProfile = null;
let roundSecondsRemaining = 0;
let roundTimerUnsubscribe = null;
let liveEventSource = null;
let liveFallbackHandle = null;
let liveReconnectHandle = null;
let liveCharacterSubscriptionId = null;
let gameplayStateWebSocket = null;
let gameplayStateReconnectHandle = null;
let gameplayMetaSyncHandle = null;
let latestGlobalGameplayState = null;
let latestActiveBuildUrl = null;
let globalGameplayStateActive = false;
let latestLiveResultId = null;
let latestLiveOptionsVersion = null;
let latestLiveRoundId = null;
let latestOptionsPayload = null;
let latestOptionsByCharacter = new Map();
let latestSlipActivityRequestId = 0;
const STONE_THROW_OUTCOME_ROUND_LIMIT = 2;
let latestSlipActivityPayload = null;
let latestResolvedOutcomeRows = [];
let latestPostGameStatsPayload = null;
let latestPerformancePayload = null;
let latestResolvedOutcomeLookup = new Map();
const GAMEPLAY_GAME_2 = "Game2";
const ROUND_LOOP_SECONDS = 200;
const STATS_WINDOW_SECONDS = 120;
const ACTIVE_ROUND_STATS_SRC = new URL(
  "../../stats/inner.html",
  window.location.href,
).toString();
const GAMEPLAY_SCHEDULE_STORAGE_KEY = "stone_odds_gameplay_schedule";
const GAME_PRELOAD_THRESHOLD_SECONDS = 30;
const BET_LOCK_THRESHOLD_SECONDS = 10;
let gameplayIntermissionActive = false;
let gameplayIntermissionHandle = null;
let pendingRoundSecondsRemaining = null;
let currentGameplayGame = null;
let gameplayFrames = [];
let activeGameplayFrameIndex = 0;
let gamePreloadIframe = null;
let gamePreloadSrc = null;
let gamePreloadActivationPending = null;
let gamePreloadedForRound = false;
let liveSnapshotRequest = null;
let lastRenderedRoundCountdown = null;
let lastRenderedRoundCountdownState = "";
let performanceViewDirty = false;
let bettingLocked = false;

function isBettingLocked() {
  const remaining = Number(roundSecondsRemaining) || 0;
  return remaining > 0 && remaining <= BET_LOCK_THRESHOLD_SECONDS;
}

function updateBettingLockUI() {
  bettingLocked = isBettingLocked();
  if (!placeBetBtn) return;
  const shouldDisable = !isUserLoggedIn || bettingLocked;
  placeBetBtn.disabled = shouldDisable;
  placeBetBtn.classList.toggle("disabled", shouldDisable);
  if (bettingLocked) {
    placeBetBtn.title = "Betting is locked in the last 10 seconds";
  } else if (!isUserLoggedIn) {
    placeBetBtn.title = "Login to place bets";
  } else {
    placeBetBtn.title = "";
  }
}

function isPreloadDebugEnabled() {
  try {
    const params = new URLSearchParams(window.location.search || "");
    if (params.get("debugPreload") === "1") return true;
    return window.localStorage.getItem("dashboard_debug_preload") === "1";
  } catch {
    return false;
  }
}

function debugPreload(...args) {
  if (!isPreloadDebugEnabled()) return;
  console.log(...args);
}

function updatePreloadDebugIndicator() {
  if (!isPreloadDebugEnabled() || !globalGameplayState) return;
  const info = window.__dashboardPreload || {};
  const remaining = Number(info.roundSecondsRemaining);
  const remainingText = Number.isFinite(remaining) ? `${remaining}s` : "n/a";
  const requestedAt = info.preloadRequestedAt
    ? new Date(info.preloadRequestedAt).toLocaleTimeString()
    : "n/a";
  const loadedAt = info.preloadLoadAt
    ? new Date(info.preloadLoadAt).toLocaleTimeString()
    : "n/a";
  const readyAt = info.preloadReadyAt
    ? new Date(info.preloadReadyAt).toLocaleTimeString()
    : "n/a";
  const src = String(
    info.preloadRequestedSrc ||
      info.preloadLoadSrc ||
      info.preloadReadySrc ||
      "",
  ).slice(0, 60);

  globalGameplayState.textContent =
    `${globalGameplayState.textContent.split("\n")[0]}\n` +
    `Preload(rem=${remainingText}) req=${requestedAt} load=${loadedAt} ready=${readyAt} src=${src}`;
}

function normalizeGameplaySrc(rawSrc) {
  if (!rawSrc) return "";
  try {
    const url = new URL(rawSrc, window.location.origin);
    if (url.origin === window.location.origin) {
      if (
        url.pathname === "/gameplay/embed" ||
        url.pathname === "/gameplay/embed/"
      ) {
        url.pathname = "/games/embed/";
      } else if (
        url.pathname === "/gameplay/embed-meta" ||
        url.pathname === "/gameplay/embed-meta/"
      ) {
        url.pathname = "/games/embed-meta/";
      }
    }
    return url.toString();
  } catch {
    return rawSrc
      .replace("/gameplay/embed-meta/", "/games/embed-meta/")
      .replace("/gameplay/embed/", "/games/embed/");
  }
}

function buildGameplayFrameSrc(gameName) {
  if (!defaultGameplaySrc) return "";
  const url = new URL(
    normalizeGameplaySrc(defaultGameplaySrc),
    window.location.origin,
  );
  if (gameName) {
    url.searchParams.set("game", gameName);
  } else {
    url.searchParams.delete("game");
  }
  return url.toString();
}

function initGameplayFrameStack() {
  if (!gameplayFrame || !gameStage || gameplayFrames.length) return;

  gameplayFrame.classList.add("gameplay-frame-active");
  gameplayFrame.setAttribute("aria-hidden", "false");
  gameplayFrame.dataset.frameKey = defaultGameplaySrc ? "default-gameplay" : "";
  gameplayFrame.dataset.frameSrc = defaultGameplaySrc
    ? normalizeGameplaySrc(defaultGameplaySrc)
    : "";
  // Track readiness for the visible frame too (important after reloads).
  attachGameplayFrameReadyTracker(gameplayFrame);

  const preloadFrame = gameplayFrame.cloneNode(false);
  preloadFrame.id = "unityGameplayFramePreload";
  preloadFrame.removeAttribute("src");
  preloadFrame.removeAttribute("loading");
  preloadFrame.setAttribute("loading", "eager");
  preloadFrame.setAttribute("aria-hidden", "true");
  preloadFrame.setAttribute("tabindex", "-1");
  preloadFrame.dataset.frameKey = "";
  preloadFrame.dataset.frameSrc = "";
  gameStage.appendChild(preloadFrame);

  attachGameplayFrameReadyTracker(preloadFrame);
  gameplayFrames = [gameplayFrame, preloadFrame];
  activeGameplayFrameIndex = 0;
}

function getActiveGameplayFrame() {
  initGameplayFrameStack();
  return gameplayFrames[activeGameplayFrameIndex] || null;
}

function getInactiveGameplayFrame() {
  initGameplayFrameStack();
  return gameplayFrames[activeGameplayFrameIndex === 0 ? 1 : 0] || null;
}

function syncGameplayFrameState(frame, targetKey, targetSrc) {
  if (!frame) return;
  frame.dataset.frameKey = targetKey || "";
  frame.dataset.frameSrc = targetSrc || "";
}

function setGameplayFrameActive(frame) {
  initGameplayFrameStack();
  const nextIndex = gameplayFrames.indexOf(frame);
  if (nextIndex === -1) return;

  gameplayFrames.forEach((candidate, index) => {
    const isActive = index === nextIndex;
    candidate.classList.toggle("gameplay-frame-active", isActive);
    candidate.setAttribute("aria-hidden", isActive ? "false" : "true");
    if (!isActive) {
      candidate.setAttribute("tabindex", "-1");
    } else {
      candidate.removeAttribute("tabindex");
    }
  });
  activeGameplayFrameIndex = nextIndex;
}

function showGameplayCover() {
  if (!gameStageCover) return;
  gameStageCover.hidden = false;
}

function hideGameplayCover() {
  if (!gameStageCover) return;
  gameStageCover.hidden = true;
}

function isGameplayFrameReady(frame) {
  return frame?.dataset?.unityReady === "true";
}

function markGameplayFrameReady(frame) {
  if (!frame) return;
  frame.dataset.unityReady = "true";
  if (frame.id === "unityGameplayFramePreload") {
    frame.dataset.preloadReadyAt = String(Date.now());
    window.__dashboardPreload = window.__dashboardPreload || {};
    window.__dashboardPreload.preloadReadyAt = Number(
      frame.dataset.preloadReadyAt,
    );
    window.__dashboardPreload.preloadReadySrc =
      frame.dataset.frameSrc || frame.src || "";
    debugPreload(
      "[Preload] preload iframe marked ready",
      window.__dashboardPreload,
    );
    updatePreloadDebugIndicator();
  }
  if (frame === getActiveGameplayFrame()) {
    hideGameplayCover();
  }
  if (
    gamePreloadActivationPending &&
    gamePreloadActivationPending.frame === frame
  ) {
    const {
      frame: pendingFrame,
      targetKey,
      targetSrc,
    } = gamePreloadActivationPending;
    gamePreloadActivationPending = null;
    setGameplayFrameActive(pendingFrame);
    currentGameplayGame = targetKey;
    hideGameplayCover();
  }
}

function trackUnityInnerFrameReady(frame, innerFrame) {
  if (!frame || !innerFrame) {
    markGameplayFrameReady(frame);
    return;
  }

  try {
    const loader =
      innerFrame.contentDocument?.getElementById("unity-loading-bar");
    if (!loader) {
      markGameplayFrameReady(frame);
      return;
    }

    const checkReady = () => {
      const style =
        innerFrame.contentWindow?.getComputedStyle?.(loader) ||
        window.getComputedStyle(loader);
      return (
        loader.hidden ||
        style.display === "none" ||
        style.visibility === "hidden"
      );
    };

    if (checkReady()) {
      markGameplayFrameReady(frame);
      return;
    }

    if (frame._unityObserver) {
      frame._unityObserver.disconnect();
      frame._unityObserver = null;
    }

    frame._unityObserver = new MutationObserver(() => {
      if (checkReady()) {
        frame._unityObserver?.disconnect();
        frame._unityObserver = null;
        if (frame._unityReadyTimeout) {
          clearTimeout(frame._unityReadyTimeout);
          frame._unityReadyTimeout = null;
        }
        markGameplayFrameReady(frame);
      }
    });
    frame._unityObserver.observe(loader, {
      attributes: true,
      attributeFilter: ["style", "hidden", "class"],
    });

    if (frame._unityReadyTimeout) {
      clearTimeout(frame._unityReadyTimeout);
    }
    frame._unityReadyTimeout = window.setTimeout(() => {
      frame._unityObserver?.disconnect();
      frame._unityObserver = null;
      frame._unityReadyTimeout = null;
      markGameplayFrameReady(frame);
    }, 10000);
  } catch (error) {
    markGameplayFrameReady(frame);
  }
}

function attachGameplayFrameReadyTracker(frame) {
  if (!frame || frame.dataset.readyTrackerAttached === "true") return;
  frame.dataset.readyTrackerAttached = "true";

  frame.addEventListener("load", () => {
    frame.dataset.unityReady = "false";
    frame.dataset.lastLoadAt = String(Date.now());
    frame.dataset.lastLoadSrc = frame.src || "";
    if (frame.id === "unityGameplayFramePreload") {
      window.__dashboardPreload = window.__dashboardPreload || {};
      window.__dashboardPreload.preloadLoadAt = Number(
        frame.dataset.lastLoadAt,
      );
      window.__dashboardPreload.preloadLoadSrc = frame.dataset.lastLoadSrc;
      debugPreload(
        "[Preload] preload iframe load event",
        window.__dashboardPreload,
      );
      updatePreloadDebugIndicator();
    }
    try {
      const innerFrame = frame.contentDocument?.querySelector("iframe.frame");
      if (innerFrame) {
        if (innerFrame.contentDocument?.readyState === "complete") {
          trackUnityInnerFrameReady(frame, innerFrame);
        } else {
          innerFrame.addEventListener(
            "load",
            () => trackUnityInnerFrameReady(frame, innerFrame),
            { once: true },
          );
        }
        return;
      }
    } catch {}

    // Cross-origin or unexpected embed structure: treat "loaded" as ready enough.
    markGameplayFrameReady(frame);
  });
}

function assignGameplayFrameSource(frame, targetKey, targetSrc) {
  if (!frame || !targetKey || !targetSrc) return;
  const normalizedTargetSrc = normalizeGameplaySrc(targetSrc);
  if (
    frame.dataset.frameKey === targetKey &&
    frame.dataset.frameSrc === normalizedTargetSrc
  ) {
    return;
  }
  frame.src = normalizedTargetSrc;
  syncGameplayFrameState(frame, targetKey, normalizedTargetSrc);
  attachGameplayFrameReadyTracker(frame);
}

function findGameplayFrame(targetKey, targetSrc) {
  if (!targetKey || !targetSrc) return null;
  const normalizedTargetSrc = normalizeGameplaySrc(targetSrc);
  initGameplayFrameStack();
  return (
    gameplayFrames.find(
      (frame) =>
        frame?.dataset?.frameKey === targetKey &&
        frame?.dataset?.frameSrc === normalizedTargetSrc,
    ) || null
  );
}

function activateExistingGameplayFrame(targetKey, targetSrc) {
  const frame = findGameplayFrame(targetKey, targetSrc);
  if (!frame) return false;
  gamePreloadActivationPending = null;
  setGameplayFrameActive(frame);
  currentGameplayGame = targetKey;
  hideGameplayCover();
  return true;
}

function setGameplayFrameSource(targetKey, targetSrc, forceReload = false) {
  if (!targetKey || !targetSrc) return;
  const normalizedTargetSrc = normalizeGameplaySrc(targetSrc);
  let expiresAt = null;
  try {
    // Persist with the current round end timestamp when available.
    const timer = window.TimerManager?.getState?.();
    const endTimeMs = Number(timer?.endTimeMs || 0);
    if (Number.isFinite(endTimeMs) && endTimeMs > Date.now()) {
      expiresAt = endTimeMs;
    }
  } catch {}

  const activeFrame = getActiveGameplayFrame();
  const activeFrameSrc = activeFrame?.dataset.frameSrc || "";
  if (
    currentGameplayGame === targetKey &&
    activeFrameSrc === normalizedTargetSrc &&
    !forceReload
  ) {
    if (!isGameplayFrameReady(activeFrame)) {
      showGameplayCover();
    }
    persistGameplaySchedule(targetKey, normalizedTargetSrc, expiresAt);
    return;
  }

  const inactiveFrame = getInactiveGameplayFrame();
  if (
    inactiveFrame &&
    inactiveFrame.dataset.frameKey === targetKey &&
    inactiveFrame.dataset.frameSrc === normalizedTargetSrc
  ) {
    if (isGameplayFrameReady(inactiveFrame)) {
      setGameplayFrameActive(inactiveFrame);
      currentGameplayGame = targetKey;
      hideGameplayCover();
      persistGameplaySchedule(targetKey, normalizedTargetSrc, expiresAt);
    } else {
      gamePreloadActivationPending = {
        frame: inactiveFrame,
        targetKey,
        targetSrc: normalizedTargetSrc,
      };
      showGameplayCover();
    }
    return;
  }

  if (activeFrame) {
    gamePreloadActivationPending = null;
    if (
      activeFrameSrc === normalizedTargetSrc &&
      currentGameplayGame === targetKey
    ) {
      if (forceReload) {
        assignGameplayFrameSource(activeFrame, targetKey, normalizedTargetSrc);
        showGameplayCover();
      }
      return;
    }
    assignGameplayFrameSource(activeFrame, targetKey, normalizedTargetSrc);
    showGameplayCover();
    setGameplayFrameActive(activeFrame);
    currentGameplayGame = targetKey;
    persistGameplaySchedule(targetKey, normalizedTargetSrc, expiresAt);
  }
}

function persistGameplaySchedule(targetKey, targetSrc, expiresAt = null) {
  try {
    window.sessionStorage.setItem(
      GAMEPLAY_SCHEDULE_STORAGE_KEY,
      JSON.stringify({
        key: targetKey,
        src: normalizeGameplaySrc(targetSrc),
        expiresAt:
          Number.isFinite(expiresAt) && expiresAt > 0
            ? Number(expiresAt)
            : null,
      }),
    );
  } catch {}
}

function readGameplaySchedule() {
  try {
    const raw = window.sessionStorage.getItem(GAMEPLAY_SCHEDULE_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    if (
      Number.isFinite(parsed.expiresAt) &&
      parsed.expiresAt > 0 &&
      Date.now() > parsed.expiresAt
    ) {
      try {
        window.sessionStorage.removeItem(GAMEPLAY_SCHEDULE_STORAGE_KEY);
      } catch {}
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function showDefaultGameplay(forceReload = false) {
  if (!defaultGameplaySrc) return;
  setGameplayFrameSource("default-gameplay", defaultGameplaySrc, forceReload);
}

function showActiveRoundStats() {
  setGameplayFrameSource("stats-inner", ACTIVE_ROUND_STATS_SRC);
}

function showGame2(forceReload = false) {
  const targetSrc = buildGameplayFrameSrc(GAMEPLAY_GAME_2);
  if (!targetSrc) return;
  setGameplayFrameSource(GAMEPLAY_GAME_2, targetSrc, forceReload);
}

function showActiveRoundStatsWhileGameplayRuns(targetGameplaySrc) {
  const normalizedGameplaySrc = normalizeGameplaySrc(targetGameplaySrc);
  if (!normalizedGameplaySrc) return;

  initGameplayFrameStack();
  const gameplayFrameCandidate = gameplayFrames.find(
    (frame) =>
      frame?.dataset?.frameKey === GAMEPLAY_GAME_2 &&
      frame?.dataset?.frameSrc === normalizedGameplaySrc,
  );
  if (gameplayFrameCandidate) {
    gamePreloadIframe = gameplayFrameCandidate;
    gamePreloadSrc = normalizedGameplaySrc;
  } else {
    preloadGameFrame(normalizedGameplaySrc);
  }

  const runningGameplayFrame =
    gameplayFrames.find(
      (frame) =>
        frame?.dataset?.frameKey === GAMEPLAY_GAME_2 &&
        frame?.dataset?.frameSrc === normalizedGameplaySrc,
    ) || null;
  const statsFrame =
    gameplayFrames.find((frame) => frame !== runningGameplayFrame) || null;

  if (!statsFrame) return;
  assignGameplayFrameSource(statsFrame, "stats-inner", ACTIVE_ROUND_STATS_SRC);
  setGameplayFrameActive(statsFrame);
  currentGameplayGame = "stats-inner";
  persistGameplaySchedule("stats-inner", ACTIVE_ROUND_STATS_SRC);
  hideGameplayCover();
}

function syncScheduledRoundDisplay() {
  const remaining = Math.max(0, Number(roundSecondsRemaining) || 0);
  const inStatsWindow = remaining > 0 && remaining <= STATS_WINDOW_SECONDS;
  const runningGameplaySrc = normalizeGameplaySrc(
    buildGameplayFrameSrc(GAMEPLAY_GAME_2),
  );
  const runningGameplayFrame = findGameplayFrame(
    GAMEPLAY_GAME_2,
    runningGameplaySrc,
  );

  if (inStatsWindow) {
    if (runningGameplayFrame) {
      showActiveRoundStatsWhileGameplayRuns(runningGameplaySrc);
      return;
    }
    if (currentGameplayGame !== "stats-inner") {
      showActiveRoundStats();
    }
    return;
  }

  if (currentGameplayGame === "stats-inner") {
    if (remaining <= 0 && runningGameplayFrame) {
      activateExistingGameplayFrame(GAMEPLAY_GAME_2, runningGameplaySrc);
      return;
    }
    showDefaultGameplay();
  }
}

function isPerformanceViewActive() {
  return document
    .getElementById("view-performance")
    ?.classList.contains("active");
}

function scheduleStatsAfterIntermission(delayMs) {
  if (gameplayIntermissionHandle) {
    clearTimeout(gameplayIntermissionHandle);
  }
  gameplayIntermissionHandle = setTimeout(
    () => {
      gameplayIntermissionActive = false;
      gameplayIntermissionHandle = null;
      showActiveRoundStats();

      if (Number.isFinite(pendingRoundSecondsRemaining)) {
        roundSecondsRemaining = Math.max(0, pendingRoundSecondsRemaining);
        pendingRoundSecondsRemaining = null;
        renderRoundCountdown();
        return;
      }

      fetchAndApplyLiveSnapshot();
    },
    Math.max(0, Number(delayMs) || 0),
  );
}

function restoreGameplayScheduleFromStorage() {
  const saved = readGameplaySchedule();
  if (!saved?.key || !saved?.src) return false;

  if (saved.key === GAMEPLAY_GAME_2) {
    gameplayIntermissionActive = false;
    pendingRoundSecondsRemaining = null;
    preloadGameFrame(saved.src);
    setGameplayFrameSource(saved.key, saved.src);
    return true;
  }

  if (saved.key === "stats-inner") {
    showActiveRoundStats();
    return true;
  }

  if (saved.key === "default-gameplay") {
    showDefaultGameplay();
    return true;
  }

  setGameplayFrameSource(saved.key, saved.src);
  persistGameplaySchedule(saved.key, saved.src, saved.expiresAt);
  return true;
}

function beginGameplayIntermission(resumeRemaining = null) {
  gameplayIntermissionActive = false;
  pendingRoundSecondsRemaining = null;
  roundSecondsRemaining = Number.isFinite(resumeRemaining)
    ? Math.max(0, Math.min(ROUND_LOOP_SECONDS, resumeRemaining))
    : ROUND_LOOP_SECONDS;
  renderRoundCountdown();
  const targetSrc = buildGameplayFrameSrc(GAMEPLAY_GAME_2);
  if (targetSrc) {
    console.log(
      `[Gameplay] Switching to preloaded game at ${roundSecondsRemaining}s`,
    );
    preloadGameFrame(targetSrc);
    setGameplayFrameSource(GAMEPLAY_GAME_2, targetSrc);
  }
}

function parseSingleOptionKey(optionKey) {
  const match = String(optionKey || "")
    .trim()
    .toUpperCase()
    .match(/^([FD])([1-5])$/);
  if (!match) return null;
  return {
    type: match[1] === "F" ? "FLOAT" : "DROWN",
    phase: Number.parseInt(match[2], 10),
  };
}

function parseDoubleOptionKey(optionKey) {
  const match = String(optionKey || "")
    .trim()
    .toUpperCase()
    .match(/^F([1-5])ANDD([1-5])$/);
  if (!match) return null;
  return {
    floatPhase: Number.parseInt(match[1], 10),
    drownPhase: Number.parseInt(match[2], 10),
  };
}

function buildSelectionConstraints(characterId = selectedCharacterId) {
  const selectedSingleFloats = new Set();
  const selectedSingleDrowns = new Set();
  const selectedSingleKeys = new Set();
  const selectedDoubleKeys = new Set();
  let maxDoubleFloatPhase = null;

  betSlip.forEach((item) => {
    if (Number(item.characterId) !== Number(characterId)) {
      return;
    }

    const key = String(item.option || "");
    if (item.betType === "Single") {
      selectedSingleKeys.add(key.toUpperCase());
      const parsed = parseSingleOptionKey(key);
      if (!parsed) return;
      if (parsed.type === "FLOAT") {
        selectedSingleFloats.add(parsed.phase);
      } else {
        selectedSingleDrowns.add(parsed.phase);
      }
      return;
    }

    if (item.betType === "Double") {
      const parsed = parseDoubleOptionKey(key);
      if (!parsed) return;
      selectedDoubleKeys.add(key.toUpperCase());
      if (
        maxDoubleFloatPhase === null ||
        parsed.floatPhase > maxDoubleFloatPhase
      ) {
        maxDoubleFloatPhase = parsed.floatPhase;
      }
    }
  });

  return {
    selectedSingleFloats,
    selectedSingleDrowns,
    selectedSingleKeys,
    selectedDoubleKeys,
    maxDoubleFloatPhase,
  };
}

function shouldDisableSingleOption(optionKey, constraints) {
  if (constraints.selectedSingleKeys.size > 0) {
    return true;
  }

  const parsed = parseSingleOptionKey(optionKey);
  if (!parsed) return false;

  if (parsed.type === "FLOAT" && constraints.selectedSingleFloats.size > 0) {
    return !constraints.selectedSingleFloats.has(parsed.phase);
  }
  if (parsed.type === "DROWN" && constraints.selectedSingleDrowns.size > 0) {
    return !constraints.selectedSingleDrowns.has(parsed.phase);
  }
  return false;
}

function shouldDisableDoubleOption(optionKey, constraints) {
  const normalizedKey = String(optionKey || "")
    .trim()
    .toUpperCase();
  if (constraints.selectedDoubleKeys.has(normalizedKey)) {
    return true;
  }

  const parsed = parseDoubleOptionKey(optionKey);
  if (!parsed) return false;

  if (constraints.maxDoubleFloatPhase === null) {
    return false;
  }
  return parsed.floatPhase <= constraints.maxDoubleFloatPhase;
}

function isOptionSelected(optionKey, betType, constraints) {
  const normalizedKey = String(optionKey || "")
    .trim()
    .toUpperCase();
  if (betType === "double") {
    return constraints.selectedDoubleKeys.has(normalizedKey);
  }
  return constraints.selectedSingleKeys.has(normalizedKey);
}

function refreshOptionAvailability() {
  renderOptionsBoard();
}

async function resolveLoginState() {
  const token = localStorage.getItem("token");
  if (!token) {
    isUserLoggedIn = false;
    currentUserProfile = null;
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/user/profile`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (response.ok) {
      const payload = await response.json();
      isUserLoggedIn = true;
      currentUserProfile = payload?.user || null;
      trackBettorActivity("profile_view", { source: "dashboard" });
    } else {
      isUserLoggedIn = false;
      currentUserProfile = null;
      localStorage.removeItem("token");
    }
  } catch {
    isUserLoggedIn = false;
    currentUserProfile = null;
  }
}

function applyAccessControl() {
  menuButtons.forEach((btn) => {
    const isBettingView = btn.dataset.view === BETTING_VIEW_ID;
    const hideForGuest = !isUserLoggedIn && !isBettingView;
    btn.style.display = hideForGuest ? "none" : "";
    btn.disabled = hideForGuest;
    btn.classList.toggle("locked", hideForGuest);
  });

  if (!isUserLoggedIn) {
    betSlip.length = 0;
    renderSlip();
    if (liveBets) {
      liveBets.innerHTML =
        '<p class="slip-empty">Login to view your current bets.</p>';
    }
    switchView(BETTING_VIEW_ID);
  }

  if (slipContainer) {
    slipContainer.style.display = isUserLoggedIn ? "grid" : "none";
  }

  if (placeBetBtn) {
    placeBetBtn.disabled = !isUserLoggedIn;
    placeBetBtn.classList.toggle("disabled", !isUserLoggedIn);
  }

  if (dashboardLogoutBtn) {
    dashboardLogoutBtn.style.display = isUserLoggedIn ? "inline-flex" : "none";
  }

  renderHeaderChips();

  if (!isUserLoggedIn) {
    if (accountSubmenu) accountSubmenu.hidden = true;
    if (demoBalanceCard) demoBalanceCard.hidden = true;
  }
}

function renderHeaderChips() {
  if (!dashboardUserChip || !dashboardUserName) return;
  if (!isUserLoggedIn || !currentUserProfile) {
    dashboardUserChip.hidden = true;
    if (dashboardBalanceChip) dashboardBalanceChip.hidden = true;
    return;
  }
  dashboardUserName.textContent = displayUserName(currentUserProfile);
  dashboardUserChip.hidden = false;
  if (dashboardBalanceChip && dashboardBalanceValue) {
    dashboardBalanceValue.textContent = `Bal: ${formatMoney(currentUserProfile.demo_balance)}`;
    dashboardBalanceChip.hidden = false;
  }
}

async function logoutFromDashboard() {
  const token = localStorage.getItem("token");

  try {
    if (token) {
      await fetch(`${API_BASE}/api/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    }
  } catch (error) {
    console.error("Logout request failed:", error);
  } finally {
    localStorage.removeItem("token");
    window.location.href = "/";
  }
}

function navigateHomeFromDashboard() {
  window.location.href = "/";
}

function switchView(viewId) {
  if (!isUserLoggedIn && viewId !== BETTING_VIEW_ID) {
    viewId = BETTING_VIEW_ID;
  }

  if (viewId !== "view-account") {
    setAccountSubmenuVisible(false);
    if (demoBalanceCard) demoBalanceCard.hidden = true;
  }

  dashboardViews.forEach((view) => {
    view.classList.toggle("active", view.id === viewId);
  });
  menuButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.view === viewId);
  });

  const activeView = document.getElementById(viewId);
  if (!activeView) return;
  mainTitle.textContent = activeView.dataset.title || "Dashboard";
  mainSubtitle.textContent = activeView.dataset.subtitle || "";

  if (viewId === "view-outcomes") {
    loadOutcomes();
  }
  if (viewId === "view-performance" && performanceViewDirty) {
    syncPerformanceState();
  }
  if (viewId === "view-transactions") {
    loadBets();
  }
  if (viewId === "view-support") {
    loadSupportEnquiries();
  }
}

function getAuthHeaders() {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function trackBettorActivity(eventType, metadata = {}) {
  if (!isUserLoggedIn) return;
  const headers = getAuthHeaders();
  if (!headers.Authorization) return;

  fetch(`${API_BASE}/api/activity`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    body: JSON.stringify({ eventType, metadata }),
    keepalive: true,
  }).catch(() => {});
}

function formatMoney(value) {
  const amount = Number(value || 0);
  return Number.isFinite(amount) ? amount.toFixed(2) : "0.00";
}

function formatDateTime(value) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (!Number.isFinite(parsed.getTime())) return "-";
  return parsed.toLocaleString([], {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatCharacterLabel(rawName) {
  const value = String(rawName || "").trim();
  if (!value) return "Unknown";
  const [baseName] = value.split("_");
  return baseName || value;
}

function getStakeFromInput(inputEl) {
  const rawValue = inputEl ? Number(inputEl.value) : 1;
  if (!Number.isFinite(rawValue) || rawValue < 1) return null;
  return Number(rawValue.toFixed(2));
}

function normalizeStakeInput(inputEl) {
  if (!inputEl) return;
  const stake = getStakeFromInput(inputEl);
  inputEl.value = stake === null ? "1.00" : stake.toFixed(2);
}

function calculateTotalPossibleWinnings() {
  const stake = getStakeFromInput(slipStakeInput);
  if (stake === null || !betSlip.length) return 0;

  const perOutcomeStake = Number((stake / betSlip.length).toFixed(2));
  const totalPossibleWinnings = betSlip.reduce((sum, bet) => {
    const odds = Number(bet?.odds);
    if (!Number.isFinite(odds)) return sum;
    return sum + odds * perOutcomeStake;
  }, 0);

  return Number(totalPossibleWinnings.toFixed(2));
}

function renderSlipSummary() {
  if (!slipPossibleWinnings) return;
  slipPossibleWinnings.textContent = formatMoney(
    calculateTotalPossibleWinnings(),
  );
}

function showDemoMessage(message, isError = false) {
  if (!demoBalanceMessage) return;
  demoBalanceMessage.textContent = message;
  demoBalanceMessage.style.color = isError ? "#ff9aa2" : "#d4e9f7";
}

function setAccountSubmenuVisible(isVisible) {
  if (!accountSubmenu) return;
  accountSubmenu.hidden = !isVisible;
  if (!isVisible && demoBalanceCard) demoBalanceCard.hidden = true;
  if (accountMenuBtn) accountMenuBtn.classList.toggle("active", isVisible);
}

async function refreshCurrentUserProfile() {
  const token = localStorage.getItem("token");
  if (!token) {
    isUserLoggedIn = false;
    currentUserProfile = null;
    return null;
  }

  const response = await fetch(`${API_BASE}/api/user/profile`, {
    method: "GET",
    headers: getAuthHeaders(),
  });

  if (!response.ok) {
    isUserLoggedIn = false;
    currentUserProfile = null;
    localStorage.removeItem("token");
    throw new Error("Could not load user profile");
  }

  const payload = await response.json();
  isUserLoggedIn = true;
  currentUserProfile = payload?.user || null;
  renderHeaderChips();
  return currentUserProfile;
}

function displayUserName(user) {
  if (!user) return "Unknown";
  const first = String(user.firstname || "").trim();
  return first || user.email || "Unknown";
}

function closeDemoCard() {
  if (demoBalanceCard) demoBalanceCard.hidden = true;
  if (demoBalanceEditor) demoBalanceEditor.hidden = true;
}

function renderDemoModalFromProfile() {
  const user = currentUserProfile;
  if (!user) return;
  if (demoUserName) demoUserName.textContent = `User: ${displayUserName(user)}`;
  if (demoBalanceValue)
    demoBalanceValue.textContent = formatMoney(user.demo_balance);
  if (demoBalanceInput) demoBalanceInput.value = formatMoney(user.demo_balance);
  if (demoBalanceEditor) demoBalanceEditor.hidden = true;
}

function toggleDemoBalanceEditor() {
  if (!demoBalanceEditor) return;
  const willShow = demoBalanceEditor.hidden;
  demoBalanceEditor.hidden = !willShow;
  if (willShow && demoBalanceInput) {
    demoBalanceInput.focus();
    demoBalanceInput.select();
  }
}

async function openDemoCard() {
  if (!isUserLoggedIn) {
    alert("Please log in first.");
    return;
  }

  try {
    await refreshCurrentUserProfile();
    renderDemoModalFromProfile();
    showDemoMessage("");
    if (demoBalanceCard) demoBalanceCard.hidden = false;
  } catch (error) {
    console.error("Failed to open demo card:", error);
    alert("Could not load demo account details.");
  }
}

async function saveDemoBalance() {
  if (!isUserLoggedIn) {
    alert("Please log in first.");
    return;
  }

  const amount = Number(demoBalanceInput?.value);
  if (!Number.isFinite(amount) || amount < 0) {
    showDemoMessage("Amount must be a non-negative number.", true);
    return;
  }

  if (demoBalanceSaveBtn) demoBalanceSaveBtn.disabled = true;
  try {
    const response = await fetch(`${API_BASE}/api/user/demo-money`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ amount }),
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload?.error || "Could not update demo balance");
    }

    currentUserProfile = {
      ...(currentUserProfile || {}),
      demo_balance: Number(payload.demo_balance || amount),
    };
    renderHeaderChips();
    renderDemoModalFromProfile();
    showDemoMessage("Demo balance updated.");
  } catch (error) {
    console.error("Failed to save demo balance:", error);
    showDemoMessage(error.message || "Could not update balance.", true);
  } finally {
    if (demoBalanceSaveBtn) demoBalanceSaveBtn.disabled = false;
  }
}

function handleAccountMenuClick() {
  if (!isUserLoggedIn) {
    alert("Please log in first.");
    return;
  }
  setAccountSubmenuVisible(accountSubmenu?.hidden);
}

function handleAccountSubAction(panel) {
  if (panel === "demo") {
    if (!demoBalanceCard?.hidden) {
      closeDemoCard();
      return;
    }
    openDemoCard();
    return;
  }
  closeDemoCard();
  showDemoMessage("");
  alert("Real account panel is coming next.");
}

function toPercent(probability) {
  return `${(Number(probability || 0) * 100).toFixed(2)}%`;
}

function formatCountdown(seconds) {
  const safe = Math.max(0, Math.floor(Number(seconds) || 0));
  const mins = Math.floor(safe / 60);
  const secs = safe % 60;
  return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function initGamePreloadIframe() {
  initGameplayFrameStack();
  gamePreloadIframe = getInactiveGameplayFrame();
}

function preloadGameFrame(src) {
  if (!src) return;
  const normalizedSrc = normalizeGameplaySrc(src);
  initGamePreloadIframe();
  if (!gamePreloadIframe) return;
  if (
    gamePreloadIframe.dataset.frameKey === GAMEPLAY_GAME_2 &&
    gamePreloadIframe.dataset.frameSrc === normalizedSrc
  ) {
    gamePreloadSrc = normalizedSrc;
    return;
  }
  gamePreloadSrc = normalizedSrc;
  gamePreloadIframe.dataset.preloadRequestedAt = String(Date.now());
  window.__dashboardPreload = window.__dashboardPreload || {};
  window.__dashboardPreload.preloadRequestedAt = Number(
    gamePreloadIframe.dataset.preloadRequestedAt,
  );
  window.__dashboardPreload.preloadRequestedSrc = normalizedSrc;
  window.__dashboardPreload.roundSecondsRemaining =
    Number(roundSecondsRemaining) || 0;
  console.log(`[Preload] Loading game: ${normalizedSrc}`);
  debugPreload("[Preload] request", window.__dashboardPreload);
  updatePreloadDebugIndicator();
  assignGameplayFrameSource(gamePreloadIframe, GAMEPLAY_GAME_2, normalizedSrc);
}

function preloadUpcomingGameplay() {
  const targetSrc = buildGameplayFrameSrc(GAMEPLAY_GAME_2);
  if (!targetSrc) return;
  preloadGameFrame(targetSrc);
}

function renderRoundCountdown() {
  if (!roundCountdown) return;
  const countdownText = formatCountdown(roundSecondsRemaining);
  const countdownState =
    roundSecondsRemaining <= 10
      ? "danger"
      : roundSecondsRemaining <= 15
        ? "warn"
        : "normal";

  if (lastRenderedRoundCountdown !== countdownText) {
    roundCountdown.textContent = countdownText;
    lastRenderedRoundCountdown = countdownText;
  }
  if (lastRenderedRoundCountdownState !== countdownState) {
    roundCountdown.classList.toggle("warn", countdownState === "warn");
    roundCountdown.classList.toggle("danger", countdownState === "danger");
    lastRenderedRoundCountdownState = countdownState;
  }
}

function applyLiveSnapshot(snapshot) {
  if (!snapshot || typeof snapshot !== "object") return;

  const timer = snapshot.timer || {};
  const roundId = Number(timer.roundId);
  let roundChanged = false;
  if (Number.isInteger(roundId) && roundId > 0) {
    const previousRoundId = latestLiveRoundId;
    latestLiveRoundId = roundId;
    if (previousRoundId !== null && previousRoundId !== roundId) {
      roundChanged = true;
      refreshRoundScopedData().catch((error) => {
        console.error("Could not refresh round-scoped data:", error);
      });
    }
  }

  // Do not drive countdown directly from live snapshot here.
  // Countdown should be authored by TimerManager only to avoid conflicting sources.
  if (!globalGameplayStateActive && currentGameplayGame !== "stats-inner") {
    showDefaultGameplay();
  }

  const latestResult = snapshot.latestResult;
  const latestResultId = Number(latestResult?.id);
  if (
    Number.isInteger(latestResultId) &&
    latestResultId > 0 &&
    latestResultId !== latestLiveResultId
  ) {
    latestLiveResultId = latestResultId;
    if (roundResult) {
      const phaseNumber = Number(latestResult.phaseNumber);
      const phaseText = Number.isFinite(phaseNumber) ? ` P${phaseNumber}` : "";
      const characterText = latestResult.characterName
        ? `${formatCharacterLabel(latestResult.characterName)}${phaseText}`
        : `Market${phaseText}`;
      const roundText = Number.isFinite(Number(latestResult.roundId))
        ? `Round ${latestResult.roundId}`
        : "Latest";
      roundResult.textContent = `${roundText}: ${characterText} -> ${latestResult.drawOption}`;
    }
    loadOutcomes();
  }

  const optionsVersion = snapshot.options?.version || null;
  const optionsPayload = snapshot.options?.payload || null;
  if (
    optionsVersion &&
    optionsPayload &&
    optionsVersion !== latestLiveOptionsVersion
  ) {
    latestLiveOptionsVersion = optionsVersion;
    const liveCharacterId = Number(snapshot.options?.characterId);
    if (Number.isInteger(liveCharacterId) && liveCharacterId > 0) {
      latestOptionsByCharacter.set(liveCharacterId, optionsPayload);
      if (liveCharacterId === Number(selectedCharacterId)) {
        latestOptionsPayload = optionsPayload;
      }
    }
    renderOptionsBoard();
  }
}

function buildGameplayStateWebSocketUrl() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/ws/gameplay/`;
}

function buildGameplayEmbedMetaUrl() {
  return new URL("/games/embed-meta/", window.location.origin).toString();
}

function buildLiveDataUrl(pathname) {
  const base = API_BASE || window.location.origin;
  return new URL(pathname, base);
}

async function fetchAndApplyGameplayMeta() {
  try {
    const res = await fetch(buildGameplayEmbedMetaUrl(), { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Gameplay meta fetch failed (${res.status})`);
    }
    const payload = await res.json().catch(() => null);
    if (!payload || typeof payload !== "object") return;

    const activeBuildUrl = String(payload.active_build_url || "").trim();
    if (activeBuildUrl && activeBuildUrl !== latestActiveBuildUrl) {
      latestActiveBuildUrl = activeBuildUrl;
      if (currentGameplayGame === "default-gameplay" && defaultGameplaySrc) {
        setGameplayFrameSource("default-gameplay", defaultGameplaySrc, true);
      }
    }

    if (payload.state) {
      applyGlobalGameplayState(payload.state);
    }
  } catch (error) {
    console.error("Could not sync gameplay meta:", error);
  }
}

function applyGlobalGameplayState(state) {
  if (!state || typeof state !== "object" || !state.status) return;
  const normalizedStatus = String(state.status || "").toUpperCase();
  const previousStatus = latestGlobalGameplayState?.status || null;
  if (
    latestGlobalGameplayState &&
    latestGlobalGameplayState.status === normalizedStatus &&
    latestGlobalGameplayState.tick === state.tick &&
    latestGlobalGameplayState.max_ticks === state.max_ticks
  ) {
    return;
  }

  latestGlobalGameplayState = {
    status: normalizedStatus,
    tick: Number(state.tick) || 0,
    max_ticks: Number(state.max_ticks) || 0,
  };
  globalGameplayStateActive = true;

  if (globalGameplayState) {
    globalGameplayState.textContent = `State: ${normalizedStatus}`;
  }

  if (normalizedStatus === "RUNNING") {
    const targetSrc = buildGameplayFrameSrc(GAMEPLAY_GAME_2);
    if (!targetSrc) return;

    if (Number(roundSecondsRemaining) > 0) {
      // Let the game start live in the background during the final countdown.
      showActiveRoundStatsWhileGameplayRuns(targetSrc);
    } else {
      // Once countdown reaches 00:00, promote the already-running gameplay.
      if (!activateExistingGameplayFrame(GAMEPLAY_GAME_2, targetSrc)) {
        showGameplayCover();
        showGame2(previousStatus !== "RUNNING");
      }
    }
  } else if (normalizedStatus === "STOPPED") {
    // When gameplay stops, fall back to the scheduled display (stats window / default).
    syncScheduledRoundDisplay();
  }
}

function scheduleGameplayStateReconnect() {
  if (gameplayStateReconnectHandle) return;
  gameplayStateReconnectHandle = setTimeout(() => {
    gameplayStateReconnectHandle = null;
    connectGameplayStateWebSocket();
  }, 3000);
}

function stopGameplayStateSync() {
  if (gameplayStateWebSocket) {
    gameplayStateWebSocket.close();
    gameplayStateWebSocket = null;
  }
  if (gameplayStateReconnectHandle) {
    clearTimeout(gameplayStateReconnectHandle);
    gameplayStateReconnectHandle = null;
  }
  if (gameplayMetaSyncHandle) {
    clearInterval(gameplayMetaSyncHandle);
    gameplayMetaSyncHandle = null;
  }
}

function connectGameplayStateWebSocket() {
  if (gameplayStateWebSocket) return;

  try {
    gameplayStateWebSocket = new WebSocket(buildGameplayStateWebSocketUrl());
    gameplayStateWebSocket.addEventListener("open", () => {
      if (gameplayStateReconnectHandle) {
        clearTimeout(gameplayStateReconnectHandle);
        gameplayStateReconnectHandle = null;
      }
      fetchAndApplyGameplayMeta();
    });

    gameplayStateWebSocket.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse(event.data || "{}");
        applyGlobalGameplayState(payload);
      } catch (error) {
        console.error("Invalid gameplay state websocket message:", error);
      }
    });

    gameplayStateWebSocket.addEventListener("error", (error) => {
      console.error("Gameplay state websocket error:", error);
    });

    gameplayStateWebSocket.addEventListener("close", () => {
      gameplayStateWebSocket = null;
      scheduleGameplayStateReconnect();
    });
  } catch (error) {
    console.error("Could not connect gameplay state websocket:", error);
    scheduleGameplayStateReconnect();
  }
}

function startGameplayStateSync() {
  stopGameplayStateSync();
  if (window.WebSocket) {
    connectGameplayStateWebSocket();
  }
  fetchAndApplyGameplayMeta();
  gameplayMetaSyncHandle = setInterval(fetchAndApplyGameplayMeta, 30000);
}

async function fetchAndApplyLiveSnapshot() {
  if (liveSnapshotRequest) return liveSnapshotRequest;

  liveSnapshotRequest = (async () => {
    try {
      const url = buildLiveDataUrl("/api/live/snapshot");
      if (Number.isInteger(selectedCharacterId) && selectedCharacterId > 0) {
        url.searchParams.set("characterId", String(selectedCharacterId));
      }
      const res = await fetch(url.toString());
      if (!res.ok) {
        throw new Error(`Live snapshot fetch failed (${res.status})`);
      }
      const payload = await res.json().catch(() => ({}));
      applyLiveSnapshot(payload);
    } catch (error) {
      console.error("Could not fetch live snapshot:", error);
    }
  })();

  try {
    await liveSnapshotRequest;
  } finally {
    liveSnapshotRequest = null;
  }
}

function stopLiveUpdates() {
  if (liveEventSource) {
    liveEventSource.close();
    liveEventSource = null;
  }
  if (liveFallbackHandle) {
    clearInterval(liveFallbackHandle);
    liveFallbackHandle = null;
  }
  if (liveReconnectHandle) {
    clearTimeout(liveReconnectHandle);
    liveReconnectHandle = null;
  }
}

function stopRoundTimer() {
  if (roundTimerUnsubscribe) {
    roundTimerUnsubscribe();
    roundTimerUnsubscribe = null;
  }
}

function scheduleLiveReconnect() {
  if (liveReconnectHandle) return;
  liveReconnectHandle = setTimeout(() => {
    liveReconnectHandle = null;
    startLiveUpdates(true);
  }, 3000);
}

function startFallbackLivePolling() {
  if (liveFallbackHandle) return;
  liveFallbackHandle = setInterval(() => {
    if (document.visibilityState !== "visible") return;
    fetchAndApplyLiveSnapshot();
  }, 3000);
}

function stopFallbackLivePolling() {
  if (!liveFallbackHandle) return;
  clearInterval(liveFallbackHandle);
  liveFallbackHandle = null;
}

function startLiveUpdates(forceRestart = false) {
  const subscriptionId =
    Number.isInteger(selectedCharacterId) && selectedCharacterId > 0
      ? selectedCharacterId
      : null;

  if (
    !forceRestart &&
    liveEventSource &&
    liveCharacterSubscriptionId === subscriptionId
  ) {
    return;
  }

  stopLiveUpdates();
  liveCharacterSubscriptionId = subscriptionId;

  if (typeof window.EventSource !== "function") {
    startFallbackLivePolling();
    fetchAndApplyLiveSnapshot();
    return;
  }

  const url = buildLiveDataUrl("/api/live/stream");
  if (subscriptionId) {
    url.searchParams.set("characterId", String(subscriptionId));
  }

  liveEventSource = new EventSource(url.toString());
  liveEventSource.addEventListener("snapshot", (event) => {
    try {
      const payload = JSON.parse(event.data || "{}");
      applyLiveSnapshot(payload);
    } catch (error) {
      console.error("Invalid live snapshot payload:", error);
    }
  });

  liveEventSource.onopen = () => {
    stopFallbackLivePolling();
    if (liveReconnectHandle) {
      clearTimeout(liveReconnectHandle);
      liveReconnectHandle = null;
    }
  };

  liveEventSource.onerror = () => {
    if (liveEventSource) {
      liveEventSource.close();
      liveEventSource = null;
    }
    startFallbackLivePolling();
    scheduleLiveReconnect();
  };
}

async function startRoundTimer() {
  if (roundTimerUnsubscribe) {
    roundTimerUnsubscribe();
    roundTimerUnsubscribe = null;
  }

  await TimerManager.refresh();

  roundTimerUnsubscribe = TimerManager.subscribe((timerState) => {
    roundSecondsRemaining = timerState.secondsRemaining;
    renderRoundCountdown();
    syncScheduledRoundDisplay();
    updateBettingLockUI();
    // Update button disabled states on the options board as we approach lock time.
    if (roundSecondsRemaining <= BET_LOCK_THRESHOLD_SECONDS + 1) {
      renderOptionsBoard();
    }
    if (isPreloadDebugEnabled()) {
      window.__dashboardPreload = window.__dashboardPreload || {};
      window.__dashboardPreload.roundSecondsRemaining =
        Number(roundSecondsRemaining) || 0;
      updatePreloadDebugIndicator();
    }

    // Preload Unity game when approaching gameplay start time
    if (
      roundSecondsRemaining <= GAME_PRELOAD_THRESHOLD_SECONDS &&
      !gamePreloadedForRound
    ) {
      gamePreloadedForRound = true;
      preloadUpcomingGameplay();
    }

    if (roundSecondsRemaining <= 0) {
      gamePreloadedForRound = false; // Reset for next round

      // At rollover, bring the already-preloaded gameplay to the front.
      const targetSrc = buildGameplayFrameSrc(GAMEPLAY_GAME_2);
      if (targetSrc) {
        debugPreload("[Preload] rollover activate", { targetSrc });
        setGameplayFrameSource(GAMEPLAY_GAME_2, targetSrc);
      }

      TimerManager.refresh().catch((error) => {
        console.error("Could not refresh round timer after rollover:", error);
      });
      fetchAndApplyLiveSnapshot();
    }
  });
}

function toLevel(rawValue) {
  const parsed = Number(rawValue || 0);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 0;
  }

  // Accept both 1-10 and 0-100 inputs, normalize to a 0-10 UI scale.
  const normalized = parsed > 10 ? parsed / 10 : parsed;
  const level = Math.min(10, Math.max(0, normalized));
  return Math.round(level * 10) / 10;
}

function clamp(num, min, max) {
  return Math.max(min, Math.min(max, num));
}

function getCharacterByIdLocal(characterId) {
  return (
    characters.find((item) => Number(item.id) === Number(characterId)) || null
  );
}

function hashCharacterSeed(character) {
  if (!character) return 1;
  const raw = `${character.id || ""}${character.name || ""}`;
  return Array.from(raw).reduce((acc, ch) => acc + ch.charCodeAt(0), 0) % 11;
}

function normalizeStatBase(rawValue) {
  const parsed = Number(rawValue || 0);
  if (!Number.isFinite(parsed)) return 5;
  if (parsed > 10) return clamp(parsed / 10, 0, 10);
  return clamp(parsed, 0, 10);
}

function toDbIntLevel(value) {
  return clamp(Math.round(Number(value) || 0), 0, 10);
}

function toValidDate(raw) {
  if (!raw) return null;
  const parsed = new Date(raw);
  return Number.isFinite(parsed.getTime()) ? parsed : null;
}

function mapHistoryRecordsByTime(records, barTimestamps, frame) {
  if (!Array.isArray(records) || records.length === 0) return [];
  if (!Array.isArray(barTimestamps) || barTimestamps.length === 0) return [];

  const timed = records
    .filter((record) => record.createdAt instanceof Date)
    .map((record) => ({
      ...record,
      bucketTime: alignToFrameBoundary(record.createdAt, frame),
    }))
    .sort((a, b) => {
      if (a.bucketTime.getTime() !== b.bucketTime.getTime()) {
        return a.bucketTime - b.bucketTime;
      }
      return a.createdAt - b.createdAt;
    });

  if (!timed.length) {
    if (records.length === 1) {
      return barTimestamps.map((barTime, idx) => ({
        idx,
        barTime,
        ...records[0],
      }));
    }

    return barTimestamps.map((barTime, idx) => {
      const ratio = idx / Math.max(barTimestamps.length - 1, 1);
      const recordIndex = Math.round(ratio * (records.length - 1));
      return {
        idx,
        barTime,
        ...records[recordIndex],
      };
    });
  }

  return barTimestamps.map((barTime, idx) => {
    let chosen = timed[0];

    for (let i = 0; i < timed.length; i += 1) {
      if (timed[i].bucketTime <= barTime) {
        chosen = timed[i];
      } else {
        break;
      }
    }

    return {
      idx,
      barTime,
      ...chosen,
      sourceTime: chosen.createdAt,
      sourceBucketTime: chosen.bucketTime,
    };
  });
}

function buildPerformanceSeries(character, frame) {
  const characterId = Number(character?.id);
  const cleanName = displayCharacterName(character?.name).toLowerCase();
  const limit = performanceFrameRoundLimits[frame] || historyBarsCount;
  const payloadRows = Array.isArray(latestPerformancePayload?.characters)
    ? latestPerformancePayload.characters.find(
        (entry) =>
          Number(entry?.characterId) === characterId ||
          displayCharacterName(entry?.name).toLowerCase() === cleanName,
      )?.rounds
    : [];

  return (Array.isArray(payloadRows) ? payloadRows : [])
    .slice(-limit)
    .map((row, idx) => ({
      idx,
      roundNumber: Number(row?.roundNumber || 0),
      roundStatus: String(row?.roundStatus || ""),
      roundLabel: `Round ${Number(row?.roundNumber || 0)}`,
      barTime: null,
      momentum: Number(row?.cumulativeScore || 0) * PERFORMANCE_SCORE_STEP,
      divergenceSigned:
        Number(row?.cumulativeScore || 0) * PERFORMANCE_SCORE_STEP,
      roundScore: Number(row?.score || 0) * PERFORMANCE_SCORE_STEP,
      cumulativeScore:
        Number(row?.cumulativeScore || 0) * PERFORMANCE_SCORE_STEP,
      betCount: Number(row?.betCount || 0),
      wins: Number(row?.wins || 0),
      losses: Number(row?.losses || 0),
      pending: Number(row?.pending || 0),
      optionCodes: Array.isArray(row?.optionCodes) ? row.optionCodes : [],
      placedAt: row?.placedAt || null,
    }));
}

function rebuildPerformanceData() {
  Object.keys(performanceData).forEach((key) => delete performanceData[key]);
  characters.forEach((character) => {
    const key = String(character.id);
    performanceData[key] = {
      "5min": buildPerformanceSeries(character, "5min"),
      "1hr": buildPerformanceSeries(character, "1hr"),
      "2hr": buildPerformanceSeries(character, "2hr"),
    };
  });
}

function buildCharacterHistoryMap(historyRows) {
  const grouped = {};

  (historyRows || []).forEach((row) => {
    const cleanName = displayCharacterName(row.name);
    if (!grouped[cleanName]) grouped[cleanName] = [];

    const stamina = toDbIntLevel(normalizeStatBase(row.stamina));
    const control = toDbIntLevel(normalizeStatBase(row.control));
    const power = toDbIntLevel(normalizeStatBase(row.power));
    const momentum = clamp((stamina + control + power) / 3, 1, 10);
    const divergenceSigned = clamp(
      control - stamina + (power - 5) * 1.1,
      -10,
      10,
    );

    grouped[cleanName].push({
      stamina,
      control,
      power,
      momentum,
      divergenceSigned,
      createdAt: toValidDate(row.created_at),
    });
  });

  Object.values(grouped).forEach((rows) => {
    rows.sort((a, b) => {
      if (!a.createdAt && !b.createdAt) return 0;
      if (!a.createdAt) return 1;
      if (!b.createdAt) return -1;
      return a.createdAt - b.createdAt;
    });
  });

  return grouped;
}

function formatAxisTime(dateObj) {
  return dateObj.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function alignToFrameBoundary(dateObj, frame) {
  const cfg = performanceFrameConfig[frame] || performanceFrameConfig["5min"];
  const stepMinutes = cfg.unit === "h" ? cfg.step * 60 : cfg.step;
  const aligned = new Date(dateObj);
  const mins = aligned.getMinutes();
  const flooredMinutes = Math.floor(mins / stepMinutes) * stepMinutes;
  aligned.setSeconds(0, 0);
  aligned.setMinutes(flooredMinutes);
  return aligned;
}

function buildTradingAxisLabels(frame, count) {
  return buildTradingAxisTimestamps(frame, count).map((timestamp) =>
    formatAxisTime(timestamp),
  );
}

function buildTradingAxisTimestamps(frame, count) {
  const cfg = performanceFrameConfig[frame] || performanceFrameConfig["5min"];
  const now = alignToFrameBoundary(new Date(), frame);
  const stepMinutes = cfg.unit === "h" ? cfg.step * 60 : cfg.step;
  const timestamps = [];

  for (let i = 0; i < count; i++) {
    const barsBack = count - 1 - i;
    const timestamp = new Date(now.getTime() - barsBack * stepMinutes * 60000);
    timestamps.push(timestamp);
  }

  return timestamps;
}

function buildAxisLabelsFromSeries(series, frame) {
  const roundLabels = (series || []).map((point) =>
    Number.isFinite(Number(point?.roundNumber))
      ? `R${Number(point.roundNumber)}`
      : String(point?.roundLabel || "").trim(),
  );

  if (roundLabels.some((label) => Boolean(label))) {
    return roundLabels;
  }

  const labels = (series || []).map((point) =>
    point?.barTime instanceof Date ? formatAxisTime(point.barTime) : "",
  );

  if (labels.some((label) => Boolean(label))) {
    return labels;
  }

  return buildTradingAxisLabels(frame, series.length);
}

function ensureCrosshairRegistration() {
  if (typeof Chart === "undefined" || typeof CrosshairPlugin === "undefined")
    return;
  if (Chart._stoneCrosshairRegistered) return;
  Chart.register(CrosshairPlugin);
  Chart._stoneCrosshairRegistered = true;
}

function pointsFromValues(values) {
  return values
    .map((value, idx) => {
      const x = (idx / (values.length - 1)) * 360;
      const y = 150 - (value / 10) * 130;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function pointsFromDynamicValues(values) {
  const safeValues = Array.isArray(values) && values.length ? values : [0];
  const minValue = Math.min(...safeValues);
  const maxValue = Math.max(...safeValues);
  const span = Math.max(1, maxValue - minValue);

  return safeValues
    .map((value, idx) => {
      const x =
        safeValues.length === 1 ? 180 : (idx / (safeValues.length - 1)) * 360;
      const normalized = (Number(value) - minValue) / span;
      const y = 150 - normalized * 130;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function getPerformanceRowsForFrame(frame) {
  const limit = performanceFrameRoundLimits[frame] || historyBarsCount;
  const rows = [];
  (Array.isArray(latestPerformancePayload?.characters)
    ? latestPerformancePayload.characters
    : []
  ).forEach((characterEntry) => {
    const rounds = Array.isArray(characterEntry?.rounds)
      ? characterEntry.rounds.slice(-limit)
      : [];
    rounds.forEach((round) => {
      rows.push({
        characterId: Number(characterEntry?.characterId || 0),
        name: String(characterEntry?.name || "Unknown"),
        ...round,
      });
    });
  });
  return rows;
}

function getYAxisBounds(values, { forceZeroBaseline = false } = {}) {
  const safeValues = (Array.isArray(values) ? values : [])
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));

  if (!safeValues.length) {
    return { min: forceZeroBaseline ? 0 : -1, max: 1, stepSize: 0.1 };
  }

  let min = Math.min(...safeValues);
  let max = Math.max(...safeValues);

  if (forceZeroBaseline) {
    min = Math.min(0, min);
    max = Math.max(0, max);
  } else {
    min = Math.min(min, 0);
    max = Math.max(max, 0);
  }

  if (min === max) {
    min -= 0.1;
    max += 0.1;
  }

  min = Math.floor(min * 10) / 10;
  max = Math.ceil(max * 10) / 10;

  return {
    min,
    max,
    stepSize: 0.1,
  };
}

function getDivergenceYAxisBounds(values) {
  const safeValues = (Array.isArray(values) ? values : [])
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));
  const maxAbs = Math.max(0.1, ...safeValues.map((value) => Math.abs(value)));
  const bound = Math.ceil(maxAbs * 10) / 10;
  return {
    min: -bound,
    max: bound,
    stepSize: 0.1,
  };
}

function renderGeneralPie(frame) {
  if (!generalPie) return;
  const rows = getPerformanceRowsForFrame(frame);
  const total =
    rows.reduce(
      (sum, row) =>
        sum +
        Number(row?.wins || 0) +
        Number(row?.losses || 0) +
        Number(row?.pending || 0),
      0,
    ) || 1;
  const winPct = Math.round(
    (rows.reduce((sum, row) => sum + Number(row?.wins || 0), 0) / total) * 100,
  );
  const lossPct = Math.round(
    (rows.reduce((sum, row) => sum + Number(row?.losses || 0), 0) / total) *
      100,
  );
  const pendingPct = Math.max(0, 100 - winPct - lossPct);
  generalPie.style.background = `conic-gradient(
    #22c55e 0% ${winPct}%,
    #c14250 ${winPct}% ${winPct + lossPct}%,
    #6b7280 ${winPct + lossPct}% 100%
  )`;
}

function renderGeneralLine(frame) {
  if (!lineCurrent || !lineCompare) return;
  const rows = getPerformanceRowsForFrame(frame);
  const roundScores = new Map();
  rows.forEach((row) => {
    const roundNumber = Number(row?.roundNumber);
    if (!Number.isFinite(roundNumber)) return;
    roundScores.set(
      roundNumber,
      Number(roundScores.get(roundNumber) || 0) + Number(row?.score || 0),
    );
  });
  const labels = Array.from(roundScores.keys()).sort((a, b) => a - b);
  let cumulative = 0;
  const currentValues = labels.map((roundNumber) => {
    cumulative += Number(roundScores.get(roundNumber) || 0);
    return cumulative;
  });
  const baseline = labels.map((_, index) => index);
  lineCurrent.setAttribute("points", pointsFromDynamicValues(currentValues));
  lineCompare.setAttribute("points", pointsFromDynamicValues(baseline));
}

function renderGeneralPerformance() {
  if (!generalPieWrap || !generalLineWrap) return;
  generalPieWrap.style.display =
    selectedGeneralChart === "pie" ? "block" : "none";
  generalLineWrap.style.display =
    selectedGeneralChart === "line" ? "block" : "none";
  renderGeneralPie(selectedGeneralFrame);
  renderGeneralLine(selectedGeneralFrame);
}

function buildResolvedOutcomeLookup(rows) {
  const lookup = new Map();

  (Array.isArray(rows) ? rows : []).forEach((row) => {
    const roundId = Number(row?.roundId);
    const characterId = Number(row?.characterId);
    const phaseNumber = Number(row?.phaseNumber);
    const outcomeCode = String(row?.outcomeCode || "").toUpperCase();
    if (
      !Number.isFinite(roundId) ||
      !Number.isFinite(characterId) ||
      !Number.isFinite(phaseNumber) ||
      !outcomeCode
    ) {
      return;
    }

    const key = `${roundId}:${characterId}`;
    let phaseLookup = lookup.get(key);
    if (!phaseLookup) {
      phaseLookup = new Map();
      lookup.set(key, phaseLookup);
    }
    if (!phaseLookup.has(phaseNumber)) {
      phaseLookup.set(phaseNumber, outcomeCode);
    }
  });

  return lookup;
}

function renderCharacterBars(series, metricKey, frame) {
  if (typeof Chart === "undefined" || !characterPerfChart) return;
  ensureCrosshairRegistration();

  if (!Array.isArray(series) || !series.length) {
    if (divergenceChart) divergenceChart.destroy();
    if (charChartRangeNote) {
      charChartRangeNote.textContent =
        "No resolved round history yet for this character.";
    }
    return;
  }

  const labels = buildAxisLabelsFromSeries(series, frame);
  const values = series.map((point) => Number(point?.[metricKey] || 0));
  const yBounds =
    metricKey === "divergenceSigned"
      ? getDivergenceYAxisBounds(values)
      : getYAxisBounds(values);
  const backgroundColors = values.map((v) => (v >= 0 ? "#2f8b78" : "#c14250"));
  const borderColors = values.map((v) => (v >= 0 ? "#1f6a5c" : "#9f3340"));

  const pxPerBar = 56;
  characterPerfChart.width = Math.max(1200, values.length * pxPerBar);
  characterPerfChart.height = 360;

  if (divergenceChart) divergenceChart.destroy();

  divergenceChart = new Chart(characterPerfChart.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "value",
          data: values,
          backgroundColor: backgroundColors,
          borderColor: borderColors,
          borderWidth: 1.2,
          borderRadius: 5,
          barPercentage: 0.75,
          categoryPercentage: 0.85,
        },
      ],
    },
    options: {
      responsive: false,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#0d3446",
          titleColor: "#e3f0fa",
          bodyColor: "#d8eaf5",
          borderColor: "#367a9e",
          borderWidth: 1,
          callbacks: {
            label: (context) => {
              const val = Number(context.raw);
              return metricKey === "divergenceSigned"
                ? `Divergence score: ${val >= 0 ? "+" : ""}${val.toFixed(1)}`
                : `Cumulative score: ${val >= 0 ? "+" : ""}${val.toFixed(1)}`;
            },
            afterLabel: (context) => {
              const point = series[context.dataIndex];
              if (!point) return "";
              const placedAt = point.placedAt
                ? formatDateTime(point.placedAt)
                : "N/A";
              return [
                `Round: ${point.roundNumber || "-"}`,
                `Options: ${(point.optionCodes || []).join(", ") || "-"}`,
                `Wins: ${Number(point.wins || 0)} | Losses: ${Number(point.losses || 0)} | Pending: ${Number(point.pending || 0)}`,
                `Placed: ${placedAt}`,
              ];
            },
          },
        },
      },
      scales: {
        y: {
          min: yBounds.min,
          max: yBounds.max,
          grid: {
            color: (context) =>
              Number(context.tick?.value) === 0 ? "#000000" : "#d3dce6",
            lineWidth: (context) => (Number(context.tick?.value) === 0 ? 3 : 1),
          },
          ticks: {
            stepSize: yBounds.stepSize,
            color: "#123e54",
            callback: (value) =>
              metricKey === "divergenceSigned"
                ? Number(value).toFixed(1)
                : Number(value).toFixed(1),
          },
        },
        x: {
          grid: { display: false },
          ticks: {
            autoSkip: false,
            maxRotation: 45,
            minRotation: 45,
            color: "#10455f",
          },
        },
      },
    },
  });

  if (charChartRangeNote) {
    const oldest = labels[0];
    const newest = labels[labels.length - 1];
    charChartRangeNote.textContent = `${oldest} (oldest) <- ${values.length} rounds -> ${newest} (latest)`;
  }
  if (charChartScrollWrapper) {
    requestAnimationFrame(() => {
      charChartScrollWrapper.scrollLeft = charChartScrollWrapper.scrollWidth;
    });
  }
}

function getSeriesValues(series, metricKey, isDivergence) {
  return series.map((point) => Number(point?.[metricKey] || 0));
}

function getOverlayColors(values, palette, opacityHigh, opacityLow) {
  return {
    background: values.map((v) =>
      v >= 0
        ? `rgba(${palette.positive.join(",")}, ${opacityHigh})`
        : `rgba(${palette.negative.join(",")}, ${opacityHigh})`,
    ),
    border: values.map((v) =>
      v >= 0
        ? `rgba(${palette.positiveBorder.join(",")}, ${opacityLow})`
        : `rgba(${palette.negativeBorder.join(",")}, ${opacityLow})`,
    ),
  };
}

function renderCompareBars(
  currentSeries,
  otherSeries,
  metricKey,
  frame,
  currentName,
  otherName,
) {
  if (typeof Chart === "undefined" || !comparePerfChart) return;
  if (
    !Array.isArray(currentSeries) ||
    !currentSeries.length ||
    !Array.isArray(otherSeries) ||
    !otherSeries.length
  ) {
    if (compareBarsChart) compareBarsChart.destroy();
    if (compareChartRangeNote) {
      compareChartRangeNote.textContent =
        "Not enough resolved history to compare characters yet.";
    }
    return;
  }

  const isDivergence = metricKey === "divergenceSigned";
  const labels = buildAxisLabelsFromSeries(currentSeries, frame);
  const currentValues = getSeriesValues(currentSeries, metricKey, isDivergence);
  const otherValues = getSeriesValues(otherSeries, metricKey, isDivergence);
  const yBounds = isDivergence
    ? getDivergenceYAxisBounds([...currentValues, ...otherValues])
    : getYAxisBounds([...currentValues, ...otherValues]);
  const currentPalette = {
    positive: [250, 204, 21],
    negative: [234, 179, 8],
    positiveBorder: [202, 138, 4],
    negativeBorder: [161, 98, 7],
  };
  const otherPalette = {
    positive: [59, 130, 246],
    negative: [99, 102, 241],
    positiveBorder: [30, 64, 175],
    negativeBorder: [67, 56, 202],
  };
  const currentColors = getOverlayColors(
    currentValues,
    currentPalette,
    0.45,
    0.7,
  );
  const otherColors = getOverlayColors(otherValues, otherPalette, 0.38, 0.65);

  const pxPerBar = 56;
  comparePerfChart.width = Math.max(1200, currentValues.length * pxPerBar);
  comparePerfChart.height = 320;

  if (compareBarsChart) compareBarsChart.destroy();

  compareBarsChart = new Chart(comparePerfChart.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: currentName,
          data: currentValues,
          backgroundColor: currentColors.background,
          borderColor: currentColors.border,
          borderWidth: 1.1,
          borderRadius: 4,
          grouped: false,
        },
        {
          label: otherName,
          data: otherValues,
          backgroundColor: otherColors.background,
          borderColor: otherColors.border,
          borderWidth: 1,
          borderRadius: 4,
          grouped: false,
        },
      ],
    },
    options: {
      responsive: false,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: "#123e54", boxWidth: 12 },
        },
      },
      scales: {
        y: {
          min: yBounds.min,
          max: yBounds.max,
          grid: {
            color: (context) =>
              Number(context.tick?.value) === 0 ? "#000000" : "#d3dce6",
            lineWidth: (context) => (Number(context.tick?.value) === 0 ? 3 : 1),
          },
          ticks: {
            stepSize: yBounds.stepSize,
            color: "#123e54",
            callback: (value) =>
              isDivergence
                ? Number(value).toFixed(1)
                : Number(value).toFixed(1),
          },
        },
        x: {
          grid: { display: false },
          ticks: {
            autoSkip: false,
            maxRotation: 45,
            minRotation: 45,
            color: "#10455f",
          },
        },
      },
    },
  });

  if (compareChartRangeNote) {
    const oldest = labels[0];
    const newest = labels[labels.length - 1];
    compareChartRangeNote.textContent = `${oldest} (oldest) <- ${currentValues.length} rounds -> ${newest} (latest)`;
  }
  if (compareSeriesInfo) {
    compareSeriesInfo.innerHTML = `
      <span class="compare-series-chip current"><i></i>${currentName}</span>
      <span class="compare-series-chip other"><i></i>${otherName}</span>
    `;
  }
  if (compareChartScrollWrapper) {
    requestAnimationFrame(() => {
      compareChartScrollWrapper.scrollLeft =
        compareChartScrollWrapper.scrollWidth;
    });
  }
}

function getCompareLineColor(index, total) {
  const softPalette = ["#4C78A8", "#72B7B2", "#54A24B", "#ECA82C", "#B279A2"];
  const safeTotal = Math.max(1, Number(total) || 1);
  const safeIndex = Math.max(0, Number(index) || 0);
  const baseColor = softPalette[safeIndex % softPalette.length];
  const rgba = (hex, alpha) => {
    const clean = String(hex || "").replace("#", "");
    const normalized =
      clean.length === 3
        ? clean
            .split("")
            .map((c) => c + c)
            .join("")
        : clean;
    const n = Number.parseInt(normalized, 16);
    const r = (n >> 16) & 255;
    const g = (n >> 8) & 255;
    const b = n & 255;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };
  return {
    border: baseColor,
    background: rgba(baseColor, 0.2),
    groupedFill: rgba(baseColor, 0.6),
  };
}

function buildRoundLabels(series) {
  const count = Array.isArray(series) ? series.length : 0;
  if (count <= 0) return [];
  const latestRound = Number(latestLiveRoundId);
  if (!Number.isInteger(latestRound) || latestRound <= 0) {
    return (series || []).map((_, index) => `Round ${index + 1}`);
  }
  const firstRound = Math.max(1, latestRound - count + 1);
  return Array.from(
    { length: count },
    (_, index) => `Round ${firstRound + index}`,
  );
}

function syncCompareFrameControlVisibility() {
  if (!compareFrameControlGroup) return;
  compareFrameControlGroup.hidden = selectedCompareChart === "bar";
}

function renderCompareGroupedBarsAll(seriesByCharacter, metricKey) {
  if (typeof Chart === "undefined" || !comparePerfChart) return;
  if (!Array.isArray(seriesByCharacter) || !seriesByCharacter.length) return;

  const isDivergence = metricKey === "divergenceSigned";
  const labels = buildRoundLabels(seriesByCharacter[0].series);
  const allValues = seriesByCharacter.flatMap((item) =>
    getSeriesValues(item.series, metricKey, isDivergence),
  );
  const yBounds = isDivergence
    ? getDivergenceYAxisBounds(allValues)
    : getYAxisBounds(allValues);
  const pxPerGroup = 64;
  comparePerfChart.width = Math.max(1200, labels.length * pxPerGroup);
  comparePerfChart.height = 320;

  if (compareBarsChart) compareBarsChart.destroy();

  const datasets = seriesByCharacter.map((item, index) => {
    const colors = getCompareLineColor(index, seriesByCharacter.length);
    return {
      label: item.name,
      data: getSeriesValues(item.series, metricKey, isDivergence),
      backgroundColor: colors.groupedFill,
      borderColor: colors.border,
      borderWidth: 1,
      borderRadius: 3,
    };
  });

  compareBarsChart = new Chart(comparePerfChart.getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: false,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: "#123e54", boxWidth: 12 },
        },
      },
      scales: {
        y: {
          min: yBounds.min,
          max: yBounds.max,
          grid: {
            color: (context) =>
              Number(context.tick?.value) === 0 ? "#000000" : "#d3dce6",
            lineWidth: (context) => (Number(context.tick?.value) === 0 ? 3 : 1),
          },
          ticks: {
            stepSize: yBounds.stepSize,
            color: "#123e54",
            callback: (value) =>
              isDivergence
                ? Number(value).toFixed(1)
                : Number(value).toFixed(1),
          },
        },
        x: {
          grid: { display: false },
          ticks: {
            autoSkip: false,
            maxRotation: 45,
            minRotation: 45,
            color: "#10455f",
          },
        },
      },
    },
  });

  if (compareChartRangeNote) {
    const oldest = labels[0];
    const newest = labels[labels.length - 1];
    compareChartRangeNote.textContent = `${oldest} (oldest) <- ${labels.length} rounds -> ${newest} (latest)`;
  }
  if (compareSeriesInfo) {
    compareSeriesInfo.innerHTML = datasets
      .map(
        (dataset) =>
          `<span class="compare-series-chip"><i style="background:${dataset.borderColor}"></i>${dataset.label}</span>`,
      )
      .join("");
  }
  if (compareChartScrollWrapper) {
    requestAnimationFrame(() => {
      compareChartScrollWrapper.scrollLeft =
        compareChartScrollWrapper.scrollWidth;
    });
  }
}

function renderCompareLinesAll(seriesByCharacter, metricKey, frame) {
  if (typeof Chart === "undefined" || !comparePerfChart) return;
  if (!Array.isArray(seriesByCharacter) || !seriesByCharacter.length) return;

  const isDivergence = metricKey === "divergenceSigned";
  const labels = buildAxisLabelsFromSeries(seriesByCharacter[0].series, frame);
  const allValues = seriesByCharacter.flatMap((item) =>
    getSeriesValues(item.series, metricKey, isDivergence),
  );
  const yBounds = isDivergence
    ? getDivergenceYAxisBounds(allValues)
    : getYAxisBounds(allValues);
  const pxPerPoint = 56;
  comparePerfChart.width = Math.max(1200, labels.length * pxPerPoint);
  comparePerfChart.height = 320;

  if (compareBarsChart) compareBarsChart.destroy();

  const datasets = seriesByCharacter.map((item, index) => {
    const colors = getCompareLineColor(index, seriesByCharacter.length);
    return {
      label: item.name,
      data: getSeriesValues(item.series, metricKey, isDivergence),
      borderColor: colors.border,
      backgroundColor: colors.background,
      pointRadius: 1.6,
      pointHoverRadius: 3.2,
      borderWidth: 2,
      tension: 0.25,
      fill: false,
    };
  });

  compareBarsChart = new Chart(comparePerfChart.getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets,
    },
    options: {
      responsive: false,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true,
          labels: { color: "#123e54", boxWidth: 12 },
        },
      },
      scales: {
        y: {
          min: yBounds.min,
          max: yBounds.max,
          grid: {
            color: (context) =>
              Number(context.tick?.value) === 0 ? "#000000" : "#d3dce6",
            lineWidth: (context) => (Number(context.tick?.value) === 0 ? 3 : 1),
          },
          ticks: {
            stepSize: yBounds.stepSize,
            color: "#123e54",
            callback: (value) =>
              isDivergence
                ? Number(value).toFixed(1)
                : Number(value).toFixed(1),
          },
        },
        x: {
          grid: { display: false },
          ticks: {
            autoSkip: false,
            maxRotation: 45,
            minRotation: 45,
            color: "#10455f",
          },
        },
      },
    },
  });

  if (compareChartRangeNote) {
    const oldest = labels[0];
    const newest = labels[labels.length - 1];
    compareChartRangeNote.textContent = `${oldest} (oldest) <- ${labels.length} bars -> ${newest} (latest)`;
  }
  if (compareSeriesInfo) {
    compareSeriesInfo.innerHTML = datasets
      .map(
        (dataset) =>
          `<span class="compare-series-chip"><i style="background:${dataset.borderColor}"></i>${dataset.label}</span>`,
      )
      .join("");
  }
  if (compareChartScrollWrapper) {
    requestAnimationFrame(() => {
      compareChartScrollWrapper.scrollLeft =
        compareChartScrollWrapper.scrollWidth;
    });
  }
}

function populatePerfCharacterNav() {
  if (!perfCharacterNav) return;
  perfCharacterNav.innerHTML = "";
  characters.forEach((character) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "perf-character-item";
    btn.textContent = displayCharacterName(character.name);
    btn.dataset.characterId = String(character.id);
    btn.classList.toggle(
      "active",
      String(character.id) === String(selectedAnalysisCharacterId),
    );
    btn.addEventListener("click", () => {
      selectCharacter(character.id);
    });
    perfCharacterNav.appendChild(btn);
  });
}

function syncCompareState() {
  const allSeries = characters
    .map((character) => {
      const characterId = String(character.id || "");
      const series = performanceData[characterId]?.[selectedCompareFrame];
      if (!Array.isArray(series) || !series.length) return null;
      return {
        name: displayCharacterName(character.name),
        series: series.slice(-historyBarsCount),
      };
    })
    .filter(Boolean);
  if (!allSeries.length) return;

  const metricKey =
    selectedCompareChart === "divergence" ? "divergenceSigned" : "momentum";
  const label =
    selectedCompareChart === "divergence"
      ? "Divergence Line Graph"
      : "Grouped Bar Chart";
  if (compareChartTitle) {
    compareChartTitle.textContent = `${label} - ${selectedCompareFrame} (All Characters)`;
  }
  if (selectedCompareChart === "divergence") {
    renderCompareLinesAll(allSeries, metricKey, selectedCompareFrame);
  } else {
    renderCompareGroupedBarsAll(allSeries, metricKey);
  }
}

function syncPerformanceState() {
  if (!isPerformanceViewActive()) {
    performanceViewDirty = true;
    return;
  }

  performanceViewDirty = false;
  const characterId = String(selectedAnalysisCharacterId || "");
  const baseSeries = performanceData[characterId]?.[selectedCharFrame];
  if (!baseSeries) return;

  if (perfCharacterNav) {
    perfCharacterNav
      .querySelectorAll(".perf-character-item")
      .forEach((item) => {
        item.classList.toggle(
          "active",
          item.dataset.characterId === String(characterId),
        );
      });
  }

  const series = baseSeries.slice(-historyBarsCount);
  const metricKey =
    selectedCharChart === "divergence" ? "divergenceSigned" : "momentum";
  const chartLabel =
    selectedCharChart === "divergence" ? "Divergence Bar Graph" : "Bar Chart";
  if (charChartTitle) {
    charChartTitle.textContent = `${chartLabel} - ${selectedCharFrame}`;
  }
  renderCharacterBars(series, metricKey, selectedCharFrame);
  renderGeneralPerformance();
  syncCompareState();
}

function initPerformanceControls() {
  if (performanceControlsBound) return;
  performanceControlsBound = true;

  charChartButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedCharChart = btn.dataset.charChart;
      charChartButtons.forEach((item) =>
        item.classList.toggle(
          "active",
          item.dataset.charChart === selectedCharChart,
        ),
      );
      syncPerformanceState();
    });
  });

  charFrameButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedCharFrame = btn.dataset.charFrame;
      charFrameButtons.forEach((item) =>
        item.classList.toggle(
          "active",
          item.dataset.charFrame === selectedCharFrame,
        ),
      );
      syncPerformanceState();
    });
  });

  generalChartButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedGeneralChart = btn.dataset.generalChart;
      generalChartButtons.forEach((item) =>
        item.classList.toggle(
          "active",
          item.dataset.generalChart === selectedGeneralChart,
        ),
      );
      syncPerformanceState();
    });
  });

  generalFrameButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedGeneralFrame = btn.dataset.generalFrame;
      generalFrameButtons.forEach((item) =>
        item.classList.toggle(
          "active",
          item.dataset.generalFrame === selectedGeneralFrame,
        ),
      );
      syncPerformanceState();
    });
  });

  compareChartButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedCompareChart = btn.dataset.compareChart;
      compareChartButtons.forEach((item) =>
        item.classList.toggle(
          "active",
          item.dataset.compareChart === selectedCompareChart,
        ),
      );
      syncCompareFrameControlVisibility();
      syncCompareState();
    });
  });

  compareFrameButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      selectedCompareFrame = btn.dataset.compareFrame;
      compareFrameButtons.forEach((item) =>
        item.classList.toggle(
          "active",
          item.dataset.compareFrame === selectedCompareFrame,
        ),
      );
      syncCompareState();
    });
  });

  syncCompareFrameControlVisibility();
}

function displayCharacterName(rawName) {
  const name = String(rawName || "").trim();
  if (!name) return "Unknown";
  const [clean] = name.split("_");
  return clean || name;
}

function createCharacterCard(character, isSelected) {
  const cleanName = displayCharacterName(character.name);
  const button = document.createElement("button");
  button.type = "button";
  button.className = `character-card${isSelected ? " selected" : ""}`;
  button.dataset.characterId = String(character.id);
  button.dataset.name = character.name;
  button.dataset.stamina = String(character.stamina);
  button.dataset.control = String(character.control);
  button.dataset.power = String(character.power);
  button.innerHTML = `
    <div class="character-head">
      <img
        class="character-avatar"
        src="/clientside/static/images/logo-vector.png"
        alt="${character.name} avatar"
      />
    </div>
    <h3>${cleanName}</h3>
    <div class="stats">
      <div class="stat-row">
        <span>Stamina</span>
        <span class="stat-score" data-role="staminaScore"></span>
      </div>
      <div class="stat-track">
        <span class="stat-fill" data-role="staminaBar"></span>
      </div>
      <div class="stat-row">
        <span>Control</span>
        <span class="stat-score" data-role="controlScore"></span>
      </div>
      <div class="stat-track">
        <span class="stat-fill" data-role="controlBar"></span>
      </div>
      <div class="stat-row">
        <span>Power</span>
        <span class="stat-score" data-role="powerScore"></span>
      </div>
      <div class="stat-track">
        <span class="stat-fill" data-role="powerBar"></span>
      </div>
    </div>
  `;

  ["stamina", "control", "power"].forEach((statName) => {
    const rawValue = Number(character[statName] || 0);
    const level = toLevel(rawValue);
    const scoreEl = button.querySelector(`[data-role="${statName}Score"]`);
    const barEl = button.querySelector(`[data-role="${statName}Bar"]`);
    if (!scoreEl || !barEl) return;
    scoreEl.textContent = `${level.toFixed(1)}/10`;
    barEl.style.width = `${level * 10}%`;
    barEl.style.background = "#00ffff";
  });

  button.addEventListener("click", () => selectCharacter(character.id));
  return button;
}

function selectedCharacter() {
  return characters.find((item) => item.id === selectedCharacterId) || null;
}

function renderSelectedCharacterState() {
  const current = selectedCharacter();

  if (!current) {
    selectedCharacterMeta.textContent = isUserLoggedIn
      ? "No character selected."
      : "Login required to place bets.";
    return;
  }

  const cleanName = displayCharacterName(current.name);
  selectedCharacterMeta.textContent = `Selected: ${cleanName} | stamina: ${current.stamina} | control: ${current.control} | power: ${current.power}`;
}

function renderSlip() {
  if (!slipList || !slipEmpty) return;
  const existingRows = slipList.querySelectorAll(".slip-item");
  existingRows.forEach((row) => row.remove());
  renderSlipSummary();

  if (!betSlip.length) {
    slipEmpty.style.display = "block";
    return;
  }

  slipEmpty.style.display = "none";
  const totalStake = getStakeFromInput(slipStakeInput);
  const perOutcomeStake =
    totalStake && betSlip.length
      ? Number((totalStake / betSlip.length).toFixed(2))
      : null;

  betSlip.forEach((bet, index) => {
    const possibleWin =
      perOutcomeStake !== null
        ? formatMoney(Number(bet.odds || 0) * perOutcomeStake)
        : "--";
    const item = document.createElement("div");
    item.className = "slip-item";
    item.innerHTML = `
      <div class="slip-item-line">
        <span>${bet.characterName}</span>
        <strong>${bet.option}</strong>
      </div>
      <div class="slip-item-footer">
        <div class="slip-item-odd">Odds: ${bet.odds} | Stake: ${perOutcomeStake !== null ? formatMoney(perOutcomeStake) : "--"} | Possible Win: ${possibleWin}</div>
        <button class="slip-item-cancel" type="button" aria-label="Cancel selected bet" title="Cancel selected bet">
          <i class="bi bi-x-circle"></i>
        </button>
      </div>
    `;
    const cancelBtn = item.querySelector(".slip-item-cancel");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        betSlip.splice(index, 1);
        renderSlip();
        refreshOptionAvailability();
      });
    }
    slipList.appendChild(item);
  });
  refreshOptionAvailability();
}

function parseBetKey(rawKey) {
  const key = String(rawKey || "");
  const separatorIndex = key.indexOf(":");
  if (separatorIndex === -1) {
    return { characterId: null, characterName: null, option: key };
  }

  const left = key.slice(0, separatorIndex);
  const option = key.slice(separatorIndex + 1);
  const idMatch = left.match(/^C(\d+)$/);

  if (idMatch) {
    return { characterId: Number(idMatch[1]), characterName: null, option };
  }

  return { characterId: null, characterName: left, option };
}

function characterNameById(characterId) {
  const found = characters.find((item) => item.id === characterId);
  return found ? displayCharacterName(found.name) : `Character #${characterId}`;
}

function deriveSlipItemOutcomeResults(item, roundNumber) {
  const explicitResults = Array.isArray(item?.outcomeResults)
    ? item.outcomeResults
    : [];
  if (explicitResults.length) {
    return explicitResults;
  }

  const safeCharacterId = Number(item?.characterId);
  if (!Number.isFinite(safeCharacterId)) {
    return [];
  }

  const safeRoundNumber = Number(roundNumber);
  const optionCode = String(item?.optionCode || "")
    .trim()
    .toUpperCase();
  const resolveOutcomeForSelectedPhase = (phaseLookup, selectedPhaseNumber) => {
    const safeLookup = phaseLookup || new Map();
    const directOutcomeCode = String(
      safeLookup.get(selectedPhaseNumber) || "",
    ).toUpperCase();
    if (directOutcomeCode) {
      return {
        phaseNumber: selectedPhaseNumber,
        outcomeCode: directOutcomeCode,
      };
    }

    let terminalDrownPhase = null;
    for (const [phaseNumber, outcomeCodeRaw] of safeLookup.entries()) {
      const phase = Number(phaseNumber);
      const outcomeCode = String(outcomeCodeRaw || "").toUpperCase();
      if (
        Number.isFinite(phase) &&
        phase <= selectedPhaseNumber &&
        outcomeCode === "DROWN" &&
        (terminalDrownPhase === null || phase < terminalDrownPhase)
      ) {
        terminalDrownPhase = phase;
      }
    }

    if (terminalDrownPhase !== null) {
      return {
        phaseNumber: terminalDrownPhase,
        outcomeCode: "DROWN",
      };
    }

    return null;
  };
  const buildResolvedEntry = (
    selectedOutcomeCode,
    selectedPhaseNumber,
    fallbackLabel,
  ) => {
    const resolvedOutcome = resolveOutcomeForSelectedPhase(
      phaseLookup,
      selectedPhaseNumber,
    );
    const resolvedOutcomeCode = resolvedOutcome?.outcomeCode || null;
    const resolvedPhaseNumber = Number(resolvedOutcome?.phaseNumber);
    const isExactMatch =
      resolvedOutcomeCode === selectedOutcomeCode &&
      Number.isFinite(resolvedPhaseNumber) &&
      resolvedPhaseNumber === selectedPhaseNumber;

    return {
      phaseNumber: selectedPhaseNumber,
      label: fallbackLabel,
      selectedOutcomeCode,
      resolvedOutcomeCode,
      resolvedPhaseNumber: Number.isFinite(resolvedPhaseNumber)
        ? resolvedPhaseNumber
        : null,
      status: resolvedOutcomeCode ? (isExactMatch ? "won" : "lost") : "pending",
    };
  };
  const buildFromPhaseLookup = (phaseLookup) => {
    const singleMatch = optionCode.match(/^([FD])([1-5])$/);
    if (singleMatch) {
      const phaseNumber = Number.parseInt(singleMatch[2], 10);
      const expected = singleMatch[1] === "F" ? "FLOAT" : "DROWN";
      return [
        buildResolvedEntry(
          expected,
          phaseNumber,
          `${singleMatch[1]}${phaseNumber}`,
        ),
      ];
    }

    const doubleMatch = optionCode.match(/^F([1-5])ANDD([1-5])$/);
    if (doubleMatch) {
      return [
        {
          label: `F${Number.parseInt(doubleMatch[1], 10)}`,
          phaseNumber: Number.parseInt(doubleMatch[1], 10),
          expected: "FLOAT",
        },
        {
          label: `D${Number.parseInt(doubleMatch[2], 10)}`,
          phaseNumber: Number.parseInt(doubleMatch[2], 10),
          expected: "DROWN",
        },
      ]
        .map((entry) =>
          buildResolvedEntry(entry.expected, entry.phaseNumber, entry.label),
        )
        .filter(Boolean);
    }

    return [];
  };

  const phaseLookup = new Map();
  if (Number.isFinite(safeRoundNumber)) {
    const cachedLookup = latestResolvedOutcomeLookup.get(
      `${safeRoundNumber}:${safeCharacterId}`,
    );
    if (cachedLookup instanceof Map) {
      cachedLookup.forEach((outcomeCode, phaseNumber) => {
        if (!phaseLookup.has(phaseNumber)) {
          phaseLookup.set(phaseNumber, outcomeCode);
        }
      });
    }
  }

  const shouldUsePostGameStats =
    Number.isFinite(safeRoundNumber) &&
    Number(latestPostGameStatsPayload?.roundId) === safeRoundNumber;
  const postGameCharacter =
    shouldUsePostGameStats &&
    Array.isArray(latestPostGameStatsPayload?.characters)
      ? latestPostGameStatsPayload.characters.find(
          (entry) => Number(entry?.characterId) === safeCharacterId,
        )
      : null;
  if (postGameCharacter && Array.isArray(postGameCharacter.phases)) {
    postGameCharacter.phases.forEach((value, index) => {
      const phaseNumber = index + 1;
      const normalized = String(value || "").toUpperCase();
      if (normalized) {
        if (!phaseLookup.has(phaseNumber)) {
          phaseLookup.set(phaseNumber, normalized);
        }
      }
    });
  }

  return buildFromPhaseLookup(phaseLookup);
}

function formatResolvedSlipOutcomeLabel(entry) {
  const phaseNumber = Number(entry?.resolvedPhaseNumber);
  const resolvedOutcomeCode = String(
    entry?.resolvedOutcomeCode || "",
  ).toUpperCase();

  if (Number.isFinite(phaseNumber) && resolvedOutcomeCode === "FLOAT") {
    return `F${phaseNumber}`;
  }
  if (Number.isFinite(phaseNumber) && resolvedOutcomeCode === "DROWN") {
    return `D${phaseNumber}`;
  }
  return "-";
}

function createSlipOrderRow(item, roundNumber) {
  const row = document.createElement("div");
  const outcomeResults = deriveSlipItemOutcomeResults(item, roundNumber);
  const itemStatus = outcomeResults.some((entry) => entry.status === "lost")
    ? "lost"
    : outcomeResults.length &&
        outcomeResults.every((entry) => entry.status === "won")
      ? "won"
      : "";
  row.className = `transaction-slip-item${itemStatus ? ` ${itemStatus}` : ""}`;
  const outcomesMarkup = outcomeResults.length
    ? `
      <div class="slip-outcome-results">
        ${outcomeResults
          .map(
            (entry) =>
              `<span class="slip-outcome-chip ${entry.status}">${formatResolvedSlipOutcomeLabel(entry)}</span>`,
          )
          .join("")}
      </div>
    `
    : "";
  row.innerHTML = `
    <div class="slip-item-line">
      <span>${item.characterName || "Unknown"}</span>
      <div class="slip-item-line-right">
        <strong class="slip-option-code${itemStatus ? ` ${itemStatus}` : ""}">${item.optionCode || "-"}</strong>
        ${outcomesMarkup}
      </div>
    </div>
    <div class="slip-item-odd">Odds: ${formatMoney(item.odds)} | Stake: ${formatMoney(item.stake)} | Possible Win: ${formatMoney(item.possibleWin)}</div>
  `;
  return row;
}

function createSlipCard(slip, { showRound = true } = {}) {
  const card = document.createElement("article");
  card.className = "bets-box";

  const headerBits = [];
  if (showRound && Number.isFinite(Number(slip.roundNumber))) {
    headerBits.push(`Round ${slip.roundNumber}`);
  }
  if (slip.placedAt) {
    headerBits.push(formatDateTime(slip.placedAt));
  }

  const headerText = headerBits.join(" | ");
  const itemsMarkupHost = document.createElement("div");
  itemsMarkupHost.className = "bets-list";

  const items = Array.isArray(slip.items) ? slip.items : [];
  if (!items.length) {
    itemsMarkupHost.innerHTML =
      '<p class="slip-empty">No paid orders recorded for this slip.</p>';
  } else {
    items.forEach((item) =>
      itemsMarkupHost.appendChild(createSlipOrderRow(item, slip.roundNumber)),
    );
  }

  card.innerHTML = `
    <div class="current-bets-head">
      <span>${headerText || "Slip"}</span>
      <span>Stake: ${formatMoney(slip.totalStake)} | Win: ${formatMoney(slip.totalPossibleWin)}</span>
    </div>
  `;
  card.appendChild(itemsMarkupHost);
  return card;
}

function renderSlipActivity(data) {
  latestSlipActivityPayload = data;
  if (liveBets) {
    liveBets.innerHTML = "";
    if (!data?.currentSlip) {
      liveBets.innerHTML =
        '<p class="slip-empty">No paid orders yet for the current round.</p>';
    } else {
      liveBets.appendChild(
        createSlipCard(data.currentSlip, { showRound: true }),
      );
    }
  }

  if (pastSlipsList) {
    pastSlipsList.innerHTML = "";
    const allPastSlips = Array.isArray(data?.pastSlips) ? data.pastSlips : [];
    const latestPastRounds = Array.from(
      new Set(
        allPastSlips
          .map((slip) => Number(slip?.roundNumber))
          .filter(Number.isFinite)
          .sort((a, b) => b - a),
      ),
    ).slice(0, 3);
    const pastSlips = allPastSlips.filter((slip) =>
      latestPastRounds.includes(Number(slip?.roundNumber)),
    );
    if (!pastSlips.length) {
      pastSlipsList.innerHTML = '<p class="slip-empty">No past slips yet.</p>';
    } else {
      pastSlips.forEach((slip) => {
        pastSlipsList.appendChild(createSlipCard(slip, { showRound: true }));
      });
    }
  }
}

function addToSlip(option, betType) {
  if (!isUserLoggedIn) {
    alert("Please log in to place bets.");
    return;
  }
  if (bettingLocked || isBettingLocked()) {
    alert("Betting is locked in the last 10 seconds.");
    return;
  }

  const current = selectedCharacter();
  if (!current) return;

  const isDoubleBet = betType === "double";
  const stake = getStakeFromInput(slipStakeInput);
  if (stake === null) {
    alert("Enter a valid stake of at least 1.00.");
    if (slipStakeInput) slipStakeInput.focus();
    return;
  }

  betSlip.push({
    characterId: current.id,
    characterName: displayCharacterName(current.name),
    option: option.key,
    odds: option.odds,
    probability: option.probability,
    betType: isDoubleBet ? "Double" : "Single",
  });
  trackBettorActivity("betslip_created", {
    character_id: current.id,
    option_code: option.key,
    bet_type: isDoubleBet ? "double" : "single",
  });
  renderSlip();
}

function formatOptionDisplayLabel(optionKey) {
  const raw = String(optionKey || "").trim();
  const doubleMatch = raw.match(/^F(\d)andD(\d)$/i);
  if (doubleMatch) {
    return `F${doubleMatch[1]}/D${doubleMatch[2]}`;
  }
  return raw.toUpperCase();
}

function createOptionButton(option, betType, character, constraints) {
  const button = document.createElement("button");
  button.className = "odd-btn";
  button.type = "button";
  button.innerHTML = `${formatOptionDisplayLabel(option.key)}<strong>${option.odds}x</strong>`;
  button.title = `Probability: ${toPercent(option.probability)}`;

  const safeConstraints =
    constraints || buildSelectionConstraints(character?.id);
  const isDisabled =
    betType === "double"
      ? shouldDisableDoubleOption(option.key, safeConstraints)
      : shouldDisableSingleOption(option.key, safeConstraints);
  const isSelected = isOptionSelected(option.key, betType, safeConstraints);

  if (!isUserLoggedIn) {
    button.disabled = true;
    button.classList.add("disabled");
    button.title = "Login to place bets";
    return button;
  }
  if (bettingLocked || isBettingLocked()) {
    button.disabled = true;
    button.classList.add("disabled");
    button.title = "Betting locked (last 10 seconds)";
    return button;
  }
  if (isSelected) {
    button.classList.add("selected");
    button.dataset.state = "Selected";
  }
  if (isDisabled) {
    button.disabled = true;
    button.classList.add("disabled");
    button.title = "Selection locked by current round rules";
    return button;
  }

  button.addEventListener("click", () => {
    if (character?.id) {
      selectedCharacterId = Number(character.id);
      renderSelectedCharacterState();
      renderOptionsBoard();
    }
    addToSlip(option, betType);
  });
  return button;
}

function createOddsBoardCard(character, data) {
  const card = document.createElement("article");
  const isSelected = Number(character.id) === Number(selectedCharacterId);
  const cleanName = displayCharacterName(character.name);
  const constraints = buildSelectionConstraints(character?.id);
  card.className = `odds-market-card${isSelected ? " selected" : ""}`;
  card.tabIndex = 0;
  card.setAttribute("role", "button");
  card.setAttribute("aria-pressed", isSelected ? "true" : "false");

  function handleCardSelect(event) {
    if (event?.target && event.target.closest(".odd-btn")) return;
    selectedCharacterId = Number(character.id);
    renderSelectedCharacterState();
    renderOptionsBoard();
  }

  card.addEventListener("click", handleCardSelect);
  card.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleCardSelect(event);
    }
  });

  const singleButtons = [];
  const doubleButtons = [];
  (data?.single?.draw || []).forEach((item) =>
    singleButtons.push(
      createOptionButton(item, "single", character, constraints),
    ),
  );
  (data?.single?.float || []).forEach((item) =>
    singleButtons.push(
      createOptionButton(item, "single", character, constraints),
    ),
  );
  ["F1", "F2", "F3", "F4"].forEach((key) => {
    const items = Array.isArray(data?.double?.[key]) ? data.double[key] : [];
    items.forEach((item) =>
      doubleButtons.push(
        createOptionButton(item, "double", character, constraints),
      ),
    );
  });

  card.innerHTML = `
    <div class="odds-market-head">
      <div class="odds-market-title">
        <img
          class="odds-market-avatar"
          src="/clientside/static/images/logo-vector.png"
          alt="${character.name} avatar"
        />
        <div>
          <div class="odds-market-name">${cleanName}</div>
        </div>
      </div>
    </div>
    <div class="odds-market-stats">
      <div class="odds-stat-row">
        <span>Stamina</span>
        <span class="odds-stat-bar"><span class="odds-stat-fill" data-stat="stamina"></span></span>
        <strong>${toLevel(character.stamina).toFixed(1)}/10</strong>
      </div>
      <div class="odds-stat-row">
        <span>Control</span>
        <span class="odds-stat-bar"><span class="odds-stat-fill" data-stat="control"></span></span>
        <strong>${toLevel(character.control).toFixed(1)}/10</strong>
      </div>
      <div class="odds-stat-row">
        <span>Power</span>
        <span class="odds-stat-bar"><span class="odds-stat-fill" data-stat="power"></span></span>
        <strong>${toLevel(character.power).toFixed(1)}/10</strong>
      </div>
    </div>
    <div class="odds-market-sections">
      <section class="odds-market-block">
        <h3>Single Bets</h3>
        <p class="odds-market-hint">D = Drown phase, F = Float phase</p>
        <div class="odds-grid odds-grid-single" data-role="single-grid"></div>
      </section>
      <section class="odds-market-block">
        <h3>Double Bets</h3>
        <p class="odds-market-hint">Float first, drown later</p>
        <div class="odds-grid odds-grid-double" data-role="double-grid"></div>
      </section>
    </div>
  `;

  ["stamina", "control", "power"].forEach((statName) => {
    const fill = card.querySelector(`[data-stat="${statName}"]`);
    if (fill) {
      fill.style.width = `${toLevel(character[statName]) * 10}%`;
    }
  });
  const singleGrid = card.querySelector('[data-role="single-grid"]');
  const doubleGrid = card.querySelector('[data-role="double-grid"]');
  singleButtons.forEach((button) => singleGrid?.appendChild(button));
  doubleButtons.forEach((button) => doubleGrid?.appendChild(button));
  return card;
}

function renderOptionsBoard() {
  if (!oddsBoardGrid) return;
  oddsBoardGrid.innerHTML = "";

  if (!characters.length || latestOptionsByCharacter.size === 0) {
    oddsBoardGrid.innerHTML =
      '<div class="odds-empty-board">No odds available yet.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();
  characters.forEach((character) => {
    const payload = latestOptionsByCharacter.get(Number(character.id));
    if (!payload) return;
    fragment.appendChild(createOddsBoardCard(character, payload));
  });
  oddsBoardGrid.appendChild(fragment);
}

async function loadCharacters() {
  try {
    const [currentRes, historyRes] = await Promise.all([
      fetch(`${API_BASE}/api/characters?limit=5`),
      fetch(`${API_BASE}/api/characters?limit=20`),
    ]);
    const [currentData, historyData] = await Promise.all([
      currentRes.json().catch(() => null),
      historyRes.json().catch(() => null),
    ]);

    if (!currentRes.ok) {
      console.error(
        "Failed to load characters:",
        currentRes.status,
        currentData,
      );
      if (oddsBoardGrid) {
        const message =
          currentData?.error ||
          currentData?.details ||
          currentRes.statusText ||
          "Unable to load characters.";
        oddsBoardGrid.innerHTML = `<div class="odds-empty-board">Unable to load characters. ${message}</div>`;
      }
      return;
    }

    characters = Array.isArray(currentData) ? currentData : [];
    characterHistoryByName = buildCharacterHistoryMap(
      Array.isArray(historyData) ? historyData : [],
    );

    if (!characters.length) {
      if (oddsBoardGrid) {
        oddsBoardGrid.innerHTML =
          '<div class="odds-empty-board">No characters available.</div>';
      }
      return;
    }

    renderSelectedCharacterState();
    rebuildPerformanceData();
    selectedAnalysisCharacterId = selectedCharacterId;
    populatePerfCharacterNav();
    syncPerformanceState();
  } catch (error) {
    console.error("Could not load characters:", error);
    if (oddsBoardGrid) {
      const message = String(error?.message || error);
      oddsBoardGrid.innerHTML = `<div class="odds-empty-board">Unable to load characters. ${message}</div>`;
    }
  }
}

async function loadPerformance() {
  latestPerformancePayload = null;
  rebuildPerformanceData();

  if (!isUserLoggedIn) {
    syncPerformanceState();
    return;
  }

  try {
    const res = await fetch(
      `${API_BASE}/api/stats/performance/characters?limit=50`,
    );
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data?.error || "Could not load performance history.");
    }
    latestPerformancePayload = data;
  } catch (error) {
    console.error("Could not load performance history:", error);
  }

  rebuildPerformanceData();
  syncPerformanceState();
}

async function refreshRoundScopedData() {
  await loadCharacters();
  await loadOptions();

  if (
    !characters.some((item) => Number(item.id) === Number(selectedCharacterId))
  ) {
    selectedCharacterId = characters[0] ? Number(characters[0].id) : null;
  }

  latestOptionsPayload =
    latestOptionsByCharacter.get(Number(selectedCharacterId)) || null;
  renderSelectedCharacterState();
  renderOptionsBoard();
  renderSlip();
}

async function loadOptions() {
  if (!characters.length) return;
  const responses = await Promise.all(
    characters.map(async (character) => {
      const query = `?characterId=${encodeURIComponent(character.id)}`;
      const res = await fetch(`${API_BASE}/api/options${query}`);
      const data = await res.json().catch(() => ({}));
      return { characterId: Number(character.id), ok: res.ok, data };
    }),
  );

  latestOptionsByCharacter = new Map();
  responses.forEach(({ characterId, ok, data }) => {
    if (ok && data?.single && data?.double) {
      latestOptionsByCharacter.set(characterId, data);
    }
  });

  if (latestOptionsByCharacter.size > 0) {
    const marketsViewed = Array.from(latestOptionsByCharacter.values()).reduce(
      (sum, payload) => {
        const singles =
          (payload?.single?.draw || []).length +
          (payload?.single?.float || []).length;
        const doubles = Object.values(payload?.double || {}).reduce(
          (innerSum, items) => innerSum + (Array.isArray(items) ? items.length : 0),
          0,
        );
        return sum + singles + doubles;
      },
      0,
    );
    trackBettorActivity("odds_view", {
      characters_viewed: latestOptionsByCharacter.size,
      markets_viewed: marketsViewed,
    });
  }

  if (latestOptionsByCharacter.size === 0) {
    renderOptionsBoard();
    selectedCharacterMeta.textContent =
      "No odds found for available characters.";
    return;
  }

  const currentPayload = latestOptionsByCharacter.get(
    Number(selectedCharacterId),
  );
  latestOptionsPayload = currentPayload || null;
  renderOptionsBoard();
}

async function loadBets() {
  if (!liveBets && !pastSlipsList) return;
  if (!isUserLoggedIn) {
    if (liveBets) {
      liveBets.innerHTML =
        '<p class="slip-empty">Login to view your current round slip.</p>';
    }
    if (pastSlipsList) {
      pastSlipsList.innerHTML =
        '<p class="slip-empty">Login to view your past slips.</p>';
    }
    return;
  }

  const requestId = ++latestSlipActivityRequestId;
  try {
    const res = await fetch(`${API_BASE}/api/slips/me`, {
      headers: {
        ...getAuthHeaders(),
      },
    });
    const data = await res.json();
    if (!res.ok) {
      const message = data?.error || "Could not load bets.";
      throw new Error(message);
    }
    if (requestId !== latestSlipActivityRequestId) {
      return;
    }
    renderSlipActivity(data);
  } catch {
    if (requestId !== latestSlipActivityRequestId) {
      return;
    }
    if (liveBets) {
      liveBets.innerHTML =
        '<p class="slip-empty">Could not load current slip.</p>';
    }
    if (pastSlipsList) {
      pastSlipsList.innerHTML =
        '<p class="slip-empty">Could not load past slips.</p>';
    }
  }
}

function renderOutcomes(rows) {
  if (!outcomesGroups) return;

  const safeRows = Array.isArray(rows) ? rows : [];
  latestResolvedOutcomeRows = safeRows;
  latestResolvedOutcomeLookup = buildResolvedOutcomeLookup(safeRows);
  if (latestSlipActivityPayload) {
    renderSlipActivity(latestSlipActivityPayload);
  }
  const latestRound = safeRows.length ? Number(safeRows[0].roundId) : null;
  const characterIds = new Set(
    safeRows.map((row) => Number(row.characterId)).filter(Number.isFinite),
  );
  const marketIds = new Set(
    safeRows.map((row) => Number(row.marketId)).filter(Number.isFinite),
  );

  if (outcomesLatestRound) {
    outcomesLatestRound.textContent = Number.isFinite(latestRound)
      ? String(latestRound)
      : "-";
  }
  if (outcomesTotalCount)
    outcomesTotalCount.textContent = String(safeRows.length);
  if (outcomesCharacterCount) {
    outcomesCharacterCount.textContent = String(characterIds.size);
  }
  if (outcomesMarketCount)
    outcomesMarketCount.textContent = String(marketIds.size);

  if (!safeRows.length) {
    outcomesGroups.innerHTML =
      '<div class="outcome-empty">No resolved outcomes yet. Once a round closes, all 25 character-phase outcomes will appear here.</div>';
    return;
  }

  const grouped = new Map();
  safeRows.forEach((row) => {
    const roundId = Number(row.roundId);
    if (!grouped.has(roundId)) {
      grouped.set(roundId, []);
    }
    grouped.get(roundId).push(row);
  });

  const sections = Array.from(grouped.entries()).map(([roundId, roundRows]) => {
    const generatedAt = roundRows[0]?.generatedAt || null;
    const rowMarkup = roundRows
      .map((row) => {
        const phaseNumber = Number(row.phaseNumber);
        const outcomeCode = String(row.outcomeCode || "").toUpperCase();
        const badgeClass =
          outcomeCode === "FLOAT"
            ? "float"
            : outcomeCode === "DROWN"
              ? "drown"
              : "";
        return `
          <tr>
            <td>${formatCharacterLabel(row.characterName)}</td>
            <td>Phase ${phaseNumber}</td>
            <td><span class="outcome-market-tag">Market ${row.marketId}</span></td>
            <td><span class="outcome-badge ${badgeClass}">${outcomeCode || "-"}</span></td>
            <td>${formatDateTime(row.generatedAt)}</td>
          </tr>
        `;
      })
      .join("");

    return `
      <article class="outcome-round-card">
        <div class="outcome-round-head">
          <div>
            <h3>Round ${roundId}</h3>
            <div class="outcome-round-meta">${roundRows.length} stone throw outcomes across all character markets</div>
          </div>
          <div class="outcome-round-meta">Generated ${formatDateTime(generatedAt)}</div>
        </div>
        <div class="outcome-table-wrap">
          <table class="outcome-table">
            <thead>
              <tr>
                <th>Character</th>
                <th>Phase</th>
                <th>Market</th>
                <th>Outcome</th>
                <th>Generated</th>
              </tr>
            </thead>
            <tbody>${rowMarkup}</tbody>
          </table>
        </div>
      </article>
    `;
  });

  outcomesGroups.innerHTML = sections.join("");
}

async function loadOutcomes() {
  if (!outcomesGroups) return;

  try {
    outcomesGroups.innerHTML =
      '<div class="simple-panel">Loading outcomes...</div>';
    const [outcomesRes, postGameStatsRes] = await Promise.all([
      fetch(
        `${API_BASE}/api/outcomes?roundLimit=${STONE_THROW_OUTCOME_ROUND_LIMIT}`,
        {
          headers: {
            ...getAuthHeaders(),
          },
        },
      ),
      fetch(`${API_BASE}/api/post-game-stats`, {
        headers: {
          ...getAuthHeaders(),
        },
      }),
    ]);
    const payload = await outcomesRes.json().catch(() => []);
    const postGameStatsPayload = await postGameStatsRes
      .json()
      .catch(() => null);
    latestPostGameStatsPayload =
      postGameStatsRes.ok && postGameStatsPayload ? postGameStatsPayload : null;
    if (!outcomesRes.ok) {
      throw new Error(payload?.error || "Could not load outcomes.");
    }
    renderOutcomes(payload);
    if (isUserLoggedIn) {
      await loadBets();
      await loadPerformance();
    }
  } catch (error) {
    console.error("Could not load outcomes:", error);
    outcomesGroups.innerHTML = `<div class="outcome-empty">${error.message || "Could not load outcomes."}</div>`;
  }
}

async function placeSlipBets() {
  if (!isUserLoggedIn) {
    alert("Please log in to place bets.");
    return;
  }
  if (bettingLocked || isBettingLocked()) {
    alert("Betting is locked in the last 10 seconds.");
    return;
  }

  if (!betSlip.length) {
    alert("Select at least one bet option first.");
    return;
  }

  const totalStake = getStakeFromInput(slipStakeInput);
  if (totalStake === null) {
    alert("Enter a valid stake of at least 1.00.");
    if (slipStakeInput) slipStakeInput.focus();
    return;
  }
  const perOutcomeStake = Number((totalStake / betSlip.length).toFixed(2));

  const requests = betSlip.map(async (bet) => {
    const response = await fetch(`${API_BASE}/api/bet`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        option: bet.option,
        characterId: bet.characterId,
        stake: perOutcomeStake,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      trackBettorActivity("failed_bet", {
        character_id: bet.characterId,
        option_code: bet.option,
        status: response.status,
      });
      throw new Error(payload?.error || `Bet failed (${response.status})`);
    }

    return payload;
  });

  const placedBets = await Promise.all(requests);
  trackBettorActivity("bet_placed", {
    bet_count: placedBets.length,
    total_stake: totalStake,
  });
  betSlip.length = 0;
  renderSlip();
  refreshOptionAvailability();
  await loadBets();
  await loadPerformance();
  const lines = (placedBets || []).map((bet) => {
    const optionCode = bet?.optionCode || bet?.option || "unknown";
    const phaseStart = Number(bet?.phaseStart);
    const phaseEndRaw = bet?.phaseEnd;
    const phaseEnd = phaseEndRaw === null ? null : Number(phaseEndRaw);

    if (Number.isFinite(phaseStart) && Number.isFinite(phaseEnd)) {
      return `${optionCode} (phases ${phaseStart}-${phaseEnd})`;
    }
    if (Number.isFinite(phaseStart)) {
      return `${optionCode} (phase ${phaseStart})`;
    }
    return optionCode;
  });
  const latestBalance = placedBets[placedBets.length - 1] || {};
  const latestBalanceValue = Number(latestBalance.playerBalance);
  if (Number.isFinite(latestBalanceValue)) {
    currentUserProfile = {
      ...(currentUserProfile || {}),
      demo_balance: latestBalanceValue,
    };
    renderHeaderChips();
    if (demoBalanceCard && !demoBalanceCard.hidden) {
      renderDemoModalFromProfile();
    }
  }
  const walletLine = Number.isFinite(latestBalanceValue)
    ? `\nWallet balance: ${formatMoney(latestBalanceValue)}`
    : "";

  alert(`Bet(s) placed:\n${lines.join("\n")}${walletLine}`);
}

function selectCharacter(characterId) {
  const nextCharacterId = Number(characterId);
  const didChange = nextCharacterId !== Number(selectedCharacterId);
  selectedCharacterId = nextCharacterId;
  latestOptionsPayload =
    latestOptionsByCharacter.get(Number(selectedCharacterId)) || null;
  renderSelectedCharacterState();
  renderOptionsBoard();
  if (!latestOptionsPayload) {
    loadOptions();
  }
  latestLiveOptionsVersion = null;
  startLiveUpdates(true);
  fetchAndApplyLiveSnapshot();
  selectedAnalysisCharacterId = selectedCharacterId;
  if (didChange) {
    trackBettorActivity("market_view", { character_id: selectedCharacterId });
    populatePerfCharacterNav();
    syncPerformanceState();
  }
}

menuButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const targetView = button.dataset.view;
    if (targetView === "view-account") {
      handleAccountMenuClick();
      return;
    }
    switchView(targetView);
  });
});

if (accountRealBtn) {
  accountRealBtn.addEventListener("click", () =>
    handleAccountSubAction("real"),
  );
}

if (accountDemoBtn) {
  accountDemoBtn.addEventListener("click", () =>
    handleAccountSubAction("demo"),
  );
}

if (demoBalanceSaveBtn) {
  demoBalanceSaveBtn.addEventListener("click", () => {
    saveDemoBalance();
  });
}

if (demoBalanceSetBtn) {
  demoBalanceSetBtn.addEventListener("click", () => {
    toggleDemoBalanceEditor();
  });
}

if (placeBetBtn) {
  placeBetBtn.addEventListener("click", () => {
    placeSlipBets().catch((error) => {
      console.error("Place bet request failed:", error);
      alert("Could not place bet(s).");
    });
  });
}

if (slipStakeInput) {
  slipStakeInput.addEventListener("input", () => {
    renderSlip();
  });

  slipStakeInput.addEventListener("blur", () => {
    normalizeStakeInput(slipStakeInput);
    renderSlip();
  });
}

async function init() {
  try {
    normalizeStakeInput(slipStakeInput);
    initGameplayFrameStack();
    await resolveLoginState();
    applyAccessControl();
    initPerformanceControls();
    if (!restoreGameplayScheduleFromStorage()) {
      showDefaultGameplay();
    }

    await loadCharacters();
    await loadOptions();

    await loadBets();
    await loadOutcomes();
    if (!isUserLoggedIn) {
      await loadPerformance();
    }

    renderSlip();
    startLiveUpdates(true);
    startGameplayStateSync();
    await startRoundTimer();
  } catch (error) {
    console.error("Dashboard init failed:", error);
    if (liveBets) {
      liveBets.innerHTML =
        '<p class="slip-empty">Could not initialize dashboard.</p>';
    }
  }
  if (globalGameplayState) {
    globalGameplayState.textContent = "State: Unknown";
  }
}

init();

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    fetchAndApplyLiveSnapshot();
    loadBets();
    if (performanceViewDirty) {
      syncPerformanceState();
    }
  }
});

window.addEventListener("beforeunload", () => {
  if (betSlip.length > 0) {
    trackBettorActivity("betslip_abandoned", {
      selected_count: betSlip.length,
    });
  }
  stopLiveUpdates();
  stopRoundTimer();
  stopGameplayStateSync();
});
