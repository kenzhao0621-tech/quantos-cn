const COOKIE_PATTERNS = [
  /\bSet-Cookie:\s*[^\n\r]*/gi,
  /\bCookie:\s*[^\n\r]*/gi,
  /\bcookie=([^\s;,&]+)/gi,
];

const AUTH_PATTERNS = [
  /\bAuthorization:\s*[^\n\r]*/gi,
  /\bBearer\s+[A-Za-z0-9._~+/=-]+/gi,
  /\baccess_token=([^\s&]+)/gi,
  /\brefresh_token=([^\s&]+)/gi,
  /\bid_token=([^\s&]+)/gi,
  /\bapi[_-]?key=([^\s&]+)/gi,
  /\bX-Api-Key:\s*[^\n\r]*/gi,
  /\bX-Auth-Token:\s*[^\n\r]*/gi,
];

const SESSION_PATTERNS = [
  /\bPHPSESSID=([^\s;,&]+)/gi,
  /\bJSESSIONID=([^\s;,&]+)/gi,
  /\bsession[_-]?id=([^\s&]+)/gi,
  /\bsid=([^\s;&]+)/gi,
];

const SIGNED_PARAM_PATTERNS = [/\bsignature=([^\s&]+)/gi, /\bX-Signature:\s*[^\n\r]*/gi];

function replaceWithRedacted(input: string, pattern: RegExp, label: string): string {
  return input.replace(pattern, (match) => {
    const eq = match.indexOf("=");
    const colon = match.indexOf(":");
    if (colon >= 0) {
      const header = match.slice(0, colon + 1);
      return `${header} [REDACTED_${label}]`;
    }
    if (eq >= 0) {
      const key = match.slice(0, eq + 1);
      return `${key}[REDACTED_${label}]`;
    }
    return `[REDACTED_${label}]`;
  });
}

/** Redact cookies, Authorization headers, bearer tokens, and session identifiers. */
export function redactSensitiveText(input: string): string {
  let output = input;
  for (const pattern of COOKIE_PATTERNS) {
    output = replaceWithRedacted(output, pattern, "COOKIE");
  }
  for (const pattern of AUTH_PATTERNS) {
    output = replaceWithRedacted(output, pattern, "AUTH");
  }
  for (const pattern of SESSION_PATTERNS) {
    output = replaceWithRedacted(output, pattern, "SESSION");
  }
  for (const pattern of SIGNED_PARAM_PATTERNS) {
    output = replaceWithRedacted(output, pattern, "SIGNATURE");
  }
  return output;
}

export function redactHeaders(
  headers: Record<string, string> | Headers,
): Record<string, string> {
  const normalized: Record<string, string> = {};
  const entries =
    headers instanceof Headers
      ? Array.from(headers.entries())
      : Object.entries(headers);

  for (const [key, value] of entries) {
    const lower = key.toLowerCase();
    if (lower === "authorization" || lower === "cookie" || lower === "set-cookie") {
      normalized[key] = "[REDACTED]";
      continue;
    }
    normalized[key] = redactSensitiveText(value);
  }
  return normalized;
}

export function redactUrlSecrets(rawUrl: string): string {
  try {
    const url = new URL(rawUrl);
    const secretKeys = new Set([
      "token",
      "access_token",
      "refresh_token",
      "api_key",
      "apikey",
      "signature",
      "sig",
      "session",
      "sessionid",
      "sid",
    ]);
    for (const key of [...url.searchParams.keys()]) {
      if (secretKeys.has(key.toLowerCase())) {
        url.searchParams.set(key, "[REDACTED]");
      }
    }
    return url.toString();
  } catch {
    return redactSensitiveText(rawUrl);
  }
}
