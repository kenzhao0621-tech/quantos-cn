import test from "node:test";
import assert from "node:assert/strict";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const configPath = resolve(__dirname, "../../config/authorized_data_targets.yaml");

const { validateTargetUrl, loadTargetRegistry } = await import("../target_policy.ts");
const { canLoadStealthPlugin, loadPlugin, getStealthLabConfigFromRegistry } = await import(
  "../plugin_registry.ts"
);

test("rejects unauthorized URL for unknown target id", async () => {
  const result = await validateTargetUrl("missing_target", "https://example.com/public/", {
    configPath,
    skipDns: true,
  });
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.code, "TARGET_NOT_AUTHORIZED");
  }
});

test("rejects unauthorized URL when target is disabled", async () => {
  const result = await validateTargetUrl(
    "third_party_financial",
    "https://eastmoney.com/",
    { configPath, skipDns: true },
  );
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.code, "TARGET_NOT_AUTHORIZED");
    assert.match(result.message, /disabled/i);
  }
});

test("rejects disallowed path for authorized domain", async () => {
  const registry = loadTargetRegistry(configPath);
  const example = registry.targets.find((t) => t.id === "example_official");
  assert.ok(example);
  const enabled = { ...example, enabled: true };

  const { validateTargetRecord } = await import("../target_policy.ts");
  const result = validateTargetRecord(enabled, new URL("https://example.com/private/secret"));
  assert.equal(result.ok, false);
  if (!result.ok) {
    assert.equal(result.code, "TARGET_PATH_NOT_AUTHORIZED");
  }
});

test("stealth lab defaults to disabled", () => {
  const registry = loadTargetRegistry(configPath);
  assert.equal(registry.stealth_lab.enabled, false);
  const fromRegistry = getStealthLabConfigFromRegistry({ targetPolicyPassed: true, profile: "test" });
  assert.equal(fromRegistry.enabled, false);
});

test("stealth cannot load for third-party target", async () => {
  const registry = loadTargetRegistry(configPath);
  const thirdParty = registry.targets.find((t) => t.id === "third_party_financial");
  assert.ok(thirdParty);

  const decision = canLoadStealthPlugin({
    profile: "stealth_lab",
    target: { ...thirdParty, enabled: true, owned_security_test_target: false },
    targetPolicyPassed: true,
    registry: {
      ...registry,
      stealth_lab: { ...registry.stealth_lab, enabled: true },
    },
  });

  assert.equal(decision.ok, false);
  if (!decision.ok) {
    assert.equal(decision.code, "STEALTH_THIRD_PARTY_FORBIDDEN");
  }
});

test("stealth cannot load when owned_security_test_target is false", async () => {
  const registry = loadTargetRegistry(configPath);
  const localhost = registry.targets.find((t) => t.id === "localhost_lab");
  assert.ok(localhost);

  const decision = canLoadStealthPlugin({
    profile: "stealth_lab",
    target: { ...localhost, enabled: true, owned_security_test_target: false },
    targetPolicyPassed: true,
    registry: {
      ...registry,
      stealth_lab: { ...registry.stealth_lab, enabled: true },
    },
  });

  assert.equal(decision.ok, false);
  if (!decision.ok) {
    assert.equal(decision.code, "STEALTH_OWNERSHIP_REQUIRED");
  }
});

test("stealth cannot load when stealth lab remains disabled", async () => {
  const registry = loadTargetRegistry(configPath);
  const localhost = registry.targets.find((t) => t.id === "localhost_lab");
  assert.ok(localhost);

  const decision = await loadPlugin("stealth", {
    profile: "stealth_lab",
    target: { ...localhost, enabled: true },
    targetPolicyPassed: true,
    registry,
  });

  assert.equal(decision.ok, false);
  if (!decision.ok) {
    assert.equal(decision.code, "STEALTH_LAB_DISABLED");
  }
});

test("production profile forbids stealth plugin", async () => {
  const registry = loadTargetRegistry(configPath);
  const localhost = registry.targets.find((t) => t.id === "localhost_lab");
  assert.ok(localhost);

  const decision = await loadPlugin("stealth", {
    profile: "production",
    target: { ...localhost, enabled: true },
    targetPolicyPassed: true,
    registry: {
      ...registry,
      stealth_lab: { ...registry.stealth_lab, enabled: true },
    },
  });

  assert.equal(decision.ok, false);
  if (!decision.ok) {
    assert.equal(decision.code, "PRODUCTION_PROFILE_FORBIDDEN");
  }
});
