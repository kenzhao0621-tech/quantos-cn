/** QuantOS CN portal — real backend bindings for all controls. */
(function () {
  const api = window.QuantOSApi;

  function $(id) {
    return document.getElementById(id);
  }

  function setPill(id, text, danger) {
    const el = $(id);
    if (!el) return;
    el.textContent = text;
    el.classList.toggle("kill", !!danger);
  }

  function logAction(label, res) {
    const body = {
      action: label,
      request_id: res.request_id,
      trace_id: res.trace_id,
      run_id: res.run_id || res.data?.run_id,
      ok: res.ok,
      status: res.status || (res.ok ? "succeeded" : "failed"),
      error: res.error,
      artifact_path: res.data?.artifact_path || res.provenance?.artifact_path || res.data?.artifact_pdf,
      result: res.data,
    };
    $("action-log-body").textContent = JSON.stringify(body, null, 2);
    return body;
  }

  async function act(label, path, options) {
    const res = await api.request(path, options);
    logAction(label, res);
    if (!res.ok && res.httpStatus === 403) {
      alert(`权限不足: 当前角色 ${api.role} — ${res.error?.message || "forbidden"}`);
    }
    return res;
  }

  const ACTIONS = {
    doctor: () => act("系统体检", "/api/v1/system/doctor", { method: "POST" }),
    "market-update": () => act("更新数据", "/api/v1/market/update", {
      method: "POST",
      body: JSON.stringify({ targets: ["indices", "bars"] }),
    }),
    "daily-run": () => act("生成日报", "/api/v1/research/daily-run", { method: "POST" }),
    "risk-check": () => act("风险自检", "/api/v1/risk/status"),
    "paper-start": () => act("Paper 启动", "/api/v1/paper/start", { method: "POST" }),
    "paper-stop": () => act("Paper 停止", "/api/v1/paper/stop", { method: "POST" }),
    "shadow-start": () => act("Shadow 启动", "/api/v1/shadow/start", { method: "POST" }),
    "shadow-stop": () => act("Shadow 停止", "/api/v1/shadow/stop", { method: "POST" }),
    halt: () => act("紧急停机", "/api/v1/risk/halt", {
      method: "POST",
      body: JSON.stringify({ reason: "portal_halt" }),
    }),
    "reset-request": () => act("申请解除停机", "/api/v1/risk/reset-request", { method: "POST" }),
    "reset-confirm": () => act("确认解除停机", "/api/v1/risk/reset-confirm", { method: "POST" }),
    backtest: () => act("运行回测", "/api/v1/research/backtest", {
      method: "POST",
      body: JSON.stringify({ as_of_date: "2026-06-16" }),
    }),
    "candidate-gate": () => act("候选门", "/api/v1/research/candidate", { method: "POST" }),
    "market-refresh": () => refreshMarket(),
    "paper-refresh": () => refreshPaper(),
    "open-pdf": async () => {
      const st = await api.request("/api/v1/system/status");
      const path = st.data?.latest_daily_report?.path_pdf;
      if (path) logAction("PDF 路径", { ok: true, data: { artifact_path: path }, request_id: st.request_id, trace_id: st.trace_id });
      else alert("日报 PDF 尚未生成");
    },
    "open-json": async () => {
      const r = await api.request("/api/v1/research/reports");
      logAction("报告列表", r);
    },
    "agents-run": () => act("多智能体研究", "/api/v1/research/agents/run", {
      method: "POST",
      body: JSON.stringify({ as_of: "2026-06-16" }),
    }),
    "native-vnpy-accept": () => act("vn.py 原生验收", "/api/v1/native/vnpy/acceptance", { method: "POST" }),
    "native-qlib-accept": () => act("Qlib 原生验收", "/api/v1/native/qlib/acceptance", { method: "POST" }),
    "data-coverage": () => act("数据覆盖检查", "/api/v1/market/indices"),
    reconcile: () => act("对账", "/api/v1/quantos/reconcile", { method: "POST" }),
    "broker-readonly": () => act("只读连接向导", "/api/v1/brokers/readonly-connect", {
      method: "POST",
      body: JSON.stringify({ broker: "ReadOnlyGateway", config: { readonly: true } }),
    }),
  };

  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const fn = ACTIONS[btn.dataset.action];
      if (fn) {
        await fn();
        await refresh();
      }
    });
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll("main.layout").forEach((m) => m.classList.add("hidden"));
      const el = $(`page-${tab.dataset.page}`);
      if (el) el.classList.remove("hidden");
    });
  });

  async function refreshOverview(st) {
    if (!st?.ok) return;
    const d = st.data;
    setPill("mode-pill", `模式: ${d.mode}`);
    setPill("session-pill", `时段: ${d.market_session}`);
    setPill("freshness-pill", `数据: ${d.data_status}`);
    setPill("capital-pill", `总资金: ¥${d.capital}`);
    setPill("budget-pill", `亏损额度: ¥${d.remaining_loss_budget}`);
    setPill("kill-pill", `Kill: ${d.kill_switch}`, d.halted || d.kill_switch === "HALTED");
    $("overview-body").textContent = JSON.stringify(d, null, 2);
    if (d.latest_daily_report) {
      $("report-detail").textContent = JSON.stringify(d.latest_daily_report, null, 2);
    }
  }

  async function refreshMarket() {
    const [snap, idx, providers] = await Promise.all([
      api.request("/api/v1/market/snapshot"),
      api.request("/api/v1/market/indices"),
      api.request("/api/v1/market/providers"),
    ]);
    const blocked = snap.data?.status === "demo_fixture" || snap.data?.error;
    $("market-body").textContent = JSON.stringify({
      blocked: blocked ? "BLOCKED_BY_DATA" : false,
      snapshot: snap.data,
      indices: idx.data,
      providers: providers.data,
      updated_at: new Date().toISOString(),
    }, null, 2);
    logAction("市场刷新", snap);
  }

  async function refreshPaper() {
    const [pnl, pos, orders] = await Promise.all([
      api.request("/api/v1/paper/pnl"),
      api.request("/api/v1/paper/positions"),
      api.request("/api/v1/paper/orders"),
    ]);
    if (pnl.ok) $("paper-pnl").textContent = JSON.stringify(pnl.data, null, 2);
    if (pos.ok) $("paper-positions").textContent = JSON.stringify(pos.data, null, 2);
    if (orders.ok) $("paper-orders").textContent = JSON.stringify(orders.data, null, 2);
  }

  async function refreshRisk(risk) {
    if (risk?.ok) {
      $("risk-detail").textContent = JSON.stringify(risk.data, null, 2);
    }
  }

  async function refreshNative() {
    const nat = await api.request("/api/v1/native/status");
    if (nat.ok) {
      const vn = nat.data.vnpy?.mode || "SHIM";
      const ql = nat.data.qlib?.mode || "SHIM";
      setPill("native-pill", `vn.py:${vn} Qlib:${ql}`);
      if ($("native-body")) $("native-body").textContent = JSON.stringify(nat.data, null, 2);
      $("vnpy-mode-tag").textContent = vn;
      $("qlib-mode-tag").textContent = ql;
    }
  }

  async function refresh() {
    if (!api.apiKey) return;
    try {
      const [st, risk, reports, shadow] = await Promise.all([
        api.request("/api/v1/system/status"),
        api.request("/api/v1/risk/status"),
        api.request("/api/v1/research/reports"),
        api.request("/api/v1/shadow/status"),
      ]);
      refreshOverview(st);
      refreshRisk(risk);
      refreshNative();
      refreshPaper();
      if (shadow.ok) {
        $("shadow-status").textContent = JSON.stringify(shadow.data, null, 2);
      }
      const nat = await api.request("/api/v1/native/status");
      if (nat.ok) {
        $("native-body").textContent = JSON.stringify(nat.data, null, 2);
        const vnMode = nat.data.vnpy?.mode || "SHIM";
        const qlMode = nat.data.qlib?.mode || "SHIM";
        setPill("native-pill", `vn.py:${vnMode} Qlib:${qlMode}`);
        $("vnpy-mode-tag").textContent = vnMode;
        $("qlib-mode-tag").textContent = qlMode;
      }
      const agents = await api.request("/api/v1/brokers/wizard");
      if (agents.ok) {
        $("gateway-list").textContent = JSON.stringify(agents.data, null, 2);
      }
      const list = $("report-list");
      list.innerHTML = "";
      if (reports.ok && reports.data?.reports) {
        reports.data.reports.slice(0, 15).forEach((r) => {
          const li = document.createElement("li");
          li.textContent = r;
          list.appendChild(li);
        });
      }
    } catch (err) {
      $("overview-body").textContent = `Error: ${err.message}`;
    }
  }

  async function showApp() {
    $("login-overlay").classList.add("hidden");
    setPill("role-pill", `角色: ${api.role}`);
    await refresh();
    setInterval(refresh, 30000);
  }

  $("btn-login")?.addEventListener("click", async () => {
    const role = $("login-role").value;
    try {
      await api.login(role);
      await showApp();
      $("login-error").classList.add("hidden");
    } catch (e) {
      $("login-error").textContent = e.message;
      $("login-error").classList.remove("hidden");
    }
  });

  $("btn-logout")?.addEventListener("click", () => {
    api.clearSession();
    location.reload();
  });

  if (api.apiKey) {
    showApp();
  }
})();
