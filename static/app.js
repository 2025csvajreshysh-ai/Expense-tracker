const COLORS = ["#75ebd0", "#8050f5", "#f8b36e", "#f15c72", "#57d0d5", "#f3d36c", "#93a8ff", "#e58dc8", "#a6dc72"];
const money = value => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Number(value || 0));
const escapeHTML = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const colorFor = (name, names = []) => COLORS[Math.max(0, names.indexOf(name)) % COLORS.length];
const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };
const monthISO = () => `${todayISO().slice(0, 7)}-01`;
const state = { view: "dashboard", categories: [], expenses: [], summary: null, budgets: [], search: "", filters: { category: "", start: "", end: "" }, editing: null, user: localStorage.getItem("spendly-demo-user") || "" };
const $ = selector => document.querySelector(selector);
const viewRoot = $("#view");

async function api(path, options = {}) {
  const response = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try { const body = await response.json(); detail = body.detail || detail; } catch { }
    throw new Error(detail);
  }
  if (response.status === 204) return null;
  return response.json();
}
function notify(message, error = false) { const box = $("#notice"); box.textContent = message; box.classList.toggle("error", error); box.classList.add("show"); clearTimeout(notify.timer); notify.timer = setTimeout(() => box.classList.remove("show"), 3200); }
function go(view) { state.view = view; location.hash = view; render(); document.querySelectorAll(".nav-link").forEach(a => a.classList.toggle("active", a.dataset.view === view)); $("#sidebar").classList.remove("open"); }
function categoriesOptions(selected = "") { return state.categories.map(c => `<option value="${escapeHTML(c.name)}" ${c.name === selected ? "selected" : ""}>${escapeHTML(c.name)}</option>`).join(""); }
function catColor(name) { return colorFor(name, state.categories.map(c => c.name)); }
function pageHeader(title, desc, action = "") {
  const header = document.querySelector("#page-header-template").content.cloneNode(true);
  header.querySelector("[data-title]").textContent = title;
  header.querySelector("[data-description]").textContent = desc;
  if (action) header.querySelector("[data-action]").innerHTML = action;
  return header;
}
function showPage(title, desc, template, action = "") {
  viewRoot.replaceChildren(pageHeader(title, desc, action));
  if (template) viewRoot.append(document.querySelector(`#${template}`).content.cloneNode(true));
}
function button(label, attrs = "", kind = "button") { return `<button class="button ${kind}" ${attrs}>${label}</button>`; }

