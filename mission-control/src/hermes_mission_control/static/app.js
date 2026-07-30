const allowedViews = new Set(["command", "missions", "tasks", "approvals", "agents", "infrastructure", "research", "knowledge", "evidence"]);
const requestedView = new URLSearchParams(window.location.search).get("view");
const state = {
  dashboard: null,
  activeView: allowedViews.has(requestedView) ? requestedView : "command",
  missionFilter: "",
  demo: new URLSearchParams(window.location.search).get("demo") === "1",
};

const intentHeaders = {
  "Content-Type": "application/json",
  "X-Hermes-Intent": "founder-action",
};

const activeStatuses = new Set(["queued", "leased", "running", "pending_approval"]);
const terminalStatuses = new Set(["succeeded", "failed", "released", "cancelled"]);

document.querySelectorAll(".nav-item").forEach((button) => {
  button.addEventListener("click", () => navigate(button.dataset.view));
});
document.querySelectorAll("[data-navigate]").forEach((button) => {
  button.addEventListener("click", () => navigate(button.dataset.navigate));
});
document.querySelectorAll(".open-intake-copy").forEach((button) => {
  button.addEventListener("click", () => openIntake(button.textContent.includes("mission") ? "mission" : "task"));
});
document.getElementById("open-intake").addEventListener("click", () => openIntake("task"));
document.getElementById("refresh").addEventListener("click", loadDashboard);
document.getElementById("task-filter").addEventListener("input", renderTasks);
document.getElementById("status-filter").addEventListener("change", renderTasks);
document.getElementById("project-filter").addEventListener("change", renderTasks);
document.getElementById("artifact-filter").addEventListener("input", renderArtifacts);
document.getElementById("artifact-type-filter").addEventListener("change", renderArtifacts);
document.getElementById("mobile-menu").addEventListener("click", () => {
  document.getElementById("primary-nav").classList.toggle("open");
});
document.getElementById("close-inspector").addEventListener("click", closeInspector);
document.getElementById("inspector-backdrop").addEventListener("click", closeInspector);
document.getElementById("command-search").addEventListener("click", openGlobalSearch);
document.getElementById("exit-demo").addEventListener("click", () => {
  window.location.href = window.location.pathname;
});
document.getElementById("mission-segments").addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  state.missionFilter = button.dataset.filter;
  document.querySelectorAll("#mission-segments button").forEach((item) => item.classList.toggle("active", item === button));
  renderMissions();
});

document.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    openGlobalSearch();
  }
  if (event.key === "Escape") closeInspector();
});

document.getElementById("intake-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  if (state.demo) return toast("Actions are disabled in demonstration mode.");
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

document.getElementById("decision-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  if (state.demo) return toast("Decisions are disabled in demonstration mode.");
  const form = new FormData(event.target);
  const action = form.get("action");
  await mutate(
    `/api/approvals/${form.get("approval_id")}/${action}`,
    { reason: form.get("reason"), expires_in_seconds: 900 },
    `Approval ${action === "approve" ? "approved" : "rejected"}.`,
  );
  document.getElementById("decision-dialog").close();
  await loadDashboard();
});

document.getElementById("ingest-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demo) return toast("Indexing is disabled in demonstration mode.");
  const path = document.getElementById("ingest-path").value;
  await mutate("/api/knowledge/ingest", { path, confidentiality: "private" }, "Document indexed locally.");
  await loadGraph();
});

document.getElementById("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("search-query").value;
  if (state.demo) return renderDemoSearch(query);
  const data = await request(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
  renderSearchResults(data.results);
});

document.getElementById("global-search-input").addEventListener("input", renderGlobalSearch);

