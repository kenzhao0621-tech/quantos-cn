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
      container.appendChild(el("p", "muted", "无阻塞项"));
      return;
    }
    const ul = el("ul", "blocker-list");
    blockers.forEach((b) => {
      const li = el("li", "blocker-item");
      li.appendChild(renderBadge("阻塞", "warn"));
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
    const maxScore = Math.max(...vm.rows.map((r) => r.score)) || 1;
    const table = el("table", "data-table");
    table.innerHTML =
      "<thead><tr><th>#</th><th>代码</th><th>最新价</th><th>今日%</th><th>20日%</th><th>60日%</th><th>趋势%</th><th>波动</th><th>成交额(亿)</th><th>评分</th><th>走势</th></tr></thead>";
    const tb = el("tbody");
    vm.rows.forEach((r) => {
      const tr = el("tr");
      const barW = Math.max(6, Math.round((r.score / maxScore) * 60));
      const up = (r.ret_20 || 0) >= 0;
      tr.innerHTML =
        `<td>${r.rank}</td>` +
        `<td><b>${r.symbol}</b></td>` +
        `<td class="num">${r.last_close}</td>` +
        `<td class="${r.last_pct >= 0 ? "up" : "down"}">${r.last_pct >= 0 ? "+" : ""}${r.last_pct}</td>` +
        `<td class="${r.ret_20 >= 0 ? "up" : "down"}">${r.ret_20 >= 0 ? "+" : ""}${r.ret_20}</td>` +
        `<td class="${r.ret_60 >= 0 ? "up" : "down"}">${r.ret_60 >= 0 ? "+" : ""}${r.ret_60}</td>` +
        `<td class="${r.trend >= 0 ? "up" : "down"}">${r.trend >= 0 ? "+" : ""}${r.trend}</td>` +
        `<td class="num">${r.vol_20}</td>` +
        `<td class="num">${(r.avg_amount / 1e8).toFixed(2)}</td>` +
        `<td><span class="score-bar" style="width:${barW}px"></span> ${r.score.toFixed(2)}</td>` +
        `<td>${sparklineSvg(r.spark, up)}</td>`;
      tb.appendChild(tr);
    });
    table.appendChild(tb);
    container.appendChild(table);
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
    toast,
    setLoading,
    countPrimaryRawJson,
  };
})(window);
