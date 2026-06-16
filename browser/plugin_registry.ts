import type { AuthorizedTarget, StealthLabConfig, TargetRegistry } from "./target_policy.ts";
import { loadTargetRegistry } from "./target_policy.ts";

export type PluginName = "stealth" | "playwright-extra";

export type PluginErrorCode =
  | "PLUGIN_NOT_ALLOWED"
  | "PLUGIN_DENY_BY_DEFAULT"
  | "STEALTH_LAB_DISABLED"
  | "STEALTH_THIRD_PARTY_FORBIDDEN"
  | "STEALTH_OWNERSHIP_REQUIRED"
  | "TARGET_POLICY_REQUIRED"
  | "PLAYWRIGHT_EXTRA_NOT_INSTALLED"
  | "PRODUCTION_PROFILE_FORBIDDEN";

export interface PluginContext {
  profile: "production" | "stealth_lab" | "test";
  target?: AuthorizedTarget;
  targetPolicyPassed: boolean;
  registry?: TargetRegistry;
  configPath?: string;
}

export interface PluginLoadSuccess {
  ok: true;
  host: "plain-playwright" | "playwright-extra";
  plugin?: string;
}

export interface PluginLoadFailure {
  ok: false;
  code: PluginErrorCode;
  message: string;
}

export type PluginLoadResult = PluginLoadSuccess | PluginLoadFailure;

export const DEFAULT_STEALTH_LAB_CONFIG: StealthLabConfig = {
  enabled: false,
  permitted_target_classes: ["localhost", "owned_staging"],
  third_party_targets_permitted: false,
  network_egress_allowlist_required: true,
  artifacts_required: true,
  human_approval_required: true,
};

/**
 * playwright-extra is an optional peer dependency — NOT installed by default.
 * Production data profiles must use plain @playwright/test / playwright only.
 */
export const PLAYWRIGHT_EXTRA_OPTIONAL_PEER = "playwright-extra";

const DENY_BY_DEFAULT_PLUGINS = new Set<PluginName>(["stealth"]);

const PRODUCTION_FORBIDDEN_PLUGINS = new Set<PluginName>(["stealth"]);

export function getStealthLabConfigFromRegistry(context: PluginContext): StealthLabConfig {
  const registry = context.registry ?? loadTargetRegistry(context.configPath);
  return registry.stealth_lab ?? DEFAULT_STEALTH_LAB_CONFIG;
}

export function isThirdPartyTarget(target: AuthorizedTarget): boolean {
  if (target.owned_security_test_target) return false;
  const localClasses = new Set(["localhost", "owned_staging", "local"]);
  return !localClasses.has(target.target_class);
}

export function canLoadStealthPlugin(context: PluginContext): PluginLoadResult {
  if (!context.targetPolicyPassed) {
    return {
      ok: false,
      code: "TARGET_POLICY_REQUIRED",
      message: "Target policy must pass before any plugin loading",
    };
  }

  if (context.profile === "production") {
    return {
      ok: false,
      code: "PRODUCTION_PROFILE_FORBIDDEN",
      message: "Stealth plugin is forbidden in production data profile",
    };
  }

  const stealthLab = getStealthLabConfigFromRegistry(context);
  if (!stealthLab.enabled) {
    return {
      ok: false,
      code: "STEALTH_LAB_DISABLED",
      message: "Stealth lab is disabled by default",
    };
  }

  if (!context.target) {
    return {
      ok: false,
      code: "STEALTH_OWNERSHIP_REQUIRED",
      message: "Stealth plugin requires an authorized target context",
    };
  }

  if (isThirdPartyTarget(context.target) && !stealthLab.third_party_targets_permitted) {
    return {
      ok: false,
      code: "STEALTH_THIRD_PARTY_FORBIDDEN",
      message: `Stealth plugin cannot load for third-party target ${context.target.id}`,
    };
  }

  if (!context.target.owned_security_test_target) {
    return {
      ok: false,
      code: "STEALTH_OWNERSHIP_REQUIRED",
      message: `Target ${context.target.id} is not marked owned_security_test_target`,
    };
  }

  if (!stealthLab.permitted_target_classes.includes(context.target.target_class)) {
    return {
      ok: false,
      code: "PLUGIN_NOT_ALLOWED",
      message: `Target class ${context.target.target_class} is not permitted for stealth lab`,
    };
  }

  return { ok: true, host: "playwright-extra", plugin: "stealth" };
}

export async function tryResolvePlaywrightExtra(): Promise<PluginLoadResult> {
  try {
    await import("playwright-extra");
    return { ok: true, host: "playwright-extra" };
  } catch {
    return {
      ok: false,
      code: "PLAYWRIGHT_EXTRA_NOT_INSTALLED",
      message:
        "playwright-extra is an optional peer dependency and is not installed by default",
    };
  }
}

export async function loadPlugin(
  name: PluginName,
  context: PluginContext,
): Promise<PluginLoadResult> {
  if (!context.targetPolicyPassed) {
    return {
      ok: false,
      code: "TARGET_POLICY_REQUIRED",
      message: "Target policy must pass before plugin loading",
    };
  }

  if (!DENY_BY_DEFAULT_PLUGINS.has(name)) {
    return {
      ok: false,
      code: "PLUGIN_DENY_BY_DEFAULT",
      message: `Plugin ${name} is not on the allowlist`,
    };
  }

  if (context.profile === "production" && PRODUCTION_FORBIDDEN_PLUGINS.has(name)) {
    return {
      ok: false,
      code: "PRODUCTION_PROFILE_FORBIDDEN",
      message: `Plugin ${name} is forbidden in production profile`,
    };
  }

  if (name === "stealth") {
    const stealthDecision = canLoadStealthPlugin(context);
    if (!stealthDecision.ok) return stealthDecision;

    const extra = await tryResolvePlaywrightExtra();
    if (!extra.ok) return extra;

    return { ok: true, host: "playwright-extra", plugin: "stealth" };
  }

  return {
    ok: false,
    code: "PLUGIN_DENY_BY_DEFAULT",
    message: `Unknown or disallowed plugin ${name}`,
  };
}

export function productionProfileHasNoStealth(context: PluginContext): boolean {
  if (context.profile !== "production") return true;
  const decision = canLoadStealthPlugin({ ...context, profile: "stealth_lab" });
  return !decision.ok;
}
