let CHARACTERS = [
  {
    name: "SHADOW",
    emoji: "S",
    color: "#e74c3c",
    power: 95,
    control: 82,
    stamina: 78,
  },
  {
    name: "VIPER",
    emoji: "V",
    color: "#27ae60",
    power: 72,
    control: 96,
    stamina: 84,
  },
  {
    name: "PHOENIX",
    emoji: "P",
    color: "#e67e22",
    power: 88,
    control: 75,
    stamina: 92,
  },
  {
    name: "FROST",
    emoji: "F",
    color: "#3498db",
    power: 69,
    control: 94,
    stamina: 88,
  },
  {
    name: "THUNDER",
    emoji: "T",
    color: "#f1c40f",
    power: 98,
    control: 71,
    stamina: 86,
  },
];

let currentChar = 0;
let rotationTime = 18;
let globalTime = 90;
let gameData = [];
let stoneAnimation = null;
let flipTimeout = null;
let currentStonePosition = 8;
let externalSyncActive = false;
let externalSyncTimeout = null;
let useLiveRoundOutcomes = false;
let game2IntermissionActive = false;
let game2IntermissionTimeout = null;
let pendingResumeGlobalTime = null;

function buildFallbackGameData() {
  const result = [];
  for (let c = 0; c < CHARACTERS.length; c++) {
    const charData = [];
    for (let p = 0; p < 7; p++) {
      charData.push(Math.random() < 0.7 - p * 0.06);
    }
    result.push(charData);
  }
  return result;
}

gameData = buildFallbackGameData();

function setGameDataFromOutcomes(characters) {
  const result = [];
  characters.forEach((character) => {
    const phases = Array.isArray(character.phases) ? character.phases : [];
    const charData = [];
    charData.push(true);
    for (let p = 0; p < 5; p++) {
      const outcomeId = phases[p];
      const normalized =
        typeof outcomeId === "string" ? outcomeId.toUpperCase() : outcomeId;
      if (normalized === "FLOAT" || normalized === 1) {
        charData.push(true);
      } else if (normalized === "DROWN" || normalized === 2) {
        charData.push(false);
      } else {
        charData.push(null);
      }
    }
    charData.push(null);
    result.push(charData);
  });
  gameData = result;
}

function mergeCharactersFromStats(statCharacters) {
  const palette = CHARACTERS;
  return statCharacters.map((entry, index) => {
    const base = palette[index % palette.length] || {};
    return {
      name: entry.name || base.name || `CHAR ${index + 1}`,
      emoji: base.emoji || "*",
      color: base.color || "#39a0ff",
      power: Number.isFinite(Number(entry.power))
        ? Number(entry.power)
        : (base.power ?? 75),
      control: Number.isFinite(Number(entry.control))
        ? Number(entry.control)
        : (base.control ?? 75),
      stamina: Number.isFinite(Number(entry.stamina))
        ? Number(entry.stamina)
        : (base.stamina ?? 75),
    };
  });
}

async function fetchPostGameStats() {
  try {
    const response = await fetch("/api/post-game-stats");
    if (!response.ok) return;
    const payload = await response.json();
    if (
      !payload ||
      !Array.isArray(payload.characters) ||
      payload.characters.length === 0
    ) {
      return;
    }
    CHARACTERS = mergeCharactersFromStats(payload.characters);
    setGameDataFromOutcomes(payload.characters);
    useLiveRoundOutcomes = true;
    createCards();
    showCharacter(0);
  } catch (error) {
    console.warn("Could not load post-game stats:", error);
  }
}

function init() {
  createCards();
  showCharacter(0);
  startTimers();
  startFadeAnimation();
  drawGraph();
  setInterval(drawGraph, 6000);
  fetchPostGameStats();
}

function syncTimerElements() {
  const timerEl = document.getElementById("rotationTimer");
  if (timerEl) timerEl.textContent = rotationTime;
  const globalEl = document.getElementById("globalTimer");
  if (globalEl) globalEl.textContent = globalTime;
}

