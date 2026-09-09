const allowedViews = new Set(["command", "work", "activity", "missions", "tasks", "proposals", "approvals", "agents", "infrastructure", "research", "knowledge", "notes", "evidence"]);
const requestedView = new URLSearchParams(window.location.search).get("view");
const allowedResearchModes = new Set(["ask", "explore", "library"]);
const requestedResearchMode = new URLSearchParams(window.location.search).get("workspace");
const requestedApproval = new URLSearchParams(window.location.search).get("approval");
const state = {
  dashboard: null,
  activeView: allowedViews.has(requestedView) ? requestedView : "command",
  missionFilter: "",
  demo: new URLSearchParams(window.location.search).get("demo") === "1",
  copilotConversationId: null,
  copilotTurns: [],
  graphData: null,
  graphSelectedId: null,
  graphView: window.matchMedia("(max-width: 680px)").matches ? "list" : "visual",
  graphTransform: { scale: 1, x: 0, y: 0 },
  researchMode: allowedResearchModes.has(requestedResearchMode) ? requestedResearchMode : "ask",
  researchContext: [],
  conversations: [],
  activeConversationId: null,
  conversationWorkspace: null,
  conversationWorkspaceLoading: false,
  requestedApprovalOpened: false,
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
document.getElementById("refresh-activity").addEventListener("click", loadDashboard);
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
document.querySelectorAll("[data-graph-view]").forEach((button) => {
  button.addEventListener("click", () => {
    state.graphView = button.dataset.graphView;
    document.querySelectorAll("[data-graph-view]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    if (state.graphData) renderGraph(state.graphData);
  });
});
document.getElementById("graph-query-form").addEventListener("submit", querySelectedGraphNode);
document.querySelectorAll("[data-research-mode]").forEach((button) => {
  button.addEventListener("click", () => setResearchMode(button.dataset.researchMode));
  button.addEventListener("keydown", (event) => navigateResearchTabs(event, button));
});
document.getElementById("clear-research-context").addEventListener("click", () => {
  state.researchContext = [];
  renderResearchContext();
});
document.getElementById("new-conversation").addEventListener("click", createConversation);
document.getElementById("refresh-conversations").addEventListener("click", loadConversations);
document.getElementById("conversation-form").addEventListener("submit", continueConversation);
document.getElementById("new-conversation-form").addEventListener("submit", submitConversation);
document.querySelectorAll("[data-close-dialog]").forEach((button) => {
  button.addEventListener("click", () => button.closest("dialog")?.close());
});
document.querySelectorAll("[data-conversation-action]").forEach((button) => {
  button.addEventListener("click", () => transitionConversation(button.dataset.conversationAction));
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
    { reason: form.get("reason"), expires_in_seconds: 900, expected_review_digest: form.get("review_digest") },
    `Approval ${action === "approve" ? "approved" : "rejected"}.`,
  );
  document.getElementById("decision-dialog").close();
  await loadDashboard();
});

document.getElementById("proposal-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  if (state.demo) return toast("Decisions are disabled in demonstration mode.");
  const form = new FormData(event.target);
  const action = form.get("action");
  await mutate(
    `/api/proposals/${form.get("proposal_id")}/${action}`,
    { reason: form.get("reason") },
    action === "materialize" ? "Governed task created." : "Proposal rejected.",
  );
  document.getElementById("proposal-dialog").close();
  await loadDashboard();
});

document.getElementById("ingest-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demo) return toast("Indexing is disabled in demonstration mode.");
  const path = document.getElementById("ingest-path").value;
  await mutate("/api/knowledge/ingest", { path, confidentiality: "private" }, "Document indexed locally.");
  await loadGraph();
});

document.getElementById("research-upload-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demo) return toast("Uploads are disabled in demonstration mode.");
  const response = await fetch("/api/research/sources/upload", {
    method: "POST",
    headers: { "X-Hermes-Intent": "founder-action" },
    body: new FormData(event.target),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: "Upload failed." }));
    return toast(typeof body.detail === "string" ? body.detail : "Upload failed.");
  }
  const result = await response.json();
  toast(`${result.document_key} registered with ${result.passages} cited passages.`);
  event.target.reset();
});

document.getElementById("sync-research-inbox").addEventListener("click", async () => {
  if (state.demo) return toast("Inbox sync is disabled in demonstration mode.");
  const button = document.getElementById("sync-research-inbox");
  button.disabled = true;
  try {
    const response = await fetch("/api/research/inbox/sync", {
      method: "POST",
      headers: { "X-Hermes-Intent": "founder-action" },
    });
    const report = await response.json();
    if (!response.ok) return toast(report.detail || "Inbox sync failed.");
    const counts = report.counts;
    document.getElementById("inbox-sync-status").textContent = `${report.inbox} · ${counts.added} added · ${counts.unchanged} unchanged · ${counts.rejected + counts.failed} need attention`;
    toast(`Research inbox synced: ${counts.added} added, ${counts.unchanged} unchanged.`);
  } finally {
    button.disabled = false;
  }
});

document.getElementById("sync-research-memory").addEventListener("click", async () => {
  if (state.demo) return toast("Memory sync is disabled in demonstration mode.");
  const button = document.getElementById("sync-research-memory");
  button.disabled = true;
  try {
    const response = await fetch("/api/research/memory-sync/proposals", {
      method: "POST",
      headers: { "X-Hermes-Intent": "founder-action" },
    });
    const proposal = await response.json();
    if (!response.ok) return toast(proposal.detail || "Memory sync proposal failed.");
    toast("Memory sync proposal is ready for founder review.");
    await loadDashboard();
    navigate("proposals");
    openProposal(proposal.id);
  } finally {
    button.disabled = false;
  }
});

document.getElementById("search-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = document.getElementById("search-query").value;
  if (state.demo) return renderDemoSearch(query);
  const data = await request(`/api/knowledge/search?q=${encodeURIComponent(query)}`);
  renderSearchResults(data.results);
});

document.getElementById("copilot-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demo) return toast("Research Copilot is unavailable in demonstration mode.");
  const question = document.getElementById("copilot-question").value.trim();
  const project = document.getElementById("copilot-project").value || null;
  const button = document.getElementById("copilot-submit");
  button.disabled = true;
  setCopilotState("Retrieving evidence", true);
  appendCopilotQuestion(question);
  try {
    const answer = await request("/api/research/copilot/questions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        project,
        conversation_id: state.copilotConversationId,
      }),
    });
    state.copilotConversationId = answer.conversation_id;
    state.copilotTurns.push(answer);
    renderCopilotAnswer(answer);
    document.getElementById("copilot-question").value = "";
    setCopilotState(answer.confidence === "insufficient_evidence" ? "Evidence insufficient" : "Answer grounded", false);
  } catch (error) {
    appendCopilotFailure(error.message);
    setCopilotState("Answer unavailable", false);
  } finally {
    button.disabled = false;
    document.getElementById("copilot-question").focus();
  }
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
  if (view === "work" && !state.demo) loadConversations();
}

async function loadConversations() {
  if (state.demo) return;
  try {
    state.conversations = await request("/api/conversations");
    if (state.activeConversationId && !state.conversations.some((item) => item.id === state.activeConversationId)) state.activeConversationId = null;
    if (!state.activeConversationId && state.conversations.length) state.activeConversationId = state.conversations[0].id;
    renderConversations();
    await loadConversationWorkspace();
  } catch (error) {
    toast(error.message);
  }
}

function renderConversations() {
  const list = document.getElementById("conversation-list");
  list.innerHTML = state.conversations.length ? state.conversations.map((item) => `
    <button class="conversation-list-item ${item.id === state.activeConversationId ? "active" : ""}" data-conversation-id="${item.id}">
      <span>${escapeHtml(item.short_id)} · ${escapeHtml(humanize(item.status))}</span>
      <strong>${escapeHtml(item.title)}</strong>
      <small>${escapeHtml(item.project || "Unclassified")} · revision ${item.revision}</small>
    </button>`).join("") : empty("No conversation threads yet.");
  document.querySelectorAll("[data-conversation-id]").forEach((button) => button.addEventListener("click", () => {
    state.activeConversationId = button.dataset.conversationId;
    state.conversationWorkspace = null;
    renderConversations();
    loadConversationWorkspace();
  }));
  const item = state.conversations.find((value) => value.id === state.activeConversationId);
  document.getElementById("conversation-empty").hidden = Boolean(item);
  document.getElementById("conversation-detail").hidden = !item;
  if (!item) return;
  document.getElementById("conversation-thread-id").textContent = `${item.short_id} · revision ${item.revision}`;
  document.getElementById("conversation-title").textContent = item.title;
  document.getElementById("conversation-state").textContent = `${humanize(item.status)} · ${item.project || "unclassified"}`;
  document.getElementById("conversation-messages").innerHTML = (item.messages || []).map((message) => `
    <article class="conversation-message ${message.role}">
      <div><strong>${message.role === "founder" ? "Founder" : "Hermes"}</strong><span>${escapeHtml(message.channel)} · ${formatDate(message.created_at)}</span></div>
      <p>${escapeHtml(message.content).replaceAll("\n", "<br>")}</p>
    </article>`).join("");
  const spec = item.current_specification || {};
  const unresolved = spec.unresolved_fields || [];
  const defaults = spec.resolved_defaults || [];
  document.getElementById("conversation-specification").innerHTML = `
    <div><p class="section-kicker">Live specification</p><h3>${escapeHtml(spec.summary || "Collecting requirements")}</h3></div>
    <dl><dt>State</dt><dd>${escapeHtml(humanize(item.status))}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(item.specification_digest || "Not compiled")}</dd></dl>
    ${unresolved.length ? `<section><strong>Still needed</strong>${bulletList(unresolved, "")}</section>` : ""}
    ${defaults.length ? `<section><strong>Resolved defaults</strong>${bulletList(defaults.map((value) => `${value.field}: ${value.value} — ${value.basis}`), "")}</section>` : ""}`;
  renderConversationWork();
  const canWrite = ["collecting", "planning", "needs_clarification", "ready_for_review", "attention_required"].includes(item.status);
  document.getElementById("conversation-message").disabled = !canWrite;
  document.querySelector("#conversation-form button").disabled = !canWrite;
  document.querySelectorAll("[data-conversation-action]").forEach((button) => {
    const resumes = button.dataset.conversationAction === "resume";
    button.hidden = resumes ? !["finished", "stopped"].includes(item.status) : !canWrite;
  });
}

async function loadConversationWorkspace() {
  const conversationId = state.activeConversationId;
  if (state.demo || !conversationId) {
    state.conversationWorkspace = null;
    renderConversationWork();
    return;
  }
  state.conversationWorkspaceLoading = true;
  renderConversationWork();
  try {
    const workspace = await request(`/api/conversations/${conversationId}/workspace`);
    if (state.activeConversationId !== conversationId) return;
    state.conversationWorkspace = workspace;
  } catch (error) {
    if (state.activeConversationId === conversationId) toast(error.message);
  } finally {
    if (state.activeConversationId === conversationId) {
      state.conversationWorkspaceLoading = false;
      renderConversationWork();
    }
  }
}

function renderConversationWork() {
  const progress = document.getElementById("conversation-progress");
  const evidence = document.getElementById("conversation-evidence");
  if (!progress || !evidence) return;
  if (state.conversationWorkspaceLoading) {
    progress.innerHTML = '<div class="conversation-work-empty">Loading canonical work state…</div>';
    evidence.innerHTML = '<div class="conversation-work-empty">Loading evidence…</div>';
    return;
  }
  const workspace = state.conversationWorkspace;
  if (!workspace || workspace.conversation?.id !== state.activeConversationId) {
    progress.innerHTML = '<div class="conversation-work-empty">No linked execution yet.</div>';
    evidence.innerHTML = '<div class="conversation-work-empty">Evidence appears after governed execution.</div>';
    document.getElementById("conversation-progress-count").textContent = "0";
    document.getElementById("conversation-evidence-count").textContent = "0";
    return;
  }
  const items = conversationTimeline(workspace);
  document.getElementById("conversation-progress-count").textContent = String(items.length);
  document.getElementById("conversation-evidence-count").textContent = String((workspace.artifacts || []).length);
  progress.innerHTML = items.length ? items.map((item) => `
    <button class="conversation-progress-item" type="button" ${item.entityId ? `data-work-${item.kind}="${escapeHtml(item.entityId)}"` : ""}>
      <span class="timeline-marker ${escapeHtml(item.state)}" aria-hidden="true"></span>
      <span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.detail)} · ${formatDate(item.createdAt)}</small></span>
    </button>`).join("") : '<div class="conversation-work-empty">No linked execution yet.</div>';
  evidence.innerHTML = (workspace.artifacts || []).length ? workspace.artifacts.map((artifact) => `
    <button class="conversation-evidence-item" type="button" data-work-artifact="${escapeHtml(artifact.id)}">
      <span><strong>${escapeHtml(artifact.name)}</strong><small>${escapeHtml(humanize(artifact.artifact_type))} · ${formatBytes(artifact.size_bytes)}</small></span>
      <span class="evidence-verification">${escapeHtml(artifact.verification_status || "registered")}</span>
    </button>`).join("") : '<div class="conversation-work-empty">Evidence appears after governed execution.</div>';
  document.querySelectorAll("[data-work-task]").forEach((button) => {
    button.onclick = () => openConversationTask(button.dataset.workTask);
  });
  document.querySelectorAll("[data-work-proposal]").forEach((button) => {
    button.onclick = () => openConversationProposal(button.dataset.workProposal);
  });
  document.querySelectorAll("[data-work-artifact]").forEach((button) => {
    button.onclick = () => openConversationArtifact(button.dataset.workArtifact);
  });
}

