/** QuantOS CN — API → Chinese ViewModels (no raw JSON in primary views). */
(function (global) {
  const MODE_LABELS = {
    RESEARCH_ONLY: "仅研究",
    PAPER_TRADING: "模拟交易",
    SHADOW_LIVE: "影子实盘",
    HALTED: "已停机",
  };

  const SESSION_LABELS = {
    pre_market: "盘前",
    market_hours: "交易中",
    post_close: "收盘后",
    closed: "休市",
  };

  function fmtCny(n) {
    if (n == null || Number.isNaN(Number(n))) return "—";
    return `¥${Number(n).toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
  }

  function fmtTime(iso) {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("zh-CN");
    } catch {
      return String(iso);
    }
  }

  /** Canonical native label — single source for header + body. */
  function mapVnpyLabel(nativeStatus, quantosStatus) {
    const iso = nativeStatus?.vnpy?.isolated_venv || {};
    const isolated = iso.mode === "NATIVE" || iso.state === "INSTALLED";
    const running = !!(quantosStatus?.vnpy_runtime?.running || quantosStatus?.vnpy_runtime?.persisted);
    if (isolated && running) return { short: "原生·运行中", long: "原生 vn.py：运行中", tone: "ok" };
    if (isolated) return { short: "原生·未启动", long: "原生 vn.py：已安装，未启动", tone: "warn" };
    return { short: "兼容模式", long: "vn.py：兼容模式", tone: "muted" };
  }

  function mapQlibLabel(nativeStatus, qlibHealth) {
    const iso = nativeStatus?.qlib?.isolated_venv || {};
    const isolated = iso.mode === "NATIVE" || iso.state === "INSTALLED";
    const providerNative = qlibHealth?.native_qlib || qlibHealth?.mode === "native";
    if (isolated || providerNative) return { short: "原生就绪", long: "Qlib：原生就绪", tone: "ok" };
    return { short: "兼容模式", long: "Qlib：兼容模式", tone: "muted" };
  }

  function fromSystemStatus(data, nativeStatus, quantosStatus) {
    if (!data) return null;
    const vn = mapVnpyLabel(nativeStatus, quantosStatus);
    const ql = mapQlibLabel(nativeStatus, data.qlib);
    const blockers = (data.blockers || []).map((b) =>
      typeof b === "string" ? { code: b, message: b } : b
    );
    return {
      modeLabel: MODE_LABELS[data.mode] || data.mode || "—",
      sessionLabel: SESSION_LABELS[data.market_session] || data.market_session || "—",
      dataStatusLabel: data.data_status || "—",
      capitalCny: data.capital,
      equityCny: data.equity_cny,
      remainingLossBudgetCny: data.remaining_loss_budget,
      killSwitchLabel: data.halted || data.kill_switch === "HALTED" ? "已触发" : "正常",
      vnpyLabel: vn.long,
      qlibLabel: ql.long,
      vnpyShort: vn.short,
      qlibShort: ql.short,
      paperLabel: data.mode === "PAPER_TRADING" ? "运行中" : "未启动",
      shadowLabel: data.mode === "SHADOW_LIVE" ? "运行中" : "未启动",
      latestReport: data.latest_daily_report
        ? {
            date: data.latest_daily_report.date || data.latest_daily_report.as_of,
            title: data.latest_daily_report.title || "量化日报",
            pathPdf: data.latest_daily_report.path_pdf,
          }
        : null,
      latestCandidate: data.latest_candidate
        ? {
            asOf: data.latest_candidate.as_of,
            verdict: data.latest_candidate.verdict || data.latest_candidate.status,
          }
        : null,
      blockers,
      raw: data,
    };
  }

  function overviewCards(vm) {
    if (!vm) return [];
    return [
      { title: "运行模式", value: vm.modeLabel, hint: `时段：${vm.sessionLabel}` },
      { title: "总资金", value: fmtCny(vm.capitalCny), hint: `权益 ${fmtCny(vm.equityCny)}` },
      { title: "剩余亏损额度", value: fmtCny(vm.remainingLossBudgetCny), hint: "¥1,000 累计上限" },
      { title: "Kill Switch", value: vm.killSwitchLabel, tone: vm.killSwitchLabel === "已触发" ? "danger" : "ok" },
      { title: "数据状态", value: vm.dataStatusLabel, hint: "Canonical DuckDB" },
      { title: "vn.py", value: vm.vnpyLabel, tone: vm.vnpyShort.includes("原生") ? "ok" : "muted" },
      { title: "Qlib", value: vm.qlibLabel, tone: vm.qlibShort.includes("原生") ? "ok" : "muted" },
      { title: "Paper / Shadow", value: `${vm.paperLabel} / ${vm.shadowLabel}` },
    ];
  }

  function fromScreener(res) {
    const d = res?.data || {};
    return {
      blocked: !!d.blocked,
      blockerReason: d.blocker_reason || "",
      asOfDate: d.as_of_date || "—",
      preset: d.preset || "—",
      universeSize: d.universe_size || 0,
      rows: (d.candidates || []).map((c) => ({
        rank: c.rank,
        symbol: c.symbol,
        last_close: c.last_close,
        last_pct: c.last_pct,
        ret_20: c.ret_20,
        ret_60: c.ret_60,
        trend: c.trend,
        vol_20: c.vol_20,
        avg_amount: c.avg_amount,
        score: c.score,
        spark: c.spark || [],
      })),
    };
  }

  function fromMarket(overview, providers, coverage) {
    const o = overview?.data || {};
    const blocked = !!o.blocked;
    const breadth = o.breadth || {};
    const idxRows = (o.indices || []).slice(0, 12).map((row) => [
      row.name || row.symbol || "—",
      row.close ?? "—",
      row.change_pct ?? "—",
      row.trade_date || "—",
    ]);
    const provRows = (providers?.data?.providers || []).map((p) => [
      p.provider || "—",
      p.status || "—",
      (p.datasets || []).join(", ") || "—",
      p.detail || p.last_ok || "—",
    ]);
    const covRows = (coverage?.data?.coverage || []).map((c) => [
      c.dataset || "—",
      c.row_count ?? 0,
      c.last_trade_date || "—",
      c.fresh ? "新鲜" : (c.blocker || "—"),
    ]);
    const summary = blocked
      ? o.blocker_reason || "数据不可用"
      : `截至 ${o.as_of_date || "—"} · ${o.freshness || "—"} · 上涨 ${breadth.advancers ?? 0} / 下跌 ${breadth.decliners ?? 0} / 涨停 ${breadth.limit_up ?? 0}`;
    return {
      blocked,
      blockedReason: blocked ? (o.blocker_reason || "数据源不可用") : "",
      blockerDataset: o.blocker_dataset || "",
      asOf: o.as_of_date || "—",
      freshness: o.freshness || "—",
      breadth,
      indices: idxRows,
      providers: provRows,
      coverage: covRows,
      snapshotSummary: summary,
    };
  }

  function fromPaper(pnl, positions, orders) {
    const p = pnl?.data || {};
    return {
      summary: {
        realized: fmtCny(p.realized_pnl ?? p.realized),
        unrealized: fmtCny(p.unrealized_pnl ?? p.unrealized),
        total: fmtCny(p.total_pnl ?? p.total),
        fees: fmtCny(p.fees),
      },
      positions: (positions?.data?.positions || positions?.data || []).map((row) => [
        row.symbol || "—",
        row.quantity ?? row.qty ?? 0,
        row.available ?? row.sellable ?? "—",
        fmtCny(row.avg_price ?? row.cost),
        fmtCny(row.market_value),
      ]),
      orders: (orders?.data?.orders || orders?.data || []).slice(0, 20).map((row) => [
        row.order_id || row.id || "—",
        row.symbol || "—",
        row.side || "—",
        row.status || "—",
        row.filled_qty ?? row.filled ?? 0,
      ]),
      empty: !(positions?.data?.positions?.length || positions?.data?.length),
    };
  }

  function fromRisk(data) {
    if (!data) return null;
    return {
      capital: fmtCny(data.capital_total_cny ?? data.capital),
      equity: fmtCny(data.equity_cny ?? data.equity),
      lossBudget: fmtCny(data.remaining_loss_budget_cny ?? data.remaining_loss_budget),
      halted: data.halted || data.kill_switch === "HALTED",
      killSwitch: data.kill_switch || "OPEN",
      blockers: data.blockers || [],
    };
  }

  function fromBrokers(data) {
    if (!data) return { rows: [], checklist: [] };
    const rows = Object.entries(data.gateways || {}).map(([name, g]) => [
      name,
      g.status || "—",
      g.real_orders ? "是" : "否",
    ]);
    return { rows, checklist: data.user_checklist || [], note: data.note };
  }

  function fromAgentsRun(data) {
    if (!data) return null;
    return {
      runId: data.run_id,
      bull: data.bull_summary,
      bear: data.bear_summary,
      risk: data.risk_verdict,
      portfolio: data.portfolio_verdict,
      gate: data.candidate_gate,
      agents: (data.agents || []).map((a) => ({
        id: a.agent_id || a.id,
        claim: a.claim,
        confidence: a.confidence,
        evidence: (a.evidence || []).slice(0, 3),
      })),
    };
  }

  function actionSummary(label, res) {
    if (!res.ok) {
      return res.error?.message || res.error?.code || "操作失败";
    }
    const d = res.data || {};
    if (d.passed === true) return "检查通过";
    if (d.mode) return `模式 → ${MODE_LABELS[d.mode] || d.mode}`;
    if (d.run_id) return `Run ${d.run_id} 已创建`;
    if (d.started_at) return "已启动";
    if (d.stopped_at) return "已停止";
    if (d.report_pdf) return "日报产物已生成";
    if (d.zero_real_orders_sent) return "零真实订单";
    return "已完成";
  }

  global.QuantOSViewModels = {
    fromSystemStatus,
    overviewCards,
    fromScreener,
    fromMarket,
    fromPaper,
    fromRisk,
    fromBrokers,
    fromAgentsRun,
    mapVnpyLabel,
    mapQlibLabel,
    actionSummary,
    fmtCny,
    fmtTime,
    MODE_LABELS,
  };
})(window);
