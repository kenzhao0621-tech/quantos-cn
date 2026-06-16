/** Unified QuantOS CN API client — cwd-independent backend envelope. */
(function (global) {
  const STORAGE_KEY = "quantos_api_key";
  const ROLE_KEY = "quantos_role";

  const DEV_KEYS = {
    admin: "demo-local-key-change-in-prod",
    researcher: "dev-researcher-key",
    viewer: "svc-portal-read",
    service_risk: "dev-service-risk-key",
    service_research: "svc-quant-pipeline",
  };

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
        res = await fetch(`${this.base}${path}`, { ...options, headers });
      } catch (err) {
        return {
          ok: false,
          status: "network_error",
          request_id,
          trace_id,
          error: { code: "NETWORK", message: err.message },
          errors: [{ code: "NETWORK", message: err.message }],
          data: null,
        };
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
})(window);
