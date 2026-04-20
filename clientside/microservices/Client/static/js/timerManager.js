/**
 * Global Timer Manager Singleton
 *
 * Single source of truth for round timer state across all pages.
 * Fetches the canonical Redis-backed timer endpoint once on startup,
 * then counts down locally in 1-second steps. A fresh server fetch is
 * only used when needed, such as after page visibility changes or when
 * a round rolls over.
 */

const TimerManager = (() => {
  let timerState = {
    roundId: 0,
    secondsRemaining: 0,
    secondsElapsed: 0,
    durationSeconds: 90,
    status: "OPEN",
    serverTimeMs: 0,
    startTimeMs: 0,
    endTimeMs: 0,
  };

  let fetchInProgress = false;
  let fetchIntervalId = null;
  let tickIntervalId = null;
  let tickStartTimeoutId = null;
  let subscribers = [];
  let isInitialized = false;
  let resolvedTimerUrl = null;
  let serverClockOffsetMs = 0;

  function buildCandidateUrls() {
    const origin = window.location.origin;
    return [
      new URL("/api/api/round/timer/", origin).toString(),
      new URL("/api/round-timer", origin).toString(),
      new URL("/api/decision/api/api/round/timer/", origin).toString(),
    ];
  }

  async function resolveTimerUrl() {
    if (resolvedTimerUrl) return resolvedTimerUrl;

    const candidates = buildCandidateUrls();
    for (const candidate of candidates) {
      try {
        const response = await fetch(candidate, {
          method: "GET",
          credentials: "same-origin",
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (response.ok) {
          resolvedTimerUrl = candidate;
          return resolvedTimerUrl;
        }
      } catch {}
    }

    throw new Error("No working round timer endpoint found");
  }

  /**
   * Fetch authoritative timer state from Redis via API
   */
  async function fetchTimerState() {
    if (fetchInProgress) return timerState;

    fetchInProgress = true;
    try {
      const timerUrl = await resolveTimerUrl();
      const response = await fetch(timerUrl, {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();

      const serverTimeMs = Number(data.server_time_ms ?? data.serverTimeMs);
      const endTimeMs = Number(data.end_time_ms ?? data.endTimeMs);
      const durationSeconds = Math.max(
        1,
        Math.floor(Number(data.duration_seconds ?? data.durationSeconds ?? 90)),
      );
      const normalizedEndTimeMs =
        Number.isFinite(endTimeMs) && endTimeMs > 0
          ? Math.floor(endTimeMs)
          : 0;

      if (Number.isFinite(serverTimeMs) && serverTimeMs > 0) {
        serverClockOffsetMs = Math.floor(serverTimeMs) - Date.now();
      }

      const computedRemaining = normalizedEndTimeMs
        ? Math.max(
            0,
            Math.floor((normalizedEndTimeMs - Date.now()) / 1000),
          )
        : Math.max(
            0,
            Math.floor(Number(data.time_remaining ?? data.secondsRemaining ?? 0)),
          );

      timerState = {
        roundId: Number(data.round_id ?? data.roundId ?? 0),
        secondsRemaining: computedRemaining,
        secondsElapsed: Math.max(0, durationSeconds - computedRemaining),
        durationSeconds,
        status: String(data.status || "OPEN"),
        serverTimeMs: Number.isFinite(serverTimeMs)
          ? Math.max(0, Math.floor(serverTimeMs))
          : Date.now(),
        startTimeMs: Math.max(
          0,
          Math.floor(Number(data.start_time_ms ?? data.startTimeMs) || 0),
        ),
        endTimeMs: normalizedEndTimeMs,
      };

      notifySubscribers(timerState);
      return timerState;
    } catch (error) {
      console.warn("[TimerManager] Fetch failed:", error.message);
      return timerState;
    } finally {
      fetchInProgress = false;
    }
  }

  function getState() {
    const projectedRemaining = timerState.endTimeMs
      ? Math.max(
          0,
          Math.floor((timerState.endTimeMs - Date.now()) / 1000),
        )
      : Math.max(0, timerState.secondsRemaining);
    return {
      ...timerState,
      secondsRemaining: projectedRemaining,
      secondsElapsed: Math.max(0, timerState.durationSeconds - projectedRemaining),
    };
  }

  /**
   * Subscribe to timer updates
   * @param {Function} callback - Called with updated state
   * @returns {Function} Unsubscribe function
   */
  function subscribe(callback) {
    subscribers.push(callback);
    try {
      callback(getState());
    } catch (error) {
      console.error("[TimerManager] Subscriber error:", error);
    }
    return () => {
      subscribers = subscribers.filter((cb) => cb !== callback);
    };
  }

  /**
   * Notify all subscribers of state change
   */
  function notifySubscribers(newState) {
    for (const callback of subscribers) {
      try {
        callback(getState());
      } catch (error) {
        console.error("[TimerManager] Subscriber error:", error);
      }
    }
  }

  /**
   * Start the timer
   */
  function start() {
    if (isInitialized) return;
    isInitialized = true;

    // Initial authoritative fetch.
    fetchTimerState();

    // Light periodic resync to keep devices aligned to server time.
    fetchIntervalId = setInterval(fetchTimerState, 15000);

    // Smooth local display updates using the server clock offset.
    const tick = () => {
      notifySubscribers(timerState);
    };

    const scheduleNextTick = () => {
      const now = new Date();
      const msUntilNextSecond = 1000 - now.getMilliseconds();
      tickStartTimeoutId = setTimeout(() => {
        tick();
        tickIntervalId = setInterval(tick, 1000);
      }, msUntilNextSecond);
    };

    scheduleNextTick();

    // Re-fetch when page becomes visible (was hidden)
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) {
        fetchTimerState();
      }
    });
  }

  /**
   * Stop the timer
   */
  function stop() {
    if (fetchIntervalId) clearInterval(fetchIntervalId);
    if (tickIntervalId) clearInterval(tickIntervalId);
    if (tickStartTimeoutId) clearTimeout(tickStartTimeoutId);
    fetchIntervalId = null;
    tickIntervalId = null;
    tickStartTimeoutId = null;
    isInitialized = false;
    subscribers = [];
  }

  /**
   * Singleton instance
   */
  return {
    start,
    stop,
    getState,
    subscribe,
    refresh: fetchTimerState,
  };
})();

// Auto-start when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => TimerManager.start());
} else {
  TimerManager.start();
}