function applyTimerValues(remainingSeconds) {
  const safeRemaining = Math.max(0, Math.floor(Number(remainingSeconds) || 0));
  const rotationSize = 18;
  rotationTime = safeRemaining > 0 ? safeRemaining % rotationSize || rotationSize : 0;
  globalTime = safeRemaining;
  syncTimerElements();
}

function startGame2Intermission(nextRemaining = null) {
  if (Number.isFinite(nextRemaining) && nextRemaining > 0) {
    pendingResumeGlobalTime = Math.max(0, Math.floor(nextRemaining));
  }

  applyTimerValues(0);
  if (game2IntermissionActive) return;

  game2IntermissionActive = true;
  game2IntermissionTimeout = setTimeout(() => {
    game2IntermissionActive = false;
    game2IntermissionTimeout = null;

    let resumeTime = Number.isFinite(pendingResumeGlobalTime)
      ? pendingResumeGlobalTime
      : 90;
    pendingResumeGlobalTime = null;

    if (!useLiveRoundOutcomes && resumeTime >= 90) {
      gameData = buildFallbackGameData();
    }

    applyTimerValues(resumeTime);
  }, 12000);
}

function createCards() {
  const container = document.getElementById("cardContainer");
  if (!container) return;
  container.innerHTML = "";

  CHARACTERS.forEach((char, idx) => {
    const card = document.createElement("div");
    card.className = "character-card";
    card.id = `card-${idx}`;
    card.innerHTML = getCardHTML(char, idx);
    container.appendChild(card);

    const rowsDiv = document.getElementById(`rows-${idx}`);
    for (let p = 0; p < 7; p++) {
      const row = document.createElement("div");
      row.className = "phase-row";
      if (p === 0) row.classList.add("start-row");
      row.id = `row-${idx}-${p}`;
      row.setAttribute("data-phase", p);
      row.setAttribute("data-state", "unreached");
      if (p === 0) {
        row.innerHTML = '<span class="phase-label-center">Start</span>';
      } else if (p === 6) {
        row.innerHTML = '<span class="phase-label-center">Phase 6+</span>';
      } else {
        row.innerHTML = `<span class="phase-label-center">Phase ${p}</span>`;
      }
      rowsDiv.appendChild(row);
    }
  });
}

function getCardHTML(char, idx) {
  return `
        <div class='character-left-panel'>
            <div class='character-avatar-container'>
                <div class='character-avatar' style='border-color: ${char.color}'>${char.emoji}</div>
            </div>
            <div class='character-name' style='color: ${char.color}'>${char.name}</div>
        </div>
        <div class='stats-right-panel'>
            <div class='grid-wrapper' id='grid-wrapper-${idx}'>
                <div class='grid-front'>
                    <div class='phase-rows' id='rows-${idx}'></div>
                </div>
                <div class='grid-back'>
                    <div class='drowned-stats-title'>DROWNED Phase</div>
                    <div id='drowned-${idx}'></div>
                </div>
                <div class='stone-container'>
                    <div class='stone' id='stone-${idx}'></div>
                </div>
                <div class='splash' id='splash-${idx}'></div>
            </div>
            <div class='stats-footer'>
                <div class='footer-stat'>Phases: <span id='completed-${idx}'>0</span>/5</div>
                <div class='footer-stat'><span id='status-${idx}'>---</span></div>
            </div>
        </div>
    `;
}

function showCharacter(idx) {
  if (stoneAnimation) {
    cancelAnimationFrame(stoneAnimation);
    stoneAnimation = null;
  }
  if (flipTimeout) clearTimeout(flipTimeout);

  document.querySelectorAll(".character-card").forEach((c, i) => {
    c.classList.toggle("active", i === idx);
  });
  currentChar = idx;
  resetCharacter(idx);
  setTimeout(() => animateStoneSmooth(idx), 500);
}

