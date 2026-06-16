#!/usr/bin/env node
import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, "..");
const testGlob = resolve(repoRoot, "browser/tests/*.test.mjs");

const nodeArgs = ["--test", testGlob];
if (process.versions.node.split(".")[0] >= "22") {
  nodeArgs.unshift("--experimental-strip-types");
}

const child = spawn(process.execPath, nodeArgs, {
  cwd: repoRoot,
  stdio: "inherit",
  env: process.env,
});

child.on("exit", (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});
