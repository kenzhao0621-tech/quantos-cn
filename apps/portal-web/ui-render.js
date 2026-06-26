/** QuantOS CN — UI components (cards, tables, badges; raw JSON only in collapsed details). */
(function (global) {
  function el(tag, cls, html) {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function renderCardGrid(container, cards) {
    if (!container) return;
    container.innerHTML = "";
    if (!cards?.length) {
      container.appendChild(renderEmpty("暂无状态", "等待系统状态加载…", ""));
      return;
    }
    const grid = el("div", "card-grid");
    cards.forEach((c) => {
      const card = el("div", `stat-card${c.tone ? " tone-" + c.tone : ""}`);
      card.appendChild(el("div", "stat-title", c.title));
      card.appendChild(el("div", "stat-value", c.value));
      if (c.hint) card.appendChild(el("div", "stat-hint", c.hint));
      grid.appendChild(card);
    });
    container.appendChild(grid);
  }

  function renderTable(container, headers, rows, emptyMsg) {
    if (!container) return;
    container.innerHTML = "";
    if (!rows?.length) {
      container.appendChild(renderEmpty("暂无数据", emptyMsg || "当前没有可显示的记录", "可尝试刷新或运行数据更新"));
      return;
    }
    const table = el("table", "data-table");
    const thead = el("thead");
    const hr = el("tr");
    headers.forEach((h) => hr.appendChild(el("th", "", h)));
    thead.appendChild(hr);
    table.appendChild(thead);
    const tbody = el("tbody");
    rows.forEach((row) => {
      const tr = el("tr");
      row.forEach((cell) => tr.appendChild(el("td", "", String(cell))));
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    container.appendChild(table);
  }

  function renderBadge(text, tone) {
    return el("span", `badge badge-${tone || "default"}`, text);
  }

  function renderEmpty(title, reason, fix) {
    const box = el("div", "empty-state");
    box.appendChild(el("strong", "", title));
    box.appendChild(el("p", "empty-reason", reason));
    if (fix) box.appendChild(el("p", "empty-fix", fix));
    return box;
  }

  function renderBlockers(container, blockers) {
    if (!container) return;
    container.innerHTML = "";
    if (!blockers?.length) {
      container.appendChild(el("p", "muted", "系统检查正常"));
      return;
    }
    const ul = el("ul", "blocker-list");
    blockers.forEach((b) => {
      const li = el("li", "blocker-item");
      li.appendChild(renderBadge("需要处理", "warn"));
      li.appendChild(document.createTextNode(" " + (b.message || b.code || String(b))));
      ul.appendChild(li);
    });
    container.appendChild(ul);
  }

  function renderKeyValues(container, pairs) {
    if (!container) return;
    container.innerHTML = "";
    const dl = el("dl", "kv-list");
    pairs.forEach(([k, v]) => {
      dl.appendChild(el("dt", "", k));
      dl.appendChild(el("dd", "", v));
    });
    container.appendChild(dl);
  }

  function renderReportSummary(container, report) {
    if (!container) return;
    container.innerHTML = "";
    if (!report) {
      container.appendChild(renderEmpty("尚无日报", "尚未生成量化日报", "点击「生成日报」创建"));
      return;
    }
    renderKeyValues(container, [
      ["日期", report.date || "—"],
      ["标题", report.title || "量化日报"],
      ["PDF", report.pathPdf ? "已生成" : "未生成"],
      ["Markdown", report.pathMd ? "已生成" : "未生成"],
      ["桌面目录", report.desktopDir || "生成后自动写入 ~/Desktop/China_A_Share_Daily_Reports"],
    ]);
  }

  function renderAgentPanel(container, vm) {
    if (!container) return;
    container.innerHTML = "";
    if (!vm) {
      container.appendChild(renderEmpty("尚未运行", "多智能体研究尚未执行", "点击「运行多智能体研究」"));
      return;
    }
    const wrap = el("div", "agent-panel");
    [["Bull", vm.bull], ["Bear", vm.bear], ["风险", vm.risk], ["组合", vm.portfolio], ["候选门", vm.gate]].forEach(
      ([title, text]) => {
        const sec = el("section", "agent-section");
        sec.appendChild(el("h3", "", title));
        sec.appendChild(el("p", "", text || "—"));
        wrap.appendChild(sec);
      }
    );
    if (vm.agents?.length) {
      const ul = el("ul", "agent-list");
      vm.agents.forEach((a) => {
        const li = el("li", "");
        li.textContent = `${a.id}：${a.claim}（置信度 ${Math.round((a.confidence || 0) * 100)}%）`;
        ul.appendChild(li);
      });
      wrap.appendChild(ul);
    }
    container.appendChild(wrap);
  }

  function renderActionLog(container, entry) {
    if (!container) return;
    const row = el("div", `action-entry${entry.ok ? " ok" : " fail"}`);
    const head = el("div", "action-head");
    head.appendChild(el("span", "action-name", entry.label));
    head.appendChild(renderBadge(entry.ok ? "成功" : "失败", entry.ok ? "ok" : "danger"));
    head.appendChild(el("span", "action-time", entry.time || new Date().toLocaleString("zh-CN")));
    row.appendChild(head);
    row.appendChild(el("div", "action-summary", entry.summary || "—"));
    if (entry.runId) row.appendChild(el("div", "action-run", `Run ID: ${entry.runId}`));
    if (entry.raw) {
      const det = el("details", "raw-details");
      det.appendChild(el("summary", "", "查看原始响应"));
      const pre = el("pre", "raw-json", JSON.stringify(entry.raw, null, 2));
      det.appendChild(pre);
      row.appendChild(det);
    }
    container.innerHTML = "";
    container.appendChild(row);
  }

  function renderJob(container, job) {
    if (!container) return;
    container.innerHTML = "";
    if (!job) {
      container.appendChild(renderEmpty("暂无任务", "尚未提交异步任务", "点击「更新数据」提交任务"));
      return;
    }
    const toneMap = { SUCCEEDED: "ok", FAILED: "danger", CANCELLED: "warn", RUNNING: "info", QUEUED: "default" };
    const wrap = el("div", "job-panel");
    const head = el("div", "job-head");
    head.appendChild(renderBadge(job.status, toneMap[job.status] || "default"));
    head.appendChild(el("span", "job-id", `任务 ${job.job_id}`));
    head.appendChild(el("span", "job-step", `步骤：${job.current_step || "—"}`));
    wrap.appendChild(head);
    const bar = el("div", "job-progress");
    const fill = el("div", "job-progress-fill");
    fill.style.width = `${job.percent || 0}%`;
    fill.textContent = `${job.percent || 0}%`;
    bar.appendChild(fill);
    wrap.appendChild(bar);
    if (job.error) wrap.appendChild(el("div", "job-error", `失败原因：${job.error}`));
    if (job.artifacts?.length) {
      const ul = el("ul", "job-artifacts");
      job.artifacts.forEach((a) => ul.appendChild(el("li", "", a)));
      wrap.appendChild(ul);
    }
    if (job.events?.length) {
      const log = el("div", "job-events");
      job.events.slice(-6).forEach((e) =>
        log.appendChild(el("div", "job-event", `[${e.percent}%] ${e.step} — ${e.message}`))
      );
      wrap.appendChild(log);
    }
    container.appendChild(wrap);
  }

  function sparklineSvg(values, up) {
    if (!values || values.length < 2) return "";
    const w = 80, h = 24, pad = 2;
    const min = Math.min(...values), max = Math.max(...values);
    const range = max - min || 1;
    const step = (w - pad * 2) / (values.length - 1);
    const pts = values
      .map((v, i) => `${(pad + i * step).toFixed(1)},${(h - pad - ((v - min) / range) * (h - pad * 2)).toFixed(1)}`)
      .join(" ");
    const color = up ? "var(--up)" : "var(--down)";
    return `<svg class="sparkline" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" /></svg>`;
  }

  function formatScreenerPrice(r, mode) {
    const live = r.live_price;
    const eod = r.last_close;
    const isLive = String(mode || "").toLowerCase() === "live";
    if (live != null && live !== "") {
      const pct =
        r.live_pct != null
          ? ` <span class="${Number(r.live_pct) >= 0 ? "up" : "down"}">${Number(r.live_pct) >= 0 ? "+" : ""}${r.live_pct}%</span>`
          : "";
      return `<span class="badge badge-pass" style="font-size:0.65rem">实时</span> ${live}${pct}`;
    }
    if (isLive) {
      return `<span class="muted">收 ${eod ?? "—"}</span> <span class="warn small">待挂价</span>`;
    }
    return String(eod ?? "—");
  }

  function renderScreener(container, vm) {
    if (!container) return;
    container.innerHTML = "";
    if (!vm || vm.blocked) {
      container.appendChild(renderEmpty("暂无候选", vm?.blockerReason || "点击「运行选股」生成排名", "请先确保数据已更新"));
      return;
    }
    if (!vm.rows.length) {
      container.appendChild(renderEmpty("无结果", "当前条件下没有候选股", "尝试降低成交额门槛"));
      return;
    }
    const maxScore = Math.max(...vm.rows.map((r) => r.final_score ?? r.score)) || 1;
    const table = el("table", "data-table screener-table");
    const capLabel = vm.capitalCny ? `¥${Math.round(vm.capitalCny)}` : "5000元";
    table.innerHTML =
      "<thead><tr><th>#</th><th>代码</th><th>名称</th><th>板块</th><th>价格</th><th>收益区间%</th><th>下行%</th><th>可买</th><th>" +
      capLabel +
      "</th><th>综合分</th><th>资格</th><th>走势</th></tr></thead>";
    const tb = el("tbody");
    vm.rows.forEach((r) => {
      const sym = r.symbol;
      const tr = el("tr", "screener-row-clickable");
      const barW = Math.max(6, Math.round(((r.final_score ?? r.score) / maxScore) * 60));
      const up = (r.ret_20 || 0) >= 0;
      const elig = r.eligibility || "—";
      const eligCls = elig === "PAPER_ELIGIBLE" ? "up" : (elig === "BLOCKED" ? "down" : "");
      const retRange = `${r.expected_return_lo_pct ?? "—"}~${r.expected_return_hi_pct ?? "—"}`;
      const afford = r.affordable_lots ? `${r.affordable_lots}手/${r.suggested_qty || 0}股` : "—";
      const displayName = r.name || "—";
      tr.innerHTML =
        `<td>${r.rank}</td>` +
        `<td><button type="button" class="symbol-link" data-screener-detail="${sym}">${sym}</button>
          <button type="button" class="mini-btn" data-watchlist-add="${sym}" data-watchlist-name="${r.name || ""}" title="收藏">★</button></td>` +
        `<td class="stock-name"><button type="button" class="symbol-link" data-screener-detail="${sym}">${displayName}</button></td>` +
        `<td>${r.sector || "—"}</td>` +
        `<td class="num">${formatScreenerPrice(r, vm.mode)}</td>` +
        `<td class="num">${retRange}</td>` +
        `<td class="num">${r.downside_risk_pct ?? "—"}</td>` +
        `<td>${r.valid_for_purchase ? "是" : "否"}</td>` +
        `<td class="num">${afford}</td>` +
        `<td><span class="score-bar" style="width:${barW}px"></span> ${(r.final_score ?? r.score).toFixed(2)}</td>` +
        `<td class="${eligCls}">${elig}${r.valid_for_purchase && r.suggested_qty ? ` <button type="button" class="mini-btn" data-live-order="${sym}" data-live-name="${r.name || ""}" data-live-qty="${r.suggested_qty}" data-live-price="${r.live_price ?? r.last_close}">实盘</button>` : ""}</td>` +
        `<td>${sparklineSvg(r.spark, up)}</td>`;
      tr.title = "点击查看选股原因与评分明细";
      tr.dataset.screenerRow = sym;
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    container.appendChild(table);
    container.appendChild(el("p", "muted small screener-row-hint", "提示：点击任意股票行打开详情弹窗，查看因子说明、评分与买卖区间。"));
  }

  function _mergeStockDetailPayload(payload) {
    const p = payload || {};
    const dossier = p.dossier?.data || p.dossier || {};
    const row = p.row || dossier.candidate || dossier.enriched || dossier || {};
    const enriched = dossier.enriched || row.enriched || row;
    return { dossier, row, enriched };
  }

  function _appendFactorList(parent, title, items, cls) {
    if (!items?.length) return;
    const sec = el("div", "stock-modal-section");
    sec.appendChild(el("h3", "", title));
    const ul = el("ul", "checklist");
    items.forEach((line) => ul.appendChild(el("li", cls || "", line)));
    sec.appendChild(ul);
    parent.appendChild(sec);
  }

  function renderStockDetailModal(bodyEl, payload) {
    if (!bodyEl) return;
    bodyEl.innerHTML = "";
    const p = payload || {};
    if (p.blocked) {
      bodyEl.appendChild(renderEmpty("无法分析", p.blocker_reason || p.blockerReason || "未找到该股票", ""));
      return;
    }
    if (p.loading && !p.row && !p.dossier) {
      bodyEl.appendChild(el("div", "stock-modal-loading", "正在加载个股分析报告…"));
      return;
    }

    const { dossier, row, enriched } = _mergeStockDetailPayload(p);
    const sym = row.symbol || dossier.symbol || "—";
    const name = row.name || dossier.name || "";
    const display = name ? `${name}（${sym}）` : sym;
    const score = row.final_score ?? row.score ?? dossier.score;
    const scoreTxt = score != null ? Number(score).toFixed(2) : "—";

    const head = el("div", "stock-modal-head");
    const titleBlock = el("div", "stock-modal-title-block");
    const h2 = el("h2", "", display);
    h2.id = "stock-modal-title";
    titleBlock.appendChild(h2);
    const subParts = [];
    if (row.rank != null) subParts.push(`排名 #${row.rank}`);
    if (row.sector || dossier.sector) subParts.push(row.sector || dossier.sector);
    if (row.validation_status || dossier.validation_status) subParts.push(`验证 ${row.validation_status || dossier.validation_status}`);
    if (dossier.model_version || row.model_version) subParts.push(`模型 ${dossier.model_version || row.model_version}`);
    titleBlock.appendChild(el("div", "stock-modal-sub", subParts.join(" · ") || "QuantOS 个股量化分析"));
    head.appendChild(titleBlock);
    const closeBtn = el("button", "stock-modal-close", "✕");
    closeBtn.type = "button";
    closeBtn.dataset.stockModalClose = "1";
    closeBtn.setAttribute("aria-label", "关闭");
    head.appendChild(closeBtn);
    bodyEl.appendChild(head);

    if (p.loading) {
      bodyEl.appendChild(el("p", "muted small", "正在加载完整报告…"));
    }

    const hero = el("div", "stock-modal-hero");
    const ring = el("div", "stock-modal-score-ring");
    ring.innerHTML = `<span class="score-num">${scoreTxt}</span><span class="score-lbl">综合分</span>`;
    hero.appendChild(ring);

    const kpis = el("div", "stock-modal-kpis");
    const price = row.live_price ?? row.last_close ?? dossier.candidate?.last_close;
    const retLo = row.expected_return_lo_pct ?? dossier.expected_return_lo_pct;
    const retHi = row.expected_return_hi_pct ?? dossier.expected_return_hi_pct;
    const kpiData = [
      ["最新价", price != null ? `¥${price}` : "—"],
      ["收益区间", retLo != null ? `${retLo}% ~ ${retHi}%` : "—"],
      ["下行风险", row.downside_risk_pct != null ? `${row.downside_risk_pct}%` : "—"],
      ["Alpha158-lite", row.alpha_score != null ? Number(row.alpha_score).toFixed(3) : (enriched.alpha_score != null ? Number(enriched.alpha_score).toFixed(3) : "—")],
      ["流动性", row.liquidity_score ?? enriched.liquidity_score ?? "—"],
      ["可买整手", row.affordable_lots ? `${row.affordable_lots}手` : (row.valid_for_purchase ? "是" : "否")],
      ["数据截止", row.data_cutoff || dossier.as_of_date || dossier.data_cutoff || "—"],
    ];
    kpiData.forEach(([k, v]) => {
      const cell = el("div", "stock-modal-kpi");
      cell.innerHTML = `<span class="k">${k}</span><span class="v">${v}</span>`;
      kpis.appendChild(cell);
    });
    hero.appendChild(kpis);
    bodyEl.appendChild(hero);

    const summaryText =
      dossier.plain_language ||
      dossier.beginner_guide?.summary ||
      row.plain_language ||
      (row.detailed_reasons?.[0] ? `核心逻辑：${row.detailed_reasons[0]}` : "");
    if (summaryText) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", "一句话解读"));
      sec.appendChild(el("p", "stock-modal-summary", summaryText));
      bodyEl.appendChild(sec);
    }

    const zones = dossier.trade_zones || row.trade_zones;
    if (zones?.buy_zone_low != null) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", "买卖区间参考（非盈利承诺）"));
      const grid = el("div", "stock-modal-zones");
      [
        ["buy", "建议买入", `¥${zones.buy_zone_low} – ¥${zones.buy_zone_high}`],
        ["stop", "止损参考", `¥${zones.stop_loss}`],
        ["sell", "止盈参考", `¥${zones.sell_zone_low} – ¥${zones.sell_zone_high}`],
      ].forEach(([cls, label, val]) => {
        const z = el("div", `stock-modal-zone ${cls}`);
        z.innerHTML = `<div class="z-label">${label}</div><div class="z-val">${val}</div>`;
        grid.appendChild(z);
      });
      sec.appendChild(grid);
      if (zones.chase_warning) sec.appendChild(el("p", "warn", "接近涨停，不建议追入。"));
      bodyEl.appendChild(sec);
    }

    const detailed =
      enriched.detailed_reasons ||
      dossier.detailed_reasons ||
      row.detailed_reasons ||
      [];
    _appendFactorList(bodyEl, "专业因子说明", detailed);

    const pos = enriched.positive_factors || row.positive_factors || dossier.positive_factors || [];
    const neg = enriched.negative_factors || row.negative_factors || dossier.negative_factors || [];
    if (pos.length || neg.length) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", "多空因子"));
      const ul = el("ul", "checklist");
      pos.forEach((line) => ul.appendChild(el("li", "up", "✓ " + line)));
      neg.forEach((line) => ul.appendChild(el("li", "down", "✗ " + line)));
      sec.appendChild(ul);
      bodyEl.appendChild(sec);
    }

    const invalid = row.invalidation_conditions || dossier.invalidation_conditions || enriched.invalidation_conditions;
    if (invalid?.length) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", "失效条件"));
      sec.appendChild(el("p", "warn", invalid.join("；")));
      bodyEl.appendChild(sec);
    }

    const notTrade = row.reasons_not_to_trade || dossier.reasons_not_to_trade;
    if (notTrade?.length) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", "不宜交易"));
      sec.appendChild(el("p", "down", notTrade.join("；")));
      bodyEl.appendChild(sec);
    }

    if (dossier.beginner_guide?.steps?.length) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", "新手操作步骤"));
      const ol = el("ol", "help-steps");
      dossier.beginner_guide.steps.forEach((s) => ol.appendChild(el("li", "", s)));
      sec.appendChild(ol);
      bodyEl.appendChild(sec);
    }

    if (dossier.institutional_report?.factors?.length) {
      const sec = el("div", "stock-modal-section");
      sec.appendChild(el("h3", "", `机构因子报告 · ${dossier.institutional_report.weighted_score} / 100`));
      const rows = dossier.institutional_report.factors.map((f) => [
        f.name,
        `${Math.round(f.weight * 100)}%`,
        Math.round(f.score * 100),
        f.evidence,
      ]);
      const sub = el("div", "");
      sec.appendChild(sub);
      renderTable(sub, ["因子", "权重", "评分", "证据"], rows, "暂无因子报告");
      if (dossier.institutional_report.methodology) {
        sec.appendChild(el("p", "muted small", dossier.institutional_report.methodology));
      }
      bodyEl.appendChild(sec);
    }

    const riskNotes = dossier.risk_notes || row.risk_notes;
    if (riskNotes?.length) {
      bodyEl.appendChild(el("div", "banner banner-warn stock-modal-section", "风险边界：" + riskNotes.join("；")));
    }

    bodyEl.appendChild(
      el(
        "p",
        "stock-modal-footnote",
        "以上内容为量化模型输出，不构成投资建议。真实交易请在券商官方平台由本人确认。",
      ),
    );

    if (!p.loading && (dossier.symbol || row.symbol)) {
      const actions = el("div", "stock-modal-actions");
      const pdfBtn = el("button", "primary", "导出选股 PDF");
      pdfBtn.type = "button";
      pdfBtn.dataset.action = "screener-report-pdf";
      actions.appendChild(pdfBtn);
      bodyEl.appendChild(actions);
    }
  }

  function openStockDetailModal() {
    const modal = document.getElementById("stock-detail-modal");
    if (!modal) return;
    modal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeStockDetailModal() {
    const modal = document.getElementById("stock-detail-modal");
    if (!modal) return;
    modal.classList.add("hidden");
    document.body.style.overflow = "";
  }

  function renderScreenerInsights(container, vm) {
    if (!vm?.rows?.length) return;
    const top = vm.rows[0];
    const box = el("div", "screener-insights");
    const title = top.name ? `${top.name}（${top.symbol}）` : top.symbol;
    box.appendChild(el("h3", "", `榜首解读 · ${title}`));
    const summary = el("p", "muted", "");
    summary.innerHTML =
      `模型 <b>${vm.modelVersion || top.model_version || "—"}</b> · ` +
      `验证 <b>${vm.validationStatus || top.validation_status || "NOT_RUN"}</b> · ` +
      `Alpha158-lite 分 <b>${(top.alpha_score ?? 0).toFixed(3)}</b> · ` +
      `数据截止 <b>${vm.dataCutoff || top.data_cutoff || "—"}</b>`;
    box.appendChild(summary);
    if (top.trade_zones?.buy_zone_low) {
      const z = top.trade_zones;
      box.appendChild(el("p", "", `参考买入区间 ¥${z.buy_zone_low} – ¥${z.buy_zone_high}；止损约 ¥${z.stop_loss}；止盈参考 ¥${z.sell_zone_low} – ¥${z.sell_zone_high}。`));
    }
    if (top.detailed_reasons?.length) {
      const ul = el("ul", "checklist");
      top.detailed_reasons.slice(0, 6).forEach((line) => ul.appendChild(el("li", "", line)));
      box.appendChild(ul);
    } else if (top.positive_factors?.length || top.negative_factors?.length) {
      const ul = el("ul", "checklist");
      (top.positive_factors || []).forEach((line) => ul.appendChild(el("li", "up", "✓ " + line)));
      (top.negative_factors || []).forEach((line) => ul.appendChild(el("li", "down", "✗ " + line)));
      box.appendChild(ul);
    }
    if (top.invalidation_conditions?.length) {
      box.appendChild(el("p", "warn small", "失效条件：" + top.invalidation_conditions.join("；")));
    }
    const openBtn = el("button", "mini-btn screener-expand-btn", "查看完整分析报告");
    openBtn.type = "button";
    openBtn.dataset.screenerDetail = top.symbol;
    box.appendChild(openBtn);
    container.appendChild(box);
  }

  function renderSelectionGuide(container, vm) {
    if (!container) return;
    container.innerHTML = "";
    const g = vm?.selectionGuide;
    if (!g || !g.title) return;
    const card = el("div", "dossier-card selection-guide");
    card.appendChild(el("h3", "", g.title));
    const sub = el("p", "muted", "");
    sub.innerHTML =
      `策略 <b>${g.preset_label || "—"}</b> · 模式 <b>${g.mode_label || "—"}</b> · ` +
      `资金 <b>¥${Number(g.capital_cny || 0).toLocaleString("zh-CN")}</b> · ` +
      `筛选 <b>${g.price_filter_summary || "—"}</b>`;
    card.appendChild(sub);
    if (g.warnings?.length) {
      g.warnings.forEach((w) => card.appendChild(el("p", "warn small", w)));
    }
    if (g.steps?.length) {
      const ol = el("ol", "checklist");
      g.steps.forEach((step) => ol.appendChild(el("li", "", step)));
      card.appendChild(ol);
    }
    if (g.field_glossary?.length) {
      const gl = el("details", "glossary");
      gl.appendChild(el("summary", "", "术语速查"));
      const ul = el("ul", "screener-detail-list");
      g.field_glossary.forEach((item) => {
        ul.appendChild(el("li", "", `<b>${item.term}</b>：${item.plain}`));
      });
      gl.appendChild(ul);
      card.appendChild(gl);
    }
    container.appendChild(card);
  }

  function renderLiveRadar(container, data, series) {
    if (!container) return;
    container.innerHTML = "";
    const d = data || {};
    if (!d.success) {
      container.appendChild(renderEmpty("实时行情不可用", d.reason || "等待刷新", "点击市场中心的「刷新实时行情」"));
      return;
    }
    const banner = el(
      "div",
      "banner banner-ok",
      `实时行情：${d.provider} · ${d.row_count} 行 · ${d.freshness} · ${d.retrieved_at}${d.cache_hit ? " · 缓存" : ""}`,
    );
    container.appendChild(banner);
    const cards = el("div", "live-ticker-grid");
    (d.top_up || []).slice(0, 6).forEach((r) => {
      const key = r.code || r.symbol;
      const vals = series?.[key] || [r.price].filter(Boolean);
      const card = el("div", "live-ticker-card");
      card.innerHTML =
        `<div class="live-symbol">${r.code || "—"} ${r.name || ""}</div>` +
        `<div class="live-price">${r.price ?? "—"}</div>` +
        `<div class="${Number(r.change_pct || 0) >= 0 ? "up" : "down"}">${Number(r.change_pct || 0) >= 0 ? "+" : ""}${r.change_pct ?? 0}%</div>` +
        sparklineSvg(vals, Number(r.change_pct || 0) >= 0);
      cards.appendChild(card);
    });
    container.appendChild(cards);
  }

  function renderBrokerLinks(container, links) {
    if (!container) return;
    container.innerHTML = "";
    if (!links?.length) {
      container.appendChild(renderEmpty("暂无官方路径", "券商链接尚未配置", ""));
      return;
    }
    const grid = el("div", "broker-link-grid");
    links.forEach((l) => {
      const card = el("div", "broker-link-card");
      card.innerHTML =
        `<h3>${l.name}</h3>` +
        `<p class="muted">${l.type || ""}</p>` +
        `<p>${l.note || ""}</p>` +
        `<button type="button" data-broker-url="${l.url}">打开官方平台</button>`;
      grid.appendChild(card);
    });
    container.appendChild(grid);
  }

  function renderAutopilot(container, data) {
    if (!container) return;
    container.innerHTML = "";
    const d = data?.data || data || {};
    if (d.checks) {
      const readyUnattended = !!d.ready_for_unattended_auto;
      const banner = el("div", readyUnattended ? "banner banner-ok" : d.ready_for_order_ticket ? "banner banner-warn" : "banner banner-warn",
        readyUnattended
          ? "无人值守实盘已就绪 — 可一键执行组合或执行票据"
          : d.ready_for_order_ticket
            ? "准入检查通过：可生成订单票据（无人值守需开启门控）"
            : "准入检查未通过");
      container.appendChild(banner);
      if (d.real_auto_trade_reason && !readyUnattended) {
        container.appendChild(el("p", "hint", `阻塞：${d.real_auto_trade_reason}`));
      }
      if (d.preflight?.warnings?.length) {
        const w = el("ul", "checklist");
        d.preflight.warnings.forEach((x) => w.appendChild(el("li", "", `⚠ ${x}`)));
        container.appendChild(w);
      }
      renderTable(
        container.appendChild(el("div", "")),
        ["检查项", "结果", "说明"],
        d.checks.map((c) => [c.name, c.passed ? "通过" : "未通过", c.detail || ""]),
        "暂无检查项",
      );
      return;
    }
    if (d.ticket_id) {
      container.appendChild(el("div", d.lines?.length ? "banner banner-ok" : "banner banner-warn",
        `订单票据 ${d.ticket_id} · ${d.status} · ${d.legal_boundary}`));
      const execBtn = el("button", "primary", "无人值守执行此票据");
      execBtn.dataset.action = "autopilot-execute-ticket";
      execBtn.dataset.ticketId = d.ticket_id;
      container.appendChild(execBtn);
      const rows = (d.lines || []).map((x) => [
        x.symbol,
        x.side,
        x.quantity,
        x.reference_price,
        x.notional_cny,
        x.sector || "—",
        x.score,
      ]);
      renderTable(container.appendChild(el("div", "")), ["代码", "方向", "数量", "参考价", "金额", "板块", "评分"], rows, "暂无可执行票据行");
      if (d.blockers?.length) {
        const ul = el("ul", "checklist");
        d.blockers.slice(0, 8).forEach((b) => ul.appendChild(el("li", "", b)));
        container.appendChild(ul);
      }
      renderBrokerLinks(container.appendChild(el("div", "")), d.broker_handoff || []);
    }
  }

  function renderModelValidation(container, data) {
    if (!container) return;
    container.innerHTML = "";
    const d = data?.data || data || {};
    if (!d.verdict) {
      container.appendChild(renderEmpty("暂无验收结果", "点击「运行生产验收」", ""));
      return;
    }
    container.appendChild(el("div", d.verdict === "READY_FOR_EXTENDED_PAPER" ? "banner banner-ok" : "banner banner-warn", `结论：${d.verdict}`));
    renderKeyValues(container.appendChild(el("div", "")), [
      ["样本交易日", d.sample?.validation_days ?? "—"],
      ["样本外天数", d.sample?.out_of_sample_days ?? "—"],
      ["样本外日均净收益", `${d.out_of_sample?.avg_daily_net_return ?? "—"}%`],
      ["样本外跑赢率", `${d.out_of_sample?.avg_outperform_rate ?? "—"}%`],
      ["滚动最大单日亏损", `${d.rolling?.max_daily_loss ?? "—"}%`],
      ["Top30 稳定度", `${d.factor_stability?.top30_overlap_avg ?? "—"}%`],
      ["涨停不可执行", d.execution?.limit_blocked_total ?? "—"],
      ["Paper/Shadow 样本", `${d.paper_shadow?.paper_records ?? 0}/${d.paper_shadow?.shadow_records ?? 0}`],
    ]);
    if (d.actions?.length) {
      const ul = el("ul", "checklist");
      d.actions.forEach((a) => ul.appendChild(el("li", "", a)));
      container.appendChild(ul);
    }
  }

  function renderGatewayReadiness(container, data) {
    if (!container) return;
    container.innerHTML = "";
    const d = data?.data || data || {};
    if (!d.checks) {
      container.appendChild(renderEmpty("暂无 Gateway 生产就绪报告", "等待检查", ""));
      return;
    }
    container.appendChild(el("div", d.passed ? "banner banner-ok" : "banner banner-warn", `Gateway 生产就绪度：${d.score}% · ${d.production_label}`));
    renderTable(
      container.appendChild(el("div", "")),
      ["模块", "状态", "说明"],
      d.checks.map((c) => [c.name, c.passed ? "通过" : "待完善", c.detail]),
      "暂无检查项",
    );
  }

  function renderStrategyLearning(container, payload) {
    if (!container) return;
    container.innerHTML = "";
    const learning = payload?.learning || payload;
    const d = payload?.proof || payload?.data || learning?.proof || learning || {};
    if (!d || d.blocked) {
      container.appendChild(renderEmpty("暂无验证", d.blocker_reason || "需要至少两个交易日数据", "先在「高级·数据」更新行情，再运行验证"));
      return;
    }
    const banner = el("div", d.verdict === "PASS" ? "banner banner-ok" : "banner banner-warn");
    banner.innerHTML =
      `<strong>T+1 验证</strong> ${d.signal_date || "—"} 选股 → ${d.proof_date || "—"} 收盘 · ` +
      `平均收益 <b>${d.avg_return ?? "—"}%</b> · 市场中位数 <b>${d.benchmark_median ?? "—"}%</b> · ` +
      `命中率 <b>${d.hit_rate ?? "—"}%</b> · 跑赢率 <b>${d.win_rate_vs_median ?? "—"}%</b> · ` +
      `结论 <b>${d.verdict || "—"}</b>`;
    container.appendChild(banner);

    const agent = learning?.agent_overlay;
    if (agent) {
      const card = el("div", "dossier-card strategy-agent-card");
      card.appendChild(el("h4", "", `TradingAgents 评审 · ${agent.risk_verdict || "—"}`));
      if (agent.reasoning_notes?.length) {
        const ul = el("ul", "checklist");
        agent.reasoning_notes.forEach((n) => ul.appendChild(el("li", "", n)));
        card.appendChild(ul);
      }
      if (agent.suggested_adjustments?.length) {
        const adjRows = agent.suggested_adjustments.map((a) => [
          a.param || "—",
          a.action || "—",
          a.target || a.delta_pct || "—",
          a.reason || "—",
        ]);
        renderTable(card.appendChild(el("div", "")), ["参数", "动作", "建议值", "原因"], adjRows, "无调整建议");
      }
      if (learning.recommended_preset) {
        card.appendChild(el("p", "muted", `推荐策略预设：<strong>${learning.recommended_preset}</strong>`));
      }
      container.appendChild(card);
    }

    if (d.what_to_adjust?.length) {
      const sec = el("div", "strategy-adjust-block");
      sec.appendChild(el("h4", "", "系统复盘建议"));
      const notes = el("ul", "checklist");
      d.what_to_adjust.forEach((n) => notes.appendChild(el("li", "", n)));
      sec.appendChild(notes);
      container.appendChild(sec);
    }

    const rows = (d.proofs || []).slice(0, 15).map((p) => [
      p.rank,
      p.symbol,
      p.next_day_return >= 0 ? `+${p.next_day_return}%` : `${p.next_day_return}%`,
      p.outperformance >= 0 ? `+${p.outperformance}%` : `${p.outperformance}%`,
      p.passed ? "达标" : "复盘",
      p.diagnosis,
    ]);
    renderTable(
      container.appendChild(el("div", "")),
      ["#", "代码", "T+1收益", "跑赢中位数", "结果", "归因"],
      rows,
      "暂无逐股验证明细",
    );
  }

  function renderProof(container, proof) {
    renderStrategyLearning(container, proof?.learning ? proof : { data: proof?.data || proof });
  }

  function renderStockAnalysis(container, data) {
    if (!container) return;
    container.innerHTML = "";
    const d = data || {};
    if (d.blocked) {
      container.appendChild(renderEmpty("无法分析", d.blocker_reason || "未找到该股票", ""));
      return;
    }
    const display = d.name ? `${d.name}（${d.symbol}）` : d.symbol;
    const box = el("div", "stock-analysis-card");
    const head = el("div", "stock-analysis-head");
    head.appendChild(el("h3", "", display));
    const scoreRow = el("div", "stock-score-row");
    const scoreVal = d.score != null ? Number(d.score).toFixed(3) : "—";
    scoreRow.innerHTML = `<span class="stock-score-label">量化评分</span><span class="stock-score-value">${scoreVal}</span>`;
    if (d.rank != null && d.universe_size) {
      scoreRow.appendChild(el("span", "stock-rank", `全市场第 ${d.rank} / ${d.universe_size} · 前 ${d.percentile_top ?? "—"}%`));
    }
    if (d.alpha_score != null) {
      scoreRow.appendChild(el("span", "stock-alpha", `Alpha158-lite ${Number(d.alpha_score).toFixed(4)}`));
    }
    head.appendChild(scoreRow);
    box.appendChild(head);

    const cand = d.candidate || {};
    const meta = el("div", "stock-meta-grid");
    const items = [
      ["最新价", cand.last_close != null ? `¥${cand.last_close}` : "—"],
      ["涨跌幅", cand.last_pct != null ? `${cand.last_pct}%` : "—"],
      ["20日收益", cand.ret_20 != null ? `${(cand.ret_20 * 100).toFixed(1)}%` : "—"],
      ["板块", cand.sector || "—"],
      ["数据日期", d.as_of_date || "—"],
    ];
    items.forEach(([k, v]) => {
      const cell = el("div", "stock-meta-item");
      cell.innerHTML = `<span class="stock-meta-key">${k}</span><span class="stock-meta-val">${v}</span>`;
      meta.appendChild(cell);
    });
    box.appendChild(meta);

    if (d.plain_language) {
      box.appendChild(el("p", "stock-summary", d.plain_language));
    }

    const enriched = d.enriched || {};
    if (d.detailed_reasons?.length) {
      box.appendChild(el("h4", "", "专业因子说明"));
      const ul = el("ul", "checklist");
      d.detailed_reasons.forEach((r) => ul.appendChild(el("li", "", r)));
      box.appendChild(ul);
    } else if (enriched.detailed_reasons?.length) {
      box.appendChild(el("h4", "", "专业因子说明"));
      const ul = el("ul", "checklist");
      enriched.detailed_reasons.forEach((r) => ul.appendChild(el("li", "", r)));
      box.appendChild(ul);
    }

    if (enriched.positive_factors?.length || enriched.negative_factors?.length) {
      box.appendChild(el("h4", "", "多空因子"));
      const ul = el("ul", "checklist");
      (enriched.positive_factors || []).forEach((r) => ul.appendChild(el("li", "up", "✓ " + r)));
      (enriched.negative_factors || []).forEach((r) => ul.appendChild(el("li", "down", "✗ " + r)));
      box.appendChild(ul);
    }

    if (d.trade_zones?.buy_zone_low) {
      const z = d.trade_zones;
      box.appendChild(el("h4", "", "买卖区间参考（非盈利承诺）"));
      box.appendChild(el("p", "", `买入 ¥${z.buy_zone_low} – ¥${z.buy_zone_high} · 止损 ¥${z.stop_loss} · 止盈 ¥${z.sell_zone_low} – ¥${z.sell_zone_high}`));
      if (z.chase_warning) box.appendChild(el("p", "warn", "接近涨停，不建议追入。"));
    }

    if (d.risk_notes?.length) {
      box.appendChild(el("div", "banner banner-warn", "风险边界：" + d.risk_notes.join("；")));
    }

    container.appendChild(box);
  }

  function renderDossier(container, dossier) {
    const d = dossier?.data || dossier || {};
    if (d._closed) {
      closeStockDetailModal();
      if (container) {
        container.innerHTML = "";
        container.appendChild(renderEmpty("个股解释已收起", "点击表格中「分析报告」打开弹窗", ""));
      }
      return;
    }
    if (!d.symbol && !dossier?.row) {
      if (container) {
        container.innerHTML = "";
        container.appendChild(renderEmpty("个股解释已收起", "点击表格中「分析报告」打开弹窗", ""));
      }
      return;
    }
    const body = document.getElementById("stock-detail-body");
    renderStockDetailModal(body, { dossier: d, row: d.candidate || d });
    openStockDetailModal();
    if (container) {
      container.innerHTML = "";
      container.appendChild(el("p", "muted small", `已打开 ${d.name || d.symbol} 分析报告弹窗`));
    }
  }

  function renderSetupCenter(container, data) {
    if (!container || !data) return;
    container.innerHTML = "";
    const score = data.score || { complete: 0, total: 5 };
    const head = el("div", "setup-head");
    head.innerHTML = `<strong>入门进度 ${score.complete}/${score.total}</strong>`;
    if (score.complete < score.total) {
      head.appendChild(el("p", "muted", "完成下列步骤后即可开始 Paper → 订单票据 → 券商人工确认。"));
    }
    container.appendChild(head);

    const list = el("ol", "setup-steps");
    (data.steps || []).forEach((step) => {
      const li = el("li", step.done ? "setup-step done" : "setup-step");
      li.innerHTML = `<span class="setup-step-title">${step.done ? "✓" : "○"} ${step.title}</span>`;
      if (step.hint) li.appendChild(el("div", "stat-hint", step.hint));
      if (step.action && !step.done) {
        const btn = el("button", "setup-action-btn", "执行");
        btn.type = "button";
        btn.dataset.setupAction = step.action;
        li.appendChild(btn);
      }
      list.appendChild(li);
    });
    container.appendChild(list);

    const arts = data.artifacts || {};
    const paths = el("div", "setup-artifacts");
    paths.appendChild(el("h4", "", "本地文件路径"));
    Object.entries(arts).forEach(([key, path]) => {
      const row = el("div", "setup-path-row");
      row.appendChild(el("span", "setup-path-key", key));
      row.appendChild(el("code", "setup-path-val", path));
      const copy = el("button", "copy-path-btn", "复制");
      copy.type = "button";
      copy.dataset.copyPath = path;
      row.appendChild(copy);
      paths.appendChild(row);
    });
    container.appendChild(paths);
  }

  function toast(title, message, tone) {
    let stack = document.getElementById("toast-stack");
    if (!stack) {
      stack = el("div", "toast-stack");
      stack.id = "toast-stack";
      document.body.appendChild(stack);
    }
    const t = el("div", `toast ${tone || "info"}`);
    const icon = tone === "ok" ? "✓" : tone === "fail" ? "✕" : "•";
    const head = el("div", "toast-title");
    head.appendChild(el("span", "", icon));
    head.appendChild(el("span", "", title));
    t.appendChild(head);
    if (message) t.appendChild(el("div", "toast-msg", message));
    stack.appendChild(t);
    const remove = () => {
      t.classList.add("toast-fade");
      setTimeout(() => t.remove(), 300);
    };
    t.addEventListener("click", remove);
    setTimeout(remove, tone === "fail" ? 7000 : 4000);
  }

  function setLoading(btn, loading, msg) {
    if (!btn) return;
    if (loading) {
      btn.dataset.prevText = btn.textContent;
      btn.textContent = msg || "处理中…";
      btn.disabled = true;
    } else {
      btn.textContent = btn.dataset.prevText || btn.textContent;
      btn.disabled = false;
    }
  }

  /** Detect raw JSON dumped into primary view containers (for E2E). */
  function countPrimaryRawJson(root) {
    const sel = root.querySelectorAll(
      ".card-grid, .data-table, .kv-list, .agent-panel, .empty-state, .stat-card"
    );
    if (sel.length > 0) return 0;
    const blocks = root.querySelectorAll(".primary-view, [data-primary-view]");
    let count = 0;
    blocks.forEach((b) => {
      const t = (b.textContent || "").trim();
      if (t.startsWith("{") && t.includes('"mode"')) count += 1;
      if (t.startsWith("[") && t.length > 200) count += 1;
    });
    return count;
  }

  function renderBrokerSession(container, data) {
    if (!container) return;
    const d = data || {};
    const bs = d.browser_session || {};
    const chips = [
      `券商 <b>${d.active_broker || "—"}</b>`,
      `会话 <b>${bs.saved ? "已保存" : "未登录"}</b>`,
      `Playwright <b>${bs.playwright_ready ? "就绪" : "未安装"}</b>`,
      `真实资金 <b>${d.real_money_enabled ? "已启用" : "关闭"}</b>`,
    ];
    container.innerHTML = chips.map((c) => `<span class="metric-chip">${c}</span>`).join("");
  }

  function renderWatchlist(container, items) {
    if (!container) return;
    container.innerHTML = "";
    const h = el("h3", "", `我的收藏 (${items.length})`);
    container.appendChild(h);
    if (!items.length) {
      container.appendChild(el("p", "muted", "在智能选股页点击 ★ 收藏股票，然后点「同步收藏到券商」"));
      return;
    }
    const ul = el("ul", "checklist");
    items.slice(0, 30).forEach((it) => {
      const li = el("li", "", `${it.symbol} ${it.name || ""}`);
      ul.appendChild(li);
    });
    container.appendChild(ul);
  }

  function renderExecutionPaths(container, data) {
    if (!container) return;
    const paths = data?.paths || [];
    container.innerHTML = "";
    const h = el("h3", "", "执行路径（按优先级回退）");
    container.appendChild(h);
    if (!paths.length) {
      container.appendChild(el("p", "muted", "点击「检测执行路径」"));
      return;
    }
    renderTable(
      container,
      ["路径", "无人值守", "可用", "状态", "说明"],
      paths.map((p) => [
        p.label || p.path_id,
        p.unattended_capable ? "是" : "否",
        p.available ? "✓" : "—",
        p.status || "",
        p.message || "",
      ]),
      "无路径",
    );
  }

  function renderBeginnerGuide(stepsEl, learningEl, data) {
    if (!stepsEl || !data) return;
    stepsEl.innerHTML = "";
    (data.steps || []).forEach((s) => {
      const card = el("div", "beginner-step-card");
      card.appendChild(el("strong", "", `${s.id}. ${s.title}`));
      card.appendChild(el("p", "muted", s.hint || ""));
      stepsEl.appendChild(card);
    });
    if (learningEl && data.daily_learning) {
      const L = data.daily_learning;
      learningEl.innerHTML = `<h3>每日算法学习</h3><p>已记录 <b>${L.screener_runs || L.scored_days || 0}</b> 次选股运行；系统对照后续走势持续改进（不承诺收益）。</p><p class="muted">${L.status || ""} ${(L.recommendations || []).slice(0, 2).join(" · ")}</p>`;
    }
  }

  function renderBrokerOfficialLinks(container, brokerId, ecosystem) {
    if (!container) return;
    container.innerHTML = "";
    const b = (ecosystem?.brokers || []).find((x) => x.broker_id === brokerId);
    if (!b) return;
    const urls = b.urls || {};
    if (b.login_type === "app_via_ths" && b.external_steps?.length) {
      const box = el("div", "broker-app-guide");
      box.appendChild(el("h3", "", `${b.label} · App 登录指引`));
      box.appendChild(el("p", "warn", "同花顺没有统一网页交易页，须用 App 绑定你的券商账户后下单。"));
      const ol = el("ol", "help-steps");
      b.external_steps.forEach((step) => ol.appendChild(el("li", "", step)));
      box.appendChild(ol);
      container.appendChild(box);
    } else {
      container.appendChild(el("h3", "", `${b.label} · 官方入口`));
    }
    const links = [
      { label: "主登录页", url: urls.trade_login },
      { label: "备用/下载", url: urls.trade_login_alt || urls.software },
      { label: "官网首页", url: urls.portal },
      { label: "下载 App", url: urls.software },
    ].filter((l) => l.url);
    const row = el("div", "broker-link-row");
    links.forEach((l) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "broker-link-btn";
      btn.dataset.brokerUrl = l.url;
      btn.textContent = l.label;
      row.appendChild(btn);
    });
    container.appendChild(row);
    if (b.order_hint) container.appendChild(el("p", "muted", b.order_hint));
  }

  function renderWafRecovery(container, waf) {
    if (!container || !waf) return;
    container.innerHTML = "";
    const box = el("div", "broker-app-guide");
    box.appendChild(el("h3", "", `${waf.broker_label || "券商"} · WAF 拦截恢复`));
    box.appendChild(el("p", "warn", waf.meaning || "页面显示 Nginx forbidden 时，是券商 WAF 拦截了你的公网 IP。"));
    const ol = el("ol", "help-steps");
    (waf.actions || []).forEach((step) => ol.appendChild(el("li", "", step)));
    box.appendChild(ol);
    const row = el("div", "broker-link-row");
    (waf.fallback_urls || []).forEach((l) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "broker-link-btn primary";
      btn.dataset.brokerUrl = l.url;
      btn.textContent = l.label || l.url;
      row.appendChild(btn);
    });
    box.appendChild(row);
    container.appendChild(box);
  }

  function renderHelpGuide(container, section) {
    if (!container) return;
    const sections = {
      start: {
        title: "三步上手（新投资者）",
        html: `
          <ol class="help-steps">
            <li><strong>更新数据</strong> — 智能选股页 →「更新数据」</li>
            <li><strong>运行选股</strong> —「运行智能选股」，点击表格行查看原因与评分</li>
            <li><strong>模拟练习</strong> — 启动 Paper，用真实行情验证策略</li>
            <li><strong>策略验证</strong> —「策略验证」页运行 T+1 自验证与学习</li>
            <li><strong>券商辅助</strong> — 连接券商 → 在官方 App 亲自确认下单</li>
          </ol>
          <p class="help-callout">核心原则：系统只<strong>预填</strong>，不自动扣款。</p>`,
      },
      broker: {
        title: "券商登录说明",
        html: `
          <ul class="help-list">
            <li><strong>东方财富 / 华泰</strong>：点「连接」在浏览器打开官方登录页。</li>
            <li><strong>同花顺</strong>：无统一网页交易，请下载 App → 绑定券商账户 → 在 App 内下单。</li>
            <li>若显示 <strong>403</strong>：换备用链接或直接用券商/同花顺 App。</li>
            <li>系统只预填订单，<strong>你必须在官方 App 亲自确认</strong>。</li>
          </ul>`,
      },
      legal: {
        title: "免责说明（必读）",
        html: `
          <ul class="help-list warn-list">
            <li>不构成投资建议，不承诺收益。</li>
            <li>不自动真实下单；不保存交易密码。</li>
            <li>T+1、涨跌停、停牌可能导致无法成交。</li>
            <li>模型会失效；每日学习用于改进算法，不等于盈利保证。</li>
          </ul>
          <p class="muted">完整版：<code>docs/USER_GUIDE.md</code></p>`,
      },
      advanced: {
        title: "进阶（有经验用户）",
        html: `
          <ul class="help-list">
            <li><strong>高级·总览</strong> — 系统体检、日报、影子实盘</li>
            <li><strong>高级·数据</strong> — 全市场同步、实时行情</li>
            <li><strong>门控</strong> — 真实资金通道默认关闭；无人值守需管理员</li>
          </ul>`,
      },
    };
    const s = sections[section] || sections.start;
    container.innerHTML = `<section class="help-section-focus"><h3>${s.title}</h3>${s.html}</section>`;
  }

  function renderPaperMonitor(container, data) {
    if (!container) return;
    container.innerHTML = "";
    const d = data?.data || data || {};
    const banner = el("div", d.enabled ? "banner banner-ok" : "banner banner-warn",
      d.enabled
        ? "实时行情监控已开启 — 仅真实报价触发买卖（Paper 页每 15 分钟自动刷新）"
        : "监控未开启 — 从选股导入组合后自动开启");
    container.appendChild(banner);
    if (d.last_error) {
      container.appendChild(el("div", "banner banner-warn", d.last_error));
    }
    const qm = d.last_quote_meta || d.quote_meta || {};
    if (qm.retrieved_at || qm.quote_count) {
      const stale = qm.stale_fallback ? " · 缓存回落" : "";
      container.appendChild(el("p", "muted", `行情源 ${qm.provider || "—"} · ${qm.quote_count || 0} 只 · ${qm.retrieved_at || "—"}${stale}`));
    }
    const rows = (d.watchlist_live || []).map((r) => [
      r.symbol,
      r.name || "—",
      r.live_price ?? "—",
      r.held ? `持仓 ${r.quantity}` : "观察",
      r.trade_zones ? `买 ${r.trade_zones.buy_zone_low}–${r.trade_zones.buy_zone_high}` : "—",
    ]);
    renderTable(container.appendChild(el("div", "")), ["代码", "名称", "实时价", "状态", "买入区间"], rows, "暂无监控标的");
    const sigs = (d.signals_recent || []).slice(-8).map((s) => [
      (s.ts || "").slice(11, 19),
      s.symbol,
      s.side || s.action,
      s.live_price ?? "—",
      s.reason || "",
    ]);
    if (sigs.length) {
      container.appendChild(el("h4", "", "最近信号"));
      renderTable(container.appendChild(el("div", "")), ["时间", "代码", "动作", "价格", "原因"], sigs, "");
    }
  }

  function renderPaperReports(container, data) {
    if (!container) return;
    container.innerHTML = "";
    const reports = data?.data?.reports || data?.reports || [];
    if (!reports.length) {
      container.appendChild(renderEmpty("暂无收盘报告", "点击「生成今日收盘报告」", ""));
      return;
    }
    const rows = reports.map((r) => [
      r.trade_date,
      r.label || "Paper 操作日报",
      `<a href="${r.download_url}" target="_blank" rel="noopener">下载 PDF</a>`,
    ]);
    renderTable(container, ["日期", "报告", "下载"], rows, "");
  }

  global.QuantOSUI = {
    renderPaperMonitor,
    renderPaperReports,
    renderCardGrid,
    renderTable,
    renderBadge,
    renderEmpty,
    renderBlockers,
    renderKeyValues,
    renderReportSummary,
    renderAgentPanel,
    renderActionLog,
    renderJob,
    renderScreener,
    renderSelectionGuide,
    renderLiveRadar,
    renderBrokerLinks,
    renderBrokerSession,
    renderWatchlist,
    renderExecutionPaths,
    renderBeginnerGuide,
    renderHelpGuide,
    renderBrokerOfficialLinks,
    renderWafRecovery,
    renderAutopilot,
    renderModelValidation,
    renderGatewayReadiness,
    renderProof,
    renderStrategyLearning,
    renderDossier,
    renderStockAnalysis,
    renderStockDetailModal,
    openStockDetailModal,
    closeStockDetailModal,
    renderSetupCenter,
    toast,
    setLoading,
    countPrimaryRawJson,
  };
})(window);
