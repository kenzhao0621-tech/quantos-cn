const statusEl = document.getElementById("status");
const form = document.getElementById("item-form");
const formError = document.getElementById("form-error");
const list = document.getElementById("items");
const listError = document.getElementById("list-error");
const loading = document.getElementById("loading");

function setStatus(msg) {
  statusEl.textContent = msg;
}

function show(el, msg) {
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hide(el) {
  el.classList.add("hidden");
  el.textContent = "";
}

async function fetchItems() {
  hide(listError);
  loading.classList.remove("hidden");
  list.innerHTML = "";
  try {
    const res = await fetch("/api/items");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    list.innerHTML = data.items
      .map((i) => `<li data-testid="item-${i.id}"><strong>${escapeHtml(i.title)}</strong> × ${i.quantity}</li>`)
      .join("");
    setStatus(`Loaded ${data.items.length} item(s)`);
  } catch (e) {
    show(listError, `Failed to load items: ${e.message}`);
    setStatus("Error loading items");
  } finally {
    loading.classList.add("hidden");
  }
}

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  hide(formError);
  const fd = new FormData(form);
  const body = { title: fd.get("title"), quantity: Number(fd.get("quantity")) };
  try {
    const res = await fetch("/api/items", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      show(formError, data.details?.join("; ") || data.error || "Validation failed");
      return;
    }
    form.reset();
    await fetchItems();
  } catch {
    show(formError, "Network error");
  }
});

document.getElementById("refresh").addEventListener("click", fetchItems);
document.getElementById("error-demo").addEventListener("click", async () => {
  hide(listError);
  loading.classList.remove("hidden");
  try {
    const res = await fetch("/api/error-demo");
    if (!res.ok) throw new Error("Simulated server error");
  } catch (e) {
    show(listError, e.message);
    setStatus("Error state displayed");
  } finally {
    loading.classList.add("hidden");
  }
});

fetchItems();
