/** Unified QuantOS CN API client — cwd-independent backend envelope. */
(function (global) {
  const STORAGE_KEY = "quantos_api_key";
  const ROLE_KEY = "quantos_role";

  const DEV_KEYS = {
    admin: "demo-local-key-change-in-prod",
    investor: "dev-investor-key",
    researcher: "dev-researcher-key",
    viewer: "svc-portal-read",
    service_risk: "dev-service-risk-key",
    service_research: "svc-quant-pipeline",
  };

  function friendlyApiError(res) {
    if (res.httpStatus === 403) {
      return "权限不足：请选择「新手投资者」或 admin 角色登录";
    }
    if (res.httpStatus === 404) {
      return "接口不存在：请重启门户（终端执行 bash scripts/start-portal.sh）";
    }
    if (res.httpStatus === 401) {
      return "未登录或会话过期，请重新登录";
    }
    return res.error?.message || res.error?.code || "请求失败";
  }

  class ApiClient {
    constructor() {
      this.base = window.location.origin;
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

    async login(role) {
      const apiKey = DEV_KEYS[role];
      if (!apiKey) throw new Error(`未知角色: ${role}`);
      const res = await this.request("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ role }),
        skipAuth: true,
      });
      if (!res.ok) throw new Error(res.error?.message || "登录失败");
      this.setSession(role, apiKey);
      return res;
    }

    async request(path, options = {}) {
      const request_id = crypto.randomUUID();
      const trace_id = crypto.randomUUID();
      const timeoutMs = options.timeoutMs || (
        path.includes("/market/sync-all") ? 240000
        : path.includes("/autopilot/order-ticket") ? 45000
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