function navigate(view) {
  if (!allowedViews.has(view)) return;
  state.activeView = view;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((item) => item.classList.toggle("active", item.id === view));
  document.getElementById("primary-nav").classList.remove("open");
  const url = new URL(window.location.href);
  if (view === "command") url.searchParams.delete("view");
  else url.searchParams.set("view", view);
  window.history.replaceState({}, "", url);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function openIntake(kind) {
  const dialog = document.getElementById("intake-dialog");
  dialog.querySelector("[name=kind]").value = kind;
  dialog.showModal();
}

async function loadDashboard() {
  setLoading(true);
  try {
    state.dashboard = state.demo ? demoDashboard() : await request("/api/dashboard");
    document.getElementById("health").textContent = state.demo ? "Demo isolated" : "Control plane online";
    document.getElementById("health-dot").classList.toggle("ok", !state.demo);
    document.getElementById("demo-banner").hidden = !state.demo;
    renderAll();
    if (!state.demo) await loadGraph();
    else renderGraph(state.dashboard.graph);
    navigate(state.activeView);
  } catch (error) {
    document.getElementById("health").textContent = "Control plane unavailable";
    document.getElementById("health-dot").classList.remove("ok");
    renderUnavailable();
    toast(`${error.message} Add ?demo=1 to inspect the prototype safely.`);
  } finally {
    setLoading(false);
  }
}

function renderAll() {
  renderCommand();
  renderMissions();
  renderTasks();
  renderApprovals();
  renderAgents();
  renderInfrastructure();
  renderResearch();
  renderArtifacts();
}

function renderCommand() {
  const data = state.dashboard;
  const tasks = data.tasks || [];
  const agents = data.agents || [];
  const approvals = data.approvals || [];
  const pendingApprovals = approvals.filter((item) => item.status === "pending");
  const active = tasks.filter((item) => activeStatuses.has(item.status));
  const failed = tasks.filter((item) => item.status === "failed");
  const online = agents.filter((item) => agentStatus(item) === "online");
  const succeeded = tasks.filter((item) => item.status === "succeeded");

  document.getElementById("metrics").innerHTML = [
    metric(active.length, "Active tasks", `${tasks.length} total recorded`),
    metric(pendingApprovals.length, "Pending decisions", pendingApprovals.length ? "Founder action required" : "Queue clear"),
    metric(`${online.length}/${agents.length}`, "Online agents", "Across three machine roles"),
    metric(succeeded.length, "Verified outcomes", `${failed.length} failed preserved`),
  ].join("");

  document.getElementById("machine-strip").innerHTML = machineCells(agents);
  document.getElementById("mission-pulse").innerHTML = missionPulse(tasks);
  document.getElementById("active-execution").innerHTML = executionColumns(tasks);
  document.getElementById("fleet-summary").innerHTML = fleetRows(agents);
  document.getElementById("recent-proof").innerHTML = proofRows(tasks, data.artifacts || []);
  renderAttention();
  renderControls();
}

function metric(value, label, context) {
  return `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span><small>${escapeHtml(context)}</small></div>`;
}

function machineCells(agents) {
  const machines = [
    { key: "vm1", label: "VM1", role: "Engineering", symbol: "V1" },
    { key: "vm2", label: "VM2", role: "Production", symbol: "V2" },
    { key: "mac", label: "Mac", role: "Founder control", symbol: "MC" },
  ];
  return machines.map((machine) => {
    const members = agents.filter((agent) => machineKey(agent.machine) === machine.key);
    const online = members.filter((agent) => agentStatus(agent) === "online").length;
    const status = online ? "online" : members.length ? "offline" : "pending";
    return `<div class="machine-cell">
      <span class="machine-symbol">${machine.symbol}</span>
      <div><strong>${machine.label} · ${machine.role}</strong><small>${members.length} registered · ${online} online</small></div>
      ${statusBadge(status)}
    </div>`;
  }).join("");
}

function missionPulse(tasks) {
  const groups = groupMissions(tasks).slice(0, 4);
  if (!groups.length) return empty("No mission-linked execution yet.");
  return groups.map((mission) => {
    const progress = mission.total ? Math.round((mission.completed / mission.total) * 100) : 0;
    return `<button class="entity-row" data-mission="${escapeHtml(mission.key)}">
      <div class="entity-primary">
        <strong>${escapeHtml(mission.title)}</strong>
        <div class="entity-meta"><span>${mission.completed}/${mission.total} terminal</span><span>${mission.active} active</span><span>${mission.failed} failed</span></div>
        <div class="progress-track"><span style="width:${progress}%"></span></div>
      </div>
      <div class="entity-side">${statusBadge(mission.failed ? "failed" : mission.active ? "running" : "succeeded")}</div>
    </button>`;
  }).join("");
}

function executionColumns(tasks) {
  const columns = [
    ["Queued", ["queued", "pending_approval"]],
    ["Leased", ["leased"]],
    ["Running", ["running"]],
    ["Terminal", ["succeeded", "failed", "released"]],
  ];
  return columns.map(([label, statuses]) => {
    const items = tasks.filter((task) => statuses.includes(task.status)).slice(0, 3);
    return `<div class="flow-column"><h3>${label}<span class="flow-count">${tasks.filter((task) => statuses.includes(task.status)).length}</span></h3>
      ${items.map((task) => `<button class="flow-item" data-task-id="${task.id}"><strong>${escapeHtml(task.title)}</strong><span>${escapeHtml(task.task_number)}</span></button>`).join("") || '<div class="empty-state">None</div>'}
    </div>`;
  }).join("");
}

function fleetRows(agents) {
  if (!agents.length) return empty("No registered agents.");
  return agents.slice(0, 5).map((agent) => `<button class="entity-row" data-agent-id="${agent.id}">
    <div class="entity-primary"><strong>${escapeHtml(agent.display_name || agent.slug)}</strong><div class="entity-meta"><span class="mono">${escapeHtml(agent.machine)}</span><span>${(agent.capabilities || []).length} capabilities</span></div></div>
    <div class="entity-side">${statusBadge(agentStatus(agent))}</div>
  </button>`).join("");
}

function proofRows(tasks, artifacts) {
  const terminal = tasks.filter((task) => terminalStatuses.has(task.status)).slice(0, 5);
  if (!terminal.length) return empty("No terminal outcomes.");
  return terminal.map((task) => {
    const count = artifacts.filter((artifact) => artifact.task_id === task.id).length;
    return `<button class="entity-row" data-task-id="${task.id}">
      <div class="entity-primary"><strong>${escapeHtml(task.title)}</strong><div class="entity-meta"><span>${count} artifacts</span><span>${relativeTime(task.updated_at)}</span></div></div>
      <div class="entity-side">${statusBadge(task.status)}</div>
    </button>`;
  }).join("");
}

function renderAttention() {
  const data = state.dashboard;
  const items = [];
  (data.approvals || []).filter((item) => item.status === "pending").forEach((approval) => {
    items.push({ severity: "pending", title: `${approval.scope?.project || "Project"} approval`, detail: `Risk ${approval.risk_level} · ${approval.scope?.task_type || "operation"}`, approval });
  });
  (data.tasks || []).filter((task) => task.status === "failed").slice(0, 3).forEach((task) => {
    items.push({ severity: "critical", title: task.title, detail: `Failed · ${relativeTime(task.updated_at)}`, task });
  });
  (data.agents || []).filter((agent) => agentStatus(agent) === "offline").slice(0, 2).forEach((agent) => {
    items.push({ severity: "critical", title: `${agent.display_name || agent.slug} offline`, detail: agent.machine, agent });
  });
  (data.tasks || []).filter((task) => task.status === "queued").slice(0, 2).forEach((task) => {
    items.push({ severity: "info", title: task.title, detail: `Queued · ${relativeTime(task.updated_at)}`, task });
  });
  document.getElementById("attention-count").textContent = items.length;
  document.getElementById("approval-count").textContent = (data.approvals || []).filter((item) => item.status === "pending").length;
  document.getElementById("attention-list").innerHTML = items.length ? items.map((item, index) => `
    <button class="attention-item ${item.severity}" data-attention="${index}">
      <span class="attention-bar"></span>
      <span><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></span>
    </button>`).join("") : empty("Nothing requires founder action.");
  document.querySelectorAll("[data-attention]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = items[Number(button.dataset.attention)];
      if (item.approval) navigate("approvals");
      else if (item.task) openTask(item.task.id);
      else if (item.agent) openAgent(item.agent.id);
    });
  });
}

