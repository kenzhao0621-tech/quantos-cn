/** QuantOS CN vn.py / Qlib — integrates with shared ViewModel UI layer. */
(function () {
  const api = window.QuantOSApi;
  const UI = window.QuantOSUI;
  const VM = window.QuantOSViewModels;

  async function qact(label, path, options, btn) {
    UI.setLoading(btn, true);
    try {
      const res = await api.request(path, options);
      if (window.QuantOSPortal?.logAction) {
        window.QuantOSPortal.logAction(label, res);
      } else {
        UI.renderActionLog(document.getElementById("action-log-body"), {
          label,
          ok: res.ok,
          summary: VM.actionSummary(label, res),
          raw: res,
        });
      }
      if (window.QuantOSPortal?.refresh) await window.QuantOSPortal.refresh();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  function bind(id, label, path, options) {
    const btn = document.getElementById(id);
    btn?.addEventListener("click", () => qact(label, path, options, btn));
  }

  bind("btn-vnpy-start", "vn.py 启动", "/api/v1/quantos/vnpy/start", { method: "POST" });
  bind("btn-vnpy-stop", "vn.py 停止", "/api/v1/quantos/vnpy/stop", { method: "POST" });
  bind("btn-vnpy-start-native", "vn.py 启动", "/api/v1/quantos/vnpy/start", { method: "POST" });
  const baselineOpts = { method: "POST", body: JSON.stringify({ as_of: "2026-06-16" }) };
  bind("btn-qlib-baseline", "Qlib 基线", "/api/v1/quantos/qlib/baseline", baselineOpts);
  bind("btn-qlib-baseline-models", "Qlib 基线", "/api/v1/quantos/qlib/baseline", baselineOpts);
  bind("btn-qlib-baseline-native", "Qlib 基线", "/api/v1/quantos/qlib/baseline", baselineOpts);
})();
