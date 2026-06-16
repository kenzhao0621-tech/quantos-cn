import test from "node:test";
import assert from "node:assert/strict";
import { validateItem } from "../backend/validate.js";

test("accepts valid item", () => {
  const r = validateItem({ title: "Valid title", quantity: 3 });
  assert.equal(r.ok, true);
  assert.equal(r.value.title, "Valid title");
});

test("rejects short title", () => {
  const r = validateItem({ title: "x", quantity: 1 });
  assert.equal(r.ok, false);
});

test("rejects invalid quantity", () => {
  const r = validateItem({ title: "Good", quantity: 0 });
  assert.equal(r.ok, false);
});

test("rejects angle brackets", () => {
  const r = validateItem({ title: "<script>", quantity: 1 });
  assert.equal(r.ok, false);
});