function renderControls() {
  const scopes = state.dashboard.control_scopes || [];
  document.getElementById("controls").innerHTML = scopes.length ? scopes.map((scope) => `
    <div class="control-row"><div><strong>${escapeHtml(scope.scope_type)} · ${escapeHtml(scope.scope_key)}</strong><div class="entity-meta">${escapeHtml(scope.reason || "No restriction")}</div></div>${statusBadge(scope.is_paused ? "paused" : "active")}</div>
  `).join("") : `<div class="control-row"><strong>Global execution</strong>${statusBadge("active")}</div>`;
}

function renderMissions() {
  if (!state.dashboard) return;
  let missions = groupMissions(state.dashboard.tasks || []);
  if (state.missionFilter === "active") missions = missions.filter((item) => item.active);
  if (state.missionFilter === "completed") missions = missions.filter((item) => !item.active && !item.failed);
  if (state.missionFilter === "attention") missions = missions.filter((item) => item.failed);
  document.getElementById("mission-list").innerHTML = missions.length ? missions.map((mission) => {
    const progress = mission.total ? Math.round((mission.completed / mission.total) * 100) : 0;
    return `<div class="mission-row" data-mission="${escapeHtml(mission.key)}">
      <div><h3>${escapeHtml(mission.title)}</h3><div class="entity-meta"><span class="mono">${escapeHtml(mission.key)}</span><span>${mission.total} tasks</span></div><div class="progress-track"><span style="width:${progress}%"></span></div></div>
      <div><strong>${progress}%</strong><div class="entity-meta"><span>${mission.completed} terminal</span></div></div>
      <div class="entity-meta"><span>${mission.active} active</span><span>${mission.failed} failed</span></div>
      ${statusBadge(mission.failed ? "failed" : mission.active ? "running" : "succeeded")}
    </div>`;
  }).join("") : empty("No missions match this view.");
}

function groupMissions(tasks) {
  const groups = new Map();
  tasks.forEach((task) => {
    const key = task.mission_id || task.project || "unassigned";
    if (!groups.has(key)) groups.set(key, { key, title: missionTitle(task), tasks: [], total: 0, completed: 0, active: 0, failed: 0 });
    const group = groups.get(key);
    group.tasks.push(task);
    group.total += 1;
    group.completed += terminalStatuses.has(task.status) ? 1 : 0;
    group.active += activeStatuses.has(task.status) ? 1 : 0;
    group.failed += task.status === "failed" ? 1 : 0;
  });
  return [...groups.values()].sort((a, b) => (b.active + b.failed) - (a.active + a.failed) || b.total - a.total);
}

function missionTitle(task) {
  if (task.mission_id && task.objective) return task.objective;
  return task.project === "swarm-control-plane" ? "Hermes platform delivery" : task.project.replaceAll("_", " ");
}

function renderTasks() {
  if (!state.dashboard) return;
  const allTasks = state.dashboard.tasks || [];
  populateSelect("status-filter", [...new Set(allTasks.map((task) => task.status))].sort(), "All statuses");
  populateSelect("project-filter", [...new Set(allTasks.map((task) => task.project))].sort(), "All projects");
  const text = document.getElementById("task-filter").value.toLowerCase();
  const status = document.getElementById("status-filter").value;
  const project = document.getElementById("project-filter").value;
  const tasks = allTasks.filter((task) =>
    (!status || task.status === status) &&
    (!project || task.project === project) &&
    (!text || `${task.title} ${task.task_number} ${task.project} ${task.task_type}`.toLowerCase().includes(text))
  );
  document.getElementById("task-table").innerHTML = tasks.length ? tasks.map((task) => `
    <tr data-task-id="${task.id}">
      <td><strong>${escapeHtml(task.title)}</strong><span class="mono">${escapeHtml(task.task_number)}</span></td>
      <td>${escapeHtml(task.project)}</td>
      <td>${escapeHtml(humanize(task.task_type))}</td>
      <td>${statusBadge(task.status)}</td>
      <td><span class="risk ${task.risk_level >= 3 ? "high" : ""}">${task.risk_level}</span></td>
      <td>${formatDate(task.updated_at)}</td>
      <td class="row-open">›</td>
    </tr>`).join("") : `<tr><td colspan="7">${empty("No tasks match these filters.")}</td></tr>`;
  bindEntityButtons();
}