function conversationTimeline(workspace) {
  const items = [];
  (workspace.events || []).forEach((event) => items.push({
    kind: "event",
    label: humanize(event.event_type),
    detail: `Conversation revision ${event.revision}`,
    state: event.resulting_status,
    createdAt: event.created_at,
  }));
  (workspace.proposals || []).forEach((proposal) => items.push({
    kind: "proposal",
    entityId: proposal.id,
    label: "Planner proposal",
    detail: `${humanize(proposal.status)} · ${shortHash(proposal.proposal_digest)}`,
    state: proposal.status,
    createdAt: proposal.created_at,
  }));
  (workspace.tasks || []).forEach((detail) => {
    const task = detail.task;
    items.push({ kind: "task", entityId: task.id, label: task.task_number, detail: humanize(task.status), state: task.status, createdAt: task.created_at });
    (detail.events || []).forEach((event) => items.push({
      kind: "task",
      entityId: task.id,
      label: humanize(event.event_type),
      detail: task.task_number,
      state: task.status,
      createdAt: event.created_at,
    }));
  });
  (workspace.approvals || []).forEach((approval) => items.push({
    kind: "task",
    entityId: approval.task_id,
    label: `Approval ${humanize(approval.status)}`,
    detail: `Risk ${approval.risk_level} · ${shortHash(approval.plan_digest)}`,
    state: approval.status,
    createdAt: approval.updated_at,
  }));
  return items.sort((left, right) => new Date(left.createdAt) - new Date(right.createdAt));
}

function openConversationTask(id) {
  const detail = (state.conversationWorkspace?.tasks || []).find((item) => String(item.task.id) === String(id));
  if (!detail) return;
  const task = detail.task;
  const artifacts = (state.conversationWorkspace.artifacts || []).filter((item) => item.task_id === task.id);
  openInspector("Thread task", task.title, `
    <section class="detail-section"><h3>Lifecycle</h3><dl class="detail-grid">
      <dt>Status</dt><dd>${statusBadge(task.status)}</dd><dt>Task number</dt><dd class="mono">${escapeHtml(task.task_number)}</dd>
      <dt>Type</dt><dd>${escapeHtml(humanize(task.task_type))}</dd><dt>Attempt</dt><dd>${task.attempt_count} of ${task.max_attempts}</dd>
      <dt>Conversation revision</dt><dd>${task.conversation_revision ?? "Not bound"}</dd><dt>Artifacts</dt><dd>${artifacts.length}</dd>
    </dl></section>
    <section class="detail-section"><h3>Objective</h3><p>${escapeHtml(task.objective)}</p></section>
    <section class="detail-section"><h3>Execution events</h3>${(detail.events || []).length ? `<ol class="detail-list">${detail.events.map((event) => `<li><strong>${escapeHtml(humanize(event.event_type))}</strong><br><span class="muted">${escapeHtml(event.message)} · ${formatDate(event.created_at)}</span></li>`).join("")}</ol>` : '<p class="muted">No execution events yet.</p>'}</section>
    <section class="detail-section"><h3>Structured result</h3><pre class="json-view">${escapeHtml(JSON.stringify(task.result || task.failure || {}, null, 2))}</pre></section>`);
}

function openConversationProposal(id) {
  const proposal = (state.conversationWorkspace?.proposals || []).find((item) => String(item.id) === String(id));
  if (!proposal) return;
  const reviewAction = proposal.status === "proposed"
    ? '<div class="detail-actions"><button class="command" id="review-thread-proposal">Open proposal review</button></div>'
    : "";
  openInspector("Thread proposal", proposal.proposal.summary, `
    <section class="detail-section"><h3>Review state</h3><dl class="detail-grid"><dt>Status</dt><dd>${statusBadge(proposal.status)}</dd><dt>Revision</dt><dd>${proposal.conversation_revision}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(proposal.proposal_digest)}</dd></dl></section>
    <section class="detail-section"><h3>Interpretation</h3><p>${escapeHtml(proposal.proposal.interpretation)}</p></section>
    <section class="detail-section"><h3>Safety constraints</h3>${bulletList(proposal.proposal.safety_constraints, "No additional constraints recorded.")}</section>${reviewAction}`);
  document.getElementById("review-thread-proposal")?.addEventListener("click", () => {
    closeInspector();
    navigate("proposals");
    const dashboardProposal = (state.dashboard?.proposals || []).find((item) => String(item.id) === String(id));
    if (dashboardProposal) openProposal(id);
  });
}

function openConversationArtifact(id) {
  const artifact = (state.conversationWorkspace?.artifacts || []).find((item) => String(item.id) === String(id));
  if (!artifact) return;
  openInspector("Thread evidence", artifact.name, `
    <section class="detail-section"><h3>Verification</h3><dl class="detail-grid"><dt>Status</dt><dd>${statusBadge(artifact.verification_status)}</dd><dt>Type</dt><dd>${escapeHtml(humanize(artifact.artifact_type))}</dd><dt>Attempt</dt><dd>${artifact.attempt_number}</dd><dt>Workflow</dt><dd>${escapeHtml(artifact.workflow)} ${escapeHtml(artifact.workflow_version)}</dd></dl></section>
    <section class="detail-section"><h3>Digest-bound provenance</h3><dl class="detail-grid"><dt>SHA-256</dt><dd class="mono">${escapeHtml(artifact.sha256)}</dd><dt>Source commit</dt><dd class="mono">${escapeHtml(artifact.source_commit)}</dd><dt>Location</dt><dd class="mono">${escapeHtml(artifact.location)}</dd></dl></section>`);
}

function createConversation() {
  if (state.demo) return toast("Actions are disabled in demonstration mode.");
  document.getElementById("new-conversation-form").reset();
  document.getElementById("conversation-dialog").showModal();
}

async function submitConversation(event) {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  if (state.demo) return;
  const form = new FormData(event.currentTarget);
  const title = String(form.get("title") || "").trim();
  const message = String(form.get("message") || "").trim();
  if (!title || !message) return;
  const result = await mutate("/api/conversations", { title, message }, "Conversation started.");
  document.getElementById("conversation-dialog").close();
  state.activeConversationId = result.conversation.id;
  state.conversationWorkspace = null;
  await loadConversations();
}

async function continueConversation(event) {
  event.preventDefault();
  if (state.demo || !state.activeConversationId) return;
  const textarea = document.getElementById("conversation-message");
  const message = textarea.value.trim();
  if (!message) return;
  await mutate(`/api/conversations/${state.activeConversationId}/turns`, { message }, "Turn added to this thread.");
  textarea.value = "";
  await loadConversations();
}

async function transitionConversation(action) {
  if (state.demo || !state.activeConversationId) return;
  await mutate(`/api/conversations/${state.activeConversationId}/transitions`, { action, reason: `Founder requested ${action} in Mission Control.` }, `Thread ${action} recorded.`);
  await loadConversations();
}

function setResearchMode(mode, { focus = false } = {}) {
  if (!allowedResearchModes.has(mode)) return;
  state.researchMode = mode;
  document.querySelectorAll("[data-research-mode]").forEach((button) => {
    const active = button.dataset.researchMode === mode;
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
    if (active && focus) button.focus();
  });
  document.querySelectorAll("[data-research-panel]").forEach((panel) => {
    const active = panel.dataset.researchPanel === mode;
    panel.hidden = !active;
    panel.classList.toggle("active", active);
  });
  const url = new URL(window.location.href);
  if (mode === "ask") url.searchParams.delete("workspace");
  else url.searchParams.set("workspace", mode);
  window.history.replaceState({}, "", url);
  if (mode === "explore" && state.graphData) renderGraph(state.graphData);
}

