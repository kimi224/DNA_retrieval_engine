(function () {
  "use strict";

  const listeners = [];
  const callTimeoutMs = 8000;
  let connected = false;
  let stopped = false;
  let latestState = null;
  let latestStateSignature = "";
  let latestRunId = null;
  let refreshPromise = null;
  let connectPromise = null;
  let pollTimer = null;
  let probeTimer = null;
  let retryDelay = 100;

  function dispatch(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail: detail }));
  }

  function callDesktopApi(method) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api[method] !== "function") {
      return Promise.reject(new Error("本地服务尚未就绪，请稍后重试"));
    }
    const args = Array.prototype.slice.call(arguments, 1);
    let result;
    try {
      result = api[method].apply(api, args);
    } catch (error) {
      return Promise.reject(error);
    }
    return new Promise(function (resolve, reject) {
      const timer = window.setTimeout(function () {
        reject(new Error("本地服务响应超时，请稍后重试"));
      }, callTimeoutMs);
      Promise.resolve(result).then(function (value) {
        window.clearTimeout(timer);
        resolve(value);
      }, function (error) {
        window.clearTimeout(timer);
        reject(error);
      });
    });
  }

  async function refreshResult(force) {
    if (!latestState || !latestState.has_result) {
      if (latestRunId !== null) dispatch("dna:result", null);
      latestRunId = null;
      return null;
    }
    if (!force && latestRunId === latestState.run_id) return null;
    const response = await callDesktopApi("get_last_result");
    if (!response.ok) throw new Error(response.error || "无法读取检索结果");
    latestRunId = response.result.run_id;
    dispatch("dna:result", response.result);
    return response.result;
  }

  function refreshState() {
    if (stopped) return Promise.reject(new Error("页面已关闭"));
    if (refreshPromise) return refreshPromise;
    refreshPromise = (async function () {
      const state = await callDesktopApi("get_state");
      if (stopped) throw new Error("页面已关闭");
      latestState = state;
      connected = true;
      retryDelay = 100;
      const signature = JSON.stringify(state);
      if (signature !== latestStateSignature) {
        latestStateSignature = signature;
        dispatch("dna:state", state);
      }
      await refreshResult(false);
      return state;
    }()).finally(function () {
      refreshPromise = null;
    });
    return refreshPromise;
  }

  function clearTimers() {
    if (pollTimer !== null) window.clearTimeout(pollTimer);
    if (probeTimer !== null) window.clearTimeout(probeTimer);
    pollTimer = null;
    probeTimer = null;
  }

  function scheduleProbe(delay) {
    if (stopped || connected || probeTimer !== null) return;
    probeTimer = window.setTimeout(function () {
      probeTimer = null;
      connectBridge().finally(function () {
        if (!connected) {
          retryDelay = Math.min(3000, Math.max(100, retryDelay * 2));
          scheduleProbe(retryDelay);
        }
      });
    }, delay);
  }

  async function connectBridge() {
    if (stopped) return false;
    if (connectPromise) return connectPromise;
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api.get_state !== "function") {
      dispatch("dna:bridge", { ready: false, status: "booting" });
      scheduleProbe(retryDelay);
      return false;
    }
    connectPromise = (async function () {
      try {
        await refreshState();
        dispatch("dna:bridge", { ready: true, status: "ready" });
        return true;
      } catch (error) {
        connected = false;
        dispatch("dna:bridge", { ready: false, status: "error" });
        dispatch("dna:error", { message: error.message || String(error) });
        return false;
      }
    }()).finally(function () { connectPromise = null; });
    return connectPromise;
  }

  function schedulePoll() {
    if (stopped || pollTimer !== null) return;
    const hidden = document.visibilityState === "hidden";
    const running = Boolean(latestState && latestState.task && latestState.task.status === "running");
    const delay = hidden ? 3000 : (running ? 250 : 1000);
    pollTimer = window.setTimeout(function () {
      pollTimer = null;
      const request = connected ? refreshState() : connectBridge();
      request.catch(function () {
        connected = false;
        dispatch("dna:bridge", { ready: false, status: "error" });
      }).finally(schedulePoll);
    }, delay);
  }

  window.dispatchAppEvent = function (eventName, payload) {
    listeners.slice().forEach(function (listener) {
      try { listener(eventName, payload); } catch (error) { /* Keep state recovery alive. */ }
    });
    if (eventName === "onTaskProgress") dispatch("dna:task", payload);
  };

  window.DnaBridge = {
    call: callDesktopApi,
    refreshState: refreshState,
    refreshResult: function () { return refreshResult(true); },
    isConnected: function () { return connected && !stopped; },
    onAppEvent: function (listener) { listeners.push(listener); },
    retry: function () {
      stopped = false;
      connected = false;
      retryDelay = 100;
      clearTimers();
      scheduleProbe(0);
      schedulePoll();
    },
    stop: function () { stopped = true; connected = false; clearTimers(); },
    resume: function () {
      if (!stopped) return;
      stopped = false;
      retryDelay = 100;
      scheduleProbe(0);
      schedulePoll();
    }
  };

  window.addEventListener("pywebviewready", function () {
    connectBridge().finally(schedulePoll);
  });
  document.addEventListener("visibilitychange", function () {
    clearTimers();
    if (!stopped) {
      if (!connected) scheduleProbe(0);
      schedulePoll();
    }
  });
  window.addEventListener("pagehide", function () { window.DnaBridge.stop(); });
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) window.DnaBridge.resume();
  });

  // Start with a short probe, then use one serialized timer for all polling.
  scheduleProbe(0);
  schedulePoll();
}());