function renderApprovals() {
  if (!state.dashboard) return;
  const approvals = state.dashboard.approvals || [];
  document.getElementById("approval-list").innerHTML = approvals.length ? approvals.map((approval) => `
    <article class="approval">
      <div>
        <div class="approval-scope">${escapeHtml(approval.id)}</div>
        <h2>${escapeHtml(approval.scope?.project || "Unknown project")} · ${escapeHtml(humanize(approval.scope?.task_type || "operation"))}</h2>
        <div class="entity-meta"><span>Risk ${approval.risk_level}</span><span>Plan ${shortHash(approval.plan_digest)}</span><span>Requested ${relativeTime(approval.created_at)}</span></div>
        <div style="margin-top:9px">${statusBadge(approval.status)}</div>
      </div>
      ${approval.status === "pending" ? `<div class="approval-actions"><button class="secondary danger" data-decision="reject" data-id="${approval.id}">Reject</button><button class="command" data-decision="approve" data-id="${approval.id}">Review & approve</button></div>` : ""}
    </article>`).join("") : empty("No approvals recorded.");
  document.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => openDecision(button.dataset.id, button.dataset.decision));
  });
}

function openDecision(id, action) {
  const approval = state.dashboard.approvals.find((item) => String(item.id) === id);
  if (!approval) return;
  const form = document.getElementById("decision-form");
  form.reset();
  form.elements.approval_id.value = id;
  form.elements.action.value = action;
  document.getElementById("decision-title").textContent = action === "approve" ? "Authorize operation" : "Reject operation";
  document.getElementById("decision-submit").textContent = action === "approve" ? "Approve for 15 minutes" : "Reject request";
  document.getElementById("decision-submit").className = action === "approve" ? "command" : "secondary danger";
  document.getElementById("decision-summary").innerHTML = `<dl>
    <dt>Project</dt><dd>${escapeHtml(approval.scope?.project || "Unknown")}</dd>
    <dt>Operation</dt><dd>${escapeHtml(humanize(approval.scope?.task_type || "operation"))}</dd>
    <dt>Risk</dt><dd>${approval.risk_level}</dd>
    <dt>Plan digest</dt><dd class="mono">${escapeHtml(approval.plan_digest)}</dd>
  </dl>`;
  document.getElementById("decision-dialog").showModal();
}

function renderAgents() {
  if (!state.dashboard) return;
  const agents = state.dashboard.agents || [];
  document.getElementById("agent-matrix").innerHTML = agents.length ? agents.map((agent) => `
    <article class="agent-card" data-agent-id="${agent.id}">
      <div class="agent-header"><div><h3>${escapeHtml(agent.display_name || agent.slug)}</h3><div class="agent-machine">${escapeHtml(agent.machine)}</div></div>${statusBadge(agentStatus(agent))}</div>
      <div class="capabilities">${(agent.capabilities || []).map((capability) => `<span class="capability">${escapeHtml(capability)}</span>`).join("")}</div>
      <div class="agent-footer"><span>Risk ceiling ${agent.risk_ceiling ?? "–"}</span><span>${escapeHtml(agent.role || agent.hermes_profile || "Worker")}</span></div>
    </article>`).join("") : empty("No agents registered.");
  bindEntityButtons();
}

function renderInfrastructure() {
  if (!state.dashboard) return;
  const tasks = (state.dashboard.tasks || []).filter((task) => task.task_type?.startsWith("infrastructure"));
  const latest = tasks[0];
  const labels = [
    ["API", latest?.status === "failed" ? "failed" : "healthy"],
    ["PostgreSQL", "healthy"],
    ["Redis", "healthy"],
    ["Backup evidence", tasks.some((task) => task.status === "succeeded") ? "verified" : "pending"],
  ];
  document.getElementById("infra-strip").innerHTML = labels.map(([label, value], index) => `
    <div class="machine-cell"><span class="machine-symbol">${["AP", "PG", "RD", "BK"][index]}</span><div><strong>${label}</strong><small>VM2 production</small></div>${statusBadge(value === "healthy" || value === "verified" ? "success" : value)}</div>
  `).join("");
  document.getElementById("infra-tasks").innerHTML = tasks.length ? tasks.map((task) => taskEntityRow(task)).join("") : empty("No infrastructure tasks recorded.");
  bindEntityButtons();
}

function renderResearch() {
  if (!state.dashboard) return;
  const tasks = (state.dashboard.tasks || []).filter((task) => task.task_type === "research_experiment");
  const accepted = tasks.filter((task) => task.result?.summary?.verdict === "accepted").length;
  document.getElementById("research-gate").innerHTML = `
    <span class="gate-symbol">G</span>
    <div><strong>Research promotion gate enforced</strong><div class="entity-meta"><span>${accepted} synthetic findings accepted</span><span>Live deployment requires a separate approval path</span></div></div>
    ${statusBadge("active")}
  `;
  document.getElementById("research-list").innerHTML = tasks.length ? tasks.map((task) => {
    const summary = task.result?.summary || {};
    const oos = summary.out_of_sample || {};
    return `<div class="research-row" data-task-id="${task.id}">
      <div><h3>${escapeHtml(summary.hypothesis_id || task.title)}</h3><div class="entity-meta"><span>${escapeHtml(summary.program_id || task.task_number)}</span><span class="mono">${shortHash(summary.evidence_sha256 || task.result?.base_commit)}</span></div></div>
      <div class="research-stat"><strong>${number(oos.annualized_sharpe)}</strong><span>OOS Sharpe</span></div>
      <div class="research-stat"><strong>${percent(oos.maximum_drawdown)}</strong><span>Max drawdown</span></div>
      <div class="research-stat"><strong>${oos.trades ?? "–"}</strong><span>Trades</span></div>
      <div>${statusBadge(summary.verdict || task.status)}<div class="entity-meta"><span>${summary.production_eligible === false ? "Not production eligible" : "Gate unknown"}</span></div></div>
    </div>`;
  }).join("") : empty("No research experiments recorded.");
  bindEntityButtons();
}

