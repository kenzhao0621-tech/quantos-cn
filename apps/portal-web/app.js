/** QuantOS CN portal — ViewModel-driven UI, real backend bindings. */
(function () {
  const api = window.QuantOSApi;
  const VM = window.QuantOSViewModels;
  const UI = window.QuantOSUI;

  let lastAgentRun = null;
  let lastAutopilotTicket = null;
  let lastScreenerVm = null;
  let lastScreenerDetailSymbol = null;
  let lastLiveRefresh = null;
  let lastLiveRefreshMeta = null;
  let liveRefreshPromise = null;
  let paperLiveTimer = null;
  let paperAutoLiveEnabled = true;
  let paperLiveCycleRunning = false;
  /** 实时行情缓存有效期；Paper 自动轮询间隔 */
  const LIVE_QUOTE_TTL_MS = 14 * 60 * 1000;
  const PAPER_AUTO_LIVE_MS = 15 * 60 * 1000;
  const INTRADAY_QUOTE_MS = 15 * 60 * 1000;
  let globalIntradayTimer = null;
  let paperMonitorTimer = null;
  let cachedNative = null;
  let cachedQuantos = null;
  let cachedBrokerEcosystem = null;
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

  async function pingGateway() {
    return api.ping();
  }

  function showGatewayBanner(up, message) {
    const banner = $("gateway-offline-banner");
    if (!banner) return;
    if (!up) {
      banner.textContent = message || `Gateway 未连接（${api.base}）— 请运行：make app`;
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }

  async function safeSection(label, fn) {
    try {
      await fn();
    } catch (err) {
      console.error(`portal:${label}`, err);
    }
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
    "market-sync-all": (btn) => marketSyncAll(btn),
    "daily-run": (btn) => act("生成日报", "/api/v1/research/daily-run", { method: "POST" }, btn),
    "risk-check": (btn) => act("风险自检", "/api/v1/risk/status", {}, btn),
    "paper-start": (btn) => act("Paper 启动", "/api/v1/paper/start", { method: "POST" }, btn).then(() => refreshPaper()),
    "paper-stop": (btn) => act("Paper 停止", "/api/v1/paper/stop", { method: "POST" }, btn).then(() => refreshPaper()),
    "shadow-start": (btn) => act("Shadow 启动", "/api/v1/shadow/start", { method: "POST" }, btn),
    "shadow-stop": (btn) => act("Shadow 停止", "/api/v1/shadow/stop", { method: "POST" }, btn),
    halt: (btn) => act("紧急停机", "/api/v1/risk/halt", {
      method: "POST",
      body: JSON.stringify({ reason: "portal_halt" }),
    }, btn),
    "reset-request": (btn) => act("申请解除停机", "/api/v1/risk/reset-request", { method: "POST" }, btn),
    "reset-confirm": (btn) => act("确认解除停机", "/api/v1/risk/reset-confirm", { method: "POST" }, btn),
    backtest: (btn) => runBacktestWithCurves(btn),
    "agents-analyze": (btn) => runAgentsAnalyze(btn),
    "candidate-gate": (btn) => act("候选门", "/api/v1/research/candidate", { method: "POST" }, btn),
    "market-refresh": () => refreshMarket(),
    "market-live-refresh": (btn) => refreshLiveMarket(btn),
    "market-update-job": (btn) => runMarketUpdateJob(btn),
    "screener-run": (btn) => runScreener(btn),
    "screener-proof": (btn) => runScreenerProof(btn),
    "screener-learn": (btn) => runScreenerLearn(btn),
    "screener-report-pdf": (btn) => exportScreenerReportPdf(btn),
    "strategy-learn-latest": (btn) => loadLatestStrategyLearning(btn),
    "screener-stock-search": (btn) => runStockSearch(btn),
    "paper-from-screener": (btn) => paperFromScreener(btn),
    "execute-allocation": (btn) => executeAllocation(btn),
    "save-preferences": (btn) => savePreferences(btn),
    "autopilot-readiness": (btn) => autopilotReadiness(btn),
    "autopilot-ticket": (btn) => autopilotTicket(btn),
    "autopilot-execute-ticket": (btn) => autopilotExecuteTicket(btn),
    "model-validate": (btn) => modelValidate(btn),
    "paper-refresh": () => refreshPaper(),
    "paper-mark-to-market": (btn) => paperMarkToMarket(btn),
    "paper-submit-order": (btn) => paperSubmitOrder(btn),
    "paper-monitor-tick": (btn) => paperMonitorTick(btn),
    "paper-monitor-stop": (btn) => paperMonitorStop(btn),
    "paper-report-close": (btn) => paperGenerateCloseReport(btn),
    "open-pdf": async () => {
      const st = await api.request("/api/v1/system/status");
      const latest = st.data?.latest_daily_report || {};
      const pdfName = latest.path_pdf ? latest.path_pdf.split("/").pop() : "";
      if (pdfName && latest.status === "AVAILABLE") {
        const url = `/api/v1/research/reports/download?file=${encodeURIComponent(pdfName)}`;
        logAction("打开 PDF", { ok: true, data: { summary: pdfName }, request_id: st.request_id, trace_id: st.trace_id });
        window.open(url, "_blank");
      } else alert("日报 PDF 尚未生成 — 请先运行「生成日报」");
    },
    "agents-run": async (btn) => {
      const res = await act("多智能体研究", "/api/v1/research/agents/run", {
        method: "POST",
        body: JSON.stringify({}),
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
    "broker-connect": (btn) => brokerConnect(btn),
    "broker-login": (btn) => brokerLogin(btn),
    "broker-sync-watchlist": (btn) => brokerSyncWatchlist(btn),
    "broker-export-fills": (btn) => brokerExportFills(btn),
    "broker-save-gates": (btn) => brokerSaveGates(btn),
    "broker-save-config": (btn) => brokerSaveConfig(btn),
    "broker-test-paths": (btn) => brokerTestPaths(btn),
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
    const watchStar = ev.target?.closest?.("[data-watchlist-add]");
    if (watchStar) {
      await addToWatchlist(watchStar.dataset.watchlistAdd, watchStar.dataset.watchlistName || "");
      return;
    }
    const liveBtn = ev.target?.closest?.("[data-live-order]");
    if (liveBtn) {
      await submitLiveOrder(liveBtn);
      return;
    }
    const closeModalBtn = ev.target?.closest?.("[data-stock-modal-close], [data-dossier-close]");
    if (closeModalBtn) {
      UI.closeStockDetailModal();
      UI.renderDossier($("screener-dossier"), { _closed: true });
      return;
    }
    const detailBtn = ev.target?.closest?.("[data-screener-detail]");
    if (detailBtn) {
      showStockDetail(detailBtn.dataset.screenerDetail);
      return;
    }
    const screenerRow = ev.target?.closest?.("tr[data-screener-row]");
    if (screenerRow && !ev.target?.closest?.("button")) {
      showStockDetail(screenerRow.dataset.screenerRow);
      return;
    }
    const setupBtn = ev.target?.closest?.("[data-setup-action]");
    if (setupBtn) {
      await handleSetupAction(setupBtn.dataset.setupAction);
      return;
    }
    const copyBtn = ev.target?.closest?.("[data-copy-path]");
    if (copyBtn?.dataset.copyPath) {
      try {
        await navigator.clipboard.writeText(copyBtn.dataset.copyPath);
        UI.toast("已复制路径", copyBtn.dataset.copyPath, "ok");
      } catch {
        UI.toast("复制失败", copyBtn.dataset.copyPath, "fail");
      }
      return;
    }
    const broker = ev.target?.closest?.("[data-broker-url]");
    if (broker) {
      const ok = confirm("将打开券商/厂商官方页面。请勿在本软件内输入交易密码；真实交易必须由你本人在官方平台确认。继续？");
      if (ok) window.open(broker.dataset.brokerUrl, "_blank", "noopener,noreferrer");
    }
  });

  $("stock-detail-modal")?.addEventListener("click", (ev) => {
    if (ev.target?.id === "stock-detail-modal") {
      UI.closeStockDetailModal();
      const hint = $("screener-dossier");
      if (hint) {
        hint.innerHTML = "";
        hint.appendChild(document.createTextNode("点击表格任意行打开个股详情；支持 Esc / 点击遮罩 / ✕ 关闭"));
      }
    }
  });

  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Escape") return;
    const modal = $("stock-detail-modal");
    if (!modal || modal.classList.contains("hidden")) return;
    UI.closeStockDetailModal();
    const hint = $("screener-dossier");
    if (hint) {
      hint.innerHTML = "";
      hint.appendChild(document.createTextNode("点击表格任意行打开个股详情；支持 Esc / 点击遮罩 / ✕ 关闭"));
    }
  });

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll("main.layout").forEach((m) => m.classList.add("hidden"));
      const el = $(`page-${tab.dataset.page}`);
      if (el) el.classList.remove("hidden");
      if (tab.dataset.page === "paper") {
        paperAutoLiveEnabled = true;
        startPaperMonitorLoop();
        refreshPaper();
      } else if (tab.dataset.page === "screener") {
        stopPaperMonitorLoop();
      } else if (tab.dataset.page === "models") {
        stopPaperMonitorLoop();
        const panel = $("model-strategy-learning");
        if (panel && !panel.children.length) {
          api.request("/api/v1/screener/learn/latest").then((res) => {
            if (res.ok && res.data?.status !== "NOT_RUN") {
              UI.renderStrategyLearning(panel, res.data);
            }
          }).catch(() => {});
        }
      } else {
        stopPaperMonitorLoop();
      }
    });
  });

  function applyHeader(vm) {
    if (!vm) return;
    setPill("mode-pill", `模式: ${vm.modeLabel}`);
    if ($("session-pill")) setPill("session-pill", `时段: ${vm.sessionLabel}`);
    setPill("freshness-pill", `数据: ${vm.dataStatusLabel}`);
    setPill("capital-pill", `资金: ${VM.fmtCny(vm.capitalCny)}`);
    if ($("budget-pill")) setPill("budget-pill", `亏损额度: ${VM.fmtCny(vm.remainingLossBudgetCny)}`);
    if ($("kill-pill")) setPill("kill-pill", `Kill: ${vm.killSwitchLabel}`, vm.killSwitchLabel === "已触发");
    if ($("native-pill")) setPill("native-pill", `${vm.vnpyShort} · ${vm.qlibShort}`);
    if ($("vnpy-mode-tag")) $("vnpy-mode-tag").textContent = vm.vnpyShort;
    if ($("qlib-mode-tag")) $("qlib-mode-tag").textContent = vm.qlibShort;
  }

  function refreshHelpPage(section) {
    const active = section || document.querySelector(".help-nav-btn.active")?.dataset.helpSection || "start";
    document.querySelectorAll(".help-nav-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.helpSection === active);
    });
    UI.renderHelpGuide($("help-content"), active);
  }

  document.querySelectorAll(".help-nav-btn").forEach((btn) => {
    btn.addEventListener("click", () => refreshHelpPage(btn.dataset.helpSection));
  });

  async function refreshSetupCenter() {
    const res = await api.request("/api/v1/system/setup-checklist");
    if (res.ok) UI.renderSetupCenter($("setup-center"), res.data);
    if (res.ok && $("guide-setup")) UI.renderSetupCenter($("guide-setup"), res.data);
    return res;
  }

  async function refreshPlatformHealth() {
    return refreshSetupCenter();
  }

  async function handleSetupAction(action) {
    if (action === "market-sync-all") return marketSyncAll(null);
    if (action === "goto-brokers") {
      document.querySelector('.tab[data-page="brokers"]')?.click();
      return;
    }
    if (action === "goto-screener") {
      document.querySelector('.tab[data-page="screener"]')?.click();
      return;
    }
    if (action === "goto-paper") {
      document.querySelector('.tab[data-page="paper"]')?.click();
      return;
    }
    if (action === "show-env") {
      const res = await api.request("/api/v1/system/setup-checklist");
      const p = res.data?.artifacts?.env_example || ".env.example";
      UI.toast("配置 Tushare", `复制 ${p} 为 .env 并填入 TUSHARE_TOKEN，然后重启 make app`, "info");
      $("setup-center")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  async function marketSyncAll(btn) {
    UI.setLoading(btn, true, "同步中…");
    try {
      const res = await api.request("/api/v1/market/sync-all", { method: "POST" });
      logAction("同步全部数据", res);
      const ms = res.data?.market_status?.labels;
      if (res.ok) {
        UI.toast(
          res.data?.ok ? "同步完成" : "部分完成",
          ms?.pill || "请查看配置中心",
          res.data?.ok ? "ok" : "fail",
        );
      }
      await refreshMarket();
      await refreshOverviewLive();
      await refreshSetupCenter();
      await refreshPlatformHealth();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function refreshOverview(st, nativeStatus, quantosStatus) {
    const vm = VM.fromSystemStatus(st?.data, nativeStatus, quantosStatus);
    applyHeader(vm);
    const ob = $("overview-body");
    if (ob) {
      ob.textContent = [
        `mode: ${st?.data?.mode || "RESEARCH_ONLY"}`,
        `PAPER: ${vm?.paperLabel || "—"}`,
        `SHADOW: ${vm?.shadowLabel || "—"}`,
        `deployment: ${st?.data?.deployment_eligibility || "—"}`,
      ].join(" · ");
    }
    UI.renderCardGrid($("overview-cards"), VM.overviewCards(vm));
    UI.renderBlockers($("overview-blockers"), vm?.blockers);
    UI.renderReportSummary($("overview-report"), vm?.latestReport);
  }

  async function checkBuildSync() {
    const banner = $("build-sync-banner");
    if (!banner) return;
    try {
      const ver = await api.request("/api/v1/system/version");
      const embedded =
        document.querySelector('meta[name="portal-build-id"]')?.content
        || document.querySelector('meta[name="quantos-build"]')?.content
        || document.body.dataset.portalBuild
        || "";
      const backend = ver.data?.portal_build_id || ver.data?.backend_build_id || "";
      if (embedded && backend && embedded !== backend) {
        banner.textContent = `STALE_BUILD_DETECTED — 请硬刷新 (前端 ${embedded} ≠ 后端 ${backend})`;
        banner.classList.remove("hidden");
      } else {
        banner.classList.add("hidden");
      }
    } catch {
      banner.classList.add("hidden");
    }
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

  function isLiveScreenerMode() {
    return ($("screener-mode")?.value || "eod") === "live";
  }

  function liveQuotesStale() {
    if (!lastLiveRefresh) return true;
    const t = Date.parse(lastLiveRefresh);
    if (Number.isNaN(t)) return true;
    return Date.now() - t > LIVE_QUOTE_TTL_MS;
  }

  function updateLiveQuotePill(meta) {
    const pill = $("live-quote-pill");
    if (!pill) return;
    const d = meta || lastLiveRefreshMeta;
    if (!d || d.blocked) {
      pill.textContent = "实时: 不可用";
      pill.classList.add("kill");
      pill.title = d?.reason || "请先连接行情源";
      return;
    }
    pill.classList.remove("kill");
    const n = d.row_count || 0;
    const at = d.retrieved_at || lastLiveRefresh || "—";
    pill.textContent = `实时: ${n}只 · ${String(at).slice(11, 19) || at}`;
    pill.title = `${d.provider || ""} · ${d.freshness || ""} · 真实报价`;
  }

  function setPaperLiveBanner(text, tone) {
    const el = $("paper-live-auto-banner");
    if (!el) return;
    if (!text) {
      el.classList.add("hidden");
      return;
    }
    el.classList.remove("hidden");
    el.className = `banner ${tone === "warn" ? "banner-warn" : "banner-ok"}`;
    el.textContent = text;
  }

  /**
   * 拉取全市场真实实时报价（去重并发）。无 mock — 失败则返回 blocked。
   */
  async function ensureLiveQuotesFresh(opts = {}) {
    const { force = false, silent = true, updateMarket = true } = opts;
    if (!force && !liveQuotesStale() && lastLiveRefreshMeta && !lastLiveRefreshMeta.blocked) {
      return { ok: true, cached: true, data: lastLiveRefreshMeta };
    }
    if (liveRefreshPromise) return liveRefreshPromise;
    liveRefreshPromise = (async () => {
      try {
        if (!silent) UI.toast("刷新实时行情", "正在获取全市场真实报价…", "ok");
        const res = await api.request("/api/v1/market/live-refresh", { method: "POST", timeoutMs: 300000 });
        const d = res.data || res.meta?.live_status || {};
        const rowCount = d.row_count || 0;
        const quotesReady = d.quotes_ready !== false && rowCount >= 100 && !d.blocked;
        lastLiveRefreshMeta = res.ok && quotesReady
          ? d
          : { ...d, blocked: true, reason: d.reason || res.error?.message || "实时行情未就绪" };
        if (res.ok && quotesReady) {
          lastLiveRefresh = d.retrieved_at || new Date().toISOString();
        }
        updateLiveQuotePill(lastLiveRefreshMeta);
        if (updateMarket) {
          const box = $("market-live");
          if (box && quotesReady) {
            box.innerHTML =
              `<div class="banner banner-ok">实时行情：${d.provider} · ${rowCount} 行 · ${d.freshness} · ${d.retrieved_at}${d.stale_fallback ? "（缓存回退）" : ""}</div>`;
            UI.renderTable(
              box.appendChild(document.createElement("div")),
              ["代码", "名称", "最新价", "涨跌幅%", "成交额"],
              (d.top_up || []).slice(0, 8).map((r) => [r.code, r.name, r.price, r.change_pct, r.amount]),
              "暂无实时涨幅榜",
            );
          } else if (box) {
            box.innerHTML = `<div class="banner banner-warn">实时行情不可证明：${lastLiveRefreshMeta.reason || "provider blocked"}</div>`;
          }
        }
        if (!silent && res.ok && quotesReady) {
          UI.toast("实时行情已更新", `${rowCount} 只 · ${d.provider || ""}`, "ok");
        }
        if (!silent && (!res.ok || !quotesReady)) {
          UI.toast("实时行情不可用", lastLiveRefreshMeta.reason || "provider blocked", "fail");
        }
        return { ...res, data: lastLiveRefreshMeta, quotesReady };
      } finally {
        liveRefreshPromise = null;
      }
    })();
    return liveRefreshPromise;
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
      return await ensureLiveQuotesFresh({ force: true, silent: false, updateMarket: true });
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
    if ($("pref-price-min")) $("pref-price-min").value = p.price_min_cny || 0;
    if ($("pref-price-max")) $("pref-price-max").value = p.price_max_cny ?? "";
    if ($("pref-price-ceiling")) $("pref-price-ceiling").checked = p.enforce_capital_price_ceiling !== false;
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
        price_min_cny: Number($("pref-price-min")?.value || 0),
        price_max_cny: $("pref-price-max")?.value ? Number($("pref-price-max").value) : null,
        enforce_capital_price_ceiling: !!$("pref-price-ceiling")?.checked,
      };
      const res = await api.request("/api/v1/user/preferences", { method: "PUT", body: JSON.stringify(body) });
      logAction("保存用户偏好", res);
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function runScreener(btn) {
    const mode = $("screener-mode")?.value || "eod";
    const liveLabel = mode === "live" ? "实时选股（约 1–2 分钟）…" : "计算中…";
    UI.setLoading(btn, true, liveLabel);
    try {
      const preset = $("screener-preset")?.value || "balanced";
      if (mode === "live") {
        $("screener-table")?.replaceChildren(
          UI.renderEmpty("实时智能选股", "后端正在刷新行情并计算因子，首次约需 1–2 分钟，请勿重复点击…", ""),
        );
      }
      const topN = $("screener-topn")?.value || "25";
      const minAmt = $("screener-minamt")?.value || "50000000";
      const capital = Number($("pref-capital")?.value || 5000);
      const priceMin = Number($("pref-price-min")?.value || 0);
      const priceMaxRaw = $("pref-price-max")?.value;
      const priceMax = priceMaxRaw ? Number(priceMaxRaw) : "";
      const priceCeiling = $("pref-price-ceiling")?.checked !== false;
      const sectors = encodeURIComponent($("pref-sectors")?.value || "");
      const excluded = encodeURIComponent($("pref-exclude-sectors")?.value || "");
      const priceQ =
        `&capital_cny=${capital}&price_min_cny=${priceMin}` +
        (priceMax !== "" ? `&price_max_cny=${priceMax}` : "") +
        `&enforce_capital_price_ceiling=${priceCeiling}`;
      const fastQ = "&fast=true";
      const res = await api.request(
        `/api/v1/screener/run?preset=${preset}&top_n=${topN}&min_amount_cny=${minAmt}&mode=${mode}&preferred_sectors=${sectors}&excluded_sectors=${excluded}${priceQ}${fastQ}`,
      );
      if (!res.ok) {
        const hint = window.QuantOSFriendlyError?.(res) || res.error?.message || "选股请求失败";
        UI.renderScreener($("screener-table"), { blocked: true, blockerReason: hint, rows: [] });
        UI.toast("选股失败", hint, "fail");
        logAction("智能选股", res);
        return res;
      }
      const vm = VM.fromScreener(res);
      lastScreenerVm = vm;
      UI.renderScreener($("screener-table"), vm);
      UI.renderSelectionGuide($("screener-guide"), vm);
      const meta = $("screener-meta");
      if (meta) {
        const df = vm.dataFreshness || {};
        const eodChip = df.expected_latest_completed
          ? `<span class="metric-chip">期望收盘 <b>${df.expected_latest_completed}</b></span>`
          : "";
        const staleChip = df.is_current === false
          ? `<span class="metric-chip warn">仓库 ${df.warehouse_max_trade_date || "—"} · ${df.user_hint || vm.dataStatusNote || "数据可能滞后"}</span>`
          : (df.sync_attempted && df.sync_ok
            ? `<span class="metric-chip">已同步至 <b>${df.warehouse_max_trade_date || vm.dataCutoff}</b></span>`
            : "");
        const liveNote = vm.mode === "live"
          ? (vm.liveStatus?.used
            ? `实时 · 匹配 ${vm.liveStatus.matched_in_universe ?? vm.rows.filter((r) => r.live_price != null).length}/${vm.universeSize} · ${vm.liveStatus.provider || vm.liveProvider || ""}`
            : `实时降级为收盘因子 · 截止 ${vm.dataCutoff}${vm.liveStatus?.hint ? " · " + vm.liveStatus.hint : ""}`)
          : `收盘因子 · 数据截止 ${vm.dataCutoff}`;
        const pf = vm.priceFilters || {};
        const priceChip =
          pf.effective_price_max_cny || pf.price_min_cny
            ? `<span class="metric-chip">股价 <b>¥${pf.price_min_cny || 0}–${pf.effective_price_max_cny ?? "∞"}</b></span>`
            : "";
        meta.innerHTML = vm.blocked
          ? ""
          : `<span class="metric-chip">截止 <b>${vm.dataCutoff}</b></span>` +
            `<span class="metric-chip">模型 <b>${vm.modelVersion}</b></span>` +
            `<span class="metric-chip">验证 <b>${vm.validationStatus}</b></span>` +
            `<span class="metric-chip">模式 <b>${vm.mode === "eod" ? "收盘·快速" : "实时"}</b></span>` +
            `<span class="metric-chip">资金参考 <b>¥${vm.capitalCny || capital}</b></span>` +
            priceChip +
            `<span class="metric-chip">候选池 <b>${vm.universeSize}</b> 只</span>` +
            `<span class="metric-chip">入选 <b>${vm.rows.length}</b> 只</span>` +
            eodChip +
            staleChip +
            `<span class="metric-chip">${liveNote}</span>` +
            (vm.agentOverlay?.framework ? `<span class="metric-chip">智能体 <b>${vm.agentOverlay.framework}</b> · ${vm.agentOverlay.risk_verdict || "—"}</span>` : "");
      }
      logAction("智能选股", res);
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

  function strategyParams() {
    return {
      preset: $("strategy-preset")?.value || $("screener-preset")?.value || "balanced",
      topN: $("strategy-topn")?.value || $("screener-topn")?.value || "25",
    };
  }

  function goStrategyTab() {
    document.querySelector('.tab[data-page="models"]')?.click();
  }

  async function loadLatestStrategyLearning(btn) {
    if (btn) UI.setLoading(btn, true, "加载中…");
    try {
      const res = await api.request("/api/v1/screener/learn/latest");
      if (res.ok && res.data?.status !== "NOT_RUN") {
        UI.renderStrategyLearning($("model-strategy-learning"), res.data);
        if (btn) goStrategyTab();
      } else if (btn) {
        UI.toast("暂无报告", "请先运行「完整自验证 + 智能体学习」", "warn");
      }
      return res;
    } finally {
      if (btn) UI.setLoading(btn, false);
    }
  }

  async function runScreenerLearn(btn) {
    UI.setLoading(btn, true, "自验证学习中…");
    try {
      const { preset, topN } = strategyParams();
      const res = await api.request(`/api/v1/screener/learn?preset=${preset}&top_n=${topN}`, { method: "POST", timeoutMs: 120000 });
      if (res.ok) {
        UI.renderStrategyLearning($("model-strategy-learning"), res.data);
        goStrategyTab();
        const agent = res.data?.agent_overlay || {};
        const rec = res.data?.recommended_preset;
        UI.toast(
          "策略自验证完成",
          `${agent.risk_verdict || "—"}${rec && rec !== preset ? ` · 建议预设: ${rec}` : ""}`,
          agent.risk_verdict === "PASS" ? "ok" : "warn",
        );
      } else {
        UI.toast("自验证失败", res.error?.message || "学习循环未完成", "fail");
      }
      logAction("策略自验证学习", res);
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function exportScreenerReportPdf(btn) {
    const sym = lastScreenerDetailSymbol || lastScreenerVm?.rows?.[0]?.symbol;
    if (!sym) {
      UI.toast("无法导出", "请先运行选股或打开个股分析", "fail");
      return;
    }
    UI.setLoading(btn, true, "生成 PDF…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const mode = $("screener-mode")?.value || "eod";
      const sectors = encodeURIComponent($("pref-sectors")?.value || "");
      const excluded = encodeURIComponent($("pref-exclude-sectors")?.value || "");
      const res = await api.request(
        `/api/v1/screener/report/${encodeURIComponent(sym)}?preset=${preset}&mode=${mode}&preferred_sectors=${sectors}&excluded_sectors=${excluded}`,
        { method: "POST", timeoutMs: 90000 },
      );
      if (res.ok && res.data?.download_url) {
        window.open(res.data.download_url, "_blank");
        UI.toast("PDF 已生成", `${sym} 选股分析报告`, "ok");
      } else {
        UI.toast("PDF 失败", res.error?.message || "渲染未完成", "fail");
      }
      logAction("导出选股 PDF", res);
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function runScreenerProof(btn) {
    UI.setLoading(btn, true, "验证中…");
    try {
      const { preset, topN } = strategyParams();
      const res = await api.request(`/api/v1/screener/proof?preset=${preset}&top_n=${topN}`);
      UI.renderStrategyLearning($("model-strategy-learning"), res.data || res);
      goStrategyTab();
      const d = res.data || {};
      UI.toast(
        d.verdict === "PASS" ? "T+1 验证通过" : "T+1 验证需复盘",
        d.blocked ? (d.blocker_reason || "无法验证") : `平均收益 ${d.avg_return}% / 市场中位数 ${d.benchmark_median}%`,
        d.verdict === "PASS" ? "ok" : "warn",
      );
      logAction("T+1 选股验证", res);
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  $("screener-mode")?.addEventListener("change", (ev) => {
    const hint = $("screener-dossier");
    const runBtn = document.querySelector('[data-action="screener-run"]');
    if (ev.target?.value === "live") {
      if (runBtn) runBtn.textContent = "运行实时智能选股";
      if (hint) {
        hint.textContent = "实时模式一键刷新并选股。点击表格任意行查看选股原因与评分。";
      }
    } else {
      if (runBtn) runBtn.textContent = "运行收盘选股（快速）";
      if (hint) hint.textContent = "收盘模式使用昨收价。点击表格任意行查看选股原因与评分明细。";
    }
  });

  async function loadAdvisoryCard(symbol) {
    const body = $("stock-detail-body");
    if (!body || !symbol) return;
    let slot = body.querySelector("#advisory-card-slot");
    if (!slot) {
      slot = document.createElement("div");
      slot.id = "advisory-card-slot";
      body.appendChild(slot);
    }
    slot.innerHTML = '<p class="muted small">正在加载 v2.3 可复现评分卡…</p>';
    try {
      const capital = Number($("pref-capital")?.value || 10000);
      const res = await api.request(
        `/api/v1/advisory/analyze?symbol=${encodeURIComponent(symbol)}&capital_cny=${capital}`,
        { timeoutMs: 45000 },
      );
      const card = res.data?.explain || res.data;
      if (res.ok) UI.renderAdvisoryCard(slot, card);
      else UI.renderAdvisoryCard(slot, { blocked: true, blocker_reason: res.error?.message });
    } catch (err) {
      UI.renderAdvisoryCard(slot, { blocked: true, blocker_reason: err?.message || "网络错误" });
    }
  }

  async function showStockDetail(symbol) {
    if (!symbol) return false;
    lastScreenerDetailSymbol = symbol;
    const body = $("stock-detail-body");
    const row = lastScreenerVm?.rows?.find((r) => r.symbol === symbol);
    UI.renderStockDetailModal(body, { row, loading: true });
    UI.openStockDetailModal();
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const mode = $("screener-mode")?.value || "live";
      const sectors = encodeURIComponent($("pref-sectors")?.value || "");
      const excluded = encodeURIComponent($("pref-exclude-sectors")?.value || "");
      const res = await api.request(
        `/api/v1/screener/dossier/${encodeURIComponent(symbol)}?preset=${preset}&mode=${mode}&preferred_sectors=${sectors}&excluded_sectors=${excluded}`,
        { timeoutMs: 45000 },
      );
      if (res.ok) {
        UI.renderStockDetailModal(body, { row, dossier: res.data, loading: false });
        loadAdvisoryCard(symbol);
        const hint = $("screener-dossier");
        if (hint) {
          hint.innerHTML = "";
          hint.appendChild(document.createTextNode(`已打开 ${res.data?.name || symbol} 分析报告弹窗`));
        }
        return true;
      }
      UI.renderStockDetailModal(body, {
        row,
        loading: false,
        blocked: !row,
        blocker_reason: res.error?.message || "无法加载完整报告",
      });
      return !!row;
    } catch (err) {
      UI.renderStockDetailModal(body, {
        row,
        loading: false,
        blocked: !row,
        blocker_reason: err?.message || "网络错误",
      });
      return !!row;
    }
  }

  async function runDossier(symbol, btn) {
    UI.setLoading(btn, true, "解释中…");
    try {
      const ok = await showStockDetail(symbol);
      if (ok) UI.toast("个股报告已生成", symbol, "ok");
      else UI.toast("报告加载失败", symbol, "fail");
      return { ok };
    } finally {
      UI.setLoading(btn, false);
    }
  }

  let stockSearchTimer = null;
  async function suggestStockSearch(query) {
    const q = (query || "").trim();
    const list = $("screener-search-suggestions");
    if (!list || q.length < 2) {
      if (list) list.innerHTML = "";
      return;
    }
    try {
      const res = await api.request(`/api/v1/screener/search?q=${encodeURIComponent(q)}&limit=8`);
      const matches = res.data?.matches || [];
      list.innerHTML = matches
        .map((m) => `<option value="${m.name ? m.name + " " : ""}${m.symbol}"></option>`)
        .join("");
    } catch {
      /* ignore autocomplete errors */
    }
  }

  async function runStockSearch(btn) {
    const query = ($("screener-stock-query")?.value || "").trim();
    if (!query) {
      UI.toast("请输入股票", "代码或名称均可", "fail");
      return { ok: false };
    }
    UI.setLoading(btn, true, "分析中…");
    const box = $("screener-search-results");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const mode = $("screener-mode")?.value || "eod";
      if (mode === "live") {
        UI.setLoading(btn, true, "刷新实时行情…");
        const lr = await ensureLiveQuotesFresh({ force: true, silent: true, updateMarket: false });
        if (!lr.ok || lr.data?.blocked) {
          UI.toast("无法分析", lr.data?.reason || lr.error?.message || "实时行情不可用", "fail");
          return { ok: false };
        }
      }
      let symbol = query;
      const capital = Number($("pref-capital")?.value || 5000);
      const sectors = encodeURIComponent($("pref-sectors")?.value || "");
      const excluded = encodeURIComponent($("pref-exclude-sectors")?.value || "");
      const suggest = await api.request(`/api/v1/screener/search?q=${encodeURIComponent(query)}&limit=5`);
      const matches = suggest.data?.matches || [];
      if (matches.length === 1) {
        symbol = matches[0].symbol;
      } else if (matches.length > 1 && !/^\d{6}/.test(query)) {
        symbol = matches[0].symbol;
      }
      const res = await api.request(
        `/api/v1/screener/analyze/${encodeURIComponent(symbol)}?preset=${preset}&mode=${mode}&capital_cny=${capital}&preferred_sectors=${sectors}&excluded_sectors=${excluded}`,
        { timeoutMs: 45000 },
      );
      if (!res.ok) {
        UI.renderStockAnalysis(box, { blocked: true, blocker_reason: res.error?.message || "未找到该股票" });
        UI.toast("搜索失败", res.error?.message || query, "fail");
        return res;
      }
      UI.renderStockAnalysis(box, res.data);
      const modalBody = $("stock-detail-body");
      UI.renderStockDetailModal(modalBody, { dossier: res.data, row: res.data?.candidate || res.data, loading: false });
      UI.openStockDetailModal();
      loadAdvisoryCard(res.data?.symbol || symbol);
      const hint = $("screener-dossier");
      if (hint) {
        hint.innerHTML = "";
        hint.appendChild(document.createTextNode(`已打开 ${res.data?.name || symbol} 分析报告弹窗`));
      }
      logAction("搜索股票", res);
      UI.toast("分析完成", res.data?.name || symbol, "ok");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  $("screener-stock-query")?.addEventListener("input", (ev) => {
    clearTimeout(stockSearchTimer);
    stockSearchTimer = setTimeout(() => suggestStockSearch(ev.target?.value), 280);
  });
  $("screener-stock-query")?.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") {
      ev.preventDefault();
      document.querySelector('[data-action="screener-stock-search"]')?.click();
    }
  });

  async function paperFromScreener(btn) {
    UI.setLoading(btn, true, "生成组合…");
    try {
      const mode = $("screener-mode")?.value || "live";
      if (mode === "live") {
        UI.setLoading(btn, true, "刷新实时行情…");
        const lr = await ensureLiveQuotesFresh({ force: true, silent: true, updateMarket: false });
        if (!lr.ok || lr.data?.blocked) {
          UI.toast("导入失败", lr.data?.reason || "实时行情不可用", "fail");
          return lr;
        }
      }
      const preset = $("screener-preset")?.value || "balanced";
      const topN = $("screener-topn")?.value || "25";
      const maxPositions = Number($("pref-positions")?.value || 5);
      const res = await api.request("/api/v1/paper/from-screener", {
        method: "POST",
        body: JSON.stringify({
          preset,
          top_n: Number(topN),
          max_positions: maxPositions,
          capital_fraction: 0.8,
          mode: $("screener-mode")?.value || "live",
        }),
      });
      logAction("选股加入 Paper", res);
      if (res.ok) {
        UI.toast("已加入 Paper 模拟组合", `生成 ${res.data?.orders?.length || 0} 张模拟订单`, "ok");
        document.querySelector('.tab[data-page="paper"]')?.click();
        paperAutoLiveEnabled = true;
        startPaperMonitorLoop();
      } else if (res.error?.code === "PAPER_NOT_STARTED") {
        UI.toast("请先启动 Paper", "点击「启动 Paper」后再加入模拟组合", "fail");
      }
      await refreshPaper();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function executeAllocation(btn) {
    const unattended = !!$("gate-unattended")?.checked;
    const msg = unattended
      ? "将运行 ensemble 选股 → 组合优化 → 无人值守实盘执行。\n需已配置 Sidecar/Playwright 门控。"
      : "将运行 ensemble 选股 → 组合优化 → 人工确认实盘下单。";
    if (!confirm(msg)) return;
    UI.setLoading(btn, true, "执行组合…");
    try {
      const preset = $("screener-preset")?.value || "balanced";
      const topN = Number($("screener-topn")?.value || 25);
      const mode = $("screener-mode")?.value || "live";
      if (mode === "live") {
        UI.setLoading(btn, true, "刷新实时行情…");
        const lr = await ensureLiveQuotesFresh({ force: true, silent: true, updateMarket: false });
        if (!lr.ok || lr.data?.blocked) {
          UI.toast("执行被拦截", lr.data?.reason || "实时行情不可用", "fail");
          return lr;
        }
        UI.setLoading(btn, true, "执行组合…");
      }
      const res = await api.request("/api/v1/trading/execute-allocation", {
        method: "POST",
        body: JSON.stringify({ preset, top_n: topN, mode, unattended, allow_drift_override: true }),
      });
      logAction(unattended ? "无人值守执行组合" : "执行组合", res);
      const n = (res.data?.results || []).filter((r) => r.ok).length;
      UI.toast(
        res.ok ? "组合执行完成" : "组合执行被拦截",
        res.ok ? `成功 ${n} 笔` : (res.error?.message || res.data?.blockers?.join("; ") || ""),
        res.ok ? "ok" : "fail",
      );
      await refreshBrokerPanel();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function autopilotExecuteTicket(btn) {
    const ticketId = btn.dataset.ticketId || lastAutopilotTicket?.ticket_id;
    if (!ticketId) {
      UI.toast("无票据", "请先生成订单票据", "fail");
      return;
    }
    if (!confirm(`无人值守执行票据 ${ticketId}？`)) return;
    UI.setLoading(btn, true, "执行票据…");
    try {
      const res = await api.request("/api/v1/autopilot/execute-ticket", {
        method: "POST",
        body: JSON.stringify({ ticket_id: ticketId, unattended: true }),
      });
      logAction("执行订单票据", res);
      UI.toast(res.ok ? "票据已执行" : "执行失败", res.error?.message || "", res.ok ? "ok" : "fail");
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
      const msg = res.data?.ready_for_unattended_auto
        ? "无人值守实盘已就绪"
        : res.data?.ready_for_order_ticket
          ? "可生成订单票据"
          : "仍有阻塞项";
      const level = res.data?.ready_for_unattended_auto || res.data?.ready_for_order_ticket ? "ok" : "fail";
      UI.toast("Autopilot 准入检查完成", msg, level);
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
      lastAutopilotTicket = res.data;
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

  async function runBacktestWithCurves(btn) {
    UI.setLoading(btn, true, "回测中（约 10–15 分钟）…");
    const box = $("backtest-result");
    if (box) box.replaceChildren(UI.renderEmpty("组合回测", "逐日运行历史信号并模拟 T+1 组合，请耐心等待…", ""));
    try {
      const body = {
        engine: "screener_portfolio",
        preset: $("strategy-preset")?.value || "balanced",
        lookback_days: Number($("backtest-lookback")?.value || 40),
        top_n: Number($("backtest-topn")?.value || 5),
      };
      const res = await api.request("/api/v1/research/backtest", {
        method: "POST",
        body: JSON.stringify(body),
        timeoutMs: 1200000,
      });
      if (box) UI.renderBacktestReport(box, res.data || {});
      const st = res.data?.status || "完成";
      UI.toast("回测完成", st, st === "OK" ? "ok" : "fail");
      return res;
    } catch (e) {
      if (box) box.replaceChildren(UI.renderEmpty("回测失败", String(e?.message || e), ""));
      throw e;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function runAgentsAnalyze(btn) {
    const symbol = ($("agents-symbol")?.value || "").trim();
    if (!symbol) {
      UI.toast("请输入股票代码", "如 600000.SH / 000001.SZ", "fail");
      return;
    }
    UI.setLoading(btn, true, "9 个智能体分析中…");
    const box = $("agents-analyze-result");
    try {
      const res = await api.request(
        `/api/v1/agents/analyze?symbol=${encodeURIComponent(symbol)}`,
        { timeoutMs: 300000 },
      );
      if (box) UI.renderAgentsAnalysis(box, res.data || {});
      const grade = res.data?.final?.rating || "?";
      UI.toast("研究完成", `评级 ${grade}`, grade === "BLOCKED" ? "fail" : "ok");
      return res;
    } catch (e) {
      if (box) box.replaceChildren(UI.renderEmpty("分析失败", String(e?.message || e), ""));
      throw e;
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
    await refreshPaperPanels();
  }

  async function refreshPaperMonitor() {
    try {
      const res = await api.request("/api/v1/paper/monitor");
      UI.renderPaperMonitor($("paper-monitor"), res);
    } catch {
      /* ignore */
    }
  }

  async function refreshPaperReports() {
    try {
      const res = await api.request("/api/v1/paper/reports");
      const box = $("paper-reports");
      if (!box) return;
      box.innerHTML = "";
      const reports = res.data?.reports || [];
      if (!reports.length) {
        box.appendChild(UI.renderEmpty("暂无收盘报告", "点击「生成今日收盘报告」", ""));
        return;
      }
      reports.slice(0, 10).forEach((r) => {
        const row = document.createElement("div");
        row.className = "paper-report-row";
        const a = document.createElement("a");
        a.href = `${api.base}${r.download_url}`;
        a.target = "_blank";
        a.rel = "noopener";
        a.textContent = `${r.trade_date} · ${r.label || "Paper 日报"} · 下载 PDF`;
        row.appendChild(a);
        box.appendChild(row);
      });
    } catch {
      /* ignore */
    }
  }

  async function paperLiveCycle(silent) {
    if (paperLiveCycleRunning) return;
    paperLiveCycleRunning = true;
    try {
      setPaperLiveBanner("正在刷新真实行情并更新 Paper 市值…", "ok");
      const lr = await ensureLiveQuotesFresh({ force: true, silent: true, updateMarket: false });
      if (!lr.ok || lr.data?.blocked) {
        setPaperLiveBanner(`实时行情不可用：${lr.data?.reason || lr.error?.message || "请稍后重试"}`, "warn");
        return lr;
      }
      await api.request("/api/v1/paper/mark-to-market", { method: "POST", timeoutMs: 60000 });
      const res = await api.request("/api/v1/paper/monitor/tick", { method: "POST", timeoutMs: 120000 });
      UI.renderPaperMonitor($("paper-monitor"), res.ok ? res : { data: res.data || res });
      await refreshPaperPanels();
      const qm = res.data?.quote_meta || {};
      const next = new Date(Date.now() + PAPER_AUTO_LIVE_MS).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
      setPaperLiveBanner(
        `真实行情 ${lr.data?.row_count || qm.quote_count || 0} 只 · ${lr.data?.retrieved_at || qm.retrieved_at || ""} · 下次自动刷新 ${next}`,
        res.ok ? "ok" : "warn",
      );
      if (!silent && !res.ok) {
        UI.toast("监控被阻断", res.error?.message || res.data?.reason || "无真实报价", "fail");
      }
      return res;
    } finally {
      paperLiveCycleRunning = false;
    }
  }

  /** 刷新 Paper 面板（不重启定时器） */
  async function refreshPaperPanels() {
    const [account, pos, orders, fills, status] = await Promise.all([
      api.request("/api/v1/paper/account").catch(() => ({ data: {} })),
      api.request("/api/v1/paper/positions"),
      api.request("/api/v1/paper/orders"),
      api.request("/api/v1/paper/fills"),
      api.request("/api/v1/system/status").catch(() => ({ data: {} })),
    ]);
    const p = VM.fromPaper(account, pos, orders, fills);
    const banner = $("paper-status-banner");
    if (banner) {
      const running = status.data?.mode === "PAPER_TRADING";
      banner.className = running ? "banner banner-ok" : "banner banner-warn";
      banner.textContent = running
        ? "Paper 运行中 — 真实行情自动刷新（15 分钟）"
        : "Paper 未启动 — 点击「启动 Paper」后开始虚拟交易";
    }
    UI.renderKeyValues($("paper-pnl"), [
      ["初始资金", p.summary.initialCapital],
      ["现金", p.summary.cash],
      ["权益", p.summary.equity],
      ["总盈亏", p.summary.totalPnl],
      ["浮动盈亏", p.summary.unrealized],
      ["持仓数", p.summary.openPositions],
    ]);
    UI.renderTable(
      $("paper-positions"),
      ["代码", "数量", "T+1可卖", "成本", "市值", "浮动盈亏"],
      p.positions,
      "暂无持仓",
    );
    UI.renderTable($("paper-fills"), ["成交号", "代码", "方向", "数量", "价格", "费用"], p.fills, "暂无成交");
    UI.renderTable($("paper-orders"), ["订单号", "代码", "方向", "状态", "成交量", "成交价"], p.orders, "暂无订单");
    await refreshPaperMonitor();
    await refreshPaperReports();
  }

  function startGlobalIntradayLoop() {
    if (globalIntradayTimer) return;
    const tick = async () => {
      try {
        const st = await api.request("/api/v1/system/status");
        const session = String(st.data?.market_session || "").toLowerCase();
        const bg = st.data?.intraday_refresh || {};
        const marketOpen = bg.market_open || session.includes("open");
        if (!marketOpen) return;
        await ensureLiveQuotesFresh({ force: liveQuotesStale(), silent: true, updateMarket: false });
      } catch {
        /* gateway offline — skip */
      }
    };
    tick();
    globalIntradayTimer = setInterval(tick, INTRADAY_QUOTE_MS);
  }

  function startPaperMonitorLoop() {
    stopPaperMonitorLoop();
    if (!paperAutoLiveEnabled) return;
    paperLiveCycle(false);
    paperLiveTimer = setInterval(() => {
      if (paperAutoLiveEnabled) paperLiveCycle(true);
    }, PAPER_AUTO_LIVE_MS);
  }

  function stopPaperMonitorLoop() {
    if (paperLiveTimer) {
      clearInterval(paperLiveTimer);
      paperLiveTimer = null;
    }
    if (paperMonitorTimer) {
      clearInterval(paperMonitorTimer);
      paperMonitorTimer = null;
    }
    setPaperLiveBanner("");
  }

  async function paperMonitorTick(btn, silent) {
    if (btn) UI.setLoading(btn, true, "监控中…");
    try {
      await ensureLiveQuotesFresh({ force: true, silent: !!silent, updateMarket: false });
      const res = await api.request("/api/v1/paper/monitor/tick", { method: "POST", timeoutMs: 120000 });
      if (!silent) logAction("Paper 实时监控", res);
      UI.renderPaperMonitor($("paper-monitor"), res.ok ? res : { data: res.data || res });
      if (!silent) {
        UI.toast(
          res.ok ? "监控完成" : "监控被阻断",
          res.ok ? `${(res.data?.actions || []).length} 条动作` : (res.error?.message || "请先刷新实时行情"),
          res.ok ? "ok" : "fail",
        );
      }
      if (res.ok) await refreshPaperPanels();
      return res;
    } finally {
      if (btn) UI.setLoading(btn, false);
    }
  }

  async function paperMonitorStop(btn) {
    UI.setLoading(btn, true, "停止…");
    try {
      paperAutoLiveEnabled = false;
      stopPaperMonitorLoop();
      await api.request("/api/v1/paper/monitor/stop", { method: "POST" });
      await refreshPaperMonitor();
      setPaperLiveBanner("已停止 15 分钟自动监控", "warn");
      UI.toast("已停止自动监控", "重新进入「模拟练习」页可恢复 15 分钟轮询", "ok");
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function paperGenerateCloseReport(btn) {
    UI.setLoading(btn, true, "生成 PDF…");
    try {
      const res = await api.request("/api/v1/paper/reports/generate-close", { method: "POST", timeoutMs: 120000 });
      logAction("Paper 收盘报告", res);
      await refreshPaperReports();
      if (res.data?.download_url) {
        window.open(`${api.base}${res.data.download_url}`, "_blank");
      }
      UI.toast(res.ok ? "收盘报告已生成" : "生成失败", res.error?.message || "", res.ok ? "ok" : "fail");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function paperMarkToMarket(btn) {
    UI.setLoading(btn, true, "刷新市值…");
    try {
      await ensureLiveQuotesFresh({ force: true, silent: false, updateMarket: false });
      const res = await api.request("/api/v1/paper/mark-to-market", { method: "POST" });
      logAction("Paper 按市价刷新", res);
      UI.toast(res.ok ? "市值已更新" : "刷新失败", res.error?.message || `${res.data?.live_prices || 0} 只实时价`, res.ok ? "ok" : "fail");
      await refreshPaper();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function paperSubmitOrder(btn) {
    const symbol = $("paper-symbol")?.value?.trim();
    if (!symbol) {
      UI.toast("缺少代码", "请输入股票代码", "fail");
      return;
    }
    UI.setLoading(btn, true, "提交中…");
    try {
      const limitRaw = Number($("paper-price")?.value || 0);
      if (limitRaw <= 0) {
        await ensureLiveQuotesFresh({ force: liveQuotesStale(), silent: true, updateMarket: false });
      }
      const res = await api.request("/api/v1/paper/order", {
        method: "POST",
        body: JSON.stringify({
          symbol,
          side: $("paper-side")?.value || "BUY",
          quantity: Number($("paper-qty")?.value || 100),
          limit_price: Number($("paper-price")?.value || 0),
        }),
      });
      logAction("Paper 模拟下单", res);
      UI.toast(
        res.ok ? "订单已提交" : "下单失败",
        res.ok ? `${res.data?.order?.symbol} ${res.data?.order?.state}` : (res.error?.message || ""),
        res.ok ? "ok" : "fail",
      );
      if (res.ok) await refreshPaper();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
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

  function selectedBrokerId() {
    return $("broker-profile")?.value || "eastmoney_manual";
  }

  function openBrokerLoginWindow(urlOrPath) {
    if (!urlOrPath) return false;
    if (urlOrPath.includes("/brokers/login-redirect/")) {
      return false;
    }
    const target = urlOrPath.startsWith("http")
      ? urlOrPath
      : `${api.base}${urlOrPath}`;
    window.open(target, "_blank", "noopener,noreferrer");
    return true;
  }

  function preferredBrokerLoginUrl(brokerId) {
    const b = (cachedBrokerEcosystem?.brokers || []).find((x) => x.broker_id === brokerId);
    const fallbacks = b?.fallback_urls || [];
    if (fallbacks.length) return fallbacks[0].url;
    if (!b?.urls) return "";
    return b.urls.portal || b.urls.trade_login || b.urls.trade_login_alt || "";
  }

  function brokerLoginUrlFromCache(brokerId) {
    const b = (cachedBrokerEcosystem?.brokers || []).find((x) => x.broker_id === brokerId);
    if (!b?.urls) return "";
    return b.urls.trade_login || b.urls.trade_login_alt || b.urls.portal || "";
  }

  async function loadBrokerEcosystem() {
    const res = await api.request("/api/v1/brokers/ecosystem");
    if (res.ok) cachedBrokerEcosystem = res.data;
    const sel = $("broker-profile");
    if (!sel || !res.ok) return;
    const cfg = await api.request("/api/v1/brokers/config");
    const active = cfg.data?.active_broker || "eastmoney_manual";
    sel.innerHTML = "";
    (res.data?.brokers || []).forEach((b) => {
      const opt = document.createElement("option");
      opt.value = b.broker_id;
      opt.textContent = `${b.label}${b.browser_capable ? "" : " (API/模拟)"}`;
      if (b.broker_id === active) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.onchange = async () => {
      await api.request("/api/v1/brokers/config", {
        method: "PUT",
        body: JSON.stringify({ active_broker: sel.value, readonly: false }),
      });
      UI.renderBrokerOfficialLinks($("broker-official-links"), sel.value, cachedBrokerEcosystem);
      await refreshBrokerPanel();
    };
    UI.renderBrokerOfficialLinks($("broker-official-links"), active, cachedBrokerEcosystem);
  }

  async function brokerConnect(btn) {
    UI.setLoading(btn, true, "连接中…");
    try {
      const bid = selectedBrokerId();
      const openUrl = preferredBrokerLoginUrl(bid);
      if (openUrl) openBrokerLoginWindow(openUrl);
      const res = await api.request("/api/v1/brokers/connect-flow", {
        method: "POST",
        body: JSON.stringify({
          broker_id: bid,
          open_login: false,
          assist_login: false,
          sync_watchlist: false,
        }),
      });
      const d = res.data || {};
      if (!openUrl && d.open_url_preferred) openBrokerLoginWindow(d.open_url_preferred);
      logAction("券商连接", res);
      const waf = d.waf_recovery;
      if (waf?.fallback_urls?.length) {
        UI.renderWafRecovery($("broker-waf-recovery"), waf);
      }
      const hint = res.ok
        ? (d.message || "已在浏览器打开官方首页 — 请在官网/App 内登录")
        : (window.QuantOSFriendlyError?.(res) || d.message || "");
      UI.toast(
        res.ok ? "请完成官方登录" : "连接失败",
        waf?.symptom ? `${waf.symptom}：优先用「官网首页」或 App` : hint,
        res.ok ? "ok" : "fail",
      );
      await refreshBrokerPanel();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function brokerLogin(btn) {
    if (!confirm("「保存登录会话」会打开自动化浏览器，部分券商会显示 Nginx forbidden。\n建议改用上方「官网首页」或 App 登录。\n仍要继续吗？")) {
      return;
    }
    UI.setLoading(btn, true, "等待登录…");
    try {
      const bid = selectedBrokerId();
      const direct = brokerLoginUrlFromCache(bid);
      if (direct) openBrokerLoginWindow(direct);
      const res = await api.request("/api/v1/brokers/login-assist", {
        method: "POST",
        body: JSON.stringify({ broker_id: bid, wait_seconds: 120, force: false }),
      });
      const d = res.data || {};
      if (d.url && d.mode === "manual_browser_only") openBrokerLoginWindow(d.url);
      logAction("保存登录会话", res);
      if (d.waf_blocked && d.waf_recovery) {
        UI.renderWafRecovery($("broker-waf-recovery"), d.waf_recovery);
      }
      UI.toast(
        d.waf_blocked ? "WAF 拦截" : d.logged_in_detected ? "登录成功" : "请完成浏览器登录",
        d.waf_blocked
          ? (d.message || "请用官网/App")
          : d.logged_in_detected
            ? "会话已保存，可预填订单"
            : (window.QuantOSFriendlyError?.(res) || d.message || "在弹出窗口完成登录"),
        d.waf_blocked ? "fail" : d.logged_in_detected ? "ok" : "warn",
      );
      await refreshBrokerPanel();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function brokerSyncWatchlist(btn) {
    UI.setLoading(btn, true, "同步中…");
    try {
      const res = await api.request("/api/v1/watchlist/sync", { method: "POST" });
      UI.toast(res.ok ? "自选同步" : "同步失败", res.data?.message || "", res.ok ? "ok" : "fail");
      await refreshBrokerPanel();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function brokerExportFills(btn) {
    UI.setLoading(btn, true, "抓取成交…");
    try {
      const res = await api.request("/api/v1/brokers/export-fills", { method: "POST" });
      UI.toast(res.ok ? "成交已导入" : "抓取失败", res.data?.message || "", res.ok ? "ok" : "fail");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function brokerSaveConfig(btn) {
    UI.setLoading(btn, true, "保存中…");
    try {
      const res = await api.request("/api/v1/brokers/config", {
        method: "PUT",
        body: JSON.stringify({
          active_broker: selectedBrokerId(),
          account_id: $("broker-account-id")?.value || "",
          sidecar_url: $("broker-sidecar-url")?.value || "",
          auto_trade_via_sidecar: !!($("broker-sidecar-url")?.value),
          readonly: false,
        }),
      });
      UI.toast(res.ok ? "配置已保存" : "保存失败", "", res.ok ? "ok" : "fail");
      await refreshBrokerPanel();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function brokerTestPaths(btn) {
    UI.setLoading(btn, true, "检测中…");
    try {
      const res = await api.request("/api/v1/brokers/execution-paths");
      UI.renderExecutionPaths($("broker-execution-paths"), res.data);
      UI.toast("路径检测完成", `${(res.data?.paths || []).filter((p) => p.available).length} 条可用`, "ok");
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function brokerSaveGates(btn) {
    UI.setLoading(btn, true, "保存中…");
    try {
      if ($("gate-local-consent")?.checked) {
        await api.request("/api/v1/brokers/local-consent", {
          method: "POST",
          body: JSON.stringify({ granted: true }),
        });
      }
      const res = await api.request("/api/v1/live-trading/gates", {
        method: "PUT",
        body: JSON.stringify({
          execution_level: $("gate-unattended")?.checked ? 3 : 2,
          real_money_enabled: !!$("gate-real-money")?.checked,
          user_confirmed_risk: !!$("gate-user-risk")?.checked,
          legal_review_passed: !!$("gate-legal")?.checked,
          unattended_auto_enabled: !!$("gate-unattended")?.checked,
          browser_auto_submit: !!$("gate-browser-auto")?.checked,
        }),
      });
      UI.toast(res.ok ? "门控已保存" : "保存失败", res.ok ? (res.data?.unattended_auto_enabled ? "无人值守已启用" : "人工确认模式") : (window.QuantOSFriendlyError?.(res) || res.error?.message || ""), res.ok ? "ok" : "fail");
      await refreshBrokerPanel();
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function addToWatchlist(symbol, name) {
    const res = await api.request("/api/v1/watchlist", {
      method: "POST",
      body: JSON.stringify({ symbol, name }),
    });
    UI.toast(res.ok ? "已收藏" : "收藏失败", `${symbol} ${name}`, res.ok ? "ok" : "fail");
    await refreshBrokerPanel();
    return res;
  }

  async function submitLiveOrder(btn) {
    const symbol = btn.dataset.liveOrder;
    const name = btn.dataset.liveName || "";
    const qty = Number(btn.dataset.liveQty || 100);
    const price = Number(btn.dataset.livePrice || 0);
    if (!symbol || !price) {
      UI.toast("无法下单", "缺少价格或代码", "fail");
      return;
    }
    const unattended = !!$("gate-unattended")?.checked;
    const msg = unattended
      ? `无人值守自动执行？\n${name || symbol}\n${qty}股 @ ¥${price}\n\n将按 Sidecar → Playwright → CSV 顺序尝试。`
      : `确认向券商提交真实买入委托？\n${name || symbol}\n${qty}股 @ ¥${price}\n\n最后一步仍需在券商页面点击确认。`;
    if (!confirm(msg)) return;
    UI.setLoading(btn, true, "提交中…");
    try {
      const endpoint = unattended ? "/api/v1/brokers/execute-auto" : "/api/v1/brokers/live-order";
      const res = await api.request(endpoint, {
        method: "POST",
        body: JSON.stringify({
          symbol,
          name,
          side: "BUY",
          quantity: qty,
          limit_price: price,
          user_confirmed: true,
          unattended,
        }),
      });
      const d = res.data || {};
      const url = d.handoff?.web_url || d.handoff?.client_url;
      if (url && !unattended) window.open(url, "_blank", "noopener,noreferrer");
      const pathHint = d.winning_path ? `路径: ${d.winning_path}` : "";
      UI.toast(
        res.ok ? (unattended ? "无人值守已执行" : "订单已推送券商") : "下单被拦截",
        [d.message || res.error?.message || d.user_action || "", pathHint].filter(Boolean).join(" · "),
        res.ok ? "ok" : "fail",
      );
      return res;
    } finally {
      UI.setLoading(btn, false);
    }
  }

  async function refreshBrokerPanel() {
    const [session, gates, watchlist, cfg] = await Promise.all([
      api.request("/api/v1/brokers/session"),
      api.request("/api/v1/live-trading/gates"),
      api.request("/api/v1/watchlist"),
      api.request("/api/v1/brokers/config"),
    ]);
    if ($("broker-sidecar-url") && cfg.data?.sidecar_url) $("broker-sidecar-url").value = cfg.data.sidecar_url;
    if ($("broker-account-id") && cfg.data?.account_id) $("broker-account-id").value = cfg.data.account_id;
    UI.renderBrokerSession($("broker-session-status"), session?.data);
    UI.renderWatchlist($("broker-watchlist"), watchlist?.data?.items || []);
    UI.renderExecutionPaths($("broker-execution-paths"), { paths: session?.data?.execution_paths || [] });
    const g = gates?.data || {};
    if ($("gate-real-money")) $("gate-real-money").checked = !!g.real_money_enabled;
    if ($("gate-user-risk")) $("gate-user-risk").checked = !!g.user_confirmed_risk;
    if ($("gate-legal")) $("gate-legal").checked = !!g.legal_review_passed;
    if ($("gate-unattended")) $("gate-unattended").checked = !!g.unattended_auto_enabled;
    if ($("gate-browser-auto")) $("gate-browser-auto").checked = !!g.browser_auto_submit;
    const mode = $("broker-execution-mode");
    if (mode) {
      mode.textContent = g.unattended_auto_enabled
        ? "执行模式: CONDITIONAL_AUTO · Mac 无人值守已启用（Sidecar 优先）"
        : g.real_money_enabled
          ? "执行模式: MANUAL_CONFIRM_ON_BROKER · 真实通道已开"
          : "执行模式: DRAFT_ONLY · 请配置门控";
    }
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
    void refreshBrokerPanel();
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
    const models = registry?.models || registry?.data?.models || (Array.isArray(registry) ? registry : []);
    const rows = (Array.isArray(models) ? models : []).map((m) => [
      m.id || m.model_id || m.name || "—",
      m.status || "—",
      m.native ? "原生" : "兼容",
      m.dsr ?? m.sharpe ?? "—",
    ]);
    UI.renderTable($("model-registry"), ["模型", "状态", "引擎", "DSR/Sharpe"], rows, "模型注册表为空 — 运行基线或回测");
  }

  async function refreshFooterVersion() {
    const ver = await api.request("/api/v1/system/version", { skipAuth: true });
    const fv = $("footer-version");
    const fbw = $("footer-build-warn");
    if (!ver.ok || !fv) return;
    const d = ver.data || {};
    const pageBuild = document.body.dataset.portalBuild || "";
    const mismatch = !!(pageBuild && d.portal_build_id && pageBuild !== d.portal_build_id);
    fv.textContent = `Backend ${d.git_commit_short || "—"} · PID ${d.process_id ?? "—"}`;
    if (fbw) fbw.classList.toggle("hidden", !mismatch);
  }

  async function refresh() {
    if (!api.apiKey) return;
    const up = await pingGateway();
    showGatewayBanner(
      up,
      `无法连接 Gateway（${api.base}）— 请在终端运行：make app  或  bash scripts/start-portal.sh`,
    );
    if (!up) {
      UI.renderEmpty($("overview-cards"), "Gateway 未连接", "所有功能需要本机 Gateway", "终端执行 make app 后刷新页面");
      return;
    }
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
      await refreshPaper();
      await loadPreferences();
      await refreshMarket();
      await refreshSetupCenter();

      UI.renderReportSummary($("report-detail"), VM.fromSystemStatus(st?.data)?.latestReport);
      const list = $("report-list");
      if (list) {
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
      }

      if (lastAgentRun) UI.renderAgentPanel($("agents-body"), VM.fromAgentsRun(lastAgentRun));
    } catch (err) {
      UI.renderEmpty($("overview-cards"), "加载失败", err.message, "检查 Gateway 是否在 8787 运行");
    }
  }

  async function showApp() {
    $("login-overlay")?.classList.add("hidden");
    if (!localStorage.getItem("quantos_legal_ack")) {
      $("legal-overlay")?.classList.remove("hidden");
    }
    try {
      await loadBrokerEcosystem();
      await refreshFooterVersion();
      await refresh();
      refreshHelpPage();
      await checkBuildSync();
      await safeSection("overview-live", refreshOverviewLive);
      ensureLiveQuotesFresh({ force: false, silent: true, updateMarket: false }).catch(() => {});
      startGlobalIntradayLoop();
      if (!window.__quantosRefreshTimer) {
        window.__quantosRefreshTimer = setInterval(refresh, 30000);
        window.__quantosLiveTimer = setInterval(refreshOverviewLive, 15000);
      }
    } catch (err) {
      showGatewayBanner(false, err.message || "门户初始化失败");
      UI.renderEmpty($("overview-cards"), "门户加载失败", err.message, "请确认 Gateway 已启动后刷新");
    }
  }

  async function enterPlatform() {
    try {
      await api.login("admin");
      await showApp();
      $("login-error")?.classList.add("hidden");
    } catch (e) {
      $("login-overlay")?.classList.remove("hidden");
      const err = $("login-error");
      if (err) {
        err.textContent = e.message;
        err.classList.remove("hidden");
      }
    }
  }

  $("btn-login")?.addEventListener("click", () => enterPlatform());

  $("btn-legal-accept")?.addEventListener("click", () => {
    localStorage.setItem("quantos_legal_ack", "1");
    $("legal-overlay")?.classList.add("hidden");
  });

  $("btn-logout")?.addEventListener("click", () => {
    api.clearSession();
    location.reload();
  });

  enterPlatform();

  window.QuantOSPortal = { refresh, logAction, ACTIONS };
})();