async function refresh() {
  try { state.categories = await api("/categories"); } catch (e) { notify(e.message, true); }
  if (state.view === "dashboard" || state.view === "reports") {
    try { state.summary = await api("/summary"); } catch (e) { notify(e.message, true); }
  }
  if (state.view === "budgets") {
    try { state.budgets = await api("/budgets"); } catch (e) { notify(e.message, true); }
  }
  if (["expenses", "add", "dashboard", "reports", "categories"].includes(state.view)) {
    try { state.expenses = await api(`/expenses?q=${encodeURIComponent(state.view === "expenses" ? state.search : "")}`); } catch (e) { notify(e.message, true); }
  }
  render();
}
function render() {
  document.querySelectorAll(".nav-link").forEach(a => a.classList.toggle("active", a.dataset.view === state.view));
  const views = { dashboard: renderDashboard, expenses: renderExpenses, add: renderExpenseForm, categories: renderCategories, budgets: renderBudgets, reports: renderReports };
  (views[state.view] || renderDashboard)();
}
function renderDashboard() {
  const s = state.summary || { month_total: 0, budget_total: 0, remaining: 0, category_count: 0, by_category: {}, trend: [] };
  const monthName = new Intl.DateTimeFormat("en", { month: "long", year: "numeric" }).format(new Date());
  const metrics = [["Total Expenses", money(s.month_total), "Spent in " + monthName, "#8050f5"], ["Total Budget", money(s.budget_total), "Across all categories", "#75ebd0"], ["Remaining", money(s.remaining), "Budget left this month", "#f8b36e"], ["Categories", s.category_count, "Active categories", "#57d0d5"]];
  const categoryData = Object.entries(s.by_category || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const grand = categoryData.reduce((sum, [, v]) => sum + v, 0);
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  showPage(state.user ? `${greeting}, ${state.user}` : "Dashboard", "A clear view of where your money goes.", "dashboard-template", button("＋ Add expense", 'data-go="add"', "button-primary"));
  viewRoot.querySelector("[data-metrics]").innerHTML = metrics.map(([title, value, note, color]) => `<article class="metric-card" style="--glow:${color}"><div class="metric-label"><span class="metric-dot"></span>${title}</div><div class="metric-value">${value}</div><div class="metric-note">${note}</div></article>`).join("");
  viewRoot.querySelector("[data-dashboard-total]").textContent = `${money(grand)} total`;
  viewRoot.querySelector("[data-dashboard-donut]").innerHTML = makeDonut(categoryData, grand, false);
  viewRoot.querySelector("[data-dashboard-trend]").innerHTML = lineChart(s.trend || []);
  viewRoot.querySelector("[data-recent-expenses]").innerHTML = expenseTable(state.expenses.slice(0, 5), false);
}
function makeDonut(entries, total, large) {
  let cursor = 0; const segments = entries.map(([name, value]) => { const start = cursor; cursor += total ? value / total * 100 : 0; return `${catColor(name)} ${start}% ${cursor}%`; });
  const chart = segments.length ? `<div class="donut-chart" style="background:conic-gradient(${segments.join(",")})"><div class="donut-hole"></div></div>` : `<div class="donut-chart" style="background:#263348"><div class="donut-hole"></div></div>`;
  const legend = entries.map(([name, value]) => `<span class="legend-item"><i class="legend-swatch" style="background:${catColor(name)}"></i>${escapeHTML(name)}</span>`).join("");
  return `<div class="donut-wrap ${large ? "large" : ""}">${chart}<div class="donut-center"><span class="donut-total">${money(total)}</span><span class="donut-caption">total spent</span></div></div><div class="legend">${legend || `<span class="panel-note">No expenses yet</span>`}</div>`;
}
function lineChart(points) {
  const w = 900, h = 205, left = 42, right = 12, top = 9, bottom = 40, iw = w - left - right, ih = h - top - bottom, max = Math.max(100, ...points.map(p => p.total));
  const coords = points.map((p, i) => [left + (points.length < 2 ? iw / 2 : i * iw / (points.length - 1)), top + ih - (p.total / max) * ih]);
  const line = coords.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const area = coords.length ? `${line} L${coords.at(-1)[0]},${top + ih} L${coords[0][0]},${top + ih} Z` : "";
  const grid = [0, .25, .5, .75, 1].map(t => { const y = top + ih * (1 - t), val = Math.round(max * t); return `<line class="chart-grid" x1="${left}" y1="${y}" x2="${w - right}" y2="${y}"/><text class="chart-label" x="${left - 6}" y="${y + 3}" text-anchor="end">${val >= 1000 ? (val / 1000).toFixed(val % 1000 ? 1 : 0) + "k" : val}</text>`; }).join("");
  const labels = points.map((p, i) => `<text class="chart-label" x="${coords[i][0]}" y="${h - 7}" text-anchor="middle">${escapeHTML(p.label.split(" ")[0])}</text>`).join("");
  const dots = coords.map(([x, y]) => `<circle class="chart-dot" cx="${x}" cy="${y}" r="3.2"/>`).join("");
  return points.length ? `<svg class="chart-svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Monthly expenses trend"><defs><linearGradient id="chartGradient" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#8050f5"/><stop offset="100%" stop-color="#8050f5" stop-opacity="0"/></linearGradient></defs>${grid}<path class="chart-area-fill" d="${area}"/><path class="chart-line" d="${line}"/>${dots}${labels}</svg>` : `<div class="empty-chart">Add an expense to see your trend.</div>`;
}
function expenseTable(items, actions = true) {
  if (!items.length) return `<div class="empty-state"><strong>No expenses found</strong>Try another filter, or add your first expense.</div>`;
  return `<table class="expense-table"><thead><tr><th>Title</th><th>Amount</th><th>Category</th><th>Date</th><th>Notes</th>${actions ? "<th style='text-align:right'>Actions</th>" : ""}</tr></thead><tbody>${items.map(e => `<tr><td><span class="expense-title">${escapeHTML(e.title)}</span></td><td>${money(e.amount)}</td><td><span class="category-chip" style="--chip:${catColor(e.category)}">${escapeHTML(e.category)}</span></td><td>${escapeHTML(e.date)}</td><td>${e.notes ? escapeHTML(e.notes) : "<span class='panel-note'>—</span>"}</td>${actions ? `<td><div class="row-actions">${button("Edit", `data-edit="${e.id}"`)}${button("Delete", `data-delete="${e.id}"`, "button-danger")}</div></td>` : ""}</tr>`).join("")}</tbody></table>`;
}
function renderExpenses() {
  const filtered = state.expenses.filter(e => (!state.filters.category || e.category === state.filters.category) && (!state.filters.start || e.date >= state.filters.start) && (!state.filters.end || e.date <= state.filters.end));
  showPage("Expenses", "Every purchase, all in one place.", "expenses-template", button("＋ Add expense", 'data-go="add"', "button-primary"));
  $("#filter-category").insertAdjacentHTML("beforeend", categoriesOptions(state.filters.category));
  $("#filter-start").value = state.filters.start; $("#filter-end").value = state.filters.end;
  viewRoot.querySelector("[data-expense-table]").innerHTML = expenseTable(filtered, true);
}
function renderExpenseForm() {
  const edit = state.editing; const title = edit ? "Edit expense" : "Add expense";
  showPage(title, edit ? "Update the details below." : "Capture a purchase while it’s fresh.", "expense-form-template");
  const form = $("#expense-form");
  form.elements.title.value = edit?.title || ""; form.elements.amount.value = edit?.amount ?? "";
  form.elements.category.innerHTML = categoriesOptions(edit?.category || "");
  form.elements.date.value = edit?.date || todayISO(); form.elements.notes.value = edit?.notes || "";
  form.querySelector("[data-save-label]").textContent = edit ? "Save changes" : "Save expense";
  if (!state.categories.length) form.insertAdjacentHTML("afterbegin", `<div class="empty-state">Create a category before adding an expense. <a href="#categories">Manage categories</a></div>`);
}
function renderCategories() {
  const counts = Object.fromEntries(state.categories.map(c => [c.name, state.expenses.filter(e => e.category === c.name).length]));
  showPage("Categories", "Keep your spending organized.", "categories-template");
  viewRoot.querySelector("[data-category-grid]").innerHTML = state.categories.map(c => `<article class="category-card"><h3>${escapeHTML(c.name)}</h3><p>${counts[c.name] || 0} ${(counts[c.name] || 0) === 1 ? "expense" : "expenses"}</p><div class="category-actions"><i class="category-color" style="--chip:${catColor(c.name)}"></i>${button("Remove", `data-category-delete="${c.id}"`, "button-quiet button-danger")}</div></article>`).join("") || `<div class="empty-state">No categories yet.</div>`;
}
function renderBudgets() {
  const rows = state.budgets.map(b => { const pct = b.amount ? b.spent / b.amount * 100 : 0; return `<article class="budget-row"><div class="budget-name">${escapeHTML(b.category)}</div><div class="progress ${pct > 100 ? "over" : ""}" title="${Math.round(pct)}% used"><span style="width:${Math.min(100, pct)}%"></span></div><div class="budget-stats"><strong>${money(b.spent)}</strong> / ${money(b.amount)}</div><form class="budget-edit" data-budget-category="${escapeHTML(b.category)}"><input class="field" name="amount" type="number" min="1" step="1" aria-label="Budget for ${escapeHTML(b.category)}" value="${b.amount}"><button class="button" type="submit">Save</button></form></article>`; }).join("");
  showPage("Budgets", "Set a monthly limit for each category.", "budget-template");
  viewRoot.querySelector("[data-budget-total]").textContent = `${money(state.budgets.reduce((n, b) => n + b.amount, 0))} total`;
  viewRoot.querySelector("[data-budget-list]").innerHTML = rows || `<div class="empty-state">Add categories to start setting budgets.</div>`;
}
function renderReports() {
  const s = state.summary || { by_category: {}, trend: [] }; const entries = Object.entries(s.by_category || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]); const total = entries.reduce((n, [, v]) => n + v, 0);
  showPage("Reports", "See how your spending adds up.", "reports-template");
  viewRoot.querySelector("[data-report-total]").textContent = `${money(total)} total`;
  viewRoot.querySelector("[data-report-donut]").innerHTML = makeDonut(entries, total, true);
  viewRoot.querySelector("[data-report-bars]").innerHTML = barChart(s.trend || []);
}
function barChart(points) {
  if (!points.length) return `<div class="empty-chart">No monthly data yet.</div>`;
  const w = 950, h = 260, L = 48, R = 8, T = 12, B = 42, iw = w - L - R, ih = h - T - B, max = Math.max(100, ...points.map(p => p.total)), step = iw / points.length, bw = Math.min(42, step * .5);
  const grid = [0, .25, .5, .75, 1].map(t => { const y = T + ih * (1 - t), v = Math.round(max * t); return `<line class="chart-grid" x1="${L}" y1="${y}" x2="${w - R}" y2="${y}"/><text class="chart-label" x="${L - 7}" y="${y + 3}" text-anchor="end">${v >= 1000 ? (v / 1000).toFixed(v % 1000 ? 1 : 0) + "k" : v}</text>`; }).join("");
  const bars = points.map((p, i) => { const bh = p.total / max * ih, x = L + i * step + (step - bw) / 2, y = T + ih - bh; return `<rect x="${x}" y="${y}" width="${bw}" height="${Math.max(1, bh)}" rx="3" fill="${p.total ? "#75ebd0" : "#23334a"}"/><text class="chart-label" x="${L + i * step + step / 2}" y="${h - 9}" text-anchor="middle">${escapeHTML(p.label.replace(" ", "\n"))}</text>`; }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Monthly expenses bar chart">${grid}${bars}</svg>`;
}

async function startEdit(id) {
  try { state.editing = await api(`/expenses/${id}`); } catch { const list = await api("/expenses"); state.editing = list.find(e => e.id === id) || null; }
  if (state.editing) go("add");
}
async function removeExpense(id) { if (!confirm("Delete this expense?")) return; try { await api(`/expenses/${id}`, { method: "DELETE" }); notify("Expense deleted."); await refresh(); } catch (e) { notify(e.message, true); } }

document.addEventListener("click", async event => {
  const nav = event.target.closest("[data-view]"); if (nav) { event.preventDefault(); go(nav.dataset.view); return; }
  const goButton = event.target.closest("[data-go]"); if (goButton) { event.preventDefault(); state.editing = null; go(goButton.dataset.go); return; }
  const edit = event.target.closest("[data-edit]"); if (edit) { startEdit(Number(edit.dataset.edit)); return; }
  const del = event.target.closest("[data-delete]"); if (del) { removeExpense(Number(del.dataset.delete)); return; }
  const catDel = event.target.closest("[data-category-delete]"); if (catDel) { if (!confirm("Remove this category?")) return; try { await api(`/categories/${catDel.dataset.categoryDelete}`, { method: "DELETE" }); notify("Category removed."); await refresh(); } catch (e) { notify(e.message, true); } return; }
  const action = event.target.closest("[data-action]")?.dataset.action;
  if (action === "filter") { state.filters = { category: $("#filter-category").value, start: $("#filter-start").value, end: $("#filter-end").value }; renderExpenses(); }
  if (action === "clear-filters") { state.filters = { category: "", start: "", end: "" }; renderExpenses(); }
});
document.addEventListener("submit", async event => {
  if (event.target.id === "demo-login-form") {
    event.preventDefault();
    const name = String(new FormData(event.target).get("name") || "").trim();
    if (!name) return;
    state.user = name;
    localStorage.setItem("spendly-demo-user", name);
    syncLogin();
    notify(`Welcome to Spendly, ${name}!`);
    await refresh();
    return;
  }
  if (event.target.id === "expense-form") {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); data.amount = Number(data.amount);
    try { if (state.editing) await api(`/expenses/${state.editing.id}`, { method: "PUT", body: JSON.stringify(data) }); else await api("/expenses", { method: "POST", body: JSON.stringify(data) }); notify(state.editing ? "Expense updated." : "Expense added."); state.editing = null; go("expenses"); await refresh(); } catch (e) { notify(e.message, true); } return;
  }
  if (event.target.id === "category-form") {
    event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); try { await api("/categories", { method: "POST", body: JSON.stringify(data) }); notify("Category added."); await refresh(); } catch (e) { notify(e.message, true); } return;
  }
  const budgetForm = event.target.closest("[data-budget-category]"); if (budgetForm) { event.preventDefault(); const category = budgetForm.dataset.budgetCategory, amount = Number(new FormData(budgetForm).get("amount")); try { await api(`/budgets/${encodeURIComponent(category)}`, { method: "PUT", body: JSON.stringify({ category, amount }) }); notify(`${category} budget updated.`); await refresh(); } catch (e) { notify(e.message, true); } }
});
function syncLogin() {
  const signedIn = Boolean(state.user);
  $("#login-screen").hidden = signedIn;
  $("#account-area").hidden = !signedIn;
  $("#account-name").textContent = state.user;
}
$("#logout-button").addEventListener("click", () => {
  state.user = "";
  localStorage.removeItem("spendly-demo-user");
  syncLogin();
});
$("#global-search").addEventListener("input", event => { state.search = event.target.value; if (state.view === "expenses") { clearTimeout(renderExpenses.timer); renderExpenses.timer = setTimeout(async () => { state.expenses = await api(`/expenses?q=${encodeURIComponent(state.search)}`); renderExpenses(); }, 180); } });
$("#global-search").addEventListener("keydown", event => { if (event.key === "Enter") { go("expenses"); state.search = event.target.value; refresh(); } });
$("#theme-toggle").addEventListener("change", event => { document.documentElement.classList.toggle("light", !event.target.checked); localStorage.setItem("spendly-light", event.target.checked ? "0" : "1"); });
$("#mobile-menu").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
window.addEventListener("hashchange", () => { const next = location.hash.slice(1); if (["dashboard", "expenses", "add", "categories", "budgets", "reports"].includes(next)) { state.view = next; state.editing = null; refresh(); } });

const isLight = localStorage.getItem("spendly-light") === "1"; document.documentElement.classList.toggle("light", isLight); $("#theme-toggle").checked = !isLight;
syncLogin();
const initial = location.hash.slice(1); if (["dashboard", "expenses", "add", "categories", "budgets", "reports"].includes(initial)) state.view = initial;
refresh();