function renderArtifacts() {
  if (!state.dashboard) return;
  const allArtifacts = state.dashboard.artifacts || [];
  populateSelect("artifact-type-filter", [...new Set(allArtifacts.map((item) => item.artifact_type))].sort(), "All types");
  const text = document.getElementById("artifact-filter").value.toLowerCase();
  const type = document.getElementById("artifact-type-filter").value;
  const artifacts = allArtifacts.filter((item) =>
    (!type || item.artifact_type === type) &&
    (!text || `${item.name} ${item.workflow} ${item.sha256} ${item.source_commit}`.toLowerCase().includes(text))
  );
  document.getElementById("artifact-list").innerHTML = artifacts.length ? artifacts.map((artifact) => `
    <div class="artifact-row" data-artifact-id="${artifact.id}">
      <div class="artifact-name"><strong>${escapeHtml(artifact.name)}</strong><span>${escapeHtml(artifact.workflow || "workflow")} · attempt ${artifact.attempt_number ?? "–"}</span></div>
      ${statusBadge(artifact.artifact_type)}
      <span>${formatBytes(artifact.size_bytes)}</span>
      <span class="digest" title="${escapeHtml(artifact.sha256)}">${escapeHtml(artifact.sha256)}</span>
      <span class="mono">${shortHash(artifact.source_commit)}</span>
      <span class="row-open">›</span>
    </div>`).join("") : empty("No artifacts match this view.");
  bindEntityButtons();
}

function bindEntityButtons() {
  document.querySelectorAll("[data-task-id]").forEach((element) => {
    element.onclick = () => openTask(element.dataset.taskId);
  });
  document.querySelectorAll("[data-agent-id]").forEach((element) => {
    element.onclick = () => openAgent(element.dataset.agentId);
  });
  document.querySelectorAll("[data-artifact-id]").forEach((element) => {
    element.onclick = () => openArtifact(element.dataset.artifactId);
  });
}

function openTask(id) {
  const task = state.dashboard.tasks.find((item) => String(item.id) === String(id));
  if (!task) return;
  const artifacts = (state.dashboard.artifacts || []).filter((item) => item.task_id === task.id);
  openInspector("Task", task.title, `
    <section class="detail-section"><h3>Lifecycle</h3><dl class="detail-grid">
      <dt>Status</dt><dd>${statusBadge(task.status)}</dd>
      <dt>Task number</dt><dd class="mono">${escapeHtml(task.task_number)}</dd>
      <dt>Type</dt><dd>${escapeHtml(humanize(task.task_type))}</dd>
      <dt>Project</dt><dd>${escapeHtml(task.project)}</dd>
      <dt>Attempt</dt><dd>${task.attempt_count} of ${task.max_attempts}</dd>
      <dt>Risk</dt><dd>${task.risk_level}</dd>
      <dt>Updated</dt><dd>${formatDate(task.updated_at)}</dd>
    </dl></section>
    <section class="detail-section"><h3>Objective</h3><p>${escapeHtml(task.objective)}</p></section>
    <section class="detail-section"><h3>Execution evidence</h3><dl class="detail-grid">
      <dt>Artifacts</dt><dd>${artifacts.length}</dd>
      <dt>Base commit</dt><dd class="mono">${escapeHtml(task.result?.base_commit || "Not recorded")}</dd>
      <dt>Workflow</dt><dd>${escapeHtml(task.result?.workflow || task.input_contract?.workflow || "Not recorded")}</dd>
      <dt>Success</dt><dd>${String(task.result?.success ?? false)}</dd>
    </dl></section>
    ${task.result?.summary ? `<section class="detail-section"><h3>Result summary</h3><pre class="json-view">${escapeHtml(JSON.stringify(task.result.summary, null, 2))}</pre></section>` : ""}
    <section class="detail-section"><h3>Structured contract</h3><pre class="json-view">${escapeHtml(JSON.stringify(task.input_contract || {}, null, 2))}</pre></section>
  `);
}

function openAgent(id) {
  const agent = state.dashboard.agents.find((item) => String(item.id) === String(id));
  if (!agent) return;
  openInspector("Agent", agent.display_name || agent.slug, `
    <section class="detail-section"><h3>Identity</h3><dl class="detail-grid">
      <dt>Slug</dt><dd class="mono">${escapeHtml(agent.slug)}</dd>
      <dt>Machine</dt><dd>${escapeHtml(agent.machine)}</dd>
      <dt>Presence</dt><dd>${statusBadge(agentStatus(agent))}</dd>
      <dt>Enabled</dt><dd>${String(agent.is_enabled ?? agent.enabled ?? true)}</dd>
      <dt>Risk ceiling</dt><dd>${agent.risk_ceiling ?? "–"}</dd>
      <dt>Role</dt><dd>${escapeHtml(agent.role || agent.hermes_profile || "Worker")}</dd>
    </dl></section>
    <section class="detail-section"><h3>Capabilities</h3><div class="capabilities">${(agent.capabilities || []).map((item) => `<span class="capability">${escapeHtml(item)}</span>`).join("")}</div></section>
  `);
}

