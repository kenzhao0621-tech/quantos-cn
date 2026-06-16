import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { isIP } from "node:net";
import { lookup } from "node:dns/promises";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DEFAULT_CONFIG_PATH = resolve(__dirname, "../config/authorized_data_targets.yaml");

export type PolicyErrorCode =
  | "TARGET_NOT_AUTHORIZED"
  | "TARGET_PATH_NOT_AUTHORIZED"
  | "TARGET_REDIRECT_NOT_AUTHORIZED"
  | "TARGET_RESOLUTION_UNSAFE";

export interface AuthorizedTarget {
  id: string;
  domain: string;
  target_class: string;
  owned_security_test_target: boolean;
  allowed_paths: string[];
  purpose: string;
  data_types: string[];
  authentication: string;
  session_state_path: string | null;
  maximum_requests_per_run: number;
  minimum_interval_seconds: number;
  expected_content_types: string[];
  stop_on_401: boolean;
  stop_on_403: boolean;
  stop_on_429: boolean;
  stop_on_captcha: boolean;
  owner_or_authorization_note: string;
  enabled: boolean;
}

export interface StealthLabConfig {
  enabled: boolean;
  permitted_target_classes: string[];
  third_party_targets_permitted: boolean;
  network_egress_allowlist_required: boolean;
  artifacts_required: boolean;
  human_approval_required: boolean;
}

export interface TargetRegistry {
  targets: AuthorizedTarget[];
  stealth_lab: StealthLabConfig;
}

export interface PolicySuccess {
  ok: true;
  target: AuthorizedTarget;
}

export interface PolicyFailure {
  ok: false;
  code: PolicyErrorCode;
  message: string;
}

export type PolicyResult = PolicySuccess | PolicyFailure;

const PRIVATE_IPV4_RANGES: Array<[number, number]> = [
  [0x0a000000, 0x0affffff], // 10.0.0.0/8
  [0xac100000, 0xac1fffff], // 172.16.0.0/12
  [0xc0a80000, 0xc0a8ffff], // 192.168.0.0/16
  [0x7f000000, 0x7fffffff], // 127.0.0.0/8
  [0xa9fe0000, 0xa9feffff], // 169.254.0.0/16 link-local
];

function ipv4ToInt(ip: string): number | null {
  const parts = ip.split(".").map((p) => Number(p));
  if (parts.length !== 4 || parts.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) {
    return null;
  }
  return ((parts[0]! << 24) >>> 0) + (parts[1]! << 16) + (parts[2]! << 8) + parts[3]!;
}

export function isPrivateOrLocalAddress(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/\.$/, "");
  if (
    normalized === "localhost" ||
    normalized.endsWith(".localhost") ||
    normalized === "::1" ||
    normalized === "[::1]"
  ) {
    return true;
  }

  const ipVersion = isIP(normalized);
  if (ipVersion === 4) {
    const value = ipv4ToInt(normalized);
    if (value === null) return false;
    return PRIVATE_IPV4_RANGES.some(([start, end]) => value >= start && value <= end);
  }

  if (ipVersion === 6) {
    const lower = normalized.toLowerCase();
    return (
      lower === "::1" ||
      lower.startsWith("fc") ||
      lower.startsWith("fd") ||
      lower.startsWith("fe80")
    );
  }

  return false;
}

function isLocalOwnedTargetClass(targetClass: string): boolean {
  return targetClass === "localhost" || targetClass === "owned_staging" || targetClass === "local";
}

function parseScalar(raw: string): string | number | boolean | null {
  const trimmed = raw.trim();
  if (trimmed === "null") return null;
  if (trimmed === "true") return true;
  if (trimmed === "false") return false;
  if (/^-?\d+$/.test(trimmed)) return Number(trimmed);
  if (
    (trimmed.startsWith('"') && trimmed.endsWith('"')) ||
    (trimmed.startsWith("'") && trimmed.endsWith("'"))
  ) {
    return trimmed.slice(1, -1);
  }
  return trimmed;
}