function resetCharacter(idx) {
  const stone = document.getElementById(`stone-${idx}`);
  if (stone) {
    stone.style.top = "8px";
    stone.style.display = "block";
    stone.className = "stone";
    stone.style.transition = "none";
  }
  currentStonePosition = 8;

  for (let p = 0; p < 7; p++) {
    const row = document.getElementById(`row-${idx}-${p}`);
    if (row) {
      row.setAttribute("data-state", "unreached");
      const icon = row.querySelector(".phase-icon");
      if (icon) icon.remove();
    }
  }

  const completedEl = document.getElementById(`completed-${idx}`);
  if (completedEl) completedEl.textContent = "0";
  const statusEl = document.getElementById(`status-${idx}`);
  if (statusEl) statusEl.textContent = "---";
  const gridWrapper = document.getElementById(`grid-wrapper-${idx}`);
  if (gridWrapper) gridWrapper.classList.remove("flipped");
  updateDrownedDisplay(idx);
}

function updateDrownedDisplay(idx) {
  const container = document.getElementById(`drowned-${idx}`);
  if (!container) return;

  const drowned = [];
  for (let p = 1; p < 6; p++) {
    if (gameData[idx][p] === false) drowned.push(p + 1);
  }

  container.innerHTML = "";
  if (drowned.length === 0) {
    container.innerHTML = '<div class="no-drown-message">None</div>';
  } else {
    drowned.slice(0, 3).forEach((p) => {
      container.innerHTML += `<div class="drowned-phase-item">Phase ${p - 1}</div>`;
    });
  }
}

function createTrail(idx, y) {
  const grid = document.getElementById(`grid-wrapper-${idx}`);
  if (!grid) return;
  const trail = document.createElement("div");
  trail.className = "trail";
  trail.style.top = `${y}px`;
  grid.querySelector(".stone-container").appendChild(trail);
  setTimeout(() => trail.remove(), 600);
}

function playSplash(idx) {
  const splash = document.getElementById(`splash-${idx}`);
  if (splash) {
    splash.classList.add("active");
    setTimeout(() => splash.classList.remove("active"), 500);
  }
}

function flipGrid(idx) {
  const grid = document.getElementById(`grid-wrapper-${idx}`);
  if (grid) {
    grid.classList.add("flipped");
    flipTimeout = setTimeout(() => {
      grid.classList.remove("flipped");
    }, 5000);
  }
}

function markPhaseAsPassed(idx, phase, isAlive) {
  const row = document.getElementById(`row-${idx}-${phase}`);
  if (!row) return;
  row.setAttribute("data-state", !isAlive ? "drowned" : "survived");

  const oldIcon = row.querySelector(".phase-icon");
  if (oldIcon) oldIcon.remove();
  const icon = document.createElement("span");
  icon.className = "phase-icon";
  icon.textContent = !isAlive ? "X" : "OK";
  row.appendChild(icon);
}

