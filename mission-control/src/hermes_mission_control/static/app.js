const state = { dashboard: null };
const intentHeaders = { "Content-Type": "application/json", "X-Hermes-Intent": "founder-action" };

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".nav-item, .view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    document.getElementById(button.dataset.view).classList.add("active");
  });
});

document.getElementById("refresh").addEventListener("click", loadDashboard);
document.getElementById("task-filter").addEventListener("input", renderTasks);
document.getElementById("status-filter").addEventListener("change", renderTasks);
document.getElementById("open-intake").addEventListener("click", () => document.getElementById("intake-dialog").showModal());

document.getElementById("intake-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  const form = new FormData(event.target);
  const payload = {
    kind: form.get("kind"),
    project: form.get("project"),
    title: form.get("title"),
    objective: form.get("objective"),
    risk_level: Number(form.get("risk_level")),
    acceptance_criteria: String(form.get("criteria")).split("\n").map((item) => item.trim()).filter(Boolean),
  };
  await mutate("/api/intake", payload, "Founder request submitted.");
  document.getElementById("intake-dialog").close();
  event.target.reset();
  await loadDashboard();
});

document.getElementById("ingest-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const path = document.getElementById("ingest-path").value;
  await mutate("/api/knowledge/ingest", { path, confidentiality: "private" }, "Document indexed locally.");
  await loadGraph();
});

document.getElementById("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("search-query").value;
  const data = await request(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
  const target = document.getElementById("search-results");
  target.innerHTML = data.results.length ? data.results.map((item) => `
    <article class="result">
      <strong>${escapeHtml(item.title)}</strong>
      <p>${escapeHtml(item.excerpt)}</p>
      <div class="citation">${escapeHtml(item.citation)}</div>
    </article>`).join("") : '<div class="empty">No cited matches.</div>';
});

async function loadDashboard() {
  try {
    state.dashboard = await request("/api/dashboard");
    document.getElementById("health").textContent = "Control plane online";
    document.getElementById("health-dot").classList.add("ok");
    renderOverview();
    renderTasks();
    renderApprovals();
    await loadGraph();
  } catch (error) {
    document.getElementById("health").textContent = "Control plane unavailable";
    document.getElementById("health-dot").classList.remove("ok");
    toast(error.message);
  }
}

function renderOverview() {
  const data = state.dashboard;
  const pending = data.approvals.filter((item) => item.status === "pending").length;
  const active = data.tasks.filter((item) => ["queued", "leased", "running", "pending_approval"].includes(item.status)).length;
  const online = data.agents.filter((item) => item.status === "online").length;
  document.getElementById("metrics").innerHTML = [
    [active, "Active tasks"], [pending, "Pending approvals"], [online, "Online agents"], [data.knowledge.sources, "Knowledge sources"],
  ].map(([value, label]) => `<div class="metric"><strong>${value}</strong><span>${label}</span></div>`).join("");
  document.getElementById("agents").innerHTML = data.agents.map((agent) => `
    <div class="row"><div><strong>${escapeHtml(agent.display_name || agent.slug)}</strong><div class="row-meta">${escapeHtml(agent.machine)}</div></div><span class="badge ${agent.status}">${agent.status}</span></div>`).join("") || '<div class="empty">No registered agents.</div>';
  document.getElementById("controls").innerHTML = data.control_scopes.map((scope) => `
    <div class="row"><div><strong>${escapeHtml(scope.scope_type)} · ${escapeHtml(scope.scope_key)}</strong><div class="row-meta">${escapeHtml(scope.reason || "No active restriction")}</div></div><span class="badge ${scope.is_paused ? "failed" : "succeeded"}">${scope.is_paused ? "paused" : "active"}</span></div>`).join("") || '<div class="empty">No control restrictions.</div>';
  document.getElementById("activity").innerHTML = data.tasks.slice(0, 8).map((task) => `
    <div class="row"><div><strong>${escapeHtml(task.title)}</strong><div class="row-meta">${escapeHtml(task.task_number)}</div></div><span class="badge ${task.status}">${task.status}</span></div>`).join("");
}

function renderTasks() {
  if (!state.dashboard) return;
  const text = document.getElementById("task-filter").value.toLowerCase();
  const status = document.getElementById("status-filter").value;
  const statuses = [...new Set(state.dashboard.tasks.map((task) => task.status))].sort();
  const select = document.getElementById("status-filter");
  const selected = select.value;
  select.innerHTML = '<option value="">All statuses</option>' + statuses.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join("");
  select.value = selected;
  const tasks = state.dashboard.tasks.filter((task) =>
    (!status || task.status === status) &&
    (!text || `${task.title} ${task.task_number} ${task.project}`.toLowerCase().includes(text))
  );
  document.getElementById("task-table").innerHTML = tasks.map((task) => `
    <tr><td><strong>${escapeHtml(task.title)}</strong><div class="row-meta">${escapeHtml(task.task_number)}</div></td><td>${escapeHtml(task.project)}</td><td><span class="badge ${task.status}">${task.status}</span></td><td>${task.risk_level}</td><td>${formatDate(task.updated_at)}</td></tr>`).join("");
}

function renderApprovals() {
  const approvals = state.dashboard.approvals;
  document.getElementById("approval-list").innerHTML = approvals.map((approval) => `
    <article class="approval">
      <div><div class="row-meta">${escapeHtml(approval.id)}</div><h2>${escapeHtml(approval.scope.project)} · ${escapeHtml(approval.scope.task_type)}</h2><span class="badge ${approval.status}">${approval.status}</span> <span class="row-meta">risk ${approval.risk_level}</span></div>
      ${approval.status === "pending" ? `<div class="approval-actions"><button class="secondary danger" data-decision="reject" data-id="${approval.id}">Reject</button><button class="command" data-decision="approve" data-id="${approval.id}">Approve</button></div>` : ""}
    </article>`).join("") || '<div class="empty">No approvals.</div>';
  document.querySelectorAll("[data-decision]").forEach((button) => button.addEventListener("click", async () => {
    const reason = window.prompt(`Reason to ${button.dataset.decision} this request:`);
    if (!reason || reason.length < 10) return toast("A reason of at least 10 characters is required.");
    await mutate(`/api/approvals/${button.dataset.id}/${button.dataset.decision}`, { reason, expires_in_seconds: 900 }, `Approval ${button.dataset.decision}d.`);
    await loadDashboard();
  }));
}

async function loadGraph() {
  const graph = await request("/api/knowledge/graph");
  const nodes = graph.nodes.slice(0, 80).map((node) => `<span class="node">${escapeHtml(node.name)} <small>${escapeHtml(node.kind)}</small></span>`).join("");
  const edges = graph.edges.slice(0, 20).map((edge) => `<div class="row-meta">${edge.source} → ${escapeHtml(edge.relation)} → ${edge.target}</div>`).join("");
  document.getElementById("graph").innerHTML = graph.nodes.length ? `<div class="graph-list">${nodes}</div>${edges}` : '<div class="empty">Index a document to build the graph.</div>';
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed.");
  return data;
}

async function mutate(url, payload, message) {
  const data = await request(url, { method: "POST", headers: intentHeaders, body: JSON.stringify(payload) });
  toast(message);
  return data;
}

function formatDate(value) {
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

function toast(message) {
  const element = document.getElementById("toast");
  element.textContent = message;
  element.classList.add("show");
  window.setTimeout(() => element.classList.remove("show"), 3000);
}

loadDashboard();
