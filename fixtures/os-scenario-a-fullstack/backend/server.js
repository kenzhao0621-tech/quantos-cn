#!/usr/bin/env node
/** Minimal API — Backend Engineer. Local fixture only; binds 127.0.0.1 */

import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { validateItem } from "./validate.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.join(__dirname, "..");
const DATA = path.join(__dirname, "data", "items.json");
const PORT = Number(process.env.SCENARIO_A_PORT || 3847);
const HOST = "127.0.0.1";

function readItems() {
  return JSON.parse(fs.readFileSync(DATA, "utf8"));
}

function writeItems(items) {
  fs.writeFileSync(DATA, JSON.stringify(items, null, 2));
}

function json(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

function serveStatic(req, res) {
  let rel = req.url === "/" ? "/index.html" : req.url.split("?")[0];
  const file = path.join(ROOT, "frontend", rel.replace(/^\//, ""));
  if (!file.startsWith(path.join(ROOT, "frontend"))) {
    return json(res, 403, { error: "forbidden" });
  }
  if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    return json(res, 404, { error: "not found" });
  }
  const ext = path.extname(file);
  const types = { ".html": "text/html", ".js": "application/javascript", ".css": "text/css" };
  res.writeHead(200, { "Content-Type": types[ext] || "text/plain" });
  res.end(fs.readFileSync(file));
}

const server = http.createServer((req, res) => {
  if (req.url?.startsWith("/api/")) {
  if (req.method === "GET" && req.url === "/api/health") {
    return json(res, 200, { ok: true, service: "scenario-a-fullstack" });
  }
  if (req.method === "GET" && req.url === "/api/items") {
    return json(res, 200, { items: readItems() });
  }
  if (req.method === "GET" && req.url === "/api/error-demo") {
    return json(res, 500, { error: "Simulated server error for UI test" });
  }
  if (req.method === "POST" && req.url === "/api/items") {
    let body = "";
    req.on("data", (c) => (body += c));
    req.on("end", () => {
      try {
        const parsed = JSON.parse(body || "{}");
        const v = validateItem(parsed);
        if (!v.ok) return json(res, 400, { error: "validation_failed", details: v.errors });
        const items = readItems();
        const next = { id: items.length ? Math.max(...items.map((i) => i.id)) + 1 : 1, ...v.value, createdAt: new Date().toISOString() };
        items.push(next);
        writeItems(items);
        return json(res, 201, { item: next });
      } catch {
        return json(res, 400, { error: "invalid_json" });
      }
    });
    return;
  }
  return json(res, 404, { error: "not found" });
  }
  return serveStatic(req, res);
});

server.listen(PORT, HOST, () => {
  console.log(`scenario-a listening http://${HOST}:${PORT}`);
});