function openArtifact(id) {
  const artifact = state.dashboard.artifacts.find((item) => String(item.id) === String(id));
  if (!artifact) return;
  openInspector("Evidence", artifact.name, `
    <section class="detail-section"><h3>Provenance</h3><dl class="detail-grid">
      <dt>Type</dt><dd>${statusBadge(artifact.artifact_type)}</dd>
      <dt>Workflow</dt><dd>${escapeHtml(artifact.workflow || "–")}</dd>
      <dt>Version</dt><dd>${escapeHtml(artifact.workflow_version || "–")}</dd>
      <dt>Attempt</dt><dd>${artifact.attempt_number ?? "–"}</dd>
      <dt>Size</dt><dd>${formatBytes(artifact.size_bytes)}</dd>
      <dt>Verification</dt><dd>${escapeHtml(artifact.verification_status || "registered")}</dd>
    </dl></section>
    <section class="detail-section"><h3>Integrity</h3><dl class="detail-grid">
      <dt>SHA-256</dt><dd class="mono">${escapeHtml(artifact.sha256)}</dd>
      <dt>Source commit</dt><dd class="mono">${escapeHtml(artifact.source_commit)}</dd>
      <dt>Location</dt><dd class="mono">${escapeHtml(artifact.location || "Workspace-local")}</dd>
    </dl></section>
  `);
}

function openInspector(kicker, title, body) {
  document.getElementById("inspector-kicker").textContent = kicker;
  document.getElementById("inspector-title").textContent = title;
  document.getElementById("inspector-body").innerHTML = body;
  document.getElementById("inspector").classList.add("open");
  document.getElementById("inspector").setAttribute("aria-hidden", "false");
  document.getElementById("inspector-backdrop").classList.add("open");
}

function closeInspector() {
  document.getElementById("inspector").classList.remove("open");
  document.getElementById("inspector").setAttribute("aria-hidden", "true");
  document.getElementById("inspector-backdrop").classList.remove("open");
}

function openGlobalSearch() {
  const dialog = document.getElementById("search-dialog");
  dialog.showModal();
  const input = document.getElementById("global-search-input");
  input.value = "";
  renderGlobalSearch();
  window.setTimeout(() => input.focus(), 0);
}

function renderGlobalSearch() {
  if (!state.dashboard) return;
  const query = document.getElementById("global-search-input").value.toLowerCase();
  const results = [
    ...(state.dashboard.tasks || []).map((item) => ({ type: "Task", label: item.title, meta: item.task_number, open: () => openTask(item.id) })),
    ...(state.dashboard.agents || []).map((item) => ({ type: "Agent", label: item.display_name || item.slug, meta: item.machine, open: () => openAgent(item.id) })),
    ...(state.dashboard.artifacts || []).map((item) => ({ type: "Evidence", label: item.name, meta: shortHash(item.sha256), open: () => openArtifact(item.id) })),
  ].filter((item) => !query || `${item.label} ${item.meta} ${item.type}`.toLowerCase().includes(query)).slice(0, 12);
  document.getElementById("global-search-results").innerHTML = results.length ? results.map((item, index) => `
    <button class="search-result" data-search-index="${index}"><span class="search-result-type">${item.type}</span><strong>${escapeHtml(item.label)}</strong><span class="mono">${escapeHtml(item.meta)}</span></button>
  `).join("") : empty("No matching entities.");
  document.querySelectorAll("[data-search-index]").forEach((button) => {
    button.addEventListener("click", () => {
      document.getElementById("search-dialog").close();
      results[Number(button.dataset.searchIndex)].open();
    });
  });
}

async function loadGraph() {
  try {
    renderGraph(await request("/api/knowledge/graph"));
  } catch (error) {
    document.getElementById("graph").innerHTML = empty("Knowledge graph unavailable.");
  }
}

function renderGraph(graph) {
  const nodes = (graph.nodes || []).slice(0, 80);
  const nodeMap = new Map(nodes.map((node) => [node.id, node.name]));
  const edges = (graph.edges || []).slice(0, 24);
  document.getElementById("graph").innerHTML = nodes.length ? `
    <div class="graph-list">${nodes.map((node) => `<span class="node">${escapeHtml(node.name)} <small>${escapeHtml(node.kind)}</small></span>`).join("")}</div>
    ${edges.map((edge) => `<div class="graph-edge">${escapeHtml(nodeMap.get(edge.source) || edge.source)} → ${escapeHtml(edge.relation)} → ${escapeHtml(nodeMap.get(edge.target) || edge.target)}</div>`).join("")}
  ` : empty("Index a document to build the graph.");
}

function renderSearchResults(results) {
  document.getElementById("search-results").innerHTML = results.length ? results.map((item) => `
    <article class="result"><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.excerpt)}</p><div class="citation">${escapeHtml(item.citation)}</div></article>
  `).join("") : empty("No cited matches.");
}

