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
    const table = el("table", "data-table");
    table.innerHTML =
      "<thead><tr><th>#</th><th>代码</th><th>板块</th><th>价格</th><th>收益区间%</th><th>下行%</th><th>崩盘</th><th>可买</th><th>5000元</th><th>综合分</th><th>资格</th><th>走势</th></tr></thead>";
    const tb = el("tbody");
    vm.rows.forEach((r) => {
      const tr = el("tr");
      const barW = Math.max(6, Math.round(((r.final_score ?? r.score) / maxScore) * 60));
      const up = (r.ret_20 || 0) >= 0;
      const elig = r.eligibility || "—";
      const eligCls = elig === "PAPER_ELIGIBLE" ? "up" : (elig === "BLOCKED" ? "down" : "");
      const retRange = `${r.expected_return_lo_pct ?? "—"}~${r.expected_return_hi_pct ?? "—"}`;
      const afford = r.affordable_lots ? `${r.affordable_lots}手/${r.suggested_qty || 0}股` : "—";
      tr.innerHTML =
        `<td>${r.rank}</td>` +
        `<td><button type="button" class="symbol-link" data-dossier-symbol="${r.symbol}" title="${(r.reasons_not_to_trade || []).join("；")}">${r.symbol}</button>
          <button type="button" class="mini-btn" data-watchlist-add="${r.symbol}" data-watchlist-name="${r.name || ""}" title="收藏">★</button></td>` +
        `<td>${r.sector || "—"}</td>` +
        `<td class="num">${r.live_price || r.last_close}</td>` +
        `<td class="num">${retRange}</td>` +
        `<td class="num">${r.downside_risk_pct ?? "—"}</td>` +
        `<td class="num">${r.crash_risk ?? "—"}</td>` +
        `<td>${r.valid_for_purchase ? "是" : "否"}</td>` +
        `<td class="num">${afford}</td>` +
        `<td><span class="score-bar" style="width:${barW}px"></span> ${(r.final_score ?? r.score).toFixed(2)}</td>` +
        `<td class="${eligCls}">${elig}${r.valid_for_purchase && r.suggested_qty ? ` <button type="button" class="mini-btn" data-live-order="${r.symbol}" data-live-name="${r.name || ""}" data-live-qty="${r.suggested_qty}" data-live-price="${r.last_close}">实盘</button>` : ""}</td>` +
        `<td>${sparklineSvg(r.spark, up)}</td>`;
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    container.appendChild(table);
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
      const banner = el("div", d.ready_for_order_ticket ? "banner banner-ok" : "banner banner-warn",
        d.ready_for_order_ticket ? "准入检查通过：可生成订单票据" : "准入检查未通过");
      container.appendChild(banner);
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

  function renderProof(container, proof) {
    if (!container) return;
    container.innerHTML = "";
    const d = proof?.data || proof || {};
    if (!d || d.blocked) {
      container.appendChild(renderEmpty("暂无验证", d.blocker_reason || "需要至少两个交易日数据", "先更新数据，再点击「验证昨日选股」"));
      return;
    }
    const banner = el("div", d.verdict === "PASS" ? "banner banner-ok" : "banner banner-warn");
    banner.innerHTML =
      `T+1 验证：${d.signal_date} 选股 → ${d.proof_date} 收盘。` +
      `平均收益 <b>${d.avg_return}%</b>，市场中位数 <b>${d.benchmark_median}%</b>，` +
      `正收益率 <b>${d.hit_rate}%</b>，跑赢率 <b>${d.win_rate_vs_median}%</b>。` +
      `结论：<b>${d.verdict}</b>`;
    container.appendChild(banner);
    if (d.what_to_adjust?.length) {
      const notes = el("ul", "checklist");
      d.what_to_adjust.forEach((n) => notes.appendChild(el("li", "", n)));
      container.appendChild(notes);
    }
    const rows = (d.proofs || []).slice(0, 10).map((p) => [
      p.rank,
      p.symbol,
      p.next_day_return >= 0 ? `+${p.next_day_return}%` : `${p.next_day_return}%`,
      p.outperformance >= 0 ? `+${p.outperformance}%` : `${p.outperformance}%`,
      p.passed ? "达标" : "复盘",
      p.diagnosis,
    ]);
    renderTable(container.appendChild(el("div", "")), ["#", "代码", "T+1收益", "跑赢中位数", "结果", "归因"], rows, "暂无验证明细");
  }

  function renderDossier(container, dossier) {
    if (!container) return;
    container.innerHTML = "";
    const d = dossier?.data || dossier || {};
    if (!d.symbol) {
      container.appendChild(renderEmpty("暂无个股解释", "先运行选股并选择候选", ""));
      return;
    }
    const box = el("div", "dossier-card");
    box.appendChild(el("h3", "", `${d.symbol} · 候选解释`));
    box.appendChild(el("p", "", d.plain_language || "暂无解释"));
    if (d.candidate?.reasons?.length) {
      const ul = el("ul", "checklist");
      d.candidate.reasons.forEach((r) => ul.appendChild(el("li", "", r)));
      box.appendChild(ul);
    }
    if (d.institutional_report?.factors?.length) {
      box.appendChild(el("h3", "", `机构因子报告 · ${d.institutional_report.weighted_score} / 100`));
      const rows = d.institutional_report.factors.map((f) => [
        f.name,
        `${Math.round(f.weight * 100)}%`,
        Math.round(f.score * 100),
        f.evidence,
      ]);
      const sub = el("div", "");
      box.appendChild(sub);
      renderTable(sub, ["因子", "权重", "评分", "证据"], rows, "暂无因子报告");
      if (d.institutional_report.methodology) {
        box.appendChild(el("p", "muted", d.institutional_report.methodology));
      }
    }
    if (d.risk_notes?.length) {
      const risk = el("div", "banner banner-warn", "风险边界：" + d.risk_notes.join("；"));
      box.appendChild(risk);
    }
    container.appendChild(box);
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

  global.QuantOSUI = {
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
    renderLiveRadar,
    renderBrokerLinks,
    renderBrokerSession,
    renderWatchlist,
    renderExecutionPaths,
    renderBeginnerGuide,
    renderAutopilot,
    renderModelValidation,
    renderGatewayReadiness,
    renderProof,
    renderDossier,
    renderSetupCenter,
    toast,
    setLoading,
    countPrimaryRawJson,
  };
})(window);