function navigateResearchTabs(event, current) {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const tabs = [...document.querySelectorAll("[data-research-mode]")];
  let index = tabs.indexOf(current);
  if (event.key === "Home") index = 0;
  else if (event.key === "End") index = tabs.length - 1;
  else index = (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  setResearchMode(tabs[index].dataset.researchMode, { focus: true });
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
    if (state.demo) loadDemoConversation();
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
  renderActivity();
  renderMissions();
  renderTasks();
  renderProposals();
  renderApprovals();
  renderAgents();
  renderInfrastructure();
  renderResearch();
  renderNotes();
  renderArtifacts();
  renderResearchWorkspaceStatus();
  renderResearchContext();
  setResearchMode(state.researchMode);
}

function renderActivity() {
  const operations = state.dashboard?.operations || [];
  const summary = state.dashboard?.operation_summary || { counts: {}, active_total: 0 };
  const activeStates = new Set(["queued", "waiting_approval", "running", "blocked", "stalled"]);
  const active = operations.filter((item) => activeStates.has(item.state));
  const recent = operations.filter((item) => !activeStates.has(item.state)).slice(0, 50);
  const activeCount = Number(summary.active_total ?? active.length);
  document.getElementById("activity-count").textContent = activeCount;
  document.getElementById("activity-active-count").textContent = `${activeCount} active`;
  document.getElementById("activity-status").classList.toggle("has-work", activeCount > 0);
  document.getElementById("activity-live-label").textContent = `${active.length} ${active.length === 1 ? "operation" : "operations"}`;
  document.getElementById("activity-summary").innerHTML = [
    metric(active.filter((item) => item.state === "running").length, "Running", "Fresh execution heartbeats"),
    metric(active.filter((item) => item.state === "waiting_approval").length, "Waiting approval", "Founder decision required"),
    metric(active.filter((item) => item.state === "stalled").length, "Stalled", "Heartbeat outside SLO"),
    metric((summary.counts || {}).failed || 0, "Failed retained", "Exact failure evidence preserved"),
  ].join("");
  document.getElementById("activity-live").innerHTML = active.length
    ? active.map(operationRow).join("")
    : empty("No active, waiting, blocked, or stalled operations.");
  document.getElementById("activity-recent").innerHTML = recent.length
    ? recent.map(operationRow).join("")
    : empty("No terminal operation receipts yet.");
}

function operationRow(operation) {
  const determinate = operation.progress_mode === "determinate" && operation.progress_total;
  const percentage = determinate ? Math.min(100, Math.round((operation.progress_current / operation.progress_total) * 100)) : null;
  const progress = determinate
    ? `<div class="operation-progress"><div class="operation-progress-track"><span style="width:${percentage}%"></span></div><span>${operation.progress_current}/${operation.progress_total} ${escapeHtml(operation.progress_unit || "")}</span></div>`
    : operation.state === "running" ? '<div class="operation-progress indeterminate"><div class="operation-progress-track"><span></span></div><span>Progress not measurable</span></div>' : "";
  const error = operation.error_summary ? `<p class="operation-error" role="alert">${escapeHtml(operation.error_summary)}</p>` : "";
  return `<article class="operation-row" data-operation-id="${operation.id}">
    <div class="operation-main">
      <div class="operation-heading"><strong>${escapeHtml(operation.title)}</strong>${statusBadge(operation.state)}</div>
      <div class="entity-meta"><span>${escapeHtml(humanize(operation.phase))}</span><span>${escapeHtml(operation.machine || "machine pending")}</span><span>${escapeHtml(operation.owner_type)}${operation.owner_id ? ` · ${escapeHtml(operation.owner_id)}` : ""}</span><span>Heartbeat ${relativeTime(operation.heartbeat_at)}</span></div>
      ${progress}${error}
    </div>
    <div class="operation-side"><span class="mono">${escapeHtml(operation.kind)}</span><small>${relativeTime(operation.updated_at)}</small></div>
  </article>`;
}

function renderNotes() {
  const notes = state.dashboard?.operational_notes || [];
  document.getElementById("note-count").textContent = notes.filter((item) => item.status !== "resolved").length;
  document.getElementById("note-list").innerHTML = notes.length ? notes.map((note) => `
    <article class="proposal-row" data-note-id="${note.id}">
      <div class="proposal-main">
        <div class="proposal-eyebrow">${escapeHtml(humanize(note.urgency))} · ${escapeHtml(note.proposed_owner)}</div>
        <h2>${escapeHtml(note.subject)}</h2>
        <p>${escapeHtml(note.finding)}</p>
        <div class="entity-meta"><span class="mono">${escapeHtml(note.note_key)}</span><span>${(note.affected_systems || []).map(escapeHtml).join(", ")}</span><span>${relativeTime(note.updated_at)}</span></div>
      </div>
      <div class="proposal-side">${statusBadge(note.status)}<span class="row-open">›</span></div>
    </article>`).join("") : empty("No operational notes recorded.");
  document.querySelectorAll("[data-note-id]").forEach((element) => {
    element.onclick = () => openNote(element.dataset.noteId);
  });
}

function openNote(id) {
  const note = (state.dashboard?.operational_notes || []).find((item) => String(item.id) === String(id));
  if (!note) return;
  const actions = note.status === "resolved"
    ? '<button class="secondary" data-note-action="reopen">Reopen</button>'
    : '<button class="secondary" data-note-action="assign">Assign</button><button class="secondary" data-note-action="defer">Defer</button><button class="secondary" data-note-proposal>Plan remediation</button><button class="command" data-note-action="resolve">Resolve with evidence</button>';
  openInspector("Operational note", note.subject, `
    <dl><dt>Status</dt><dd>${escapeHtml(humanize(note.status))}</dd><dt>Urgency</dt><dd>${escapeHtml(humanize(note.urgency))}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(note.record_digest)}</dd><dt>Owner</dt><dd>${escapeHtml(note.assigned_to || note.proposed_owner)}</dd></dl>
    <section class="detail-section"><h3>Finding</h3><p>${escapeHtml(note.finding)}</p></section>
    <section class="detail-section"><h3>Evidence</h3>${bulletList(note.evidence, "No evidence recorded.")}</section>
    <section class="detail-actions">${actions}</section>`);
  document.querySelectorAll("[data-note-action]").forEach((button) => {
    button.onclick = () => transitionNote(note, button.dataset.noteAction);
  });
  const proposalButton = document.querySelector("[data-note-proposal]");
  if (proposalButton) proposalButton.onclick = () => requestNoteProposal(note);
}

async function requestNoteProposal(note) {
  if (state.demo) return toast("Actions are disabled in demonstration mode.");
  const objective = window.prompt("What bounded outcome should the planner propose?");
  if (!objective || objective.trim().length < 10) return toast("An objective of at least 10 characters is required.");
  await mutate(`/api/operational-notes/${note.id}/proposal-request`, { objective: objective.trim() }, "Planning request queued for founder review.");
  closeInspector();
  await loadDashboard();
}

async function transitionNote(note, action) {
  if (state.demo) return toast("Actions are disabled in demonstration mode.");
  const reason = window.prompt(`Reason to ${action} this note:`);
  if (!reason || reason.trim().length < 10) return toast("A reason of at least 10 characters is required.");
  const payload = { action, reason: reason.trim(), evidence: [] };
  if (action === "assign") payload.assigned_to = note.proposed_owner;
  if (action === "defer") {
    const until = window.prompt("Defer until (ISO date/time):");
    if (!until) return;
    payload.deferred_until = new Date(until).toISOString();
  }
  if (action === "resolve") {
    const evidence = window.prompt("Resolution evidence reference:");
    if (!evidence) return toast("Resolution evidence is required.");
    payload.evidence = [evidence.trim()];
  }
  await mutate(`/api/operational-notes/${note.id}/transitions`, payload, `Note ${action} recorded.`);
  closeInspector();
  await loadDashboard();
}

function renderCommand() {
  const data = state.dashboard;
  const tasks = data.tasks || [];
  const agents = data.agents || [];
  const approvals = data.approvals || [];
  const pendingApprovals = approvals.filter((item) => item.status === "pending");
  const pendingProposals = (data.proposals || []).filter((item) => item.status === "proposed");
  const active = tasks.filter((item) => activeStatuses.has(item.status));
  const failed = tasks.filter((item) => item.status === "failed");
  const online = agents.filter((item) => agentStatus(item) === "online");
  const succeeded = tasks.filter((item) => item.status === "succeeded");

  document.getElementById("metrics").innerHTML = [
    metric(active.length, "Active tasks", `${tasks.length} total recorded`),
    metric(pendingApprovals.length + pendingProposals.length, "Pending decisions", (pendingApprovals.length + pendingProposals.length) ? "Founder action required" : "Queue clear"),
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
  (data.proposals || []).filter((item) => item.status === "proposed").forEach((proposal) => {
    items.push({ severity: "pending", title: proposal.proposal.summary, detail: `${humanize(proposal.proposal.recommended_action)} · proposal`, proposal });
  });
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
  document.getElementById("proposal-count").textContent = (data.proposals || []).filter((item) => item.status === "proposed").length;
  document.getElementById("attention-list").innerHTML = items.length ? items.map((item, index) => `
    <button class="attention-item ${item.severity}" data-attention="${index}">
      <span class="attention-bar"></span>
      <span><strong>${escapeHtml(item.title)}</strong><p>${escapeHtml(item.detail)}</p></span>
    </button>`).join("") : empty("Nothing requires founder action.");
  document.querySelectorAll("[data-attention]").forEach((button) => {
    button.addEventListener("click", () => {
      const item = items[Number(button.dataset.attention)];
      if (item.proposal) openProposal(item.proposal.id);
      else if (item.approval) navigate("approvals");
      else if (item.task) openTask(item.task.id);
      else if (item.agent) openAgent(item.agent.id);
    });
  });
}

function renderProposals() {
  if (!state.dashboard) return;
  const proposals = state.dashboard.proposals || [];
  document.getElementById("proposal-list").innerHTML = proposals.length ? proposals.map((item) => {
    const proposal = item.proposal;
    const task = proposal.proposed_task;
    const questions = proposal.clarification_questions || [];
    return `<article class="proposal-row" data-proposal-id="${item.id}">
      <div class="proposal-main">
        <div class="proposal-eyebrow">${escapeHtml(humanize(proposal.recommended_action))} · ${escapeHtml(proposal.target_role || "Unassigned role")}</div>
        <h2>${escapeHtml(proposal.summary)}</h2>
        <p>${escapeHtml(proposal.interpretation)}</p>
        ${!task && questions.length ? `<div class="proposal-clarification"><strong>Clarification required</strong>${bulletList(questions, "")}</div>` : ""}
        <div class="entity-meta"><span>${task ? escapeHtml(task.project) : "No task drafted"}</span><span>${task ? escapeHtml(humanize(task.task_type)) : "Clarification required"}</span><span>${relativeTime(item.created_at)}</span></div>
      </div>
      <div class="proposal-side">${task ? `<span class="risk ${task.risk_level >= 3 ? "high" : ""}">Risk ${task.risk_level}</span>` : ""}${statusBadge(item.status)}<span class="row-open">›</span></div>
    </article>`;
  }).join("") : empty("No founder proposals recorded.");
  document.querySelectorAll("[data-proposal-id]").forEach((element) => {
    element.onclick = () => openProposal(element.dataset.proposalId);
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
  const taskGroups = new Map(groupMissions(state.dashboard.tasks || []).map((item) => [item.key, item]));
  let missions = (state.dashboard.missions || []).map((mission) => ({
    ...mission,
    ...(taskGroups.get(mission.id) || { total: 0, completed: 0, active: 0, failed: 0 }),
    key: mission.id,
    title: mission.objective,
  }));
  if (state.missionFilter === "active") missions = missions.filter((item) => ["active", "recovering"].includes(item.supervision_status || item.status));
  if (state.missionFilter === "completed") missions = missions.filter((item) => item.status === "succeeded");
  if (state.missionFilter === "attention") missions = missions.filter((item) => item.supervision_status === "attention_required" || item.status === "blocked");
  document.getElementById("mission-list").innerHTML = missions.length ? missions.map((mission) => {
    const progress = mission.total ? Math.round((mission.completed / mission.total) * 100) : 0;
    const supervisor = mission.supervision_enabled ? mission.supervision_status : "manual";
    return `<div class="mission-row" data-mission="${escapeHtml(mission.key)}">
      <div><h3>${escapeHtml(mission.title)}</h3><div class="entity-meta"><span class="mono">${escapeHtml(mission.milestone_id || mission.key)}</span><span>${mission.total} tasks</span><span>Supervisor: ${escapeHtml(humanize(supervisor))}</span><span>${mission.recovery_count || 0} recoveries</span></div><div class="progress-track"><span style="width:${progress}%"></span></div></div>
      <div><strong>${progress}%</strong><div class="entity-meta"><span>${mission.completed} terminal</span></div></div>
      <div class="entity-meta"><span>${mission.active} active</span><span>${mission.failed} failed</span></div>
      ${mission.supervision_status === "pending_approval" ? `<button class="command" data-mission-approve="${mission.id}">Approve plan</button>` : statusBadge(supervisor === "attention_required" ? "failed" : supervisor)}
    </div>`;
  }).join("") : empty("No missions match this view.");
  document.querySelectorAll("[data-mission-approve]").forEach((button) => {
    button.onclick = async () => {
      await api(`/api/missions/${button.dataset.missionApprove}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Hermes-Intent": "founder-action" },
        body: JSON.stringify({ reason: "Founder approved the immutable supervised mission plan." }),
      });
      await loadDashboard();
    };
  });
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
  const center = state.dashboard.approval_center || { counts: {}, items: [] };
  const items = center.items || [];
  const counts = center.counts || {};
  document.getElementById("approval-summary").innerHTML = [
    metric(counts.actionable || 0, "Ready", "Current and executable"),
    metric(counts.blocked || 0, "Blocked", "Prerequisite or state mismatch"),
    metric(counts.decided || 0, "Decided", "Receipts retained"),
  ].join("");
  document.getElementById("approval-list").innerHTML = items.length ? items.map((item) => {
    const approval = item.approval;
    const task = item.task || {};
    const readiness = approval.status !== "pending" ? approval.status : item.actionable ? "ready" : "blocked";
    const blockers = (item.blocked_by || []).map((entry) => `${humanize(entry.kind)}: ${entry.reference} (${humanize(entry.status)})`);
    return `
    <article class="approval approval-${escapeHtml(readiness)}">
      <div>
        <div class="approval-scope">${escapeHtml(task.task_number || approval.id)} · review ${shortHash(item.review_digest)}</div>
        <h2>${escapeHtml(task.title || `${approval.scope?.project || "Unknown project"} approval`)}</h2>
        <p class="approval-objective">${escapeHtml(task.objective || "No objective recorded.")}</p>
        <div class="entity-meta"><span>Risk ${approval.risk_level}</span><span title="${escapeHtml(approval.plan_digest)}">Plan ${shortHash(approval.plan_digest)}</span><span>${item.prerequisites?.length || 0} prerequisites</span><span>Requested ${relativeTime(approval.created_at)}</span></div>
        ${blockers.length ? `<div class="approval-blockers"><strong>Not ready</strong>${bulletList(blockers, "")}</div>` : ""}
        <div class="approval-state">${statusBadge(approval.status)}<span class="readiness readiness-${escapeHtml(readiness)}">${escapeHtml(humanize(readiness))}</span></div>
      </div>
      <div class="approval-actions"><a class="secondary button-link" href="?view=approvals&amp;approval=${encodeURIComponent(approval.id)}">Review link</a>${approval.status === "pending" ? `<button class="secondary danger" data-decision="reject" data-id="${approval.id}">Reject</button><button class="command" data-decision="approve" data-id="${approval.id}" ${item.actionable ? "" : "disabled"}>Review & approve</button>` : `<button class="secondary" data-decision="review" data-id="${approval.id}">View receipt</button>`}</div>
    </article>`;
  }).join("") : empty("No approval gates recorded.");
  document.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => openDecision(button.dataset.id, button.dataset.decision));
  });
  if (requestedApproval && !state.requestedApprovalOpened) {
    const requested = items.find((item) => String(item.approval.id) === requestedApproval);
    state.requestedApprovalOpened = true;
    if (requested) openDecision(requestedApproval, "review");
    else toast("That approval review is unavailable or no longer retained.");
  }
  const authority = state.dashboard.authority || {};
  const policy = authority.policy;
  const activeDelegations = (authority.delegations || []).filter((item) => item.status === "active");
  const activeExceptions = (authority.exceptions || []).filter((item) => item.status === "approved");
  document.getElementById("authority-policy").innerHTML = policy ? `
    <div class="policy-row"><strong>Policy</strong><span>${escapeHtml(policy.version)}</span>${statusBadge(policy.status)}</div>
    <div class="policy-row"><strong>Digest</strong><span class="mono">${shortHash(policy.manifest_digest)}</span><span>${policy.manifest?.decisions?.length || 0} rights</span></div>
    <div class="policy-row"><strong>Delegated</strong><span>${activeDelegations.length} active</span><span>${activeExceptions.length} exceptions</span></div>
  ` : empty("No active authority policy. Consequential decisions fail closed.");
}

function openDecision(id, action) {
  const item = (state.dashboard.approval_center?.items || []).find((entry) => String(entry.approval.id) === id);
  if (!item) return;
  const approval = item.approval;
  const task = item.task || {};
  const form = document.getElementById("decision-form");
  form.reset();
  form.elements.approval_id.value = id;
  form.elements.action.value = action;
  form.elements.review_digest.value = item.review_digest;
  const readOnly = action === "review";
  document.getElementById("decision-title").textContent = readOnly ? "Approval receipt" : action === "approve" ? "Authorize bounded task" : "Reject task";
  document.getElementById("decision-submit").textContent = action === "approve" ? "Approve for 15 minutes" : "Reject request";
  document.getElementById("decision-submit").className = action === "approve" ? "command" : "secondary danger";
  document.getElementById("decision-submit").hidden = readOnly;
  form.elements.reason.closest("label").hidden = readOnly;
  form.elements.reason.required = !readOnly;
  const acknowledgement = document.getElementById("decision-acknowledgement");
  acknowledgement.hidden = action !== "approve";
  acknowledgement.querySelector("input").required = action === "approve";
  const prerequisites = (item.prerequisites || []).map((entry) => `${entry.task_number} · ${entry.title} · ${humanize(entry.status)}`);
  document.getElementById("decision-summary").innerHTML = `
    <div class="decision-verdict ${item.actionable ? "decision-ready" : "decision-blocked"}"><strong>${item.actionable ? "Current and executable" : approval.status === "pending" ? "Not actionable" : humanize(approval.status)}</strong><span>${item.actionable ? "One bounded lease may be authorized." : "No execution authority is available from this record."}</span></div>
    <dl>
    <dt>Task</dt><dd>${escapeHtml(task.task_number || approval.task_id)} · ${escapeHtml(task.title || "Untitled")}</dd>
    <dt>Project</dt><dd>${escapeHtml(task.project || approval.scope?.project || "Unknown")}</dd>
    <dt>Operation</dt><dd>${escapeHtml(humanize(task.task_type || approval.scope?.task_type || "operation"))}</dd>
    <dt>Risk</dt><dd>${approval.risk_level}</dd>
    <dt>Plan digest</dt><dd class="mono">${escapeHtml(approval.plan_digest)}</dd>
    <dt>Review digest</dt><dd class="mono">${escapeHtml(item.review_digest)}</dd>
    <dt>Authority policy</dt><dd class="mono">${escapeHtml(item.authority_policy?.manifest_digest || "Unavailable")}</dd>
    <dt>Allowed machines</dt><dd>${escapeHtml((task.allowed_machines || []).join(", ") || "None declared")}</dd>
    <dt>Required capabilities</dt><dd>${escapeHtml((task.required_capabilities || []).join(", ") || "None declared")}</dd>
    <dt>Expected outputs</dt><dd>${escapeHtml((task.expected_outputs || []).join(", ") || "None declared")}</dd>
    <dt>Expiry</dt><dd>${action === "approve" ? "15 minutes after approval; consumed by one task lease" : approval.expires_at ? formatDate(approval.expires_at) : "Not issued"}</dd>
  </dl>
  <section class="decision-contract"><h3>Objective</h3><p>${escapeHtml(task.objective || "No objective recorded.")}</p><h3>Acceptance criteria</h3>${bulletList(task.acceptance_criteria || [], "None recorded.")}<h3>Prerequisites</h3>${bulletList(prerequisites, "No task prerequisites.")}<h3>Bounded effect</h3><p>${escapeHtml(item.claim_boundary)}</p></section>`;
  document.getElementById("decision-dialog").showModal();
}

function renderAgents() {
  if (!state.dashboard) return;
  const agents = state.dashboard.agents || [];
  document.getElementById("agent-matrix").innerHTML = agents.length ? agents.map((agent) => {
    const deployment = activeDeployment(agent.id);
    const charter = (state.dashboard.agent_charters || []).find((item) => String(item.agent_id) === String(agent.id) && item.status === "active");
    const grants = (state.dashboard.agent_capability_grants || []).filter((item) => String(item.agent_id) === String(agent.id) && item.status === "active");
    const workloadIdentity = (state.dashboard.workload_identities?.identities || []).find((item) => String(item.agent_id) === String(agent.id) && item.status === "active");
    const manifest = deployment?.package?.manifest;
    return `
    <article class="agent-card" data-agent-id="${agent.id}">
      <div class="agent-header"><div><h3>${escapeHtml(agent.display_name || agent.slug)}</h3><div class="agent-machine">${escapeHtml(agent.machine)}</div></div>${statusBadge(agentStatus(agent))}</div>
      <div class="capabilities">${(agent.capabilities || []).map((capability) => `<span class="capability">${escapeHtml(capability)}</span>`).join("")}</div>
      <p class="agent-role">${escapeHtml(manifest?.role || agent.role || agent.hermes_profile || "Worker")}</p>
      <div class="agent-envelope"><span>${manifest?.task_types?.length || 0} task types</span><span>${manifest?.repository_profile?.repositories?.length || 0} repositories</span><span>${manifest?.permission_profile?.privileged_operations ? "Privileged" : "Unprivileged"}</span></div>
      <div class="agent-footer"><span>Risk ceiling ${manifest?.risk_ceiling ?? agent.risk_ceiling ?? "–"}</span><span>${deployment ? `Package ${escapeHtml(deployment.package.version)}` : "No active package"}</span><span>${charter ? `Charter ${escapeHtml(charter.version)}` : "No active charter"}</span><span>${grants.length} active grants</span><span>${workloadIdentity ? `Identity ${escapeHtml(workloadIdentity.version)} · ${workloadIdentity.scopes.length} scopes` : "No workload identity"}</span></div>
    </article>`;
  }).join("") : empty("No agents registered.");
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
  const machines = state.dashboard.fleet_health?.machines || [];
  document.getElementById("fleet-health").innerHTML = machines.length ? machines.map((machine) => {
    const metrics = machine.metrics || {};
    const activeIncidents = machine.incidents || [];
    const backup = metrics.control_plane_backup_verified == null
      ? ""
      : `<span>Backup ${metrics.control_plane_backup_verified && !metrics.control_plane_backup_failed ? "verified" : "attention"} · ${formatDuration(metrics.control_plane_backup_age_seconds)} old</span>`;
    return `<article class="entity-row">
      <div class="entity-primary">
        <strong>${escapeHtml(machine.machine)}</strong>
        <div class="entity-meta"><span>CPU ${formatPercent(metrics.cpu_utilization_percent)}</span><span>Memory available ${formatPercent(metrics.memory_available_percent)}</span><span>Disk ${formatPercent(metrics.disk_used_percent)}</span><span>${activeIncidents.length} active incidents</span></div>
        <div class="entity-meta"><span>Last sample ${relativeTime(machine.last_observed_at)}</span><span>PSI CPU ${formatPercent(metrics.cpu_pressure_avg10)}</span><span>PSI I/O ${formatPercent(metrics.io_pressure_avg10)}</span>${backup}</div>
      </div>
      <div class="entity-side">${statusBadge(machine.status === "healthy" ? "success" : machine.status)}</div>
    </article>`;
  }).join("") : empty("No fleet observations received yet.");
  const observability = state.dashboard.observability || { summary: {}, services: [], alerts: [] };
  const sloStates = observability.services || [];
  const routedAlerts = observability.alerts || [];
  const sloSummary = observability.summary || {};
  document.getElementById("slo-freshness").textContent = observability.generated_at
    ? `Evaluated ${relativeTime(observability.generated_at)}`
    : "No current evaluation";
  document.getElementById("slo-summary").innerHTML = [
    metric(sloSummary.healthy || 0, "Healthy", "Current evidence meets objective"),
    metric(sloSummary.breached || 0, "Breached", "Sustained breach routes once"),
    metric(sloSummary.missing || 0, "Missing", "Required telemetry absent"),
    metric(sloSummary.unknown || 0, "Unknown", "No measurement; never assumed healthy"),
  ].join("");
  document.getElementById("service-slos").innerHTML = sloStates.length ? sloStates.map((item) => `
    <article class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(item.service_key)} · ${escapeHtml(humanize(item.indicator))}</strong>
        <div class="entity-meta"><span>Owner ${escapeHtml(item.owner)}</span><span>Evaluated ${relativeTime(item.evaluated_at)}</span><span>${item.consecutive_breaches || 0} consecutive breaches</span></div>
      </div><div class="entity-side">${statusBadge(item.status === "healthy" ? "success" : item.status)}</div>
    </article>`).join("") : empty("No catalog-bound SLO states exist yet.");
  document.getElementById("routed-alerts").innerHTML = routedAlerts.length ? routedAlerts.map((alert) => `
    <article class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(alert.summary)}</strong>
        <div class="entity-meta"><span>${escapeHtml(alert.severity)}</span><span>Owner ${escapeHtml(alert.owner)}</span><span>Route ${escapeHtml(alert.route)}</span><span>Updated ${relativeTime(alert.updated_at)}</span></div>
      </div><div class="entity-side">${statusBadge(alert.state)}${alert.state === "firing" ? `<button class="text-button" data-slo-alert="${alert.id}" data-alert-action="acknowledge">Acknowledge</button><button class="text-button" data-slo-alert="${alert.id}" data-alert-action="silence">Silence</button>` : ""}${alert.state === "silenced" ? `<button class="text-button" data-slo-alert="${alert.id}" data-alert-action="unsilence">Unsilence</button>` : ""}</div>
    </article>`).join("") : empty("No active routed service alerts.");
  document.querySelectorAll("[data-slo-alert]").forEach((button) => {
    button.onclick = () => transitionServiceAlert(button.dataset.sloAlert, button.dataset.alertAction);
  });
  document.getElementById("infra-tasks").innerHTML = tasks.length ? tasks.map((task) => taskEntityRow(task)).join("") : empty("No infrastructure tasks recorded.");
  bindEntityButtons();
}

async function transitionServiceAlert(alertId, action) {
  if (state.demo) return toast("Actions are disabled in demonstration mode.");
  const reason = window.prompt(`Reason to ${action} this service alert:`);
  if (!reason || reason.trim().length < 10) return toast("A reason of at least 10 characters is required.");
  const payload = { action, reason: reason.trim() };
  if (action === "silence") payload.silence_seconds = 3600;
  await mutate(`/api/observability/alerts/${alertId}`, payload, `Service alert ${action} recorded.`);
  await loadDashboard();
}

function formatPercent(value) {
  return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : "–";
}

async function decideResearchCycle(button) {
  const decision = button.dataset.researchCycleDecision;
  const rationale = decision === "approved"
    ? "Founder approved this evidence-grounded daily research question."
    : window.prompt("Why should this daily research question be rejected?");
  if (!rationale) return;
  button.disabled = true;
  try {
    await mutate(`/api/research/cycles/${button.dataset.cycleId}/decision`, {
      expected_question_digest: button.dataset.cycleDigest,
      decision,
      rationale,
    }, `Daily research question ${decision}.`);
    await loadDashboard();
  } catch (error) {
    toast(error.message);
    button.disabled = false;
  }
}

function formatDuration(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value)) return "unknown age";
  if (value < 3600) return `${Math.max(1, Math.round(value / 60))}m`;
  if (value < 86400) return `${Math.round(value / 3600)}h`;
  return `${(value / 86400).toFixed(1)}d`;
}

function renderResearch() {
  if (!state.dashboard) return;
  const tasks = (state.dashboard.tasks || []).filter((task) => task.task_type === "research_experiment");
  const cycles = state.dashboard.research_cycles || [];
  const domains = state.dashboard.research_domains || [];
  const domainReadiness = state.dashboard.research_domain_readiness || [];
  const intelligenceRuns = state.dashboard.research_intelligence_runs || [];
  const memoryExports = state.dashboard.research_memory_exports || [];
  const datasetManifests = state.dashboard.research_dataset_manifests || [];
  const datasetBuilds = state.dashboard.research_dataset_builds || [];
  const alphaCampaigns = state.dashboard.alpha_campaigns || [];
  const dossiers = state.dashboard.evidence_dossiers || [];
  const lifecycleStates = state.dashboard.evidence_lifecycle_states || [];
  const blockedRegister = state.dashboard.blocked_artifact_register || { total: 0, counts_by_classification: {}, items: [] };
  const surveillanceSources = state.dashboard.surveillance_sources || [];
  const surveillanceCandidates = state.dashboard.surveillance_candidates || [];
  const surveillanceDigests = state.dashboard.surveillance_digests || [];
  const scientificReviewQueue = state.dashboard.scientific_review_queue || [];
  const scientificBenchmarks = state.dashboard.scientific_benchmarks || [];
  const mathematicsCapabilities = state.dashboard.mathematics_capabilities || [];
  const intelligenceEvaluation = state.dashboard.intelligence_evaluation || { status: "not_demonstrated", domains: {}, limitations: [] };
  const derivedState = state.dashboard.derived_state || { current: false, pending_changes: 0, retrieval: { stale: true }, graph: { stale: true }, latest_run: null };
  const lifecycleItems = state.dashboard.institutional_lifecycles?.items || [];
  const consequenceItems = state.dashboard.lifecycle_consequences?.items || [];
  const memoryTasks = (state.dashboard.tasks || []).filter((task) => task.task_type === "research_memory_sync");
  document.getElementById("scientific-review-count").textContent = `${scientificReviewQueue.length} pending`;
  const derivedRun = derivedState.latest_run;
  document.getElementById("derived-state-status").innerHTML = statusBadge(derivedState.current ? "current" : (derivedRun?.state || "stale"));
  document.getElementById("derived-state").innerHTML = `
    <article class="entity-row"><div class="entity-primary"><strong>${derivedState.current ? "Derived views are current" : "Derived work is pending"}</strong><div class="entity-meta"><span>Corpus epoch ${derivedState.corpus_epoch ?? "unknown"}</span><span>${derivedState.pending_changes || 0} unclaimed changes</span><span>Retrieval ${derivedState.retrieval?.stale ? "stale" : "current"}</span><span>Graph ${derivedState.graph?.stale ? "stale" : "current"}</span>${derivedRun ? `<span>${escapeHtml(humanize(derivedRun.phase))}</span><span>${escapeHtml(derivedRun.strategy)}</span>` : ""}</div><p>${escapeHtml(derivedState.claim_boundary || "Canonical evidence remains available while derived views converge.")}</p>${derivedRun?.error_summary ? `<p>${escapeHtml(derivedRun.error_summary)}</p>` : ""}</div></article>`;
  document.getElementById("scientific-review-queue").innerHTML = scientificReviewQueue.length ? scientificReviewQueue.map((item) => `
    <article class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(humanize(item.scientific_type))}</strong><div class="entity-meta"><span>${escapeHtml(item.representation_version)}</span><span class="mono">${shortHash(item.source_region_digest)}</span><span>${item.uncertainties.length} uncertainties</span></div><p>${escapeHtml(item.normalized_content.slice(0, 240))}</p></div>
      <div class="entity-side">${statusBadge(item.status)}<button class="secondary compact" data-scientific-review="${item.id}" ${item.corpus_digest ? "" : "disabled"}>${item.corpus_digest ? "Review" : "Benchmark required"}</button></div>
    </article>`).join("") : empty("No scientific representations await independent adjudication.");
  document.getElementById("scientific-benchmarks").innerHTML = scientificBenchmarks.length ? scientificBenchmarks.slice(0, 8).map((item) => `
    <article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(item.benchmark_version)}</strong><div class="entity-meta"><span>${item.counts.adjudicated || 0}/${item.counts.sampled || 0} adjudicated</span><span>${item.counts.conflicted || 0} conflicts</span><span class="mono">${shortHash(item.sample_digest)}</span></div></div>${statusBadge(item.status)}</article>`).join("") : "";
  document.getElementById("mathematics-capabilities").innerHTML = mathematicsCapabilities.length ? mathematicsCapabilities.map((item) => `
    <article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(humanize(item.agent_role))}</strong><div class="entity-meta"><span>${item.demonstrated_tasks.length} demonstrated tasks</span><span>${item.limitations.length} limitations</span><span class="mono">${shortHash(item.record_digest)}</span></div></div>${statusBadge(item.status)}</article>`).join("") : empty("No agent mathematics capability has been independently demonstrated yet.");
  const intelligenceDomains = Object.entries(intelligenceEvaluation.domains || {});
  document.getElementById("intelligence-evaluation-status").innerHTML = statusBadge(intelligenceEvaluation.status);
  document.getElementById("intelligence-evaluation").innerHTML = `
    <article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(humanize(intelligenceEvaluation.status))}</strong><div class="entity-meta"><span>${intelligenceDomains.filter(([, value]) => value.status === "qualified").length}/${intelligenceDomains.length} domains qualified</span><span>${(intelligenceEvaluation.representative_failures || []).length} representative failures</span>${intelligenceEvaluation.evaluation_digest ? `<span class="mono">${shortHash(intelligenceEvaluation.evaluation_digest)}</span>` : ""}</div><p>${escapeHtml(intelligenceEvaluation.claim_boundary || "No held-out live-corpus reasoning qualification has been recorded.")}</p>${(intelligenceEvaluation.limitations || []).length ? `<p>${intelligenceEvaluation.limitations.map(humanize).join(" · ")}</p>` : ""}</div></article>
    ${intelligenceDomains.map(([domain, value]) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(domain)}</strong><div class="entity-meta"><span>${value.passed || 0}/${value.items || 0} passed</span></div></div>${statusBadge(value.status || "not_demonstrated")}</article>`).join("")}`;
  document.querySelectorAll("[data-scientific-review]").forEach((button) => {
    button.onclick = async () => {
      const item = scientificReviewQueue.find((candidate) => candidate.id === button.dataset.scientificReview);
      if (!item) return;
      const context = await request(`/api/research/scientific-fidelity/review-context/${item.id}`);
      const sourceText = context.source?.payload?.content_text || "Source region text is unavailable.";
      const parserOutputs = item.parser_outputs.map((output) => `${output.parser}: ${output.content}`).join("\n\n");
      const proceed = window.confirm(`SOURCE REGION\n${sourceText}\n\nNORMALIZED REPRESENTATION\n${item.normalized_content}\n\nPARSER OUTPUTS\n${parserOutputs}\n\nContinue to immutable adjudication?`);
      if (!proceed) return;
      const decision = window.prompt("Decision: equivalent, material_mismatch, wrong_object_class, incomplete_region, unsupported_notation, or unreadable_source");
      if (!decision) return;
      const rationale = window.prompt("Independent rationale (at least 10 characters):");
      if (!rationale || rationale.trim().length < 10) return toast("A substantive rationale is required.");
      await mutate("/api/research/scientific-fidelity/adjudications", {
        representation_id: item.id, reviewer_id: "founder-mission-control", reviewer_role: "founder_operator",
        decision: decision.trim(), rationale: rationale.trim(), gold_payload: {}, corpus_digest: item.corpus_digest,
      }, "Immutable scientific adjudication recorded.");
      await loadDashboard();
    };
  });
  const lifecycleSubjects = new Map();
  lifecycleItems.forEach((item) => {
    const key = `${item.subject_type}:${item.subject_id}`;
    const subject = lifecycleSubjects.get(key) || { subject_type: item.subject_type, subject_id: item.subject_id, states: {} };
    subject.states[item.dimension] = item;
    lifecycleSubjects.set(key, subject);
  });
  document.getElementById("lifecycle-count").textContent = `${lifecycleSubjects.size} governed subjects`;
  document.getElementById("institutional-lifecycles").innerHTML = lifecycleSubjects.size ? [...lifecycleSubjects.values()].map((subject) => `
    <article class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(subject.subject_type)} · ${escapeHtml(subject.subject_id)}</strong>
        <div class="entity-meta">${["research", "evidence", "operations", "capital"].map((dimension) => {
          const projection = subject.states[dimension];
          return `<span>${humanize(dimension)}: ${escapeHtml(projection?.state || "missing")} · v${projection?.version ?? 0}</span>`;
        }).join("")}</div>
      </div>
    </article>`).join("") : empty("No governed lifecycle subjects have been registered.");
  document.getElementById("consequence-count").textContent = `${consequenceItems.length} retained decisions`;
  document.getElementById("lifecycle-consequences").innerHTML = consequenceItems.length ? consequenceItems.slice(0, 12).map((item) => `
    <article class="entity-row">
      <div class="entity-primary"><strong>${humanize(item.action)} · ${humanize(item.status)}</strong>
        <div class="entity-meta"><span>${escapeHtml(item.prior_state)} → ${escapeHtml(item.resulting_state)}</span><span>Rollback: ${escapeHtml(item.rollback_state)}</span><span>${item.affected_descendants.length} descendants</span><span class="mono">${shortHash(item.record_digest)}</span></div>
        <p>${escapeHtml(item.reason)}</p>
      </div>
    </article>`).join("") : empty("No lifecycle consequences have been recorded.");
  const latestMemoryTask = memoryTasks[0];
  const latestMemory = memoryExports[0];
  const memoryStatus = document.getElementById("memory-sync-status");
  if (latestMemoryTask && ["queued", "leased", "running", "pending_approval"].includes(latestMemoryTask.status)) {
    memoryStatus.textContent = `${latestMemoryTask.task_number} · ${humanize(latestMemoryTask.status)}`;
  } else if (latestMemory) {
    const counts = latestMemory.export?.counts || {};
    memoryStatus.textContent = `${shortHash(latestMemory.export_digest)} · ${counts.trades ?? 0} trades · ${relativeTime(latestMemory.registered_at)}`;
  } else {
    memoryStatus.textContent = "No structured Bulletproof memory export registered.";
  }
  const accepted = tasks.filter((task) => task.result?.summary?.verdict === "accepted").length;
  document.getElementById("research-gate").innerHTML = `
    <span class="gate-symbol">G</span>
    <div><strong>Research promotion gate enforced</strong><div class="entity-meta"><span>${accepted} synthetic findings accepted</span><span>Live deployment requires a separate approval path</span></div></div>
    ${statusBadge("active")}
  `;
  document.getElementById("research-cycles").innerHTML = cycles.length ? cycles.map((cycle) => `
    <div class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(cycle.question)}</strong><div class="entity-meta"><span>${escapeHtml(cycle.cycle_date)}</span><span>${escapeHtml(cycle.question_key)}</span><span>${escapeHtml(cycle.digest?.selection?.mode === "approved_research_intelligence" ? "Research Intelligence" : "mandate fallback")}</span><span>${escapeHtml(cycle.digest?.approval?.decision || "founder review required")}</span><span class="mono">${shortHash(cycle.question_digest)}</span></div>${cycle.digest?.selection?.ranking ? `<p>Director score ${number(cycle.digest.selection.ranking.director_score)} · novelty ${number(cycle.digest.selection.ranking.novelty_score)} · evidence ${number(cycle.digest.selection.ranking.evidence_quality)}</p>` : ""}</div>
      <div class="entity-side">${cycle.status === "awaiting_brief" && !cycle.digest?.approval ? `<button class="secondary compact" data-research-cycle-decision="rejected" data-cycle-id="${cycle.id}" data-cycle-digest="${cycle.question_digest}">Reject</button><button class="primary compact" data-research-cycle-decision="approved" data-cycle-id="${cycle.id}" data-cycle-digest="${cycle.question_digest}">Approve</button>` : ""}${statusBadge(cycle.status)}</div>
    </div>
  `).join("") : empty("No supervised daily research cycle has been scheduled.");
  document.querySelectorAll("[data-research-cycle-decision]").forEach((button) => {
    button.addEventListener("click", () => decideResearchCycle(button));
  });
  const activeCampaigns = alphaCampaigns.filter((item) => item.status === "running");
  document.getElementById("alpha-campaign-count").textContent = `${activeCampaigns.length} active · ${alphaCampaigns.length} total`;
  document.getElementById("alpha-campaigns").innerHTML = alphaCampaigns.length ? alphaCampaigns.map((item) => {
    const datasets = item.specification?.dataset_bindings || [];
    const boundary = item.claim_boundary || "No-capital research coordination only.";
    const execution = item.execution;
    return `<article class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(item.campaign_key)} · v${escapeHtml(item.version)}</strong>
        <div class="entity-meta"><span>${escapeHtml(humanize(item.phase))}</span><span>Next: ${escapeHtml(humanize(item.next_action))}</span><span>${item.hypothesis_count}/${item.budget?.max_hypotheses || 0} hypotheses</span><span>${item.trial_count}/${item.budget?.max_total_trials || 0} trials</span><span>${datasets.length} real-data bindings</span><span>Heartbeat ${relativeTime(item.heartbeat_at)}</span><span class="mono">${shortHash(item.campaign_digest)}</span></div>
        <p>${escapeHtml(item.objective)}</p><p>${escapeHtml(boundary)}</p>
        ${execution ? `<div class="entity-meta"><span>Executor ${escapeHtml(humanize(execution.status))}</span><span>${execution.attempt_count}/${execution.max_attempts} attempts</span><span>${escapeHtml(humanize(execution.disposition || "awaiting receipt"))}</span><span>Worker ${relativeTime(execution.heartbeat_at)}</span><span class="mono">${escapeHtml(execution.task_number)}</span></div>` : ""}
        ${item.terminal_reason?.category ? `<p class="operation-error">${escapeHtml(humanize(item.terminal_reason.category))}</p>` : ""}
      </div><div class="entity-side">${statusBadge(item.status)}</div>
    </article>`;
  }).join("") : empty("No admitted real-data alpha campaign has been registered.");
  document.getElementById("research-datasets").innerHTML = datasetManifests.length ? datasetManifests.map((item) => {
    const builds = datasetBuilds.filter((build) => build.manifest_id === item.id);
    const latest = builds[0];
    return `<div class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(item.manifest_key)}</strong><div class="entity-meta"><span>${escapeHtml(item.manifest.provider.name)}</span><span>${escapeHtml(item.manifest.instruments.join(", "))}</span><span>${escapeHtml(item.manifest.timeframe)}</span><span>as of ${formatDate(item.manifest.as_of)}</span></div><div class="entity-meta"><span class="mono">manifest ${shortHash(item.manifest_digest)}</span><span class="mono">data ${shortHash(latest?.content_digest)}</span><span>${latest?.rows ?? 0} rows</span></div></div>
      ${statusBadge(latest && latest.content_digest === latest.rebuild_content_digest ? "verified" : "pending")}
    </div>`;
  }).join("") : empty("No point-in-time dataset build is registered.");
  const readinessRows = domainReadiness.map((domain) => `<div class="entity-row">
    <div class="entity-primary"><strong>${escapeHtml(domain.domain_key)}</strong><div class="entity-meta"><span>curriculum v${escapeHtml(domain.curriculum_version)}</span><span>${domain.covered_topic_count}/${domain.topic_count} topics</span><span>${number(domain.topic_coverage * 100)}% coverage</span><span>${domain.quarantined_items} quarantined</span><span class="mono">${shortHash(domain.graph_manifest_digest)}</span></div>${domain.reasons.length ? `<p>${domain.reasons.map(humanize).join(" · ")}</p>` : ""}</div>
    ${statusBadge(domain.ready ? "qualified" : "gaps_detected")}
  </div>`);
  const legacyRows = domains.map((domain) => {
    const latestRun = intelligenceRuns.find((run) => run.domain_profile_id === domain.id);
    const selected = latestRun?.selected_candidate;
    return `<div class="entity-row">
      <div class="entity-primary"><strong>${escapeHtml(domain.title)}</strong><div class="entity-meta"><span>${escapeHtml(domain.domain_key)} v${escapeHtml(domain.version)}</span><span>${domain.document_keys.length} immutable sources</span><span class="mono">${shortHash(domain.corpus_digest)}</span></div>${selected ? `<p>${escapeHtml(selected.question)}</p>` : ""}</div>
      ${statusBadge(domain.status)}
    </div>`;
  });
  document.getElementById("research-domains").innerHTML = [...readinessRows, ...legacyRows].join("") || empty("No domain has passed its institutional brain evaluation.");
  const surveillanceSummary = document.getElementById("research-surveillance-summary");
  surveillanceSummary.innerHTML = `
    <div class="machine-cell"><span class="machine-symbol">SF</span><div><strong>${surveillanceSources.filter((item) => item.is_enabled).length}</strong><small>approved feeds</small></div></div>
    <div class="machine-cell"><span class="machine-symbol">CA</span><div><strong>${surveillanceCandidates.length}</strong><small>governed candidates</small></div></div>
    <div class="machine-cell"><span class="machine-symbol">WD</span><div><strong>${surveillanceDigests.length}</strong><small>weekly digests</small></div></div>`;
  document.getElementById("research-surveillance").innerHTML = surveillanceCandidates.length ? surveillanceCandidates.slice(0, 20).map((item) => `
    <button class="entity-row entity-button" type="button" data-surveillance-id="${item.id}">
      <div class="entity-primary"><strong>${escapeHtml(item.title)}</strong><div class="entity-meta"><span>${escapeHtml(item.publication_status)}</span><span>novelty ${number(item.assessment?.novelty_score)}</span><span>quality ${number(item.assessment?.evidence_quality)}</span><span>${escapeHtml(item.routing?.target || "review")}</span><span class="mono">${shortHash(item.content_digest)}</span></div></div>
      ${statusBadge(item.publication_status === "retracted" ? "failed" : "pending")}
    </button>
  `).join("") : empty("No surveillance candidates have been collected.");
  document.getElementById("research-dossiers").innerHTML = dossiers.length ? dossiers.map((item) => {
    const dossier = item.dossier || {};
    const objects = dossier.objects || {};
    return `<button class="entity-row entity-button" type="button" data-dossier-id="${item.id}">
      <div class="entity-primary"><strong>${escapeHtml(item.question)}</strong><div class="entity-meta"><span>${escapeHtml(item.dossier_key)} v${item.version}</span><span>${objects.supporting_evidence?.length ?? 0} supporting</span><span>${objects.opposing_evidence?.length ?? 0} opposing</span><span>${dossier.access_limitations?.length ?? 0} redacted</span><span class="mono">${shortHash(item.record_digest)}</span></div></div>
      ${statusBadge("frozen")}
    </button>`;
  }).join("") : empty("No frozen evidence dossier has been compiled.");
  document.getElementById("research-lifecycle").innerHTML = lifecycleStates.length ? lifecycleStates.map((item) => `
    <button class="entity-row entity-button" type="button" data-lifecycle-id="${item.object_id}">
      <div class="entity-primary"><strong>${escapeHtml(item.state)}</strong><div class="entity-meta"><span class="mono">${shortHash(item.object_id)}</span><span>version ${item.version}</span><span>${item.retention_hold ? "retention hold" : "no hold"}</span><span>${formatDate(item.effective_at)}</span></div></div>
      ${statusBadge(item.state)}
    </button>
  `).join("") : empty("No evidence has left active memory.");
  const blockedCounts = Object.entries(blockedRegister.counts_by_classification || {});
  document.getElementById("blocked-artifact-summary").innerHTML = `
    <div class="machine-cell"><span class="machine-symbol">BQ</span><div><strong>${blockedRegister.total || 0}</strong><small>requiring action</small></div></div>
    ${blockedCounts.map(([classification, count]) => `<div class="machine-cell"><div><strong>${count}</strong><small>${escapeHtml(humanize(classification))}</small></div></div>`).join("")}
  `;
  document.getElementById("blocked-artifact-register").innerHTML = blockedRegister.items?.length ? blockedRegister.items.map((item) => `
    <button class="entity-row entity-button" type="button" data-blocked-job-id="${item.original_job_id}">
      <div class="entity-primary"><strong>${escapeHtml(item.source_title || item.filename)}</strong><div class="entity-meta"><span>${escapeHtml(item.project)}</span><span>${item.attempts?.length || 0} bounded attempts</span><span class="mono">${shortHash(item.content_digest)}</span></div><p>${escapeHtml(item.action_required)}</p></div>
      ${statusBadge(item.classification)}
    </button>
  `).join("") : empty("No blocked or quarantined artifacts require action.");
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
  document.querySelectorAll("[data-surveillance-id]").forEach((element) => {
    element.onclick = async () => {
      const replay = await request(`/api/research/surveillance/${element.dataset.surveillanceId}/replay`);
      openInspector("Surveillance provenance", replay.external_id, `
        <div class="inspector-section"><p class="section-kicker">Citation replay</p><h3>${escapeHtml(replay.publication_status)}</h3><p>${replay.exact_replay ? "Fetch receipt and publication identity are available." : "Fetch receipt is unavailable; candidate cannot advance."}</p><div class="entity-meta"><span class="mono">${escapeHtml(replay.content_digest)}</span><span>${escapeHtml(replay.canonical_url)}</span></div></div>`);
    };
  });
  document.querySelectorAll("[data-blocked-job-id]").forEach((element) => {
    element.onclick = () => {
      const item = blockedRegister.items.find((entry) => entry.original_job_id === element.dataset.blockedJobId);
      if (!item) return;
      const attempts = (item.attempts || []).map((attempt) => `<div class="inspector-row"><span>${escapeHtml(humanize(attempt.method))}</span><strong>${escapeHtml(attempt.outcome || attempt.pipeline_status || "recorded")}</strong><small>${escapeHtml(attempt.failure_category || "")}</small></div>`).join("");
      openInspector("Blocked artifact", item.source_title || item.filename, `
        <div class="inspector-section"><p class="section-kicker">Required action</p><h3>${escapeHtml(humanize(item.classification))}</h3><p>${escapeHtml(item.action_required)}</p><div class="entity-meta"><span>${item.retry_eligible ? "Recovery eligible" : "Terminal decision"}</span><span class="mono">${escapeHtml(item.content_digest)}</span></div></div>
        <div class="inspector-section"><h3>Recovery ledger</h3>${attempts || '<p class="muted">No recovery attempt has run yet.</p>'}</div>
        ${item.redacted_edition_proposal ? '<div class="inspector-section"><h3>Redacted edition</h3><p>A provenance-preserving proposal exists and requires founder approval. It is not authorized for publication.</p></div>' : ""}
      `);
    };
  });
}

async function openDossier(id) {
  const dossier = await request(`/api/research/dossiers/${id}`);
  const body = dossier.dossier || {};
  const objects = body.objects || {};
  const evidenceRows = (items, label) => (items || []).map((item) => `
    <div class="inspector-row"><span>${label}</span><strong>${escapeHtml(item.object_type || "evidence")}</strong><small class="mono">${shortHash(item.content_digest)}</small>${item.citation_replay_path ? `<small class="mono">citation replay available</small>` : ""}</div>
  `).join("") || `<p class="muted">No ${label.toLowerCase()} recorded.</p>`;
  openInspector("Frozen evidence dossier", `${dossier.dossier_key} v${dossier.version}`, `
    <div class="inspector-section"><p class="section-kicker">Frozen question</p><h3>${escapeHtml(dossier.question)}</h3><p>${escapeHtml(dossier.decision_context)}</p><div class="entity-meta"><span>${formatDate(dossier.frozen_at)}</span><span class="mono">${escapeHtml(dossier.record_digest)}</span></div></div>
    <div class="inspector-section"><h3>Supporting evidence</h3>${evidenceRows(objects.supporting_evidence, "Supporting")}</div>
    <div class="inspector-section"><h3>Opposing evidence</h3>${evidenceRows(objects.opposing_evidence, "Opposing")}</div>
    <div class="inspector-section"><h3>Synthesis</h3><p>${escapeHtml(body.synthesis || "No synthesis recorded.")}</p><p><strong>Recommendation:</strong> ${escapeHtml(body.recommendation || "None")}</p><p><strong>Dissent:</strong> ${escapeHtml((body.dissent || []).join("; ") || "None recorded")}</p></div>
    <div class="inspector-section"><h3>Access ledger</h3>${(body.access_limitations || []).map((item) => `<div class="inspector-row"><span>Protected evidence exists</span><strong>${escapeHtml(item.reason)}</strong><small class="mono">${escapeHtml(item.object_id)}</small></div>`).join("") || '<p class="muted">No evidence redacted for this role.</p>'}</div>
    <button id="replay-dossier" class="secondary" type="button">Replay frozen dossier</button>
    <div id="dossier-replay-result"></div>
  `);
  document.getElementById("replay-dossier").addEventListener("click", async () => {
    const replay = await request(`/api/research/dossiers/${id}/replay`);
    document.getElementById("dossier-replay-result").innerHTML = `<div class="inspector-section"><h3>Replay result</h3><p>${replay.exact_replay ? "All frozen identities and digests match." : "Historical state preserved; later impacts detected."}</p><div class="entity-meta"><span>${replay.impacts?.length ?? 0} later impacts</span></div></div>`;
  });
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
  document.querySelectorAll("[data-dossier-id]").forEach((element) => {
    element.onclick = () => openDossier(element.dataset.dossierId);
  });
  document.querySelectorAll("[data-lifecycle-id]").forEach((element) => {
    element.onclick = async () => {
      const dossier = await request(`/api/research/evidence/${element.dataset.lifecycleId}/lifecycle`);
      const current = dossier.state;
      const events = dossier.events || [];
      const impacts = dossier.impacts || [];
      openInspector("Evidence lifecycle", current.state, `
        <div class="inspector-section"><p class="section-kicker">Current materialized state</p><h3>${escapeHtml(current.state)}</h3><div class="entity-meta"><span class="mono">${escapeHtml(current.object_id)}</span><span>version ${current.version}</span><span>${current.retention_hold ? "retention hold active" : "no retention hold"}</span></div></div>
        <div class="inspector-section"><p class="section-kicker">Immutable lineage</p><h3>${events.length} lifecycle events</h3><p>${events.map((item) => `${escapeHtml(item.event_type)} by ${escapeHtml(item.authority)}`).join(" · ") || "No transitions recorded."}</p><div class="entity-meta"><span>${impacts.length} impact reports</span><span class="mono">${escapeHtml(dossier.dossier_digest)}</span></div></div>`);
    };
  });
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
  const deployment = activeDeployment(agent.id);
  const pkg = deployment?.package;
  const manifest = pkg?.manifest;
  const permission = manifest?.permission_profile;
  const repository = manifest?.repository_profile;
  openInspector("Agent", agent.display_name || agent.slug, `
    <section class="detail-section"><h3>Identity</h3><dl class="detail-grid">
      <dt>Slug</dt><dd class="mono">${escapeHtml(agent.slug)}</dd>
      <dt>Machine</dt><dd>${escapeHtml(agent.machine)}</dd>
      <dt>Presence</dt><dd>${statusBadge(agentStatus(agent))}</dd>
      <dt>Enabled</dt><dd>${String(agent.is_enabled ?? agent.enabled ?? true)}</dd>
      <dt>Risk ceiling</dt><dd>${manifest?.risk_ceiling ?? agent.risk_ceiling ?? "–"}</dd>
      <dt>Profile</dt><dd>${escapeHtml(agent.hermes_profile || "Worker")}</dd>
    </dl></section>
    <section class="detail-section"><h3>Role and responsibility</h3>
      <p><strong>${escapeHtml(manifest?.role || agent.role || "No deployed role package")}</strong></p>
      <p>${escapeHtml(roleResponsibility(manifest))}</p>
    </section>
    <section class="detail-section"><h3>Tasks this agent can carry out</h3>
      <div class="capabilities">${(manifest?.task_types || []).map((item) => `<span class="capability strong">${escapeHtml(humanize(item))}</span>`).join("") || '<span class="muted">No executable task types deployed.</span>'}</div>
      <dl class="detail-grid compact">
        <dt>Workflows</dt><dd>${listOrNone((manifest?.workflows || []).map((item) => item.name))}</dd>
        <dt>Machines</dt><dd>${listOrNone(manifest?.allowed_machines)}</dd>
        <dt>Repositories</dt><dd>${listOrNone(repository?.repositories)}</dd>
      </dl>
    </section>
    <section class="detail-section"><h3>Capabilities</h3><div class="capabilities">${(agent.capabilities || []).map((item) => `<span class="capability">${escapeHtml(item)}</span>`).join("")}</div></section>
    <section class="detail-section"><h3>Effective permissions</h3><dl class="detail-grid">
      <dt>Profile</dt><dd>${escapeHtml(permission?.name || "No active package")}</dd>
      <dt>Network</dt><dd>${escapeHtml(humanize(permission?.network_access || "none"))}</dd>
      <dt>Writable roots</dt><dd>${listOrNone(permission?.writable_roots)}</dd>
      <dt>Privileged ops</dt><dd>${yesNo(permission?.privileged_operations)}</dd>
      <dt>Primary write</dt><dd>${yesNo(repository?.primary_checkout_write)}</dd>
      <dt>Remote write</dt><dd>${yesNo(repository?.remote_write)}</dd>
    </dl></section>
    <section class="detail-section"><h3>Signed deployment</h3><dl class="detail-grid">
      <dt>Package</dt><dd>${escapeHtml(pkg ? `${pkg.name} ${pkg.version}` : "None")}</dd>
      <dt>Active</dt><dd>${yesNo(deployment?.deployment?.is_active)}</dd>
      <dt>Source commit</dt><dd class="mono">${escapeHtml(pkg?.source_commit || "Not recorded")}</dd>
      <dt>Manifest digest</dt><dd class="mono">${escapeHtml(pkg?.manifest_digest || "Not recorded")}</dd>
    </dl></section>
  `);
}

function openProposal(id) {
  const item = (state.dashboard.proposals || []).find((proposal) => String(proposal.id) === String(id));
  if (!item) return;
  const proposal = item.proposal;
  const task = proposal.proposed_task;
  openInspector("Founder proposal", proposal.summary, `
    <section class="detail-section"><h3>Planner recommendation</h3><dl class="detail-grid">
      <dt>Status</dt><dd>${statusBadge(item.status)}</dd>
      <dt>Action</dt><dd>${escapeHtml(humanize(proposal.recommended_action))}</dd>
      <dt>Target role</dt><dd>${escapeHtml(proposal.target_role || "Not assigned")}</dd>
      <dt>Digest</dt><dd class="mono">${escapeHtml(item.proposal_digest)}</dd>
    </dl></section>
    <section class="detail-section"><h3>Interpretation</h3><p>${escapeHtml(proposal.interpretation)}</p></section>
    <section class="detail-section"><h3>Assumptions</h3>${bulletList(proposal.assumptions, "No assumptions recorded.")}</section>
    <section class="detail-section ${!task ? "clarification-required" : ""}"><h3>${!task ? "Clarification required before approval" : "Clarification questions"}</h3>${bulletList(proposal.clarification_questions, "No clarification required.")}</section>
    <section class="detail-section"><h3>Safety constraints</h3>${bulletList(proposal.safety_constraints, "No additional constraints recorded.")}</section>
    ${task ? `<section class="detail-section"><h3>Proposed governed task</h3><dl class="detail-grid">
      <dt>Project</dt><dd>${escapeHtml(task.project)}</dd>
      <dt>Type</dt><dd>${escapeHtml(humanize(task.task_type))}</dd>
      <dt>Risk</dt><dd>${task.risk_level}</dd>
      <dt>Machines</dt><dd>${listOrNone(task.allowed_machines)}</dd>
      <dt>Capabilities</dt><dd>${listOrNone(task.required_capabilities)}</dd>
      <dt>Approval</dt><dd>${task.approval_required || task.risk_level >= 2 ? "Required" : "Automatic policy"}</dd>
    </dl><p><strong>${escapeHtml(task.title)}</strong></p><p>${escapeHtml(task.objective)}</p></section>` : ""}
    ${item.status === "proposed" ? `<section class="detail-actions"><button class="secondary danger" data-proposal-action="reject">Reject</button>${task ? '<button class="command" data-proposal-action="materialize">Create governed task</button>' : ""}</section>` : ""}
  `);
  document.querySelectorAll("[data-proposal-action]").forEach((button) => {
    button.onclick = () => openProposalDecision(item, button.dataset.proposalAction);
  });
}

function openProposalDecision(proposal, action) {
  closeInspector();
  const form = document.getElementById("proposal-form");
  form.reset();
  form.elements.proposal_id.value = proposal.id;
  form.elements.action.value = action;
  const create = action === "materialize";
  document.getElementById("proposal-title").textContent = create ? "Create governed task" : "Reject proposal";
  document.getElementById("proposal-submit").textContent = create ? "Create governed task" : "Reject proposal";
  document.getElementById("proposal-submit").className = create ? "command" : "secondary danger";
  document.getElementById("proposal-summary").innerHTML = `<p>${escapeHtml(proposal.proposal.summary)}</p><dl><dt>Target role</dt><dd>${escapeHtml(proposal.proposal.target_role || "Unassigned")}</dd><dt>Risk</dt><dd>${proposal.proposal.proposed_task?.risk_level ?? "–"}</dd></dl>`;
  document.getElementById("proposal-dialog").showModal();
}

function activeDeployment(agentId) {
  const deployments = (state.dashboard.package_deployments || []).filter((item) =>
    String(item.deployment?.agent_id) === String(agentId) && item.deployment?.is_active
  );
  return deployments.at(-1);
}

function roleResponsibility(manifest) {
  if (!manifest) return "No active signed role package is deployed. This identity should not receive work.";
  const tasks = (manifest.task_types || []).map(humanize).join(", ");
  const repos = manifest.repository_profile?.repositories || [];
  const scope = repos.length ? ` within ${repos.join(", ")}` : " without repository access";
  return `Responsible for ${tasks || "no executable task types"}${scope}.`;
}

function listOrNone(values) {
  return values?.length ? values.map((item) => escapeHtml(humanize(item))).join(", ") : "None";
}

function yesNo(value) {
  return value ? "Yes" : "No";
}

function bulletList(values, fallback) {
  return values?.length ? `<ul class="detail-list">${values.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : `<p class="muted">${escapeHtml(fallback)}</p>`;
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

function setCopilotState(label, busy) {
  const element = document.getElementById("copilot-state");
  element.classList.toggle("busy", busy);
  element.innerHTML = `<span class="state-dot"></span>${escapeHtml(label)}`;
}

function renderResearchWorkspaceStatus() {
  const element = document.getElementById("research-workspace-status");
  if (!element) return;
  const graph = state.graphData || {};
  const domains = state.dashboard?.research_domains || [];
  const blocked = state.dashboard?.blocked_artifacts || {};
  const graphReady = Boolean(graph.projection_version);
  element.innerHTML = `
    <div><span>Projection</span><strong>${escapeHtml(graph.projection_version || "Unavailable")}</strong><small>${graphReady ? "Current bounded read model" : "Graph evidence unavailable"}</small></div>
    <div><span>Visible graph</span><strong>${(graph.nodes || []).length.toLocaleString()} / ${(graph.edges || []).length.toLocaleString()}</strong><small>Nodes / relationships</small></div>
    <div><span>Qualified domains</span><strong>${domains.length.toLocaleString()}</strong><small>Authorized research curricula</small></div>
    <div><span>Ingestion attention</span><strong>${Number(blocked.total || 0).toLocaleString()}</strong><small>Blocked or quarantined artifacts</small></div>`;
}

function addResearchContext(item) {
  if (!item?.id) return;
  const normalized = {
    id: String(item.id),
    label: String(item.label || item.object_type || "Canonical evidence"),
    type: String(item.type || item.object_type || "evidence"),
    digest: String(item.digest || item.content_digest || ""),
    source: item.source || null,
  };
  state.researchContext = [normalized, ...state.researchContext.filter((entry) => entry.id !== normalized.id)].slice(0, 8);
  renderResearchContext();
}

function renderResearchContext() {
  const element = document.getElementById("research-context-items");
  if (!element) return;
  const clear = document.getElementById("clear-research-context");
  clear.disabled = state.researchContext.length === 0;
  element.innerHTML = state.researchContext.length ? state.researchContext.map((item) => `
    <span class="research-context-item">
      <button type="button" data-context-open="${escapeHtml(item.id)}"><strong>${escapeHtml(truncate(item.label, 38))}</strong><small>${escapeHtml(humanize(item.type))}${item.digest ? ` · ${escapeHtml(shortHash(item.digest))}` : ""}</small></button>
      <button type="button" class="context-remove" data-context-remove="${escapeHtml(item.id)}" aria-label="Remove ${escapeHtml(item.label)} from working context" title="Remove from context">×</button>
    </span>`).join("") : `<span class="context-empty">Select a citation or graph node to keep it in view.</span>`;
  element.querySelectorAll("[data-context-remove]").forEach((button) => button.addEventListener("click", () => {
    state.researchContext = state.researchContext.filter((item) => item.id !== button.dataset.contextRemove);
    renderResearchContext();
  }));
  element.querySelectorAll("[data-context-open]").forEach((button) => button.addEventListener("click", async () => {
    const item = state.researchContext.find((entry) => entry.id === button.dataset.contextOpen);
    if (item?.source) return openCopilotSource(item.source);
    setResearchMode("explore");
    await queryGraphRoot(item.id);
  }));
}

function appendCopilotQuestion(question) {
  const thread = document.getElementById("copilot-thread");
  thread.querySelector(".copilot-empty")?.remove();
  thread.insertAdjacentHTML("beforeend", `
    <article class="copilot-message founder-message">
      <div class="message-author">Founder</div>
      <p>${escapeHtml(question)}</p>
    </article>
    <article id="copilot-pending" class="copilot-message copilot-message-pending" aria-label="Research Copilot is preparing an answer">
      <div class="message-author">Research Copilot</div>
      <div class="thinking-line"><span></span><span></span><span></span>Retrieving and validating canonical evidence</div>
    </article>
  `);
  thread.scrollTop = thread.scrollHeight;
}

function appendCopilotFailure(message) {
  document.getElementById("copilot-pending")?.remove();
  const thread = document.getElementById("copilot-thread");
  thread.insertAdjacentHTML("beforeend", `
    <article class="copilot-message copilot-failure" role="alert">
      <div class="message-author">Research Copilot</div>
      <p>${escapeHtml(message)}</p>
    </article>
  `);
}

function renderCopilotAnswer(answer) {
  document.getElementById("copilot-pending")?.remove();
  const sourceIndex = new Map((answer.sources || []).map((source, index) => [String(source.object_id), index + 1]));
  const claims = (answer.claims || []).map((claim) => {
    const citations = (claim.citation_object_ids || []).map((id) => {
      const source = (answer.sources || []).find((item) => String(item.object_id) === String(id));
      return `<button class="inline-citation" type="button" data-copilot-source="${escapeHtml(id)}" aria-label="Open citation ${sourceIndex.get(String(id))}">[${sourceIndex.get(String(id))}]</button>`;
    }).join("");
    return `<li><span>${escapeHtml(claim.text)}</span>${citations}<small>${claim.evidence_class === "agent_inference" ? "Agent inference" : "Source evidence"}</small></li>`;
  }).join("");
  const thread = document.getElementById("copilot-thread");
  thread.insertAdjacentHTML("beforeend", `
    <article class="copilot-message assistant-message">
      <div class="answer-header"><div class="message-author">Research Copilot</div>${confidenceBadge(answer.confidence)}</div>
      <p class="copilot-answer">${escapeHtml(answer.answer)}</p>
      ${claims ? `<ol class="answer-claims">${claims}</ol>` : ""}
      ${(answer.limitations || []).length ? `<div class="answer-limitations"><strong>Limits</strong>${answer.limitations.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}</div>` : ""}
      <div class="answer-receipt"><span class="mono">Corpus ${escapeHtml(shortHash(answer.corpus_digest || ""))}</span><span class="mono">Context ${escapeHtml(shortHash(answer.context_pack_digest || ""))}</span><span>${number((answer.retrieval_confidence || 0) * 100)}% retrieval confidence</span></div>
    </article>
  `);
  renderCopilotSources(answer);
  bindCopilotCitations(answer);
  thread.scrollTop = thread.scrollHeight;
}

function confidenceBadge(confidence) {
  const label = confidence === "insufficient_evidence" ? "Insufficient evidence" : humanize(confidence);
  return `<span class="confidence ${escapeHtml(confidence)}">${escapeHtml(label)}</span>`;
}

function renderCopilotSources(answer) {
  const sources = answer.sources || [];
  document.getElementById("copilot-answer-meta").innerHTML = `
    <div class="answer-status-line">${confidenceBadge(answer.confidence)}<span>${sources.length} cited object${sources.length === 1 ? "" : "s"}</span></div>
    <dl><dt>Corpus</dt><dd class="mono">${escapeHtml(shortHash(answer.corpus_digest || ""))}</dd><dt>Context</dt><dd class="mono">${escapeHtml(shortHash(answer.context_pack_digest || ""))}</dd></dl>
  `;
  document.getElementById("copilot-sources").innerHTML = sources.length ? sources.map((source, index) => `
    <button class="copilot-source" type="button" data-copilot-source="${escapeHtml(source.object_id)}">
      <span class="source-number">${index + 1}</span>
      <span><strong>${escapeHtml(humanize(source.object_type))}</strong><small>${escapeHtml((source.excerpt || "").slice(0, 180))}</small><span class="mono">${escapeHtml(shortHash(source.content_digest))}</span></span>
    </button>
  `).join("") : empty("No source met the evidence threshold.");
}

function bindCopilotCitations(answer) {
  document.querySelectorAll("[data-copilot-source]").forEach((button) => {
    button.addEventListener("click", () => {
      const source = (answer.sources || []).find((item) => String(item.object_id) === button.dataset.copilotSource);
      if (source) openCopilotSource(source);
    });
  });
}

function openCopilotSource(source) {
  addResearchContext({ id: source.object_id, label: source.object_type, type: source.object_type, digest: source.content_digest, source });
  const coordinates = source.citation?.coordinates || {};
  openInspector("Canonical citation", humanize(source.object_type), `
    <section class="detail-section"><h3>Evidence</h3><p class="replay-excerpt">${escapeHtml(source.excerpt)}</p></section>
    <section class="detail-section"><h3>Identity</h3><dl class="detail-grid">
      <dt>Object</dt><dd class="mono">${escapeHtml(source.object_id)}</dd>
      <dt>Digest</dt><dd class="mono">${escapeHtml(source.content_digest)}</dd>
      <dt>Page</dt><dd>${escapeHtml(coordinates.page || "Unavailable")}</dd>
      <dt>Lines</dt><dd>${escapeHtml(coordinates.line_start || "–")}–${escapeHtml(coordinates.line_end || "–")}</dd>
      <dt>Access</dt><dd>${statusBadge(source.access_class)}</dd>
    </dl></section>
    <div class="inspector-actions"><button class="secondary replay-citation" type="button" data-replay-object="${escapeHtml(source.object_id)}">Replay exact citation</button><button class="secondary" type="button" data-explore-object="${escapeHtml(source.object_id)}">Explore relationships</button></div>
    <div id="citation-replay-result"></div>
  `);
  document.querySelector("[data-replay-object]").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    try {
      const replay = await request(`/api/research/copilot/citations/${encodeURIComponent(button.dataset.replayObject)}`);
      document.getElementById("citation-replay-result").innerHTML = `<pre class="citation-replay">${escapeHtml(JSON.stringify(replay, null, 2))}</pre>`;
    } catch (error) {
      document.getElementById("citation-replay-result").innerHTML = empty(error.message);
    } finally {
      button.disabled = false;
    }
  });
  document.querySelector("[data-explore-object]").addEventListener("click", async (event) => {
    closeInspector();
    navigate("knowledge");
    setResearchMode("explore");
    await queryGraphRoot(event.currentTarget.dataset.exploreObject);
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
  state.graphData = graph;
  renderResearchWorkspaceStatus();
  document.querySelectorAll("[data-graph-view]").forEach((item) => {
    const active = item.dataset.graphView === state.graphView;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  const nodes = (graph.nodes || []).slice(0, 100);
  const nodeMap = new Map(nodes.map((node) => [String(node.id), node]));
  const edges = (graph.edges || []).filter((edge) => nodeMap.has(String(edge.source)) && nodeMap.has(String(edge.target))).slice(0, 240);
  if (!nodes.length) {
    document.getElementById("graph").innerHTML = empty("Build the canonical graph projection to explore research lineage.");
    return;
  }
  if (!nodeMap.has(String(state.graphSelectedId))) state.graphSelectedId = String(nodes[0].id);
  const selected = nodeMap.get(String(state.graphSelectedId));
  document.getElementById("graph-expand").disabled = !selected;
  const positions = graphPositions(nodes);
  const visual = `
    <div class="graph-canvas-shell">
      <div class="graph-canvas-toolbar" role="group" aria-label="Graph zoom controls">
        <button type="button" class="icon-button" data-graph-zoom="in" aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" class="icon-button" data-graph-zoom="out" aria-label="Zoom out" title="Zoom out">−</button>
        <button type="button" class="icon-button graph-fit" data-graph-zoom="fit" aria-label="Fit graph" title="Fit graph">Fit</button>
      </div>
      <svg id="knowledge-graph-svg" class="knowledge-graph-svg" width="900" height="520" viewBox="0 0 900 520" role="img" aria-labelledby="graph-svg-title graph-svg-desc">
        <title id="graph-svg-title">Canonical research relationship graph</title>
        <desc id="graph-svg-desc">${nodes.length} evidence nodes and ${edges.length} visible relationships. Use the Relationships view for a keyboard-first adjacency list.</desc>
        <defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"></path></marker></defs>
        <g id="graph-viewport" transform="translate(${state.graphTransform.x} ${state.graphTransform.y}) scale(${state.graphTransform.scale})">
          <g class="graph-links">${edges.map((edge) => graphEdgeSvg(edge, positions)).join("")}</g>
          <g class="graph-nodes">${nodes.map((node, index) => graphNodeSvg(node, positions.get(String(node.id)), index, String(node.id) === String(state.graphSelectedId))).join("")}</g>
        </g>
      </svg>
      <div class="graph-legend"><span><i class="legend-shape claim"></i>Claim</span><span><i class="legend-shape result"></i>Result</span><span><i class="legend-shape source"></i>Source</span><span><i class="legend-line supports"></i>Supports</span><span><i class="legend-line contradicts"></i>Contradicts</span></div>
    </div>`;
  const relationships = `
    <div class="graph-adjacency" role="list" aria-label="Visible graph relationships">
      ${edges.length ? edges.map((edge) => graphRelationshipRow(edge, nodeMap)).join("") : empty("The selected bounded view contains no explicit relationships.")}
    </div>`;
  document.getElementById("graph").innerHTML = `
    <div class="projection-meta"><span>${escapeHtml(graph.projection_version || "local-knowledge-v1")}</span><span>${nodes.length.toLocaleString()} nodes</span><span>${edges.length.toLocaleString()} relationships</span><span class="mono">${escapeHtml(shortHash(graph.query_digest || graph.corpus_digest || ""))}</span>${graph.truncated ? "<span>Bounded at query limit</span>" : ""}</div>
    <div class="graph-workspace">
      <div class="graph-primary">${state.graphView === "visual" ? visual : relationships}</div>
      ${graphSelectionPanel(selected, edges, nodeMap)}
    </div>`;
  bindGraphInteractions(nodeMap);
}

function graphPositions(nodes) {
  const positions = new Map();
  nodes.forEach((node, index) => {
    if (index === 0) return positions.set(String(node.id), { x: 450, y: 260 });
    const angle = index * 2.399963;
    const radius = Math.min(225, 38 + Math.sqrt(index) * 34);
    positions.set(String(node.id), { x: 450 + Math.cos(angle) * radius * 1.55, y: 260 + Math.sin(angle) * radius });
  });
  return positions;
}

function graphNodeSvg(node, position, index, selected) {
  const type = String(node.object_type || node.kind || "evidence");
  const label = String(node.label || node.name || node.id);
  const shape = type === "claim" ? `<rect x="-8" y="-8" width="16" height="16" rx="2"></rect>` : type === "result" ? `<path d="M 0 -10 L 10 0 L 0 10 L -10 0 Z"></path>` : `<circle r="8"></circle>`;
  return `<g class="graph-node-svg type-${escapeHtml(type)}${selected ? " selected" : ""}" transform="translate(${position.x} ${position.y})" data-graph-node="${escapeHtml(node.id)}" tabindex="0" role="button" aria-pressed="${selected}" aria-label="${escapeHtml(label)}, ${escapeHtml(type)}">${shape}${(index < 14 || selected) ? `<text x="12" y="4">${escapeHtml(truncate(label, 34))}</text>` : ""}</g>`;
}

function graphEdgeSvg(edge, positions) {
  const source = positions.get(String(edge.source));
  const target = positions.get(String(edge.target));
  return `<line class="graph-link predicate-${escapeHtml(edge.predicate || edge.relation || "related")}" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" marker-end="url(#graph-arrow)"><title>${escapeHtml(humanize(edge.predicate || edge.relation || "related"))}</title></line>`;
}

function graphRelationshipRow(edge, nodeMap) {
  const source = nodeMap.get(String(edge.source));
  const target = nodeMap.get(String(edge.target));
  return `<div class="graph-relationship" role="listitem"><button type="button" data-graph-node="${escapeHtml(source.id)}">${escapeHtml(source.label || source.name)}</button><span class="relationship-predicate ${escapeHtml(edge.predicate || edge.relation)}">${escapeHtml(humanize(edge.predicate || edge.relation))}</span><button type="button" data-graph-node="${escapeHtml(target.id)}">${escapeHtml(target.label || target.name)}</button></div>`;
}

function graphSelectionPanel(node, edges, nodeMap) {
  const related = edges.filter((edge) => String(edge.source) === String(node.id) || String(edge.target) === String(node.id));
  return `<aside class="graph-selection" aria-label="Selected graph node">
    <p class="section-kicker">Selected evidence</p><h3>${escapeHtml(node.label || node.name)}</h3>
    <dl class="detail-grid"><dt>Type</dt><dd>${escapeHtml(node.object_type || node.kind)}</dd><dt>Project</dt><dd>${escapeHtml(node.project || "Local knowledge")}</dd><dt>Access</dt><dd>${statusBadge(node.access_class || "private")}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(shortHash(node.content_digest || ""))}</dd><dt>Visible links</dt><dd>${related.length.toLocaleString()}</dd></dl>
    <div class="graph-selection-actions"><button class="secondary" type="button" data-graph-replay="${escapeHtml(node.id)}">Replay evidence</button></div>
    <div class="selection-neighbors">${related.slice(0, 6).map((edge) => { const other = nodeMap.get(String(edge.source) === String(node.id) ? String(edge.target) : String(edge.source)); return `<button type="button" data-graph-node="${escapeHtml(other.id)}"><span>${escapeHtml(humanize(edge.predicate || edge.relation))}</span>${escapeHtml(other.label || other.name)}</button>`; }).join("") || `<span class="muted">No visible neighbors.</span>`}</div>
  </aside>`;
}

function bindGraphInteractions(nodeMap) {
  document.querySelectorAll("[data-graph-node]").forEach((element) => {
    const select = () => {
      state.graphSelectedId = element.dataset.graphNode;
      const node = nodeMap.get(String(state.graphSelectedId));
      addResearchContext({ id: node.id, label: node.label || node.name, type: node.object_type || node.kind, digest: node.content_digest });
      renderGraph(state.graphData);
    };
    element.addEventListener("click", select);
    element.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") { event.preventDefault(); select(); }
    });
  });
  document.querySelectorAll("[data-graph-zoom]").forEach((button) => button.addEventListener("click", () => {
    if (button.dataset.graphZoom === "fit") state.graphTransform = { scale: 1, x: 0, y: 0 };
    else state.graphTransform.scale = Math.max(.55, Math.min(2.2, state.graphTransform.scale * (button.dataset.graphZoom === "in" ? 1.2 : .8)));
    renderGraph(state.graphData);
  }));
  const replay = document.querySelector("[data-graph-replay]");
  if (replay) replay.addEventListener("click", () => replayGraphEvidence(nodeMap.get(replay.dataset.graphReplay)));
}

async function replayGraphEvidence(node) {
  openInspector("Canonical graph evidence", node.label || node.name, `<div id="graph-replay-result" class="empty-state">Replaying canonical evidence…</div>`);
  try {
    const replay = await request(`/api/research/copilot/citations/${encodeURIComponent(node.id)}`);
    document.getElementById("graph-replay-result").innerHTML = `<pre class="citation-replay">${escapeHtml(JSON.stringify(replay, null, 2))}</pre>`;
  } catch (error) {
    document.getElementById("graph-replay-result").innerHTML = empty(error.message);
  }
}

async function querySelectedGraphNode(event) {
  event.preventDefault();
  if (!state.graphSelectedId) return;
  await queryGraphRoot(state.graphSelectedId);
}

async function queryGraphRoot(rootId) {
  const button = document.getElementById("graph-expand");
  button.disabled = true;
  document.getElementById("graph").classList.add("loading");
  try {
    const predicate = document.getElementById("graph-predicate").value;
    const graph = await request("/api/knowledge/graph/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        root_ids: [rootId], mode: "neighborhood", predicates: predicate ? [predicate] : [],
        direction: document.getElementById("graph-direction").value,
        max_depth: Number(document.getElementById("graph-depth").value), max_nodes: 100,
      }),
    });
    state.graphSelectedId = rootId;
    state.graphTransform = { scale: 1, x: 0, y: 0 };
    renderGraph(graph);
  } catch (error) {
    toast(error.message);
  } finally {
    document.getElementById("graph").classList.remove("loading");
    button.disabled = !state.graphSelectedId;
  }
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

