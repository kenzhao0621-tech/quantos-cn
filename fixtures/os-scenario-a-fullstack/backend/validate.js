/** Input validation — Backend Engineer */

export function validateItem(body) {
  const errors = [];
  if (!body || typeof body !== "object") {
    return { ok: false, errors: ["Body must be a JSON object"] };
  }
  const title = String(body.title ?? "").trim();
  const quantity = Number(body.quantity);
  if (title.length < 2 || title.length > 80) {
    errors.push("title must be 2–80 characters");
  }
  if (!Number.isInteger(quantity) || quantity < 1 || quantity > 999) {
    errors.push("quantity must be an integer between 1 and 999");
  }
  if (/[<>]/.test(title)) {
    errors.push("title must not contain angle brackets");
  }
  return errors.length ? { ok: false, errors } : { ok: true, value: { title, quantity } };
}
