/** Typed frontend action registry — single source for portal controls. */
(function (global) {
  const REGISTRY = {
    "system.doctor": { label_zh: "系统体检", role: "market:read", method: "POST", endpoint: "/api/v1/system/doctor" },
    "market.update": { label_zh: "更新数据", role: "research:run", method: "POST", endpoint: "/api/v1/market/update" },
    "research.dailyRun": { label_zh: "生成日报", role: "research:run", method: "POST", endpoint: "/api/v1/research/daily-run" },
    "research.backtest": { label_zh: "运行回测", role: "research:run", method: "POST", endpoint: "/api/v1/research/backtest" },
    "research.candidate": { label_zh: "候选门", role: "research:run", method: "POST", endpoint: "/api/v1/research/candidate" },
    "research.agentsRun": { label_zh: "多智能体研究", role: "research:run", method: "POST", endpoint: "/api/v1/research/agents/run" },
    "paper.start": { label_zh: "启动 Paper", role: "mode:promote", method: "POST", endpoint: "/api/v1/paper/start" },
    "paper.stop": { label_zh: "停止 Paper", role: "mode:promote", method: "POST", endpoint: "/api/v1/paper/stop" },
    "paper.order": { label_zh: "Paper 模拟下单", role: "paper:trade", method: "POST", endpoint: "/api/v1/paper/order" },
    "paper.markToMarket": { label_zh: "Paper 按市价刷新", role: "paper:trade", method: "POST", endpoint: "/api/v1/paper/mark-to-market" },
    "shadow.start": { label_zh: "启动 Shadow", role: "mode:promote", method: "POST", endpoint: "/api/v1/shadow/start" },
    "shadow.stop": { label_zh: "停止 Shadow", role: "mode:promote", method: "POST", endpoint: "/api/v1/shadow/stop" },
    "risk.halt": { label_zh: "紧急停机", role: "risk:halt", method: "POST", endpoint: "/api/v1/risk/halt" },
    "risk.resetRequest": { label_zh: "申请解除停机", role: "risk:reset_request", method: "POST", endpoint: "/api/v1/risk/reset-request" },
    "risk.resetConfirm": { label_zh: "确认解除停机", role: "risk:reset_confirm", method: "POST", endpoint: "/api/v1/risk/reset-confirm" },
    "native.vnpyAccept": { label_zh: "vn.py 原生验收", role: "research:run", method: "POST", endpoint: "/api/v1/native/vnpy/acceptance" },
    "native.qlibAccept": { label_zh: "Qlib 原生验收", role: "research:run", method: "POST", endpoint: "/api/v1/native/qlib/acceptance" },
    "native.vnpyStart": { label_zh: "启动 vn.py", role: "research:run", method: "POST", endpoint: "/api/v1/quantos/vnpy/start" },
    "native.qlibBaseline": { label_zh: "Qlib 基线", role: "research:run", method: "POST", endpoint: "/api/v1/quantos/qlib/baseline" },
    "broker.readonlyConnect": { label_zh: "只读连接向导", role: "portal:admin", method: "POST", endpoint: "/api/v1/brokers/readonly-connect" },
    "trading.preflight": { label_zh: "执行预检", role: "market:read", method: "GET", endpoint: "/api/v1/trading/preflight" },
    "trading.executeAllocation": { label_zh: "一键执行组合", role: "mode:promote", method: "POST", endpoint: "/api/v1/trading/execute-allocation" },
    "autopilot.executeTicket": { label_zh: "无人值守执行票据", role: "mode:promote", method: "POST", endpoint: "/api/v1/autopilot/execute-ticket" },
  };

  const DATA_ACTION_MAP = {
    doctor: "system.doctor",
    "market-update": "market.update",
    "daily-run": "research.dailyRun",
    backtest: "research.backtest",
    "candidate-gate": "research.candidate",
    "agents-run": "research.agentsRun",
    "paper-start": "paper.start",
    "paper-stop": "paper.stop",
    "shadow-start": "shadow.start",
    "shadow-stop": "shadow.stop",
    halt: "risk.halt",
    "reset-request": "risk.resetRequest",
    "reset-confirm": "risk.resetConfirm",
    "native-vnpy-accept": "native.vnpyAccept",
    "native-qlib-accept": "native.qlibAccept",
  };

  global.QuantOSActionRegistry = { REGISTRY, DATA_ACTION_MAP };
})(window);