function truncate(value, length) {
  const text = String(value ?? "");
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
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

function loadDemoConversation() {
  const now = new Date().toISOString();
  const conversation = {
    id: "conversation-demo",
    short_id: "c7a32fb91e20",
    title: "BTC weekend liquidity research",
    project: "bulletproof_bt",
    status: "ready_for_review",
    revision: 4,
    specification_digest: "7dc489f42d1f0dfa45821c76bad2ae17473cad80534f32e2a1d4a8c31c64e9b6",
    current_specification: {
      summary: "Test whether weekend liquidity changes short-horizon momentum net of costs.",
      unresolved_fields: [],
      resolved_defaults: [{ field: "base_ref", value: "main", basis: "repository default" }],
    },
    messages: [
      { role: "founder", channel: "telegram", content: "Test whether BTC weekend liquidity changes short-horizon momentum after costs.", created_at: now },
      { role: "assistant", channel: "telegram", content: "I retained the hypothesis and selected bounded research defaults. The specification is ready for review.", created_at: now },
      { role: "founder", channel: "mission-control", content: "Use the conservative cost tier and retain every negative result.", created_at: now },
    ],
  };
  const task = { ...state.dashboard.tasks[0], conversation_revision: 4, created_at: now };
  const proposal = { ...state.dashboard.proposals[0], conversation_id: conversation.id, conversation_revision: 4 };
  const artifact = state.dashboard.artifacts?.[0];
  state.conversations = [conversation];
  state.activeConversationId = conversation.id;
  state.conversationWorkspace = {
    conversation,
    events: [{ event_type: "conversation_created", resulting_status: "collecting", revision: 1, created_at: now }],
    proposals: [proposal],
    tasks: [{ task, events: [{ event_type: "task_created", message: "Task created from reviewed founder specification.", created_at: now }] }],
    approvals: [],
    artifacts: artifact ? [artifact] : [],
  };
  renderConversations();
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
    approval_center: {
      generated_at: now,
      counts: { pending: 1, actionable: 1, blocked: 0, decided: 0 },
      items: [{
        approval: { id: "approval-demo", task_id: "infra-1", status: "pending", risk_level: 3, created_at: now, updated_at: now, plan_digest: "bc50ba1014ff33e68defbba9a1c727e2513d782fa1473547834d62cba1c16879", scope: { project: "swarm-control-plane", task_type: "infrastructure_operation" }, requested_by: "founder-operator", decided_by: null, decision_reason: null, issued_at: null, expires_at: null, consumed_at: null },
        task: { id: "infra-1", task_number: "VM2-RESTART-20260730", title: "Approved controlled VM2 API restart", objective: "Restart only the control-plane API with pre/post checks.", project: "swarm-control-plane", task_type: "infrastructure_operation", status: "pending_approval", risk_level: 3, plan_digest: "bc50ba1014ff33e68defbba9a1c727e2513d782fa1473547834d62cba1c16879", input_contract: { operation: "restart-control-plane-api" }, acceptance_criteria: ["Preflight and post-checks remain healthy."], expected_outputs: ["infrastructure evidence"], required_capabilities: ["controlled-restart"], allowed_machines: ["vm2-deployment"], max_attempts: 1 },
        review_digest: "4f197ff22b523dd4a79cf9fe4c7f8c8bbeb580160b1a8f0d3879eb3b4a08b855",
        current: true, executable: true, actionable: true, blocked_by: [], changed_fields: [], prerequisites: [], mission: null,
        authority_policy: { version: "1.0.0", manifest_digest: "a".repeat(64) }, notification: { state: "pending" }, notification_duplicates: 0, events: [],
        claim_boundary: "The approval authorizes one bounded task lease and grants no broader execution or capital authority.",
      }],
    },
    proposals: [
      {
        id: "proposal-demo",
        source_task_id: "mission-1",
        planner_agent_id: "agent-planner",
        status: "proposed",
        proposal_digest: "d24a51f4db52eb5365ac17534a2189d4d353350292efd17048e12a9c64f75561",
        created_at: now,
        proposal: {
          schema_version: 1,
          summary: "Plan a bounded Mission Control agent-profile enhancement",
          interpretation: "Expose each active role package as the authoritative task and permission envelope, then validate the dashboard without deploying production changes.",
          recommended_action: "create_task",
          assumptions: ["The signed deployment registry remains the permission source of truth."],
          clarification_questions: [],
          target_role: "Restricted VM1 engineering worker",
          target_role_reason: "The change is isolated engineering work in swarm-control-plane.",
          safety_constraints: ["No primary checkout writes.", "No remote repository write.", "Founder review precedes task creation."],
          proposed_task: {
            project: "swarm-control-plane",
            task_type: "engineering_mission",
            title: "Expand Mission Control agent profiles",
            objective: "Implement and validate complete role and permission inspection.",
            priority: 70,
            risk_level: 1,
            input_contract: { repository: "swarm-control-plane", workflow: "engineering-mission", base_ref: "main" },
            expected_outputs: ["patch", "validation logs"],
            acceptance_criteria: ["Every agent profile shows its effective signed permissions."],
            approval_policy: { kind: "automatic", risk: 1 },
            approval_required: false,
            required_capabilities: ["git", "python", "testing"],
            allowed_machines: ["vm1-developer"],
            max_attempts: 1,
          },
        },
      },
    ],
    package_deployments: [
      demoDeployment("agent-eng", "vm1-engineering-worker", "Restricted VM1 engineering worker", ["code_validation", "engineering_mission"], ["code-validation", "engineering-mission"], ["swarm-control-plane", "bulletproof_bt", "invariance_research"], 1, ["workspace"]),
      demoDeployment("23c62000-1fad-48bb-8ce5-3f4cb26f3779", "vm1-research-runner", "Restricted VM1 reproducible research runner", ["research_experiment"], ["research-experiment"], ["bulletproof_bt"], 1, ["workspace"]),
      demoDeployment("agent-infra", "vm2-infrastructure-operator", "Restricted VM2 infrastructure observer and controlled operator", ["infrastructure_observation", "infrastructure_operation"], ["infrastructure-observer", "controlled-restart"], ["swarm-control-plane"], 3, ["infrastructure-workspace"]),
    ],
    operation_summary: { counts: { running: 1, waiting_approval: 1, succeeded: 4, failed: 1 }, active_total: 2, terminal_total: 5 },
    operations: [
      { id: "op-rebuild", operation_key: "graph-rebuild:demo", kind: "knowledge_graph_rebuild", title: "Rebuild canonical knowledge graph", project: "systematic-research", machine: "vm2-deployment", owner_type: "service", owner_id: "swarm-api", state: "running", phase: "project-edges", progress_mode: "determinate", progress_current: 684210, progress_total: 1368759, progress_unit: "edges", heartbeat_at: now, started_at: new Date(Date.now() - 16 * 60_000).toISOString(), completed_at: null, cancellable: false, retryable: false, error_summary: null, links: {}, detail: {}, input_digest: null, record_digest: "b".repeat(64), created_at: now, updated_at: now },
      { id: "op-approval", operation_key: "task:demo-approval", kind: "infrastructure_operation", title: "Rotate the application database certificate", project: "invariance-research", machine: "vm2-deployment", owner_type: "task", owner_id: "demo-approval", state: "waiting_approval", phase: "approval", progress_mode: "indeterminate", progress_current: null, progress_total: null, progress_unit: null, heartbeat_at: now, started_at: null, completed_at: null, cancellable: false, retryable: false, error_summary: null, links: {}, detail: {}, input_digest: "c".repeat(64), record_digest: "d".repeat(64), created_at: now, updated_at: now },
      { id: "op-complete", operation_key: "task:demo-complete", kind: "research_experiment", title: "Validate the bounded BTC momentum hypothesis", project: "bulletproof_bt", machine: "vm1-developer", owner_type: "task", owner_id: "demo-complete", state: "succeeded", phase: "complete", progress_mode: "determinate", progress_current: 1, progress_total: 1, progress_unit: "task", heartbeat_at: now, started_at: new Date(Date.now() - 25 * 60_000).toISOString(), completed_at: now, cancellable: false, retryable: false, error_summary: null, links: {}, detail: {}, input_digest: "e".repeat(64), record_digest: "f".repeat(64), created_at: now, updated_at: now },
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

function demoDeployment(agentId, name, role, taskTypes, workflows, repositories, riskCeiling, writableRoots) {
  return {
    deployment: { agent_id: agentId, is_active: true },
    package: {
      name,
      version: "1.0.0",
      source_commit: "309b48d5d412282a3e5f12ec7c2889f7adbffe23",
      manifest_digest: "a".repeat(64),
      manifest: {
        role,
        task_types: taskTypes,
        workflows: workflows.map((workflow) => ({ name: workflow })),
        allowed_machines: [agentId === "agent-infra" ? "vm2-deployment" : "vm1-developer"],
        risk_ceiling: riskCeiling,
        permission_profile: { name: name.replaceAll("vm1-", "restricted-"), network_access: "control-plane", privileged_operations: false, writable_roots: writableRoots },
        repository_profile: { repositories, primary_checkout_write: false, remote_write: false },
      },
    },
  };
}

updateClock();
window.setInterval(updateClock, 30000);
window.setInterval(() => {
  const activeMemoryTask = (state.dashboard?.tasks || []).some(
    (task) => task.task_type === "research_memory_sync" && activeStatuses.has(task.status),
  );
  const activeOperation = Number(state.dashboard?.operation_summary?.active_total || 0) > 0;
  if (!state.demo && (activeMemoryTask || activeOperation || state.activeView === "activity")) loadDashboard();
}, 15000);
window.setInterval(() => {
  if (!state.demo && state.activeView === "work") loadConversations();
}, 10000);
loadDashboard();
