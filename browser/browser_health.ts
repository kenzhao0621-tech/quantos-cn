export type BrowserHealthStatus = "healthy" | "degraded" | "unavailable";

export interface BrowserHealth {
  status: BrowserHealthStatus;
  playwrightAvailable: boolean;
  playwrightExtraInstalled: boolean;
  stealthLabEnabled: boolean;
  plainPlaywrightPreferred: boolean;
  message: string;
  checkedAt: string;
}

export interface BrowserHealthInput {
  playwrightAvailable: boolean;
  playwrightExtraInstalled: boolean;
  stealthLabEnabled: boolean;
}

export function buildBrowserHealth(input: BrowserHealthInput): BrowserHealth {
  const checkedAt = new Date().toISOString();
  const plainPlaywrightPreferred = true;

  if (!input.playwrightAvailable) {
    return {
      status: "unavailable",
      playwrightAvailable: false,
      playwrightExtraInstalled: input.playwrightExtraInstalled,
      stealthLabEnabled: input.stealthLabEnabled,
      plainPlaywrightPreferred,
      message: "Playwright is not available",
      checkedAt,
    };
  }

  if (input.stealthLabEnabled && !input.playwrightExtraInstalled) {
    return {
      status: "degraded",
      playwrightAvailable: true,
      playwrightExtraInstalled: false,
      stealthLabEnabled: true,
      plainPlaywrightPreferred,
      message: "Stealth lab enabled but playwright-extra is not installed",
      checkedAt,
    };
  }

  return {
    status: "healthy",
    playwrightAvailable: true,
    playwrightExtraInstalled: input.playwrightExtraInstalled,
    stealthLabEnabled: input.stealthLabEnabled,
    plainPlaywrightPreferred,
    message: "Plain Playwright runtime ready",
    checkedAt,
  };
}