function animateStoneSmooth(idx) {
  const stone = document.getElementById(`stone-${idx}`);
  const grid = document.getElementById(`grid-wrapper-${idx}`);
  if (!stone || !grid) return;

  const startY = 8;
  const gridHeight = grid.clientHeight;
  let endY = gridHeight - 28;
  let distance = endY - startY;

  let drownedPhase = -1;
  let lastKnownPhase = -1;
  for (let p = 1; p < 6; p++) {
    if (gameData[idx][p] === true || gameData[idx][p] === false) {
      lastKnownPhase = p;
    }
    if (gameData[idx][p] === false && drownedPhase === -1) {
      drownedPhase = p;
    }
  }

  let stopPhase = -1;
  if (drownedPhase === -1 && lastKnownPhase !== -1) {
    const hasNullAfter = gameData[idx]
      .slice(lastKnownPhase + 1, 6)
      .some((value) => value === null);
    if (hasNullAfter) {
      stopPhase = Math.min(lastKnownPhase + 1, 5);
    }
  }

  const rowHeight = (gridHeight - 20) / 7;
  const phasePositions = [];
  for (let p = 0; p < 7; p++) {
    phasePositions.push(8 + p * rowHeight);
  }

  let stoppedEarly = false;
  if (drownedPhase !== -1) {
    endY = phasePositions[drownedPhase];
    distance = endY - startY;
  } else if (stopPhase !== -1) {
    const stopIndex = Math.max(1, stopPhase - 1);
    endY = phasePositions[stopIndex];
    distance = endY - startY;
    stoppedEarly = true;
  } else if (lastKnownPhase === -1) {
    endY = startY;
    distance = 0;
    stoppedEarly = true;
  }

  let startTime = null;
  const duration = 1200;
  let lastPhase = -1;
  let phasesCompleted = 0;

  function animate(currentTime) {
    if (!startTime) startTime = currentTime;
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const currentY = startY + distance * progress;
    stone.style.top = `${currentY}px`;

    if (Math.random() > 0.7) {
      createTrail(idx, currentY);
    }

    let currentPhase = -1;
    for (let p = 0; p < 7; p++) {
      if (currentY >= phasePositions[p] - 5 && currentY <= phasePositions[p] + rowHeight) {
        currentPhase = p;
        break;
      }
    }

    if (currentPhase !== -1 && currentPhase !== lastPhase) {
      const row = document.getElementById(`row-${idx}-${currentPhase}`);
      if (row) {
        row.classList.add("active");
        if (lastPhase !== -1 && lastPhase < currentPhase) {
          const prevRow = document.getElementById(`row-${idx}-${lastPhase}`);
          if (prevRow) {
            prevRow.classList.remove("active");
            const isAlive = gameData[idx][lastPhase] === true;
            if (gameData[idx][lastPhase] !== null) {
              markPhaseAsPassed(idx, lastPhase, isAlive);
            }
            if (isAlive) {
              phasesCompleted++;
              const completedEl = document.getElementById(`completed-${idx}`);
              if (completedEl) completedEl.textContent = phasesCompleted;
            }
          }
        }
        lastPhase = currentPhase;
      }
    }

    if (progress < 1) {
      stoneAnimation = requestAnimationFrame(animate);
    } else {
      const finalPhase = drownedPhase !== -1 ? drownedPhase : 5;
      const finalRow = document.getElementById(`row-${idx}-${finalPhase}`);
      if (finalRow) {
        finalRow.classList.remove("active");
        const isAlive = gameData[idx][finalPhase] === true;
        if (gameData[idx][finalPhase] !== null) {
          markPhaseAsPassed(idx, finalPhase, isAlive);
        }
        if (isAlive && finalPhase !== drownedPhase) {
          phasesCompleted++;
          const completedEl = document.getElementById(`completed-${idx}`);
          if (completedEl) completedEl.textContent = phasesCompleted;
        }
      }

      const statusEl = document.getElementById(`status-${idx}`);
      if (drownedPhase !== -1) {
        stone.classList.add("drowned");
        playSplash(idx);
        if (statusEl) statusEl.textContent = `DROWNED P${drownedPhase + 1}`;
      } else if (statusEl) {
        statusEl.textContent = lastKnownPhase === -1 ? "NO DATA" : stoppedEarly ? `STOPPED P${stopPhase - 1}` : "SURVIVED";
      }

      setTimeout(() => {
        flipGrid(idx);
      }, 500);

      stoneAnimation = null;
    }
  }

  stoneAnimation = requestAnimationFrame(animate);
}

// Server-based timer state with synchronization
let lastRotationTime = 18; // Track previous rotation time to detect rotation boundaries
let timerUnsubscribe = null; // Unsubscribe function for TimerManager

/**
 * Apply external timer sync (from parent frame postMessage).
 * Overrides server state temporarily during sync window.
 */
