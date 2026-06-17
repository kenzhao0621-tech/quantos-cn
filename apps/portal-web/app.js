/** QuantOS CN portal — ViewModel-driven UI, real backend bindings. */
(function () {
  const api = window.QuantOSApi;
  const VM = window.QuantOSViewModels;
  const UI = window.QuantOSUI;

  let lastAgentRun = null;
  let lastScreenerVm = null;
  let cachedNative = null;
  let cachedQuantos = null;
  const liveSeries = {};

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
    const summary = VM.actionSummary(label, res);
    UI.renderActionLog($("action-log-body"), {
      label,
      ok: res.ok,
      time: new Date().toLocaleString("zh-CN"),
      summary,
      runId: res.run_id || res.data?.run_id,
      raw: { request_id: res.request_id, trace_id: res.trace_id, data: res.data, error: res.error },
    });
    UI.toast(
      `${label}${res.ok ? " 成功" : " 失败"}`,
      res.ok ? summary : (res.error?.message || "操作未成功"),
      res.ok ? "ok" : "fail",
    );
    return res;
  }

  async function act(label, path, options, btn) {
    UI.setLoading(btn, true);
    try {
      const res = await api.request(path, options);
      logAction(label, res);
      if (!res.ok && res.httpStatus === 403) {
        UI.toast("权限不足", `当前角色 ${api.role} 无此权限`, "fail");
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
    "market-live-refresh": (btn) => refreshLiveMarket(btn),
    "market-update-job": (btn) => runMarketUpdateJob(btn),
    "screener-run": (btn) => runScreener(btn),
    "screener-proof": (btn) => runScreenerProof(btn),
    "screener-dossier-top": (btn) => runTopDossier(btn),
    "paper-from-screener": (btn) => paperFromScreener(btn),
    "save-preferences": (btn) => savePreferences(btn),
    "autopilot-readiness": (btn) => autopilotReadiness(btn),
    "autopilot-ticket": (btn) => autopilotTicket(btn),
    "model-validate": (btn) => modelValidate(btn),
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

  document.addEventListener("click", async (ev) => {
    const btn = ev.target?.closest?.("[data-dossier-symbol]");
    if (btn) {
      await runDossier(btn.dataset.dossierSymbol, btn);
      return;
    }
    const broker = ev.target?.closest?.("[data-broker-url]");
    if (broker) {
      const ok = confirm("将打开券商/厂商官方页面。请勿在本软件内输入交易密码；真实交易必须由你本人在官方平台确认。继续？");
      if (ok) window.open(broker.dataset.brokerUrl, "_blank", "noopener,noreferrer");
    }
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll("main.layout").forEach((m) => m.classList.add("hidden"));
      const el = $(`page-${tab.dataset.page}`);
      if (el) el.classList.remove("hidden");
      if (tab.dataset.page === "screener" && !$("screener-table")?.children.length) {
        runScreener($("screener-meta") ? document.querySelector('[data-action="screener-run"]') : null);
      }
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
    refreshLivePlan();
  }

  async function refreshLivePlan() {
    const plan = await api.request("/api/v1/market/intraday-plan");
    const p = plan.data || {};
    const rows = (p.slots || []).map((s) => [s.label, s.time, s.due_today ? "今日已到点" : "待到点", s.purpose]);
    UI.renderTable($("market-live-plan"), ["窗口", "时间", "状态", "用途"], rows, "暂无刷新计划");
  }

  async function refreshLiveMarket(btn) {
    UI.setLoading(btn, true, "刷新中…");
    try {
      const res = await api.request("/api/v1/market/live-refresh", { method: "POST" });
      const d = res.data || {};
      const box = $("market-live");
      if (box) {
        if (d.blocked) {
          box.innerHTML = `<div class="banner banner-warn">实时行情不可证明：${d.reason || "provider blocked"}</div>`;
        } else {
          box.innerHTML =
            `<div class="banner banner-ok">实时行情：${d.provider} · ${d.row_count} 行 · ${d.freshness} · ${d.retrieved_at}</div>`;
          UI.renderTable(
            box.appendChild(document.createElement("div")),
            ["代码", "名称", "最新价", "涨跌幅%", "成交额"],
            (d.top_up || []).slice(0, 8).map((r) => [r.code, r.name, r.price, r.change_pct, r.amount]),
            "暂无实时涨幅榜",
          );
        }
      }
      UI.toast(d.blocked ? "实时行情不可用" : "实时行情已更新", d.blocked ? (d.reason || "provider blocked") : `${d.row_count} 行`, d.blocked ? "fail" : "ok");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function refreshOverviewLive() {
    const res = await api.request("/api/v1/market/live-snapshot?require_live=false");
    const d = res.data || {};
    if (d.top_up?.length) {
      d.top_up.slice(0, 12).forEach((r) => {
        const key = r.code || r.symbol;
        if (!key || r.price == null) return;
        liveSeries[key] = (liveSeries[key] || []).concat([Number(r.price)]).slice(-24);
      });
    }
    UI.renderLiveRadar($("overview-live"), d, liveSeries);
  }

  async function loadPreferences() {
    const res = await api.request("/api/v1/user/preferences");
    const p = res.data || {};
    if ($("pref-capital")) $("pref-capital").value = Math.round(p.capital_cny || 100000);
    if ($("pref-loss")) $("pref-loss").value = Math.round((p.max_loss_pct || 0.08) * 1000) / 10;
    if ($("pref-positions")) $("pref-positions").value = p.max_positions || 5;
    if ($("pref-single")) $("pref-single").value = Math.round((p.max_single_position_pct || 0.18) * 100);
    if ($("pref-sectors")) $("pref-sectors").value = (p.preferred_sectors || []).join(",");
    if ($("pref-exclude-sectors")) $("pref-exclude-sectors").value = (p.excluded_sectors || []).join(",");
    if ($("screener-preset") && p.strategy_preset) $("screener-preset").value = p.strategy_preset;
    if ($("screener-minamt") && p.min_amount_cny) $("screener-minamt").value = String(p.min_amount_cny);
  }

  async function savePreferences(btn) {
    UI.setLoading(btn, true, "保存中…");
    try {
      const body = {
        capital_cny: Number($("pref-capital")?.value || 100000),
        max_loss_pct: Number($("pref-loss")?.value || 8) / 100,
        max_positions: Number($("pref-positions")?.value || 5),
        max_single_position_pct: Number($("pref-single")?.value || 18) / 100,
        cash_buffer_pct: 0.2,
        min_amount_cny: Number($("screener-minamt")?.value || 100000000),
        strategy_preset: $("screener-preset")?.value || "balanced",
        preferred_sectors: splitCsv($("pref-sectors")?.value || ""),
        excluded_sectors: splitCsv($("pref-exclude-sectors")?.value || ""),
      };
      const res = await api.request("/api/v1/user/preferences", { method: "PUT", body: JSON.stringify(body) });
      logAction("保存用户偏好", res);
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function runScreener(btn) {
    UI.setLoading(btn, true, "计算中…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const mode = $("screener-mode")?.value || "live";
      const topN = $("screener-topn")?.value || "25";
      const minAmt = $("screener-minamt")?.value || "100000000";
      const sectors = encodeURIComponent($("pref-sectors")?.value || "");
      const excluded = encodeURIComponent($("pref-exclude-sectors")?.value || "");
      const res = await api.request(
        `/api/v1/screener/run?preset=${preset}&top_n=${topN}&min_amount_cny=${minAmt}&mode=${mode}&preferred_sectors=${sectors}&excluded_sectors=${excluded}`,
        { timeoutMs: 90000 },
      );
      if (!res.ok) {
        UI.renderScreener($("screener-table"), { blocked: true, blockerReason: res.error?.message || "选股请求失败", rows: [] });
        UI.toast("选股失败", res.error?.message || "请稍后重试", "fail");
        return res;
      }
      const vm = VM.fromScreener(res);
      lastScreenerVm = vm;
      UI.renderScreener($("screener-table"), vm);
      const meta = $("screener-meta");
      if (meta) {
        meta.innerHTML = vm.blocked
          ? ""
          : `<span class="metric-chip">截止 <b>${vm.dataCutoff}</b></span>` +
            `<span class="metric-chip">模型 <b>${vm.modelVersion}</b></span>` +
            `<span class="metric-chip">验证 <b>${vm.validationStatus}</b></span>` +
            `<span class="metric-chip">历史因子 <b>${vm.factorAsOfDate}</b></span>` +
            (vm.liveRetrievedAt ? `<span class="metric-chip">实时行情 <b>${vm.liveRetrievedAt}</b></span>` : "") +
            (vm.liveProvider ? `<span class="metric-chip">实时源 <b>${vm.liveProvider}</b></span>` : "") +
            `<span class="metric-chip">模式 <b>${vm.mode}</b></span>` +
            `<span class="metric-chip">策略 <b>${vm.preset}</b></span>` +
            `<span class="metric-chip">候选池 <b>${vm.universeSize}</b> 只</span>` +
            `<span class="metric-chip">入选 <b>${vm.rows.length}</b> 只</span>`;
      }
      UI.toast(
        res.ok && !vm.blocked ? "选股完成" : "选股失败",
        res.ok && !vm.blocked ? `从 ${vm.universeSize} 只中选出 ${vm.rows.length} 只` : (vm.blockerReason || "请先更新数据"),
        res.ok && !vm.blocked ? "ok" : "fail",
      );
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  function splitCsv(value) {
    return String(value || "").replaceAll("，", ",").split(",").map((x) => x.trim()).filter(Boolean);
  }

  async function runScreenerProof(btn) {
    UI.setLoading(btn, true, "验证中…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const topN = $("screener-topn")?.value || "25";
      const res = await api.request(`/api/v1/screener/proof?preset=${preset}&top_n=${topN}`);
      UI.renderProof($("screener-proof"), res);
      const d = res.data || {};
      UI.toast(
        d.verdict === "PASS" ? "昨日选股验证通过" : "昨日选股需要复盘",
        d.blocked ? (d.blocker_reason || "无法验证") : `平均收益 ${d.avg_return}% / 市场中位数 ${d.benchmark_median}%`,
        d.verdict === "PASS" ? "ok" : "fail",
      );
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function runTopDossier(btn) {
    UI.setLoading(btn, true, "解释中…");
    try {
      if (!lastScreenerVm?.rows?.length) {
        await runScreener(document.querySelector('[data-action="screener-run"]'));
      }
      const top = lastScreenerVm?.rows?.[0];
      if (!top?.symbol) {
        UI.toast("暂无候选", "请先运行选股", "fail");
        return { ok: false };
      }
      return runDossier(top.symbol, btn);
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function runDossier(symbol, btn) {
    UI.setLoading(btn, true, "解释中…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const mode = $("screener-mode")?.value || "live";
      const sectors = encodeURIComponent($("pref-sectors")?.value || "");
      const excluded = encodeURIComponent($("pref-exclude-sectors")?.value || "");
      const res = await api.request(`/api/v1/screener/dossier/${encodeURIComponent(symbol)}?preset=${preset}&mode=${mode}&preferred_sectors=${sectors}&excluded_sectors=${excluded}`);
      UI.renderDossier($("screener-dossier"), res);
      UI.toast("个股报告已生成", symbol, "ok");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function paperFromScreener(btn) {
    UI.setLoading(btn, true, "生成组合…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const topN = $("screener-topn")?.value || "25";
      const maxPositions = Number($("pref-positions")?.value || 5);
      const res = await api.request("/api/v1/paper/from-screener", {
        method: "POST",
        body: JSON.stringify({ preset, top_n: Number(topN), max_positions: maxPositions, capital_fraction: 0.8 }),
      });
      logAction("选股加入 Paper", res);
      if (res.ok) {
        UI.toast("已加入 Paper 模拟组合", `生成 ${res.data?.orders?.length || 0} 张模拟订单`, "ok");
      } else if (res.error?.code === "PAPER_NOT_STARTED") {
        UI.toast("请先启动 Paper", "点击「启动 Paper」后再加入模拟组合", "fail");
      }
      await refreshPaper();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function autopilotReadiness(btn) {
    UI.setLoading(btn, true, "检查中…");
    try {
      const res = await api.request("/api/v1/autopilot/readiness");
      UI.renderAutopilot($("autopilot-panel"), res);
      UI.toast("Autopilot 准入检查完成", res.data?.ready_for_order_ticket ? "可生成订单票据" : "仍有阻塞项", res.data?.ready_for_order_ticket ? "ok" : "fail");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function autopilotTicket(btn) {
    UI.setLoading(btn, true, "生成票据…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const mode = $("screener-mode")?.value || "live";
      const topN = Number($("screener-topn")?.value || 25);
      const res = await api.request("/api/v1/autopilot/order-ticket", {
        method: "POST",
        body: JSON.stringify({ preset, top_n: topN, mode }),
      });
      UI.renderAutopilot($("autopilot-panel"), res);
      logAction("生成订单票据", res);
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function modelValidate(btn) {
    UI.setLoading(btn, true, "验收中…");
    try {
      const body = {
        preset: $("screener-preset")?.value || "balanced",
        lookback_days: Number($("validation-days")?.value || 45),
        top_n: Number($("validation-topn")?.value || 10),
        max_per_sector: 2,
        cost_bps: Number($("validation-cost")?.value || 8),
        slippage_bps: Number($("validation-slippage")?.value || 12),
        min_amount_cny: Number($("screener-minamt")?.value || 100000000),
      };
      const res = await api.request("/api/v1/models/validate", {
        method: "POST",
        body: JSON.stringify(body),
      });
      UI.renderModelValidation($("model-validation"), res);
      UI.toast("模型验收完成", res.data?.verdict || "完成", res.data?.verdict === "READY_FOR_EXTENDED_PAPER" ? "ok" : "fail");
      return res;
    } finally {
      UI.setLoading(btn, false);
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
      ["现金", p.summary.cash],
      ["权益", p.summary.equity],
      ["模拟盈亏", p.summary.realized],
      ["持仓数", p.summary.openPositions],
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
    UI.renderBrokerLinks($("broker-links"), broker?.data?.portal_links || []);
    api.request("/api/v1/gateway/readiness").then((r) => UI.renderGatewayReadiness($("gateway-readiness"), r));
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
    // Compare the build the browser loaded against the SAME server's stable build.
    // Mismatch => the browser is holding HTML from a previous server instance.
    const mismatch = !!(pageBuild && d.portal_build_id && pageBuild !== d.portal_build_id);
    $("footer-version").textContent = `Backend ${d.git_commit_short} · PID ${d.process_id}`;
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
      await loadPreferences();
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
    if (!localStorage.getItem("quantos_legal_ack")) {
      $("legal-overlay")?.classList.remove("hidden");
    }
    setPill("role-pill", `角色: ${api.role}`);
    await refreshFooterVersion();
    await refresh();
    await refreshOverviewLive();
    setInterval(refresh, 30000);
    setInterval(refreshOverviewLive, 15000);
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

  $("btn-legal-accept")?.addEventListener("click", () => {
    localStorage.setItem("quantos_legal_ack", "1");
    $("legal-overlay")?.classList.add("hidden");
  });

  $("btn-logout")?.addEventListener("click", () => {
    api.clearSession();
    location.reload();
  });

  if (api.apiKey) showApp();

  window.QuantOSPortal = { refresh, logAction, ACTIONS };
})();
