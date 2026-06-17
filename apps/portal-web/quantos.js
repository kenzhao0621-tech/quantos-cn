/** QuantOS CN vn.py / Qlib portal extensions */
(function () {
  const api = window.QuantOSApi;

  async function refreshQuantOS() {
    if (!api.apiKey) return;
    try {
      const st = await api.request("/api/v1/quantos/status");
      if (st.ok) {
        const vn = st.data.vnpy_runtime?.native_vnpy ? "NATIVE" : "SHIM";
        const ql = st.data.qlib_provider?.native_qlib ? "NATIVE" : "SHIM";
        document.getElementById("vnpy-status").textContent = JSON.stringify(st.data.vnpy_runtime, null, 2);
        document.getElementById("qlib-status").textContent = JSON.stringify(st.data.qlib_provider, null, 2);
        document.getElementById("model-registry").textContent = JSON.stringify(st.data.model_registry, null, 2);
        document.getElementById("vnpy-mode-tag").textContent = vn;
        document.getElementById("qlib-mode-tag").textContent = ql;
      }
      const gw = await api.request("/api/v1/quantos/vnpy/gateways");
      if (gw.ok) document.getElementById("gateway-list").textContent = JSON.stringify(gw.data, null, 2);
      const ev = await api.request("/api/v1/quantos/vnpy/events");
      if (ev.ok) document.getElementById("shadow-events").textContent = JSON.stringify(ev.data.events?.slice(-10), null, 2);
    } catch (e) {
      console.error(e);
    }
  }

  async function qact(label, path, options) {
    const res = await api.request(path, options);
    const el = document.getElementById("action-log-body");
    if (el) {
      el.textContent = JSON.stringify({
        action: label,
        request_id: res.request_id,
        trace_id: res.trace_id,
        ok: res.ok,
        result: res.data,
        error: res.error,
      }, null, 2);
    }
    await refreshQuantOS();
    return res;
  }

  document.getElementById("btn-vnpy-start")?.addEventListener("click", () =>
    qact("vnpy start", "/api/v1/quantos/vnpy/start", { method: "POST" }));
  document.getElementById("btn-vnpy-stop")?.addEventListener("click", () =>
    qact("vnpy stop", "/api/v1/quantos/vnpy/stop", { method: "POST" }));
  document.getElementById("btn-qlib-baseline")?.addEventListener("click", () =>
    qact("qlib baseline", "/api/v1/quantos/qlib/baseline", {
      method: "POST",
      body: JSON.stringify({ as_of: "2026-06-16" }),
    }));
  document.getElementById("btn-qlib-baseline-models")?.addEventListener("click", () =>
    qact("qlib baseline", "/api/v1/quantos/qlib/baseline", {
      method: "POST",
      body: JSON.stringify({ as_of: "2026-06-16" }),
    }));
  document.getElementById("btn-vnpy-start-native")?.addEventListener("click", () =>
    qact("vnpy start", "/api/v1/quantos/vnpy/start", { method: "POST" }));
  document.getElementById("btn-qlib-baseline-native")?.addEventListener("click", () =>
    qact("qlib baseline", "/api/v1/quantos/qlib/baseline", {
      method: "POST",
      body: JSON.stringify({ as_of: "2026-06-16" }),
    }));

  if (api.apiKey) {
    refreshQuantOS();
    setInterval(refreshQuantOS, 30000);
  }
  document.getElementById("btn-login")?.addEventListener("click", () => {
    setTimeout(refreshQuantOS, 500);
  });
})();