function applyExternalTimerSync(remainingSeconds) {
  const safeRemaining = Math.max(0, Math.floor(Number(remainingSeconds) || 0));
  if (safeRemaining === 0) {
    startGame2Intermission();
    return;
  }

  if (game2IntermissionActive) {
    pendingResumeGlobalTime = safeRemaining;
    return;
  }

  applyTimerValues(safeRemaining);
  externalSyncActive = true;
  if (externalSyncTimeout) clearTimeout(externalSyncTimeout);
  externalSyncTimeout = setTimeout(() => {
    externalSyncActive = false;
    externalSyncTimeout = null;
  }, 2500);
}

window.addEventListener("message", (event) => {
  if (!event || !event.data || event.data.type !== "round-timer") return;
  applyExternalTimerSync(event.data.remaining);
});

/**
 * Initialize timer using global TimerManager singleton.
 * All timer state comes from Redis via centralized manager.
 */
function startTimers() {
  // Unsubscribe from previous subscription if any
  if (timerUnsubscribe) {
    timerUnsubscribe();
    timerUnsubscribe = null;
  }
  
  // Subscribe to global TimerManager (single source of truth from Redis)
  timerUnsubscribe = TimerManager.subscribe((timerState) => {
    if (externalSyncActive || game2IntermissionActive) return;
    
    const currentRemaining = timerState.secondsRemaining;
    const rotationSize = 18;
    
    // Apply timer values (rotationTime and globalTime)
    applyTimerValues(currentRemaining);
    
    // Detect and handle rotation boundaries
    const newRotationTime = currentRemaining > 0 
      ? currentRemaining % rotationSize || rotationSize 
      : 0;
    
    if (newRotationTime !== lastRotationTime && newRotationTime > lastRotationTime) {
      // Rotation boundary crossed - advance character
      const total = CHARACTERS.length || 1;
      const next = (currentChar + 1) % total;
      showCharacter(next);
      lastRotationTime = newRotationTime;
    } else if (lastRotationTime > 0 && newRotationTime === 0) {
      // Wrapped around 18 seconds
      const total = CHARACTERS.length || 1;
      const next = (currentChar + 1) % total;
      showCharacter(next);
      lastRotationTime = 0;
    } else {
      lastRotationTime = newRotationTime;
    }
    
    // Handle countdown completion
    if (currentRemaining <= 0) {
      startGame2Intermission(90);
    }
  });
}

function startFadeAnimation() {
  setInterval(() => {
    document.querySelectorAll(".stat-bar-container").forEach((el) => {
      el.classList.add("fade-out");
      setTimeout(() => el.classList.remove("fade-out"), 2000);
    });
  }, 6000);
}

function drawGraph() {
  const svg = document.getElementById("graphSvg");
  if (!svg) return;

  const w = window.innerWidth;
  const h = window.innerHeight;
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);
  svg.innerHTML = "";

  const colors = ["#ffd700", "#e74c3c", "#3498db", "#27ae60"];
  for (let line = 0; line < 4; line++) {
    const points = [];
    for (let i = 0; i <= 20; i++) {
      points.push({
        x: (i / 20) * w,
        y: h * 0.2 + Math.sin(i * 0.5 + line) * 30 + Math.random() * 40,
      });
    }

    let path = `M ${points[0].x} ${points[0].y}`;
    for (let i = 1; i < points.length; i++) {
      path += ` L ${points[i].x} ${points[i].y}`;
    }

    const lineEl = document.createElementNS("http://www.w3.org/2000/svg", "path");
    lineEl.setAttribute("d", path);
    lineEl.setAttribute("fill", "none");
    lineEl.setAttribute("stroke", colors[line]);
    lineEl.setAttribute("stroke-width", "1.5");
    lineEl.setAttribute("stroke-opacity", "0.2");
    svg.appendChild(lineEl);
  }
}

window.onload = () => {
  init();
  
  // Cleanup timer subscriptions on page unload
  window.addEventListener("beforeunload", () => {
    if (timerUnsubscribe) {
      timerUnsubscribe();
      timerUnsubscribe = null;
    }
    if (game2IntermissionTimeout) clearTimeout(game2IntermissionTimeout);
    if (externalSyncTimeout) clearTimeout(externalSyncTimeout);
  });
};