/** Minimal YAML reader for the authorized target registry schema (no external deps). */
export function parseAuthorizedTargetsYaml(yamlText: string): TargetRegistry {
  const lines = yamlText.split(/\r?\n/);
  const targets: AuthorizedTarget[] = [];
  let stealth_lab: StealthLabConfig = {
    enabled: false,
    permitted_target_classes: [],
    third_party_targets_permitted: false,
    network_egress_allowlist_required: true,
    artifacts_required: true,
    human_approval_required: true,
  };

  let section: "none" | "targets" | "stealth_lab" = "none";
  let current: Record<string, unknown> | null = null;
  let currentKey: string | null = null;
  let listKey: string | null = null;

  const flushTarget = () => {
    if (!current || section !== "targets") return;
    targets.push(current as unknown as AuthorizedTarget);
    current = null;
  };

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    if (trimmed === "targets:") {
      flushTarget();
      section = "targets";
      continue;
    }
    if (trimmed === "stealth_lab:") {
      flushTarget();
      section = "stealth_lab";
      current = {};
      continue;
    }

    if (section === "targets" && /^- id:/.test(trimmed)) {
      flushTarget();
      current = { id: String(parseScalar(trimmed.replace(/^- id:\s*/, ""))) };
      continue;
    }

    const listMatch = trimmed.match(/^- (.+)$/);
    const kvMatch = trimmed.match(/^([^:]+):\s*(.*)$/);

    if (section === "stealth_lab" && listMatch && listKey) {
      const items = (current as Record<string, unknown>)[listKey];
      if (Array.isArray(items)) items.push(parseScalar(listMatch[1]!));
      continue;
    }

    if (kvMatch) {
      const key = kvMatch[1]!.trim();
      const valueRaw = kvMatch[2] ?? "";

      if (section === "stealth_lab") {
        if (!valueRaw && !listMatch) {
          listKey = key;
          (current as Record<string, unknown>)[key] = [];
          continue;
        }
        (current as Record<string, unknown>)[key] = parseScalar(valueRaw);
        listKey = null;
        continue;
      }

      if (section === "targets" && current) {
        if (!valueRaw) {
          currentKey = key;
          current[key] = [];
          continue;
        }
        current[key] = parseScalar(valueRaw);
        currentKey = null;
        continue;
      }
    }

    if (section === "targets" && current && currentKey && listMatch) {
      const items = current[currentKey];
      if (Array.isArray(items)) items.push(parseScalar(listMatch[1]!));
    }
  }

  flushTarget();

  if (current && section === "stealth_lab") {
    stealth_lab = current as unknown as StealthLabConfig;
  }

  return { targets, stealth_lab };
}

export function loadTargetRegistry(configPath: string = DEFAULT_CONFIG_PATH): TargetRegistry {
  if (!existsSync(configPath)) {
    throw new Error(`Authorized target config not found: ${configPath}`);
  }
  const yamlText = readFileSync(configPath, "utf8");
  return parseAuthorizedTargetsYaml(yamlText);
}

export function findTargetById(
  registry: TargetRegistry,
  targetId: string,
): AuthorizedTarget | undefined {
  return registry.targets.find((t) => t.id === targetId);
}

export function hostnameMatchesTarget(hostname: string, target: AuthorizedTarget): boolean {
  const host = hostname.toLowerCase();
  const domain = target.domain.toLowerCase();
  return host === domain || host.endsWith(`.${domain}`);
}

export function pathAllowedForTarget(pathname: string, target: AuthorizedTarget): boolean {
  if (!target.allowed_paths?.length) return false;
  return target.allowed_paths.some((prefix) => pathname.startsWith(prefix));
}