function renderDemoSearch(query) {
  const q = query.toLowerCase();
  const results = [
    {
      title: "M8 Research Mission Validation",
      excerpt: "The bounded synthetic pilot succeeded on attempt 1 under vm1-research-runner. The finding is explicitly ineligible for production.",
      citation: "docs/m8-validation.md:49-118 · sha256:a6831781…",
    },
    {
      title: "Hermes Swarm Delivery Plan",
      excerpt: "VM1 performs engineering and research execution, VM2 performs production operations, and the Mac is the founder command center.",
      citation: "docs/hermes-swarm-delivery-plan.md:43-68 · sha256:8914a183…",
    },
  ].filter((item) => `${item.title} ${item.excerpt}`.toLowerCase().includes(q));
  renderSearchResults(results);
}

function taskEntityRow(task) {
  return `<button class="entity-row" data-task-id="${task.id}">
    <div class="entity-primary"><strong>${escapeHtml(task.title)}</strong><div class="entity-meta"><span class="mono">${escapeHtml(task.task_number)}</span><span>${relativeTime(task.updated_at)}</span></div></div>
    <div class="entity-side"><span class="risk ${task.risk_level >= 3 ? "high" : ""}">${task.risk_level}</span>${statusBadge(task.status)}</div>
  </button>`;
}

