(function () {
  "use strict";

  const subscribers = [];
  const store = { app: null, result: null, bridgeReady: false, bridgeStatus: "booting", error: null };

  function notify() {
    const snapshot = window.DnaStore.snapshot();
    subscribers.forEach(function (subscriber) {
      try { subscriber(snapshot); } catch (error) { /* Rendering errors stay page-local. */ }
    });
  }

  window.addEventListener("dna:bridge", function (event) {
    store.bridgeReady = Boolean(event.detail && event.detail.ready);
    store.bridgeStatus = event.detail && event.detail.status || (store.bridgeReady ? "ready" : "booting");
    notify();
  });
  window.addEventListener("dna:state", function (event) {
    store.app = event.detail;
    store.bridgeReady = true;
    store.bridgeStatus = "ready";
    store.error = null;
    notify();
  });
  window.addEventListener("dna:result", function (event) {
    store.result = event.detail;
    notify();
  });
  window.addEventListener("dna:error", function (event) {
    store.error = event.detail && event.detail.message;
    store.bridgeStatus = "error";
    notify();
  });

  window.DnaStore = {
    subscribe: function (subscriber) {
      subscribers.push(subscriber);
      subscriber(window.DnaStore.snapshot());
      return function () {
        const index = subscribers.indexOf(subscriber);
        if (index >= 0) subscribers.splice(index, 1);
      };
    },
    snapshot: function () {
      return {
        app: store.app,
        result: store.result,
        bridgeReady: store.bridgeReady,
        bridgeStatus: store.bridgeStatus,
        error: store.error
      };
    }
  };
}());