export function validateTargetRecord(
  target: AuthorizedTarget | undefined,
  url: URL,
): PolicyResult {
  if (!target) {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: `No authorized target for host ${url.hostname}`,
    };
  }

  if (!target.enabled) {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: `Target ${target.id} is disabled`,
    };
  }

  if (!hostnameMatchesTarget(url.hostname, target)) {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: `Host ${url.hostname} does not match target domain ${target.domain}`,
    };
  }

  if (url.protocol !== "https:" && url.protocol !== "http:") {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: `Unsupported protocol ${url.protocol}`,
    };
  }

  if (url.protocol === "http:" && !isLocalOwnedTargetClass(target.target_class)) {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: "Mixed-content downgrade blocked for non-local targets",
    };
  }

  if (!pathAllowedForTarget(url.pathname, target)) {
    return {
      ok: false,
      code: "TARGET_PATH_NOT_AUTHORIZED",
      message: `Path ${url.pathname} is not allowed for target ${target.id}`,
    };
  }

  const privateHost = isPrivateOrLocalAddress(url.hostname);
  if (privateHost && !isLocalOwnedTargetClass(target.target_class)) {
    return {
      ok: false,
      code: "TARGET_RESOLUTION_UNSAFE",
      message: `Private/local host ${url.hostname} is not permitted for target class ${target.target_class}`,
    };
  }

  return { ok: true, target };
}

export async function resolveHostnameSafety(
  hostname: string,
  target: AuthorizedTarget,
): Promise<PolicyResult> {
  if (isIP(hostname)) {
    if (isPrivateOrLocalAddress(hostname) && !isLocalOwnedTargetClass(target.target_class)) {
      return {
        ok: false,
        code: "TARGET_RESOLUTION_UNSAFE",
        message: `Direct private IP ${hostname} is not permitted`,
      };
    }
    return { ok: true, target };
  }

  try {
    const records = await lookup(hostname, { all: true });
    for (const record of records) {
      if (isPrivateOrLocalAddress(record.address) && !isLocalOwnedTargetClass(target.target_class)) {
        return {
          ok: false,
          code: "TARGET_RESOLUTION_UNSAFE",
          message: `DNS for ${hostname} resolves to private address ${record.address}`,
        };
      }
    }
    return { ok: true, target };
  } catch (error) {
    return {
      ok: false,
      code: "TARGET_RESOLUTION_UNSAFE",
      message: `DNS resolution failed for ${hostname}: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

export function validateRedirectChain(
  urls: string[],
  registry: TargetRegistry,
  initialTargetId: string,
): PolicyResult {
  const initial = findTargetById(registry, initialTargetId);
  if (!initial) {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: `Unknown target id ${initialTargetId}`,
    };
  }

  for (const href of urls) {
    let parsed: URL;
    try {
      parsed = new URL(href);
    } catch {
      return {
        ok: false,
        code: "TARGET_REDIRECT_NOT_AUTHORIZED",
        message: `Invalid redirect URL ${href}`,
      };
    }

    const match =
      registry.targets.find(
        (t) => t.enabled && t.id === initialTargetId && hostnameMatchesTarget(parsed.hostname, t),
      ) ?? registry.targets.find((t) => t.enabled && hostnameMatchesTarget(parsed.hostname, t));

    const result = validateTargetRecord(match, parsed);
    if (!result.ok) {
      return {
        ok: false,
        code: "TARGET_REDIRECT_NOT_AUTHORIZED",
        message: `Redirect blocked: ${result.message}`,
      };
    }
  }

  return { ok: true, target: initial };
}

export async function validateTargetUrl(
  targetId: string,
  rawUrl: string,
  options: { configPath?: string; skipDns?: boolean } = {},
): Promise<PolicyResult> {
  const registry = loadTargetRegistry(options.configPath);
  const target = findTargetById(registry, targetId);

  let parsed: URL;
  try {
    parsed = new URL(rawUrl);
  } catch {
    return {
      ok: false,
      code: "TARGET_NOT_AUTHORIZED",
      message: `Invalid URL ${rawUrl}`,
    };
  }

  const recordResult = validateTargetRecord(target, parsed);
  if (!recordResult.ok) return recordResult;

  if (!options.skipDns) {
    const dnsResult = await resolveHostnameSafety(parsed.hostname, recordResult.target);
    if (!dnsResult.ok) return dnsResult;
  }

  return recordResult;
}

export function getStealthLabConfig(configPath?: string): StealthLabConfig {
  return loadTargetRegistry(configPath).stealth_lab;
}
