(function () {
  "use strict";

  const listeners = [];
  let connected = false;
  let latestState = null;
  let latestStateSignature = "";
  let latestRunId = null;
  let refreshInFlight = false;
  let connectInFlight = false;

  function dispatch(name, detail) {
    window.dispatchEvent(new CustomEvent(name, { detail: detail }));
  }

  async function callDesktopApi(method) {
    const api = window.pywebview && window.pywebview.api;
    if (!api || typeof api[method] !== "function") {
      throw new Error("本地服务尚未就绪，请稍后重试");
    }
    const args = Array.prototype.slice.call(arguments, 1);
    return api[method].apply(api, args);
  }

  async function refreshResult(force) {
    if (!latestState || !latestState.has_result) {
      dispatch("dna:result", null);
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

  async function refreshState() {
    // pywebview serializes bridge work; never pile up overlapping polling
    // calls when a slow disk/index operation takes longer than the interval.
    if (refreshInFlight) return latestState;
    refreshInFlight = true;
    try {
      const state = await callDesktopApi("get_state");
      connected = true;
      latestState = state;
      const signature = JSON.stringify(state);
      if (signature !== latestStateSignature) {
        latestStateSignature = signature;
        dispatch("dna:state", state);
      }
      await refreshResult(false);
      return state;
    } finally {
      refreshInFlight = false;
    }
  }

  async function connectBridge() {
    if (connectInFlight) return false;
    if (!window.pywebview || !window.pywebview.api || !window.pywebview.api.get_state) return false;
    connectInFlight = true;
    try {
      await refreshState();
      dispatch("dna:bridge", { ready: true });
      return true;
    } catch (error) {
      dispatch("dna:error", { message: error.message || String(error) });
      return false;
    } finally {
      connectInFlight = false;
    }
  }

  window.dispatchAppEvent = function (eventName, payload) {
    listeners.forEach(function (listener) {
      try { listener(eventName, payload); } catch (error) { /* One listener must not block state recovery. */ }
    });
    if (eventName === "onTaskProgress") {
      dispatch("dna:task", payload);
      window.setTimeout(function () { refreshState().catch(function () {}); }, 40);
    }
  };

  window.DnaBridge = {
    call: callDesktopApi,
    refreshState: refreshState,
    refreshResult: function () { return refreshResult(true); },
    isConnected: function () { return connected; },
    onAppEvent: function (listener) { listeners.push(listener); }
  };

  window.addEventListener("pywebviewready", connectBridge);
  let attempts = 0;
  const probe = window.setInterval(async function () {
    attempts += 1;
    if ((await connectBridge()) || attempts >= 30) {
      window.clearInterval(probe);
      if (!connected) dispatch("dna:bridge", { ready: false });
    }
  }, 100);
  function pollState() {
    window.setTimeout(function () {
      if (connected) refreshState().catch(function () { connected = false; });
      else connectBridge();
      pollState();
    }, 500);
  }
  pollState();
}());
