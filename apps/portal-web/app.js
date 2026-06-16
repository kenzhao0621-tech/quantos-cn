const API_BASE = window.location.origin;
const API_KEY = "demo-local-key-change-in-prod";

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...(options.headers || {}),
    },
  });
  return res.json();
}

function setPill(id, text, danger = false) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.classList.toggle("kill", danger);
}

async function refresh() {
  try {
    const [status, risk, agents, pnl, pos, sidecar, reports] = await Promise.all([
      api("/api/v1/status"),
      api("/api/v1/risk/status"),
      api("/api/v1/agents"),
      api("/api/v1/paper/pnl"),
      api("/api/v1/paper/positions"),
      api("/api/v1/sidecar/gc-mgc/status"),
      api("/api/v1/research/reports"),
    ]);

    if (status.ok && status.data) {
      const d = status.data;
      setPill("mode-pill", `MODE: ${d.mode}`);
      setPill("session-pill", `SESSION: ${d.market_session}`);
      setPill("freshness-pill", `DATA: ${d.data_status}`);
      setPill("capital-pill", `CAPITAL: ¥${d.capital}`);
      setPill("budget-pill", `LOSS BUDGET: ¥${d.remaining_loss_budget}`);
      setPill("kill-pill", `KILL: ${d.kill_switch}`, d.kill_switch === "HALTED");
      setPill("run-pill", `AUTONOMOUS: ${d.autonomous_label}`);
      document.getElementById("risk-detail").textContent = JSON.stringify(d, null, 2);
    }

    if (risk.ok && risk.data) {
      const blockers = (risk.data.blockers || []).join(", ") || "none";
      document.getElementById("risk-detail").textContent += `\n\nBlockers: ${blockers}`;
    }

    const agentList = document.getElementById("agent-list");
    agentList.innerHTML = "";
    if (agents.ok && agents.data?.agents) {
      agents.data.agents.forEach((a) => {
        const li = document.createElement("li");
        li.textContent = `${a.name} (${a.id})${a.isolated ? " [SIDECAR]" : ""}`;
        agentList.appendChild(li);
      });
    }

    if (pnl.ok && pnl.data) {
      document.getElementById("paper-pnl").textContent = JSON.stringify(pnl.data, null, 2);
    }
    if (pos.ok && pos.data) {
      document.getElementById("paper-positions").textContent = JSON.stringify(pos.data, null, 2);
    }
    if (sidecar.ok && sidecar.data) {
      document.getElementById("sidecar-status").textContent = JSON.stringify(sidecar.data, null, 2);
    }

    const reportList = document.getElementById("report-list");
    reportList.innerHTML = "";
    if (reports.ok && reports.data?.reports) {
      reports.data.reports.forEach((r) => {
        const li = document.createElement("li");
        li.textContent = r;
        reportList.appendChild(li);
      });
    }
  } catch (err) {
    document.getElementById("risk-detail").textContent = `Error: ${err.message}`;
  }
}

document.getElementById("btn-refresh").addEventListener("click", refresh);
document.getElementById("btn-halt").addEventListener("click", async () => {
  await api("/api/v1/risk/halt", { method: "POST", body: JSON.stringify({ reason: "portal_halt" }) });
  await refresh();
});

refresh();
setInterval(refresh, 30000);
