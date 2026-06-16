import { chromium, type Browser, type BrowserContext, type Page, type Response } from "playwright";
import { buildBrowserHealth, type BrowserHealth } from "./browser_health.ts";
import { redactHeaders, redactSensitiveText, redactUrlSecrets } from "./artifact_redactor.ts";
import { loadPlugin } from "./plugin_registry.ts";
import { loadSessionMetadata, storageStatePathForTarget } from "./session_manager.ts";
import {
  findTargetById,
  loadTargetRegistry,
  validateTargetUrl,
  type AuthorizedTarget,
  type PolicyResult,
} from "./target_policy.ts";

export interface AuthorizedSession {
  targetId: string;
  target: AuthorizedTarget;
  pageUrl: string;
  context: BrowserContext;
  page: Page;
}

export interface CapturedResponse {
  pageUrl: string;
  requestUrl: string;
  responseUrl: string;
  method: string;
  status: number;
  contentType: string | null;
  byteLength: number;
  retrievedAt: string;
  targetId: string;
  contentHash: string;
  headers: Record<string, string>;
}

export interface CaptureResult {
  targetId: string;
  responses: CapturedResponse[];
}

export interface BrowserRuntimeOptions {
  configPath?: string;
  profile?: "production" | "stealth_lab" | "test";
  headless?: boolean;
}

export interface BrowserRuntime {
  healthCheck(): Promise<BrowserHealth>;
  openAuthorizedTarget(targetId: string, startUrl?: string): Promise<AuthorizedSession>;
  captureAuthorizedResponses(targetId: string, startUrl?: string): Promise<CaptureResult>;
  close(): Promise<void>;
}

async function isPlaywrightExtraInstalled(): Promise<boolean> {
  try {
    await import("playwright-extra");
    return true;
  } catch {
    return false;
  }
}

function hashContent(content: string): string {
  let hash = 0;
  for (let i = 0; i < content.length; i += 1) {
    hash = (hash * 31 + content.charCodeAt(i)) >>> 0;
  }
  return hash.toString(16);
}

export class PlaywrightBrowserRuntime implements BrowserRuntime {
  private browser: Browser | null = null;
  private readonly configPath?: string;
  private readonly profile: "production" | "stealth_lab" | "test";
  private readonly headless: boolean;

  constructor(options: BrowserRuntimeOptions = {}) {
    this.configPath = options.configPath;
    this.profile = options.profile ?? "production";
    this.headless = options.headless ?? true;
  }

  async healthCheck(): Promise<BrowserHealth> {
    const registry = loadTargetRegistry(this.configPath);
    const playwrightExtraInstalled = await isPlaywrightExtraInstalled();
    return buildBrowserHealth({
      playwrightAvailable: true,
      playwrightExtraInstalled,
      stealthLabEnabled: registry.stealth_lab.enabled,
    });
  }

  private async ensureBrowser(): Promise<Browser> {
    if (this.browser) return this.browser;

    // Production and third-party paths always use plain Playwright — no stealth.
    this.browser = await chromium.launch({ headless: this.headless });
    return this.browser;
  }

  private async assertTargetPolicy(
    targetId: string,
    rawUrl: string,
  ): Promise<{ target: AuthorizedTarget; url: string }> {
    const policy: PolicyResult = await validateTargetUrl(targetId, rawUrl, {
      configPath: this.configPath,
      skipDns: rawUrl.includes("localhost"),
    });
    if (!policy.ok) {
      throw new Error(`${policy.code}: ${policy.message}`);
    }

    const pluginDecision = await loadPlugin("stealth", {
      profile: this.profile,
      target: policy.target,
      targetPolicyPassed: true,
      configPath: this.configPath,
    });

    if (pluginDecision.ok) {
      throw new Error(
        "PLUGIN_POLICY_VIOLATION: stealth must not load for authorized data collection runtime",
      );
    }

    return { target: policy.target, url: rawUrl };
  }

  async openAuthorizedTarget(targetId: string, startUrl?: string): Promise<AuthorizedSession> {
    const registry = loadTargetRegistry(this.configPath);
    const target = findTargetById(registry, targetId);
    if (!target) {
      throw new Error(`TARGET_NOT_AUTHORIZED: Unknown target ${targetId}`);
    }

    const url = startUrl ?? `https://${target.domain}${target.allowed_paths[0] ?? "/"}`;
    const { target: authorizedTarget } = await this.assertTargetPolicy(targetId, url);

    const browser = await this.ensureBrowser();
    const contextOptions: Parameters<Browser["newContext"]>[0] = {};

    const metadata = await loadSessionMetadata(targetId);
    if (metadata) {
      contextOptions.storageState = metadata.storageStatePath;
    } else if (target.session_state_path) {
      contextOptions.storageState = storageStatePathForTarget(targetId);
    }

    const context = await browser.newContext(contextOptions);
    const page = await context.newPage();
    const response = await page.goto(url, { waitUntil: "domcontentloaded" });
    if (!response) {
      throw new Error(`TARGET_NOT_AUTHORIZED: Navigation produced no response for ${url}`);
    }

    const finalUrl = redactUrlSecrets(page.url());
    const finalPolicy = await validateTargetUrl(targetId, finalUrl, {
      configPath: this.configPath,
      skipDns: finalUrl.includes("localhost"),
    });
    if (!finalPolicy.ok) {
      await context.close();
      throw new Error(`${finalPolicy.code}: ${finalPolicy.message}`);
    }

    return {
      targetId,
      target: authorizedTarget,
      pageUrl: finalUrl,
      context,
      page,
    };
  }

  async captureAuthorizedResponses(
    targetId: string,
    startUrl?: string,
  ): Promise<CaptureResult> {
    const session = await this.openAuthorizedTarget(targetId, startUrl);
    const responses: CapturedResponse[] = [];

    const handler = async (response: Response) => {
      const request = response.request();
      const headers = redactHeaders(response.headers());
      let byteLength = 0;
      try {
        const body = await response.body();
        byteLength = body.byteLength;
      } catch {
        byteLength = 0;
      }

      responses.push({
        pageUrl: redactUrlSecrets(session.page.url()),
        requestUrl: redactUrlSecrets(request.url()),
        responseUrl: redactUrlSecrets(response.url()),
        method: request.method(),
        status: response.status(),
        contentType: response.headers()["content-type"] ?? null,
        byteLength,
        retrievedAt: new Date().toISOString(),
        targetId,
        contentHash: hashContent(`${response.status()}:${byteLength}`),
        headers,
      });
    };

    session.page.on("response", handler);
    await session.page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => undefined);
    session.page.off("response", handler);
    await session.context.close();

    return { targetId, responses };
  }

  async close(): Promise<void> {
    if (this.browser) {
      await this.browser.close();
      this.browser = null;
    }
  }
}

export function createBrowserRuntime(options?: BrowserRuntimeOptions): BrowserRuntime {
  return new PlaywrightBrowserRuntime(options);
}

export function redactRuntimeMessage(message: string): string {
  return redactSensitiveText(message);
}