function populateSelect(id, values, placeholder) {
  const select = document.getElementById(id);
  const selected = select.value;
  select.innerHTML = `<option value="">${placeholder}</option>${values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(humanize(value))}</option>`).join("")}`;
  select.value = selected;
}

function statusBadge(status) {
  const safe = String(status || "unknown").toLowerCase().replace(/[^a-z0-9_-]/g, "");
  return `<span class="status ${safe}">${escapeHtml(humanize(status || "unknown"))}</span>`;
}

function agentStatus(agent) {
  if (agent.is_enabled === false || agent.enabled === false) return "offline";
  return agent.status || agent.presence || "offline";
}

function machineKey(machine = "") {
  const value = machine.toLowerCase();
  if (value.includes("vm1")) return "vm1";
  if (value.includes("vm2")) return "vm2";
  return "mac";
}

function number(value) {
  return typeof value === "number" ? value.toFixed(2) : "–";
}

function percent(value) {
  return typeof value === "number" ? `${(value * 100).toFixed(2)}%` : "–";
}

function humanize(value) {
  return String(value ?? "").replaceAll("_", " ").replaceAll("-", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function shortHash(value) {
  return value ? `${String(value).slice(0, 8)}…` : "–";
}

function formatBytes(value) {
  if (!Number.isFinite(Number(value))) return "–";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KiB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function formatDate(value) {
  if (!value) return "–";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "–";
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(date);
}

function relativeTime(value) {
  if (!value) return "unknown";
  const delta = Date.now() - new Date(value).getTime();
  if (!Number.isFinite(delta)) return "unknown";
  const minutes = Math.max(0, Math.floor(delta / 60000));
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function empty(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" }[char]));
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  let data;
  try {
    data = await response.json();
  } catch (_) {
    data = {};
  }
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Request failed.");
  return data;
}

async function mutate(url, payload, message) {
  const data = await request(url, { method: "POST", headers: intentHeaders, body: JSON.stringify(payload) });
  toast(message);
  return data;
}

function toast(message) {
  const element = document.getElementById("toast");
  element.textContent = message;
  element.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => element.classList.remove("show"), 3200);
}

function setLoading(loading) {
  document.getElementById("refresh").disabled = loading;
  document.getElementById("refresh").setAttribute("aria-busy", String(loading));
}

function renderUnavailable() {
  if (state.dashboard) return;
  document.getElementById("metrics").innerHTML = [
    metric("–", "Active tasks", "Control plane unavailable"),
    metric("–", "Pending decisions", "State not loaded"),
    metric("–", "Online agents", "State not loaded"),
    metric("–", "Verified outcomes", "State not loaded"),
  ].join("");
  document.getElementById("machine-strip").innerHTML = ["VM1", "VM2", "Mac"].map((label) => `<div class="machine-cell"><span class="machine-symbol">${label.slice(0, 2)}</span><div><strong>${label}</strong><small>State unavailable</small></div>${statusBadge("offline")}</div>`).join("");
}

function updateClock() {
  document.getElementById("clock").textContent = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "UTC" }).format(new Date());
}

function demoDashboard() {
  const now = new Date().toISOString();
  const task = {
    id: "4e2feecf-3dbc-4946-9bbf-1613ddf211ce",
    task_number: "M8-RESEARCH-20260730T125144329740Z",
    project: "bulletproof_bt",
    task_type: "research_experiment",
    title: "M8 synthetic momentum research pilot",
    objective: "Execute and independently audit one predeclared synthetic research hypothesis.",
    status: "succeeded",
    risk_level: 1,
    attempt_count: 1,
    max_attempts: 1,
    updated_at: now,
    input_contract: { repository: "bulletproof_bt", workflow: "research-experiment", base_ref: "main", hypothesis: "lagged-return-momentum", dataset: "synthetic-regime-v1", seed: 20260730 },
    result: {
      success: true,
      workflow: "research-experiment",
      base_commit: "10b8870ad5e80b6dab6e7362ad1d4033302266db",
      summary: {
        program_id: "M8-SYNTHETIC-MOMENTUM",
        hypothesis_id: "M8-H1-LAGGED-MOMENTUM",
        verdict: "accepted",
        production_eligible: false,
        audit_passed: true,
        evidence_sha256: "a68317817f2b39c760f1c4743050ad6a5d5719b51db543c5b0eb9983b4d398c8",
        out_of_sample: { annualized_sharpe: 6.24037808, maximum_drawdown: 0.02786945, trades: 121, observations: 420 },
      },
    },
  };
  return {
    health: { status: "ok" },
    tasks: [
      task,
      { id: "infra-1", task_number: "VM2-RESTART-20260730", project: "swarm-control-plane", task_type: "infrastructure_operation", title: "Approved controlled VM2 API restart", objective: "Restart only the control-plane API with pre/post checks.", status: "succeeded", risk_level: 3, attempt_count: 1, max_attempts: 1, updated_at: now, input_contract: { operation: "restart-control-plane-api" }, result: { success: true, workflow: "vm2-infrastructure" } },
      { id: "mission-1", task_number: "M9-PLANNER-001", project: "swarm-control-plane", task_type: "founder_request", title: "Design the next autonomous planning milestone", objective: "Prepare M9 for founder review.", status: "queued", risk_level: 0, attempt_count: 0, max_attempts: 1, updated_at: now, input_contract: { request_kind: "mission" }, result: {} },
      { id: "code-1", task_number: "M6-ENGINEERING-004", project: "swarm-control-plane", task_type: "engineering_mission", title: "Validate infrastructure evidence registration", objective: "Add bounded artifact evidence.", status: "succeeded", risk_level: 1, attempt_count: 1, max_attempts: 1, updated_at: now, input_contract: { workflow: "engineering-mission" }, result: { success: true, workflow: "engineering-mission", base_commit: "510883dcd35bdc81ebfe9ed3c2559ab47f042109" } },
      { id: "failed-1", task_number: "M8-RESEARCH-DISCOVERY", project: "bulletproof_bt", task_type: "research_experiment", title: "M8 validation-boundary discovery", objective: "Run the first supervised pilot.", status: "failed", risk_level: 1, attempt_count: 1, max_attempts: 1, updated_at: new Date(Date.now() - 3600000).toISOString(), input_contract: { workflow: "research-experiment" }, result: {} },
    ],
    agents: [
      { id: "agent-eng", slug: "vm1-developer-coder", display_name: "VM1 Engineering Worker", machine: "vm1-developer", role: "Restricted engineering", status: "online", is_enabled: true, risk_ceiling: 1, capabilities: ["git", "python", "testing", "backtesting"] },
      { id: "23c62000-1fad-48bb-8ce5-3f4cb26f3779", slug: "vm1-research-runner", display_name: "VM1 Research Runner", machine: "vm1-developer", role: "Restricted research", status: "online", is_enabled: true, risk_ceiling: 1, capabilities: ["git", "python", "backtesting", "research-audit"] },
      { id: "agent-infra", slug: "vm2-infrastructure-operator", display_name: "VM2 Infrastructure Operator", machine: "vm2-deployment", role: "Approved infrastructure runbooks", status: "online", is_enabled: true, risk_ceiling: 3, capabilities: ["infrastructure-observation", "service-health", "controlled-restart"] },
      { id: "agent-mac", slug: "mac-founder-control", display_name: "Mac Founder Control", machine: "mac-founder", role: "Founder command surface", status: "online", is_enabled: true, risk_ceiling: 0, capabilities: ["founder-intake", "knowledge-search"] },
    ],
    approvals: [
      { id: "approval-demo", status: "pending", risk_level: 3, created_at: now, plan_digest: "bc50ba1014ff33e68defbba9a1c727e2513d782fa1473547834d62cba1c16879", scope: { project: "swarm-control-plane", task_type: "infrastructure_operation" } },
    ],
    artifacts: [
      { id: "artifact-evidence", task_id: task.id, attempt_number: 1, artifact_type: "result", name: "research-evidence.json", size_bytes: 1917, sha256: "a68317817f2b39c760f1c4743050ad6a5d5719b51db543c5b0eb9983b4d398c8", source_commit: task.result.base_commit, workflow: "research-experiment", workflow_version: "1.0.0", verification_status: "verified", location: "workspace-local" },
      { id: "artifact-audit", task_id: task.id, attempt_number: 1, artifact_type: "evidence", name: "research-audit.json", size_bytes: 818, sha256: "3c34b883b29be9214640e66e8103051e334f1cabd7570a2ffcf3d29b698c8b88", source_commit: task.result.base_commit, workflow: "research-experiment", workflow_version: "1.0.0", verification_status: "verified", location: "workspace-local" },
      { id: "artifact-report", task_id: task.id, attempt_number: 1, artifact_type: "report", name: "research-report.md", size_bytes: 876, sha256: "7743669b2813b5acf4cdb081f3ca0e578251139fee58cfe2c088000ef5c90fc1", source_commit: task.result.base_commit, workflow: "research-experiment", workflow_version: "1.0.0", verification_status: "verified", location: "workspace-local" },
    ],
    control_scopes: [],
    knowledge: { sources: 2, chunks: 209, entities: 7, edges: 5 },
    graph: {
      nodes: [
        { id: 1, name: "Hermes", kind: "system" },
        { id: 2, name: "VM1", kind: "machine" },
        { id: 3, name: "VM2", kind: "machine" },
        { id: 4, name: "Mac", kind: "machine" },
        { id: 5, name: "M8", kind: "milestone" },
      ],
      edges: [
        { source: 1, target: 2, relation: "engineered_on" },
        { source: 1, target: 3, relation: "operates_on" },
        { source: 1, target: 4, relation: "directed_from" },
        { source: 5, target: 2, relation: "executed_on" },
      ],
    },
  };
}

updateClock();
window.setInterval(updateClock, 30000);
loadDashboard();
