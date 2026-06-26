/** Unified QuantOS CN API client — cwd-independent backend envelope. */
(function (global) {
  const STORAGE_KEY = "quantos_api_key";
  const ROLE_KEY = "quantos_role";

  const DEV_KEYS = {
    admin: "demo-local-key-change-in-prod",
  };

  const DEFAULT_ROLE = "admin";

  function friendlyApiError(res) {
    if (res.httpStatus === 403) {
      return "权限不足：请重新进入平台";
    }
    if (res.httpStatus === 404) {
      return "接口不存在：请重启门户（终端执行 bash scripts/start-portal.sh）";
    }
    if (res.httpStatus === 401) {
      return "未登录或会话过期，请重新登录";
    }
    if (res.status === "timeout" || res.error?.code === "TIMEOUT") {
      return "请求超时：智能选股请改用「收盘数据」模式，或先在高级·数据刷新行情";
    }
    if (res.status === "network_error" || res.error?.code === "NETWORK") {
      return "无法连接 Gateway — 请运行 make app 或 bash scripts/start-portal.sh";
    }
    return res.error?.message || res.error?.code || "请求失败";
  }

  function resolveApiBase() {
    const stored = sessionStorage.getItem("quantos_api_base") || localStorage.getItem("quantos_api_base");
    if (stored) return String(stored).replace(/\/$/, "");
    const origin = window.location.origin;
    if (!origin || origin === "null" || origin.startsWith("file:")) {
      return "http://127.0.0.1:8787";
    }
    return origin.replace(/\/$/, "");
  }

  class ApiClient {
    constructor() {
      this.base = resolveApiBase();
    }

    get apiKey() {
      return sessionStorage.getItem(STORAGE_KEY) || "";
    }

    get role() {
      return sessionStorage.getItem(ROLE_KEY) || "";
    }

    setSession(role, apiKey) {
      sessionStorage.setItem(ROLE_KEY, role);
      sessionStorage.setItem(STORAGE_KEY, apiKey);
    }

    clearSession() {
      sessionStorage.removeItem(ROLE_KEY);
      sessionStorage.removeItem(STORAGE_KEY);
    }

    async ping() {
      const res = await this.request("/health", { skipAuth: true, timeoutMs: 5000 });
      return res.ok || res.httpStatus === 200;
    }

    async login(role = DEFAULT_ROLE) {
      const effectiveRole = DEV_KEYS[role] ? role : DEFAULT_ROLE;
      const apiKey = DEV_KEYS[effectiveRole];
      if (!apiKey) throw new Error(`未知角色: ${role}`);
      const up = await this.ping();
      if (!up) {
        throw new Error(
          `无法连接 Gateway（${this.base}）。请在终端运行：make app  或  bash scripts/start-portal.sh`,
        );
      }
      const res = await this.request("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ role: effectiveRole }),
        skipAuth: true,
      });
      if (!res.ok) throw new Error(res.error?.message || "登录失败");
      this.setSession(effectiveRole, apiKey);
      return res;
    }

    async request(path, options = {}) {
      const request_id = crypto.randomUUID();
      const trace_id = crypto.randomUUID();
      const timeoutMs = options.timeoutMs || (
        path.includes("/market/sync-all") ? 240000
        : path.includes("/market/live-refresh") ? 300000
        : path.includes("/autopilot/order-ticket") ? 45000
        : path.includes("/screener/run") ? 120000
        : 90000
      );
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      const headers = {
        "Content-Type": "application/json",
        "X-Request-Id": request_id,
        "X-Trace-Id": trace_id,
        ...(options.headers || {}),
      };
      if (!options.skipAuth && this.apiKey) {
        headers["X-API-Key"] = this.apiKey;
      }
      let res;
      try {
        const { timeoutMs: _timeout, ...fetchOptions } = options;
        res = await fetch(`${this.base}${path}`, { ...fetchOptions, headers, signal: controller.signal });
      } catch (err) {
        return {
          ok: false,
          status: err.name === "AbortError" ? "timeout" : "network_error",
          request_id,
          trace_id,
          error: { code: err.name === "AbortError" ? "TIMEOUT" : "NETWORK", message: err.name === "AbortError" ? `请求超时（${timeoutMs}ms）` : err.message },
          errors: [{ code: err.name === "AbortError" ? "TIMEOUT" : "NETWORK", message: err.message }],
          data: null,
        };
      } finally {
        clearTimeout(timer);
      }
      let json;
      try {
        json = await res.json();
      } catch {
        json = { ok: false, error: { message: res.statusText } };
      }
      return {
        ...json,
        httpStatus: res.status,
        request_id: json.request_id || request_id,
        trace_id: json.trace_id || trace_id,
      };
    }
  }

  global.QuantOSApi = new ApiClient();
  global.QuantOSDevKeys = DEV_KEYS;
  global.QuantOSFriendlyError = friendlyApiError;
})(window);
