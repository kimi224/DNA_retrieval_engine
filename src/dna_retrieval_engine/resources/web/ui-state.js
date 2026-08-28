(function () {
  "use strict";

  function capabilities(snapshot) {
    const app = snapshot && snapshot.app;
    const task = app && app.task;
    const dataset = app && app.dataset;
    const running = Boolean(task && task.status === "running");
    const bridgeReady = Boolean(snapshot && snapshot.bridgeReady && app && app.bridge_ready);
    const dataLoaded = Boolean(dataset && dataset.loaded);
    const hasResult = Boolean(snapshot && snapshot.result);
    const remote = app && app.capabilities || {};
    const allows = function (key) { return remote[key] === undefined || Boolean(remote[key]); };
    return {
      bridgeReady: bridgeReady,
      running: running,
      dataLoaded: dataLoaded,
      hasResult: hasResult,
      // Tabs, fields and parameter controls are local UI state and remain
      // usable before a dataset or the bridge is ready.
      canConfigure: !running && allows("can_configure"),
      canChooseInput: bridgeReady && !running && allows("can_choose_input"),
      canLoadDataset: bridgeReady && !running && allows("can_load_dataset"),
      canRunSearch: bridgeReady && dataLoaded && !running && allows("can_run_search"),
      canExport: bridgeReady && hasResult && !running && allows("can_export"),
      canCancel: bridgeReady && running && allows("can_cancel"),
      canInspect: bridgeReady && dataLoaded && !running && allows("can_inspect")
    };
  }

  window.DnaUiState = { capabilities: capabilities };
}());
