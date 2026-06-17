/** QuantOS CN portal — ViewModel-driven UI, real backend bindings. */
(function () {
  const api = window.QuantOSApi;
  const VM = window.QuantOSViewModels;
  const UI = window.QuantOSUI;

  let lastAgentRun = null;
  let cachedNative = null;
  let cachedQuantos = null;

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
    UI.renderActionLog($("action-log-body"), {
      label,
      ok: res.ok,
      time: new Date().toLocaleString("zh-CN"),
      summary: VM.actionSummary(label, res),
      runId: res.run_id || res.data?.run_id,
      raw: { request_id: res.request_id, trace_id: res.trace_id, data: res.data, error: res.error },
    });
    return res;
  }

  async function act(label, path, options, btn) {
    UI.setLoading(btn, true);
    try {
      const res = await api.request(path, options);
      logAction(label, res);
      if (!res.ok && res.httpStatus === 403) {
        alert(`权限不足: 当前角色 ${api.role} — ${res.error?.message || "forbidden"}`);
      }
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  const ACTIONS = {
    doctor: (btn) => act("系统体检", "/api/v1/system/doctor", { method: "POST" }, btn),
    "market-update": (btn) => act("更新数据", "/api/v1/market/update", {
      method: "POST",
      body: JSON.stringify({ targets: ["indices", "bars"] }),
    }, btn),
    "daily-run": (btn) => act("生成日报", "/api/v1/research/daily-run", { method: "POST" }, btn),
    "risk-check": (btn) => act("风险自检", "/api/v1/risk/status", {}, btn),
    "paper-start": (btn) => act("Paper 启动", "/api/v1/paper/start", { method: "POST" }, btn),
    "paper-stop": (btn) => act("Paper 停止", "/api/v1/paper/stop", { method: "POST" }, btn),
    "shadow-start": (btn) => act("Shadow 启动", "/api/v1/shadow/start", { method: "POST" }, btn),
    "shadow-stop": (btn) => act("Shadow 停止", "/api/v1/shadow/stop", { method: "POST" }, btn),
    halt: (btn) => act("紧急停机", "/api/v1/risk/halt", {
      method: "POST",
      body: JSON.stringify({ reason: "portal_halt" }),
    }, btn),
    "reset-request": (btn) => act("申请解除停机", "/api/v1/risk/reset-request", { method: "POST" }, btn),
    "reset-confirm": (btn) => act("确认解除停机", "/api/v1/risk/reset-confirm", { method: "POST" }, btn),
    backtest: (btn) => act("运行回测", "/api/v1/research/backtest", {
      method: "POST",
      body: JSON.stringify({ as_of_date: "2026-06-16" }),
    }, btn),
    "candidate-gate": (btn) => act("候选门", "/api/v1/research/candidate", { method: "POST" }, btn),
    "market-refresh": () => refreshMarket(),
    "market-update-job": (btn) => runMarketUpdateJob(btn),
    "paper-refresh": () => refreshPaper(),
    "open-pdf": async () => {
      const st = await api.request("/api/v1/system/status");
      const path = st.data?.latest_daily_report?.path_pdf;
      if (path) {
        logAction("打开 PDF", { ok: true, data: { summary: path }, request_id: st.request_id, trace_id: st.trace_id });
        window.open(`/api/v1/research/reports?format=pdf`, "_blank");
      } else alert("日报 PDF 尚未生成 — 请先运行「生成日报」");
    },
    "agents-run": async (btn) => {
      const res = await act("多智能体研究", "/api/v1/research/agents/run", {
        method: "POST",
        body: JSON.stringify({ as_of: "2026-06-16" }),
      }, btn);
      if (res.ok) {
        lastAgentRun = res.data;
        UI.renderAgentPanel($("agents-body"), VM.fromAgentsRun(lastAgentRun));
      }
      return res;
    },
    "native-vnpy-accept": (btn) => act("vn.py 原生验收", "/api/v1/native/vnpy/acceptance", { method: "POST" }, btn),
    "native-qlib-accept": (btn) => act("Qlib 原生验收", "/api/v1/native/qlib/acceptance", { method: "POST" }, btn),
    "broker-readonly": (btn) => act("只读连接向导", "/api/v1/brokers/readonly-connect", {
      method: "POST",
      body: JSON.stringify({ broker: "ReadOnlyGateway", config: { readonly: true } }),
    }, btn),
  };

  document.querySelectorAll("[data-action]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const fn = ACTIONS[btn.dataset.action];
      if (fn) {
        await fn(btn);
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

  function applyHeader(vm) {
    if (!vm) return;
    setPill("mode-pill", `模式: ${vm.modeLabel}`);
    setPill("session-pill", `时段: ${vm.sessionLabel}`);
    setPill("freshness-pill", `数据: ${vm.dataStatusLabel}`);
    setPill("capital-pill", `总资金: ${VM.fmtCny(vm.capitalCny)}`);
    setPill("budget-pill", `亏损额度: ${VM.fmtCny(vm.remainingLossBudgetCny)}`);
    setPill("kill-pill", `Kill: ${vm.killSwitchLabel}`, vm.killSwitchLabel === "已触发");
    setPill("native-pill", `${vm.vnpyShort} · ${vm.qlibShort}`);
    $("vnpy-mode-tag").textContent = vm.vnpyShort;
    $("qlib-mode-tag").textContent = vm.qlibShort;
  }

  async function refreshOverview(st, nativeStatus, quantosStatus) {
    const vm = VM.fromSystemStatus(st?.data, nativeStatus, quantosStatus);
    applyHeader(vm);
    UI.renderCardGrid($("overview-cards"), VM.overviewCards(vm));
    UI.renderBlockers($("overview-blockers"), vm?.blockers);
    UI.renderReportSummary($("overview-report"), vm?.latestReport);
  }

  async function refreshMarket() {
    const [overview, providers, coverage] = await Promise.all([
      api.request("/api/v1/market/overview"),
      api.request("/api/v1/market/providers"),
      api.request("/api/v1/market/coverage"),
    ]);
    const m = VM.fromMarket(overview, providers, coverage);
    const banner = $("market-summary");
    if (banner) {
      banner.innerHTML = m.blocked
        ? `<div class="banner banner-warn">数据被阻断（${m.blockerDataset || "数据集"}）— ${m.blockedReason}</div>`
        : `<div class="banner banner-ok">市场概览：${m.snapshotSummary}</div>`;
    }
    UI.renderTable($("market-indices"), ["指数", "收盘", "涨跌幅%", "交易日"], m.indices, "指数数据为空 — 请运行「更新数据」");
    UI.renderTable($("market-providers"), ["数据源", "状态", "数据集", "说明"], m.providers, "Provider 信息不可用");
    if ($("market-coverage")) {
      UI.renderTable($("market-coverage"), ["数据集", "行数", "最新交易日", "状态"], m.coverage, "暂无覆盖信息");
    }
  }

  async function runMarketUpdateJob(btn) {
    UI.setLoading(btn, true, "提交任务…");
    try {
      const res = await api.request("/api/v1/market/refresh", {
        method: "POST",
        body: JSON.stringify({ datasets: ["indices", "bars"], mode: "END_OF_DAY" }),
      });
      const jobId = res?.data?.job_id;
      logAction("更新数据（任务）", res);
      if (!jobId) return res;
      for (let i = 0; i < 60; i += 1) {
        const jr = await api.request(`/api/v1/jobs/${jobId}`);
        const job = jr?.data;
        UI.renderJob($("market-job"), job);
        if (!job || ["SUCCEEDED", "FAILED", "CANCELLED"].includes(job.status)) break;
        await new Promise((r) => setTimeout(r, 1000));
      }
      await refreshMarket();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function refreshPaper() {
    const [pnl, pos, orders] = await Promise.all([
      api.request("/api/v1/paper/pnl"),
      api.request("/api/v1/paper/positions"),
      api.request("/api/v1/paper/orders"),
    ]);
    const p = VM.fromPaper(pnl, pos, orders);
    UI.renderKeyValues($("paper-pnl"), [
      ["已实现盈亏", p.summary.realized],
      ["浮动盈亏", p.summary.unrealized],
      ["合计", p.summary.total],
      ["费用", p.summary.fees],
    ]);
    UI.renderTable($("paper-positions"), ["代码", "数量", "T+1可卖", "成本", "市值"], p.positions, "暂无持仓");
    UI.renderTable($("paper-orders"), ["订单号", "代码", "方向", "状态", "成交量"], p.orders, "暂无订单");
  }

  function refreshRiskView(risk) {
    const r = VM.fromRisk(risk?.data);
    if (!r) return;
    UI.renderKeyValues($("risk-detail"), [
      ["总资金", r.capital],
      ["权益", r.equity],
      ["剩余亏损额度", r.lossBudget],
      ["Kill Switch", r.killSwitch],
      ["停机状态", r.halted ? "已停机" : "正常"],
    ]);
  }

  function refreshNativeView(nativeStatus, quantosStatus) {
    cachedNative = nativeStatus?.data;
    cachedQuantos = quantosStatus?.data;
    const vm = VM.fromSystemStatus({ qlib: nativeStatus?.data?.qlib?.main_provider }, nativeStatus?.data, quantosStatus?.data);
    const vn = VM.mapVnpyLabel(nativeStatus?.data, quantosStatus?.data);
    const ql = VM.mapQlibLabel(nativeStatus?.data, nativeStatus?.data?.qlib?.main_provider);
    UI.renderKeyValues($("native-body"), [
      ["vn.py 隔离环境", nativeStatus?.data?.vnpy?.isolated_venv?.state || "—"],
      ["vn.py 模式", vn.long],
      ["vn.py 运行", quantosStatus?.data?.vnpy_runtime?.running ? "运行中" : "未启动"],
      ["Qlib 隔离环境", nativeStatus?.data?.qlib?.isolated_venv?.state || "—"],
      ["Qlib 模式", ql.long],
      ["真实下单", "已禁用"],
    ]);
    UI.renderKeyValues($("vnpy-status"), [
      ["状态", vn.long],
      ["网关", quantosStatus?.data?.vnpy_runtime?.active_gateway || "PaperGateway"],
      ["最近事件", `${quantosStatus?.data?.vnpy_runtime?.recent_events?.length || 0} 条`],
    ]);
    UI.renderKeyValues($("qlib-status"), [
      ["状态", ql.long],
      ["仓库", nativeStatus?.data?.qlib?.main_provider?.warehouse_exists ? "已就绪" : "缺失"],
    ]);
  }

  function refreshBrokers(broker) {
    const b = VM.fromBrokers(broker?.data);
    UI.renderTable($("gateway-list"), ["Gateway", "状态", "真实下单"], b.rows, "券商 Gateway 未配置");
    const cl = $("broker-checklist");
    if (cl) {
      cl.innerHTML = "";
      if (b.checklist?.length) {
        const ul = document.createElement("ul");
        ul.className = "checklist";
        b.checklist.forEach((item) => {
          const li = document.createElement("li");
          li.textContent = item;
          ul.appendChild(li);
        });
        cl.appendChild(ul);
      }
      if (b.note) cl.appendChild(Object.assign(document.createElement("p"), { className: "muted", textContent: b.note }));
    }
  }

  function refreshShadow(shadow, events) {
    if (shadow?.ok) {
      const d = shadow.data;
      UI.renderKeyValues($("shadow-status"), [
        ["状态", d.status || d.mode || "—"],
        ["零真实订单", d.zero_real_orders_sent !== false ? "是" : "否"],
        ["运行 ID", d.run_id || "—"],
      ]);
    }
    const evRows = (events?.data?.events || []).slice(-10).map((e) => [
      e.type || e.event || "—",
      e.symbol || "—",
      e.ts || e.time || "—",
    ]);
    UI.renderTable($("shadow-events"), ["事件", "标的", "时间"], evRows, "暂无影子事件");
  }

  function refreshModels(registry) {
    const models = registry?.data?.models || registry?.data || [];
    const rows = (Array.isArray(models) ? models : []).map((m) => [
      m.id || m.name || "—",
      m.status || "—",
      m.native ? "原生" : "兼容",
      m.dsr ?? m.sharpe ?? "—",
    ]);
    UI.renderTable($("model-registry"), ["模型", "状态", "引擎", "DSR/Sharpe"], rows, "模型注册表为空 — 运行基线或回测");
  }

  async function refreshFooterVersion() {
    const ver = await api.request("/api/v1/system/version", { skipAuth: true });
    if (!ver.ok) return;
    const d = ver.data;
    const pageBuild = document.body.dataset.portalBuild || "";
    const mismatch = pageBuild && d.frontend_build_id && !d.frontend_build_id.startsWith(pageBuild.split("-")[0]);
    $("footer-version").textContent = `Backend ${d.git_commit_short} · Frontend ${d.frontend_build_id?.slice(0, 24) || "—"} · PID ${d.process_id}`;
    $("footer-build-warn").classList.toggle("hidden", !mismatch);
  }

  async function refresh() {
    if (!api.apiKey) return;
    try {
      const [st, risk, reports, shadow, nativeStatus, quantosStatus, events] = await Promise.all([
        api.request("/api/v1/system/status"),
        api.request("/api/v1/risk/status"),
        api.request("/api/v1/research/reports"),
        api.request("/api/v1/shadow/status"),
        api.request("/api/v1/native/status"),
        api.request("/api/v1/quantos/status"),
        api.request("/api/v1/quantos/vnpy/events"),
      ]);
      await refreshOverview(st, nativeStatus?.data, quantosStatus?.data);
      refreshRiskView(risk);
      refreshNativeView(nativeStatus?.data, quantosStatus?.data);
      refreshBrokers(await api.request("/api/v1/brokers/wizard"));
      refreshShadow(shadow, events);
      refreshModels(quantosStatus?.data?.model_registry);
      refreshPaper();
      await refreshMarket();

      UI.renderReportSummary($("report-detail"), VM.fromSystemStatus(st?.data)?.latestReport);
      const list = $("report-list");
      list.innerHTML = "";
      if (reports.ok && reports.data?.reports?.length) {
        reports.data.reports.slice(0, 15).forEach((r) => {
          const li = document.createElement("li");
          li.textContent = typeof r === "string" ? r : r.path || r.date || JSON.stringify(r);
          list.appendChild(li);
        });
      } else {
        list.appendChild(Object.assign(document.createElement("li"), { className: "muted", textContent: "尚无历史报告" }));
      }

      if (lastAgentRun) UI.renderAgentPanel($("agents-body"), VM.fromAgentsRun(lastAgentRun));
    } catch (err) {
      UI.renderEmpty($("overview-cards"), "加载失败", err.message, "检查 Gateway 是否在 8787 运行");
    }
  }

  async function showApp() {
    $("login-overlay").classList.add("hidden");
    setPill("role-pill", `角色: ${api.role}`);
    await refreshFooterVersion();
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

  if (api.apiKey) showApp();

  window.QuantOSPortal = { refresh, logAction, ACTIONS };
})();
