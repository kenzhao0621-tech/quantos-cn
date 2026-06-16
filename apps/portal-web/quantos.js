/** QuantOS CN portal extensions */
(function () {
  const API_KEY = "demo-local-key-change-in-prod";
  async function qapi(path, options = {}) {
    const res = await fetch(`${window.location.origin}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", "X-API-Key": API_KEY, ...(options.headers || {}) },
    });
    return res.json();
  }

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      const page = tab.dataset.page;
      document.querySelectorAll("main.layout").forEach((m) => m.classList.add("hidden"));
      const el = document.getElementById(`page-${page}`);
      if (el) el.classList.remove("hidden");
    });
  });

  async function refreshQuantOS() {
    try {
      const st = await qapi("/api/v1/quantos/status");
      if (st.ok) {
        document.getElementById("quantos-status").textContent = JSON.stringify(st.data, null, 2);
        document.getElementById("vnpy-status").textContent = JSON.stringify(st.data.vnpy_runtime, null, 2);
        document.getElementById("qlib-status").textContent = JSON.stringify(st.data.qlib_provider, null, 2);
        document.getElementById("model-registry").textContent = JSON.stringify(st.data.model_registry, null, 2);
        document.getElementById("broker-pill").textContent = `券商: ${st.data.vnpy_runtime?.active_gateway || "—"}`;
      }
      const gw = await qapi("/api/v1/quantos/vnpy/gateways");
      if (gw.ok) document.getElementById("gateway-list").textContent = JSON.stringify(gw.data, null, 2);
      const ev = await qapi("/api/v1/quantos/vnpy/events");
      if (ev.ok) document.getElementById("shadow-events").textContent = JSON.stringify(ev.data.events?.slice(-10), null, 2);
    } catch (e) {
      console.error(e);
    }
  }

  document.getElementById("btn-vnpy-start")?.addEventListener("click", async () => {
    await qapi("/api/v1/quantos/vnpy/start", { method: "POST" });
    refreshQuantOS();
  });
  document.getElementById("btn-vnpy-stop")?.addEventListener("click", async () => {
    await qapi("/api/v1/quantos/vnpy/stop", { method: "POST" });
    refreshQuantOS();
  });
  document.getElementById("btn-qlib-baseline")?.addEventListener("click", async () => {
    const r = await qapi("/api/v1/quantos/qlib/baseline", { method: "POST", body: JSON.stringify({ as_of: "2026-06-16" }) });
    document.getElementById("qlib-status").textContent = JSON.stringify(r.data, null, 2);
  });

  refreshQuantOS();
  setInterval(refreshQuantOS, 30000);
})();
