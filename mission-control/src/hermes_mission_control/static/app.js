const allowedViews = new Set(["command", "autonomy", "work", "activity", "workflows", "missions", "tasks", "proposals", "approvals", "agents", "infrastructure", "execution", "research", "knowledge", "notes", "evidence"]);
const requestedView = new URLSearchParams(window.location.search).get("view");
const allowedResearchModes = new Set(["ask", "explore", "library"]);
const requestedResearchMode = new URLSearchParams(window.location.search).get("workspace");
const requestedApproval = new URLSearchParams(window.location.search).get("approval");
const requestedWalkthrough = new URLSearchParams(window.location.search).get("walkthrough") === "1";
const requestedLibrarySource = new URLSearchParams(window.location.search).get("source");
const requestedLibraryKind = new URLSearchParams(window.location.search).get("sourceKind");
const requestedLibraryCitation = new URLSearchParams(window.location.search).get("cite");
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
  graphExtent: "global",
  graphScope: "canonical",
  graphPath: [],
  graphSelectedEdgeId: null,
  graphTransform: { scale: 1, x: 0, y: 0 },
  researchMode: allowedResearchModes.has(requestedResearchMode) ? requestedResearchMode : "ask",
  researchContext: [],
  conversations: [],
  activeConversationId: null,
  conversationWorkspace: null,
  conversationWorkspaceLoading: false,
  conversationFilter: "open",
  conversationSearch: "",
  conversationWorkEvents: [],
  conversationEventIds: new Set(),
  conversationEventCursor: null,
  conversationEventTimer: null,
  conversationPendingUpdates: 0,
  approvalView: "actionable",
  requestedApprovalOpened: false,
  executionEnvironment: "all",
  backtestPage: null,
  backtestOffset: 0,
  backtestLoading: false,
  dashboardLoading: false,
  dashboardFetchedAt: null,
  dashboardRefreshError: null,
  libraryCatalog: null,
  libraryOffset: 0,
  libraryLimit: 30,
  libraryReader: null,
  libraryListScroll: 0,
  libraryDeepLinkOpened: false,
  graphLayoutSignature: null,
  graphLayout: new Map(),
  graphDragging: false,
  overviewEventSource: null,
  overviewEventCursor: null,
  overviewReconnectAttempts: 0,
  overviewReconnectTimer: null,
  overviewPollingFallback: true,
  overviewRefreshQueued: false,
  workflows: null,
  workflowLoading: false,
  selectedWorkflowId: null,
  selectedAutonomyStage: "discover",
  agentDetail: null,
  agentDetailTab: "overview",
  agentDetailLoading: false,
  backtestDetail: null,
  venueEvents: null,
  venueEventsLoading: false,
  venueEventsError: null,
  venueEventsRequestId: 0,
  investorWalkthrough: null,
  walkthroughSession: null,
  walkthroughStartedAt: null,
  walkthroughCompletedSteps: new Set(),
  walkthroughCurrentStepId: null,
  requestedWalkthroughOpened: false,
};
restoreGraphViewState();

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
document.getElementById("open-investor-walkthrough").addEventListener("click", openInvestorWalkthrough);
document.getElementById("refresh").addEventListener("click", loadDashboard);
document.getElementById("refresh-activity").addEventListener("click", loadDashboard);
document.getElementById("refresh-workflows").addEventListener("click", () => loadWorkflows({ refresh: true }));
document.getElementById("refresh-autonomy").addEventListener("click", async () => {
  await Promise.all([loadDashboard({ silent: true }), loadWorkflows({ refresh: true, silent: true })]);
  renderAutonomy();
});
document.getElementById("agent-filter").addEventListener("input", renderAgents);
let libraryFilterTimer = null;
document.getElementById("library-filter").addEventListener("input", () => {
  window.clearTimeout(libraryFilterTimer);
  libraryFilterTimer = window.setTimeout(() => {
    state.libraryOffset = 0;
    loadLibraryCatalog();
  }, 180);
});
document.getElementById("library-kind").addEventListener("change", () => {
  state.libraryOffset = 0;
  loadLibraryCatalog();
});
document.getElementById("refresh-library").addEventListener("click", loadLibraryCatalog);
document.getElementById("library-reader-back").addEventListener("click", closeLibraryReader);
document.getElementById("library-load-more").addEventListener("click", loadNextLibraryRange);
document.getElementById("library-load-all").addEventListener("click", () => loadAllLibraryRanges());
document.getElementById("library-find-form").addEventListener("submit", findInLibraryDocument);
document.querySelectorAll("[data-library-unit]").forEach((button) => {
  button.addEventListener("click", () => switchLibraryUnit(button.dataset.libraryUnit));
});
document.getElementById("refresh-graph").addEventListener("click", loadGraph);
document.getElementById("graph-find").addEventListener("input", renderGraphFindResults);
document.getElementById("execution-environments").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-execution-environment]");
  if (!button) return;
  state.executionEnvironment = button.dataset.executionEnvironment;
  document.querySelectorAll("[data-execution-environment]").forEach((item) => {
    const active = item === button;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  loadVenueEvents();
});
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
document.getElementById("graph-path-form").addEventListener("submit", queryGraphPath);
document.getElementById("graph-clear-path").addEventListener("click", clearGraphPath);
document.getElementById("graph-scope").addEventListener("change", (event) => {
  state.graphScope = event.target.value;
  state.graphSelectedId = null;
  state.graphPath = [];
  saveGraphViewState();
  loadGraph();
});
document.querySelectorAll("[data-graph-extent]").forEach((button) => {
  button.addEventListener("click", () => {
    state.graphExtent = button.dataset.graphExtent;
    document.querySelectorAll("[data-graph-extent]").forEach((item) => {
      const active = item === button;
      item.classList.toggle("active", active);
      item.setAttribute("aria-pressed", String(active));
    });
    saveGraphViewState();
    if (state.graphExtent === "global") loadGraph();
    else if (state.graphSelectedId) queryGraphRoot(state.graphSelectedId);
  });
});
["graph-direction", "graph-depth", "graph-predicate", "graph-object-type"].forEach((id) => {
  document.getElementById(id).addEventListener("change", () => {
    saveGraphViewState();
    if (id === "graph-object-type" && state.graphData) renderGraph(state.graphData);
  });
});
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
document.getElementById("conversation-filter").addEventListener("input", (event) => {
  state.conversationSearch = event.target.value.trim().toLowerCase();
  renderConversations();
});
document.querySelectorAll("[data-conversation-filter]").forEach((button) => button.addEventListener("click", () => {
  state.conversationFilter = button.dataset.conversationFilter;
  document.querySelectorAll("[data-conversation-filter]").forEach((item) => item.setAttribute("aria-selected", String(item === button)));
  renderConversations();
}));
document.getElementById("conversation-new-events").addEventListener("click", () => {
  state.conversationPendingUpdates = 0;
  renderConversationWork({ revealLatest: true });
});
document.querySelectorAll("[data-approval-view]").forEach((button) => button.addEventListener("click", () => {
  state.approvalView = button.dataset.approvalView;
  document.querySelectorAll("[data-approval-view]").forEach((item) => item.setAttribute("aria-selected", String(item === button)));
  renderApprovals();
}));
document.getElementById("new-conversation-form").addEventListener("submit", submitConversation);
document.getElementById("walkthrough-finding-form").addEventListener("submit", submitWalkthroughFinding);
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
  const reason = String(form.get("reason") || "").trim();
  const acknowledgement = event.target.elements.digest_acknowledged;
  if (reason.length < 10) {
    showDecisionError("Enter a decision reason of at least 10 characters.");
    event.target.elements.reason.focus();
    return;
  }
  if (action === "approve" && !acknowledgement.checked) {
    showDecisionError("Confirm that you reviewed the exact digest, scope, prerequisites, and bounded effect.");
    acknowledgement.focus();
    return;
  }
  const button = document.getElementById("decision-submit");
  const idleLabel = button.textContent;
  showDecisionError("");
  button.disabled = true;
  button.textContent = action === "approve" ? "Approving…" : "Rejecting…";
  button.setAttribute("aria-busy", "true");
  try {
    await mutate(
      `/api/approvals/${form.get("approval_id")}/${action}`,
      { reason, expires_in_seconds: 900, expected_review_digest: form.get("review_digest") },
      `Approval ${action === "approve" ? "approved" : "rejected"}.`,
    );
    document.getElementById("decision-dialog").close();
    await loadDashboard();
  } catch (error) {
    showDecisionError(error.message || "The approval decision could not be recorded.");
  } finally {
    button.disabled = false;
    button.textContent = idleLabel;
    button.setAttribute("aria-busy", "false");
  }
});

document.getElementById("proposal-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  if (state.demo) return toast("Decisions are disabled in demonstration mode.");
  const form = new FormData(event.target);
  const action = form.get("action");
  const payload = { reason: form.get("reason") };
  const mandatePanel = document.getElementById("proposal-mandate-panel");
  if (action === "materialize" && !mandatePanel.hidden) {
    const mandate = alphaMandates().find((item) => item.id === form.get("mandate_id") && item.status === "active");
    if (!mandate) {
      setMandateFeedback("proposal-mandate-feedback", "Select or activate a bounded research mandate before materialization.", "error");
      return;
    }
    payload.mandate_id = mandate.id;
    payload.mandate_digest = mandate.mandate_digest;
  }
  const button = document.getElementById("proposal-submit");
  const idleLabel = button.textContent;
  button.disabled = true;
  button.textContent = action === "materialize" ? "Materializing…" : "Rejecting…";
  try {
    await mutate(
      `/api/proposals/${form.get("proposal_id")}/${action}`,
      payload,
      action === "materialize" ? "Governed task created." : "Proposal rejected.",
    );
    document.getElementById("proposal-dialog").close();
    await loadDashboard();
  } catch (error) {
    if (!mandatePanel.hidden) {
      setMandateFeedback("proposal-mandate-feedback", error.message || "Materialization could not be completed.", "error");
    } else {
      toast(error.message || "The proposal decision could not be recorded.");
    }
  } finally {
    button.disabled = false;
    button.textContent = idleLabel;
  }
});

document.getElementById("alpha-mandate-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (state.demo) return toast("Mandate preparation is disabled in demonstration mode.");
  const form = new FormData(event.target);
  await prepareAlphaMandate({
    sourceId: form.get("source_mandate_id"),
    cadence: form.get("cadence"),
    objective: form.get("objective"),
    feedbackId: "alpha-mandate-workbench-feedback",
  });
});

document.getElementById("proposal-prepare-mandate").addEventListener("click", async () => {
  if (state.demo) return toast("Mandate preparation is disabled in demonstration mode.");
  const form = document.getElementById("proposal-form");
  const prepared = await prepareAlphaMandate({
    sourceId: form.elements.mandate_source_id.value,
    cadence: form.elements.mandate_cadence.value,
    objective: form.elements.mandate_objective.value,
    feedbackId: "proposal-mandate-feedback",
  });
  if (prepared) renderProposalMandatePanel(prepared.id);
});

document.getElementById("mandate-approval-form").addEventListener("submit", async (event) => {
  if (event.submitter?.value === "cancel") return;
  event.preventDefault();
  if (state.demo) return toast("Mandate activation is disabled in demonstration mode.");
  const form = new FormData(event.target);
  const error = document.getElementById("mandate-approval-error");
  if (form.get("digest_acknowledged") !== "yes") {
    error.textContent = "Review and acknowledge the exact mandate boundary before activation.";
    error.hidden = false;
    return;
  }
  const reason = String(form.get("reason") || "").trim();
  if (reason.length < 10) {
    error.textContent = "A substantive activation rationale is required.";
    error.hidden = false;
    return;
  }
  const button = event.submitter;
  button.disabled = true;
  button.textContent = "Activating…";
  try {
    await mutate(`/api/research/alpha-discovery/mandates/${form.get("mandate_id")}/approve`, {
      expected_mandate_digest: form.get("mandate_digest"),
      reason,
    }, "No-capital research mandate activated.");
    document.getElementById("mandate-dialog").close();
    await loadDashboard();
    if (document.getElementById("proposal-dialog").open && !document.getElementById("proposal-mandate-panel").hidden) {
      renderProposalMandatePanel(form.get("mandate_id"));
    }
  } catch (requestError) {
    error.textContent = requestError.message || "The mandate could not be activated.";
    error.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "Activate mandate";
  }
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

function navigate(view, { resetScroll = true } = {}) {
  if (!allowedViews.has(view)) return;
  state.activeView = view;
  document.querySelectorAll(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  document.querySelectorAll(".view").forEach((item) => item.classList.toggle("active", item.id === view));
  document.getElementById("primary-nav").classList.remove("open");
  const url = new URL(window.location.href);
  if (view === "command") url.searchParams.delete("view");
  else url.searchParams.set("view", view);
  window.history.replaceState({}, "", url);
  if (resetScroll) window.scrollTo({ top: 0, behavior: "smooth" });
  if (view === "work" && !state.demo) loadConversations();
  if (view === "workflows" && !state.workflows) loadWorkflows();
  if (view === "autonomy") {
    if (!state.workflows) loadWorkflows();
    else renderAutonomy();
  }
  if (view === "execution" && !state.venueEvents) loadVenueEvents();
}

async function openInvestorWalkthrough() {
  const coach = document.getElementById("walkthrough-coach");
  coach.hidden = false;
  document.getElementById("walkthrough-coach-body").innerHTML = '<div class="walkthrough-loading" role="status">Loading canonical walkthrough evidence…</div>';
  if (state.demo) {
    state.investorWalkthrough = demoWalkthroughBoundary();
    renderInvestorWalkthrough();
    return;
  }
  try {
    state.investorWalkthrough = await request("/api/investor-walkthrough?refresh=true");
    renderInvestorWalkthrough();
  } catch (error) {
    document.getElementById("walkthrough-coach-body").innerHTML = `<div class="walkthrough-error" role="alert"><strong>Walkthrough evidence unavailable</strong><p>${escapeHtml(error.message)}</p><button class="secondary" type="button" data-walkthrough-retry>Retry</button><button class="text-button" type="button" data-walkthrough-close>Close</button></div>`;
    document.querySelector("[data-walkthrough-retry]").onclick = openInvestorWalkthrough;
    document.querySelector("[data-walkthrough-close]").onclick = closeInvestorWalkthrough;
  }
}

function demoWalkthroughBoundary() {
  return {
    schema_version: "mission-control-investor-walkthrough-v1",
    status: "demonstration_only",
    ready_steps: 0,
    total_steps: 5,
    steps: [],
    claim_boundary: "Demonstration mode contains illustrative UI data and cannot be used as investor rehearsal evidence. Reconnect to the canonical control plane.",
  };
}

function renderInvestorWalkthrough() {
  const projection = state.investorWalkthrough;
  const body = document.getElementById("walkthrough-coach-body");
  if (!projection) return;
  if (projection.status === "demonstration_only") {
    body.innerHTML = `<div class="walkthrough-heading"><div><p class="section-kicker">Investor walkthrough</p><h2>Canonical evidence required</h2></div><button class="icon-button" type="button" data-walkthrough-close aria-label="Close walkthrough" title="Close">×</button></div><p>${escapeHtml(projection.claim_boundary)}</p><button class="command" type="button" data-walkthrough-reconnect>Reconnect to control plane</button>`;
    body.querySelector("[data-walkthrough-close]").onclick = closeInvestorWalkthrough;
    body.querySelector("[data-walkthrough-reconnect]").onclick = () => { window.location.href = window.location.pathname; };
    return;
  }
  if (!state.walkthroughSession) {
    const steps = projection.steps || [];
    body.innerHTML = `<div class="walkthrough-heading"><div><p class="section-kicker">Investor walkthrough</p><h2>Evidence-backed system tour</h2></div><button class="icon-button" type="button" data-walkthrough-close aria-label="Close walkthrough" title="Close">×</button></div>
      <div class="walkthrough-readiness ${projection.status}"><strong>${projection.ready_steps}/${projection.total_steps} steps ready</strong><span>${projection.status === "ready" ? "A complete canonical path is available." : "Missing steps will be disclosed, never simulated."}</span></div>
      <ol class="walkthrough-preview">${steps.map((step) => `<li class="${step.status}"><span>${step.ordinal}</span><div><strong>${escapeHtml(step.title)}</strong><small>${step.status === "ready" ? `${step.evidence.length} evidence ${step.evidence.length === 1 ? "record" : "records"}` : escapeHtml(step.unavailable_reason)}</small></div></li>`).join("")}</ol>
      <p class="walkthrough-boundary">${escapeHtml(projection.claim_boundary)}</p>
      <button class="command" type="button" data-walkthrough-start>Start bounded rehearsal</button>`;
    body.querySelector("[data-walkthrough-close]").onclick = closeInvestorWalkthrough;
    body.querySelector("[data-walkthrough-start]").onclick = startInvestorWalkthrough;
    return;
  }
  const steps = projection.steps || [];
  const current = steps.find((step) => step.id === state.walkthroughCurrentStepId)
    || steps.find((step) => !state.walkthroughCompletedSteps.has(step.id));
  if (!current) {
    finishInvestorWalkthrough();
    return;
  }
  state.walkthroughCurrentStepId = current.id;
  const completed = state.walkthroughCompletedSteps.size;
  const unavailable = current.status === "unavailable";
  body.innerHTML = `<div class="walkthrough-heading"><div><p class="section-kicker">Bounded rehearsal</p><h2>Step ${current.ordinal} of ${projection.total_steps}</h2></div><button class="icon-button" type="button" data-walkthrough-close aria-label="Hide walkthrough" title="Hide">×</button></div>
    <div class="walkthrough-progress" aria-label="${completed} of ${projection.total_steps} steps completed"><span style="width:${Math.round(completed / projection.total_steps * 100)}%"></span></div>
    <section class="walkthrough-current ${current.status}"><span class="walkthrough-step-number">${current.ordinal}</span><div><h3>${escapeHtml(current.title)}</h3><p>${escapeHtml(current.prompt)}</p></div></section>
    ${unavailable ? `<div class="walkthrough-disclosure" role="status"><strong>Canonical step unavailable</strong><span>${escapeHtml(current.unavailable_reason)}</span></div>` : `<p class="walkthrough-evidence-count">${current.evidence.length} canonical evidence ${current.evidence.length === 1 ? "record" : "records"} linked</p>`}
    <div class="walkthrough-actions"><button class="secondary" type="button" data-walkthrough-open ${unavailable ? "disabled" : ""}>Open evidence</button><button class="command" type="button" data-walkthrough-complete>${unavailable ? "Acknowledge unavailable" : "Step understood"}</button></div>
    <div class="walkthrough-footer"><button class="text-button" type="button" data-walkthrough-finding>Record a finding</button><button class="text-button" type="button" data-walkthrough-end>End rehearsal</button></div>`;
  body.querySelector("[data-walkthrough-close]").onclick = closeInvestorWalkthrough;
  body.querySelector("[data-walkthrough-open]").onclick = () => openWalkthroughStep(current);
  body.querySelector("[data-walkthrough-complete]").onclick = () => completeWalkthroughStep(current);
  body.querySelector("[data-walkthrough-finding]").onclick = () => openWalkthroughFinding(current.id);
  body.querySelector("[data-walkthrough-end]").onclick = () => finishInvestorWalkthrough("abandoned");
}

async function startInvestorWalkthrough() {
  const projection = state.investorWalkthrough;
  try {
    state.walkthroughSession = await request("/api/investor-walkthrough/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        walkthrough_digest: projection.walkthrough_digest,
        ready_steps: projection.ready_steps,
        total_steps: projection.total_steps,
      }),
    });
    state.walkthroughStartedAt = performance.now();
    state.walkthroughCompletedSteps = new Set();
    state.walkthroughCurrentStepId = projection.steps[0]?.id || null;
    renderInvestorWalkthrough();
  } catch (error) {
    toast(error.message);
    await openInvestorWalkthrough();
  }
}

async function recordWalkthroughObservation(stepId, kind, note = null) {
  if (!state.walkthroughSession) return;
  await request(`/api/investor-walkthrough/sessions/${encodeURIComponent(state.walkthroughSession.id)}/observations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step_id: stepId, kind, elapsed_ms: walkthroughElapsed(), note }),
  });
}

async function openWalkthroughStep(step) {
  try {
    await recordWalkthroughObservation(step.id, "opened");
  } catch (error) {
    toast(`Rehearsal timing was not retained: ${error.message}`);
  }
  if (step.id === "command") {
    navigate("command");
  } else if (step.id === "workflow") {
    if (!state.workflows) await loadWorkflows();
    openWorkflow(step.entity_id);
  } else if (step.id === "agent") {
    navigate("agents");
    await openAgent(step.entity_id);
  } else if (step.id === "backtest") {
    navigate("research");
    openBacktest(step.entity_id);
  } else if (step.id === "venue") {
    navigate("execution");
    state.executionEnvironment = "demo";
    document.querySelectorAll("[data-execution-environment]").forEach((button) => {
      const active = button.dataset.executionEnvironment === "demo";
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    await loadVenueEvents();
    openVenueEvent(step.entity_id);
  }
}

async function completeWalkthroughStep(step) {
  try {
    await recordWalkthroughObservation(step.id, "completed", step.status === "unavailable" ? step.unavailable_reason : null);
    state.walkthroughCompletedSteps.add(step.id);
    const next = state.investorWalkthrough.steps.find((item) => !state.walkthroughCompletedSteps.has(item.id));
    state.walkthroughCurrentStepId = next?.id || null;
    renderInvestorWalkthrough();
  } catch (error) {
    toast(error.message);
  }
}

function openWalkthroughFinding(stepId) {
  const dialog = document.getElementById("walkthrough-finding-dialog");
  const form = document.getElementById("walkthrough-finding-form");
  form.reset();
  form.elements.step_id.value = stepId;
  dialog.showModal();
  window.setTimeout(() => form.elements.kind.focus(), 0);
}

async function submitWalkthroughFinding(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    await recordWalkthroughObservation(form.get("step_id"), form.get("kind"), String(form.get("note")).trim());
    document.getElementById("walkthrough-finding-dialog").close();
    toast("Rehearsal finding retained.");
  } catch (error) {
    toast(error.message);
  }
}

async function finishInvestorWalkthrough(status = "completed") {
  if (!state.walkthroughSession) return;
  try {
    await request(`/api/investor-walkthrough/sessions/${encodeURIComponent(state.walkthroughSession.id)}/finish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status,
        elapsed_ms: walkthroughElapsed(),
        summary: status === "completed" ? `${state.walkthroughCompletedSteps.size} walkthrough steps reviewed.` : "Rehearsal ended before every step was reviewed.",
      }),
    });
    toast(status === "completed" ? "Investor rehearsal retained." : "Partial rehearsal retained.");
    state.walkthroughSession = null;
    state.walkthroughStartedAt = null;
    state.walkthroughCompletedSteps = new Set();
    closeInvestorWalkthrough();
  } catch (error) {
    toast(error.message);
  }
}

function walkthroughElapsed() {
  return Math.max(0, Math.round(performance.now() - (state.walkthroughStartedAt || performance.now())));
}

function closeInvestorWalkthrough() {
  document.getElementById("walkthrough-coach").hidden = true;
}

async function loadConversations() {
  if (state.demo) return;
  try {
    state.conversations = await request("/api/conversations");
    if (state.activeConversationId && !state.conversations.some((item) => item.id === state.activeConversationId)) state.activeConversationId = null;
    const retained = window.localStorage.getItem("hermes.activeConversationId");
    if (!state.activeConversationId && retained && state.conversations.some((item) => item.id === retained)) state.activeConversationId = retained;
    if (!state.activeConversationId && state.conversations.length) state.activeConversationId = state.conversations[0].id;
    renderConversations();
    await loadConversationWorkspace();
  } catch (error) {
    toast(error.message);
  }
}

function renderConversations() {
  const list = document.getElementById("conversation-list");
  const openStates = new Set(["collecting", "planning", "needs_clarification", "ready_for_review", "attention_required"]);
  const filtered = state.conversations.filter((item) => {
    const archived = item.status === "archived";
    const stateMatch = state.conversationFilter === "all" || (state.conversationFilter === "archived" ? archived : openStates.has(item.status));
    const text = `${item.title} ${item.short_id} ${item.project || ""} ${item.working_summary || ""}`.toLowerCase();
    return stateMatch && (!state.conversationSearch || text.includes(state.conversationSearch));
  });
  list.innerHTML = filtered.length ? filtered.map((item) => `
    <button class="conversation-list-item ${item.id === state.activeConversationId ? "active" : ""}" data-conversation-id="${item.id}">
      <span>${escapeHtml(item.short_id)} · ${escapeHtml(humanize(item.status))}</span>
      <strong>${escapeHtml(item.title)}</strong>
      <small>${escapeHtml(item.project || "Unclassified")} · revision ${item.revision}</small>
    </button>`).join("") : empty("No conversation threads yet.");
  document.querySelectorAll("[data-conversation-id]").forEach((button) => button.addEventListener("click", () => {
    state.activeConversationId = button.dataset.conversationId;
    window.localStorage.setItem("hermes.activeConversationId", state.activeConversationId);
    state.conversationWorkspace = null;
    resetConversationEventStream();
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
    await loadConversationWorkEvents({ reset: true });
  } catch (error) {
    if (state.activeConversationId === conversationId) toast(error.message);
  } finally {
    if (state.activeConversationId === conversationId) {
      state.conversationWorkspaceLoading = false;
      renderConversationWork();
    }
  }
}

function resetConversationEventStream() {
  window.clearTimeout(state.conversationEventTimer);
  state.conversationWorkEvents = [];
  state.conversationEventIds = new Set();
  state.conversationEventCursor = null;
  state.conversationPendingUpdates = 0;
}

async function loadConversationWorkEvents({ reset = false } = {}) {
  const conversationId = state.activeConversationId;
  if (state.demo || !conversationId) return;
  if (reset) resetConversationEventStream();
  const query = new URLSearchParams({ limit: "250" });
  if (state.conversationEventCursor) query.set("after", state.conversationEventCursor);
  try {
    const page = await request(`/api/conversations/${conversationId}/work-events?${query}`);
    if (state.activeConversationId !== conversationId) return;
    const unseen = (page.events || []).filter((item) => !state.conversationEventIds.has(item.id));
    unseen.forEach((item) => state.conversationEventIds.add(item.id));
    state.conversationWorkEvents.push(...unseen);
    state.conversationEventCursor = page.next_cursor || state.conversationEventCursor;
    if (!reset && unseen.length) state.conversationPendingUpdates += unseen.length;
    renderConversationWork();
    document.getElementById("conversation-live-status").textContent = unseen.length ? `${unseen.length} durable work updates received.` : "Thread is current.";
  } catch (error) {
    document.getElementById("conversation-live-status").textContent = `Work updates paused: ${error.message}`;
  } finally {
    window.clearTimeout(state.conversationEventTimer);
    if (state.activeConversationId === conversationId) state.conversationEventTimer = window.setTimeout(() => loadConversationWorkEvents(), 5000);
  }
}

function renderConversationWork({ revealLatest = false } = {}) {
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
  const items = state.conversationWorkEvents.length ? state.conversationWorkEvents.map((event) => ({
    kind: event.task_id ? "task" : event.source_type === "proposal" ? "proposal" : "event",
    entityId: event.task_id || (event.source_type === "proposal" ? event.source_id : null),
    label: event.label,
    detail: event.detail,
    state: event.state,
    category: event.category,
    createdAt: event.occurred_at,
  })) : conversationTimeline(workspace);
  document.getElementById("conversation-progress-count").textContent = String(items.length);
  document.getElementById("conversation-evidence-count").textContent = String((workspace.artifacts || []).length);
  progress.innerHTML = items.length ? items.map((item) => `
    <button class="conversation-progress-item" type="button" data-event-category="${escapeHtml(item.category || "planning")}" ${item.entityId ? `data-work-${item.kind}="${escapeHtml(item.entityId)}"` : ""}>
      <span class="timeline-marker ${escapeHtml(item.state)}" aria-hidden="true"></span>
      <span><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.detail)} · ${formatDate(item.createdAt)}</small></span>
    </button>`).join("") : '<div class="conversation-work-empty">No linked execution yet.</div>';
  const updateButton = document.getElementById("conversation-new-events");
  updateButton.hidden = state.conversationPendingUpdates === 0;
  updateButton.textContent = `${state.conversationPendingUpdates} new work update${state.conversationPendingUpdates === 1 ? "" : "s"}`;
  if (revealLatest) progress.lastElementChild?.scrollIntoView({ block: "nearest", behavior: "smooth" });
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
  const submit = event.currentTarget.querySelector("button[type=submit]");
  const message = textarea.value.trim();
  if (!message) return;
  submit.disabled = true;
  submit.textContent = "Sending…";
  document.getElementById("conversation-live-status").textContent = "Founder turn is being accepted.";
  try {
    await mutate(`/api/conversations/${state.activeConversationId}/turns`, { message }, "Turn added to this thread.");
    textarea.value = "";
    await loadConversations();
  } catch (error) {
    document.getElementById("conversation-live-status").textContent = `Turn was not accepted: ${error.message}`;
    textarea.focus();
  } finally {
    submit.disabled = false;
    submit.textContent = "Send";
  }
}

async function transitionConversation(action) {
  if (state.demo || !state.activeConversationId) return;
  await mutate(`/api/conversations/${state.activeConversationId}/transitions`, { action, reason: `Founder requested ${action} in Mission Control.` }, `Thread ${action} recorded.`);
  await loadConversations();
}

function setResearchMode(mode, { focus = false } = {}) {
  if (!allowedResearchModes.has(mode)) return;
  const previousMode = state.researchMode;
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
  if (mode === "explore" && state.graphData && previousMode !== mode) renderGraph(state.graphData);
  if (mode === "library" && !state.libraryCatalog) loadLibraryCatalog();
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

async function loadDashboard({ silent = false } = {}) {
  if (state.dashboardLoading) return;
  state.dashboardLoading = true;
  if (!silent) setLoading(true);
  try {
    if (!state.demo) {
      document.getElementById("health").textContent = "Contacting control plane · freshness not yet verified";
      document.getElementById("health-dot").classList.remove("ok");
    }
    state.dashboard = state.demo ? demoDashboard() : await request("/api/dashboard?refresh=true");
    state.dashboardFetchedAt = Date.now();
    state.dashboardRefreshError = null;
    if (state.demo) loadDemoConversation();
    renderConnectionStatus();
    document.getElementById("demo-banner").hidden = !state.demo;
    if (silent) renderActiveView();
    else renderAll();
    await loadWorkflows({ silent: true });
    if (!state.demo && !state.graphData) await loadGraph();
    else if (state.demo && !state.graphData) renderGraph(state.dashboard.graph);
    if (!silent) navigate(state.activeView, { resetScroll: false });
    if (requestedWalkthrough && !state.requestedWalkthroughOpened) {
      state.requestedWalkthroughOpened = true;
      await openInvestorWalkthrough();
    }
    if (!state.demo) startOverviewEvents();
  } catch (error) {
    document.getElementById("health").textContent = "Control plane unavailable";
    document.getElementById("health-dot").classList.remove("ok");
    if (silent && state.dashboard) {
      state.dashboardRefreshError = error.message;
      renderSnapshotAge();
    } else {
      renderUnavailable();
      toast(`${error.message} Add ?demo=1 to inspect the prototype safely.`);
    }
  } finally {
    state.dashboardLoading = false;
    if (!silent) setLoading(false);
    renderSnapshotAge();
    if (state.overviewRefreshQueued && !state.demo && document.visibilityState === "visible") {
      state.overviewRefreshQueued = false;
      queueOverviewRefresh();
    }
  }
}

function startOverviewEvents() {
  if (state.demo || document.visibilityState !== "visible" || state.overviewEventSource) return;
  const query = state.overviewEventCursor ? `?cursor=${encodeURIComponent(state.overviewEventCursor)}` : "";
  const source = new EventSource(`/api/overview/events${query}`);
  state.overviewEventSource = source;
  source.onopen = () => {
    state.overviewReconnectAttempts = 0;
    state.overviewPollingFallback = false;
  };
  source.addEventListener("overview.changed", queueOverviewRefresh);
  source.addEventListener("overview.unavailable", queueOverviewRefresh);
  source.addEventListener("overview.cursor_expired", () => {
    state.overviewEventCursor = null;
    queueOverviewRefresh();
  });
  source.onerror = () => {
    if (state.overviewEventSource !== source) return;
    source.close();
    state.overviewEventSource = null;
    state.overviewPollingFallback = true;
    scheduleOverviewReconnect();
  };
}

function queueOverviewRefresh(event) {
  const eventId = event?.lastEventId;
  if (eventId) {
    const previous = Number(state.overviewEventCursor || 0);
    if (Number(eventId) <= previous) return;
    state.overviewEventCursor = eventId;
  }
  if (state.overviewRefreshQueued) return;
  if (state.dashboardLoading) {
    state.overviewRefreshQueued = true;
    return;
  }
  state.overviewRefreshQueued = true;
  window.setTimeout(async () => {
    state.overviewRefreshQueued = false;
    if (!state.demo && document.visibilityState === "visible") await loadDashboard({ silent: true });
  }, 120);
}

function scheduleOverviewReconnect() {
  if (state.demo || document.visibilityState !== "visible" || state.overviewReconnectTimer) return;
  const delay = Math.min(30_000, 1_000 * (2 ** Math.min(state.overviewReconnectAttempts++, 5)));
  state.overviewReconnectTimer = window.setTimeout(() => {
    state.overviewReconnectTimer = null;
    startOverviewEvents();
  }, delay);
}

function stopOverviewEvents() {
  if (state.overviewEventSource) state.overviewEventSource.close();
  state.overviewEventSource = null;
  if (state.overviewReconnectTimer) window.clearTimeout(state.overviewReconnectTimer);
  state.overviewReconnectTimer = null;
}

function renderAll() {
  renderCommand();
  renderAutonomy();
  renderActivity();
  renderWorkflows();
  renderMissions();
  renderTasks();
  renderProposals();
  renderApprovals();
  renderAgents();
  renderInfrastructure();
  renderExecution();
  renderResearch();
  renderNotes();
  renderArtifacts();
  renderResearchWorkspaceStatus();
  renderResearchContext();
  setResearchMode(state.researchMode);
  renderSnapshotAge();
}

function renderActiveView() {
  if (!state.dashboard) return;
  if (state.activeView === "command") {
    renderCommand();
    renderActivity();
  } else if (state.activeView === "autonomy") renderAutonomy();
  else if (state.activeView === "activity") renderActivity();
  else if (state.activeView === "workflows") renderWorkflows();
  renderSnapshotAge();
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
  const machines = machineInventory(data);
  const online = machines.filter((item) => item.presence === "online");
  const succeeded = tasks.filter((item) => item.status === "succeeded");

  document.getElementById("metrics").innerHTML = [
    metric(active.length, "Active tasks", `${tasks.length} total recorded`),
    metric(pendingApprovals.length + pendingProposals.length, "Pending decisions", (pendingApprovals.length + pendingProposals.length) ? "Founder action required" : "Queue clear"),
    metric(`${online.length}/${machines.length}`, "Online machines", "Fused probe and worker evidence"),
    metric(succeeded.length, "Verified outcomes", `${failed.length} failed preserved`),
  ].join("");

  document.getElementById("machine-strip").innerHTML = machineCells(machines);
  document.getElementById("mission-pulse").innerHTML = missionPulse(tasks);
  document.getElementById("active-execution").innerHTML = renderWorkflowFlow(state.workflows, data);
  document.querySelectorAll("[data-operation-id]").forEach((button) => {
    button.onclick = () => openOperation(button.dataset.operationId);
  });
  document.querySelectorAll("[data-workflow-id]").forEach((button) => {
    button.onclick = () => openWorkflow(button.dataset.workflowId);
  });
  document.getElementById("fleet-summary").innerHTML = fleetRows(machines);
  renderCommandVenues(data.execution_telemetry);
  document.getElementById("recent-proof").innerHTML = proofRows(tasks, data.artifacts || []);
  renderAttention();
  renderControls();
  renderCodexAuth();
}

async function loadWorkflows({ refresh = false, silent = false } = {}) {
  if (state.workflowLoading) return;
  state.workflowLoading = true;
  try {
    state.workflows = state.demo ? demoWorkflowProjection() : await request(`/api/workflows${refresh ? "?refresh=true" : ""}`);
    const items = state.workflows?.items || [];
    if (!items.some((item) => item.instance_id === state.selectedWorkflowId)) {
      state.selectedWorkflowId = items[0]?.instance_id || null;
    }
    if (!silent || state.activeView === "workflows") renderWorkflows();
    if (state.activeView === "command") renderCommand();
    if (state.activeView === "autonomy") renderAutonomy();
  } catch (error) {
    if (!silent) toast(error.message);
  } finally {
    state.workflowLoading = false;
  }
}

function renderWorkflows() {
  const projection = state.workflows;
  const items = projection?.items || [];
  const running = items.filter((item) => item.state === "running");
  const attention = items.filter((item) => ["blocked", "stalled", "waiting_approval"].includes(item.state));
  const terminal = items.filter((item) => ["succeeded", "failed", "cancelled"].includes(item.state));
  document.getElementById("workflow-summary").innerHTML = [
    metric(running.length, "Running leaves", "Observed leaf work only"),
    metric(attention.length, "Needs attention", "Blocker, stale heartbeat, or approval"),
    metric(items.filter((item) => item.native_backtest?.state === "running").length, "Native backtests", "Live execute-stage leaves"),
    metric(terminal.length, "Terminal instances", "Outcome retained with evidence"),
  ].join("");
  document.getElementById("workflow-count").textContent = items.length;
  document.getElementById("workflow-list").innerHTML = items.length ? items.map((item) => workflowListItem(item)).join("") : empty("No workflow instances have been projected yet.");
  document.querySelectorAll("[data-workflow-id]").forEach((button) => {
    button.onclick = () => openWorkflow(button.dataset.workflowId);
  });
  const selected = items.find((item) => item.instance_id === state.selectedWorkflowId);
  document.getElementById("workflow-detail").innerHTML = selected ? workflowDetail(selected) : empty("Select a workflow instance to inspect its stage, owner, blocker, and evidence.");
}

function openWorkflow(instanceId) {
  state.selectedWorkflowId = instanceId;
  if (state.activeView !== "workflows") navigate("workflows");
  renderWorkflows();
}

function workflowListItem(item) {
  const selected = item.instance_id === state.selectedWorkflowId;
  const leaf = item.current_leaf;
  const detail = leaf ? `${humanize(leaf.phase || leaf.state)} · ${relativeTime(leaf.heartbeat_at)}` : nextWorkflowAction(item);
  return `<button class="workflow-list-item ${selected ? "active" : ""}" data-workflow-id="${escapeHtml(item.instance_id)}" aria-pressed="${selected}">
    <span class="workflow-list-top"><span class="workflow-kind">${escapeHtml(humanize(item.workflow?.name))}</span>${statusBadge(item.state)}</span>
    <strong>${escapeHtml(item.title)}</strong>
    <span>${escapeHtml(item.machine || "Machine unreported")} · ${escapeHtml(detail)}</span>
  </button>`;
}

function workflowDetail(item) {
  const leaf = item.current_leaf;
  const stages = item.stages || [];
  const blockers = item.blockers || [];
  const sourceEvents = item.source_event_ids || [];
  return `<header class="workflow-detail-heading">
      <div><p class="section-kicker">${escapeHtml(humanize(item.instance_kind))}</p><h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.workflow?.name || "Unknown workflow")}${item.workflow?.version ? ` · v${escapeHtml(item.workflow.version)}` : ""}</p></div>
      ${statusBadge(item.state)}
    </header>
    <section class="workflow-stage-map" aria-label="Workflow stage map">
      ${stages.map((stage, index) => `<div class="workflow-stage ${stage.state === "running" ? "active" : ""} ${stage.state === "not_running" ? "inactive" : ""}"><span>${index + 1}</span><strong>${escapeHtml(humanize(stage.name))}</strong><small>${escapeHtml(humanize(stage.state))}</small></div>`).join('<i aria-hidden="true"></i>')}
    </section>
    <dl class="workflow-facts">
      <dt>Current leaf</dt><dd>${leaf ? `${escapeHtml(humanize(leaf.kind))} · ${escapeHtml(leaf.id)}` : "No live leaf run"}</dd>
      <dt>Owner</dt><dd>${escapeHtml(item.owner?.id || item.owner?.type || "Unreported")}</dd>
      <dt>Machine</dt><dd>${escapeHtml(item.machine || "Unreported")}</dd>
      <dt>Heartbeat</dt><dd>${leaf?.heartbeat_at ? `${escapeHtml(relativeTime(leaf.heartbeat_at))} · ${escapeHtml(formatDate(leaf.heartbeat_at))}` : "No live heartbeat"}</dd>
      <dt>Next action</dt><dd>${escapeHtml(nextWorkflowAction(item))}</dd>
      <dt>Native backtest</dt><dd>${item.native_backtest ? escapeHtml(humanize(item.native_backtest.state)) : "Not applicable"}</dd>
      <dt>Terminal outcome</dt><dd>${item.terminal_outcome ? escapeHtml(humanize(item.terminal_outcome)) : "Not terminal"}</dd>
    </dl>
    <section class="workflow-evidence"><div><p class="section-kicker">Evidence</p><h3>Bound to source records</h3></div>
      <p>Entry ${escapeHtml(shortHash(item.entry_evidence?.digest))} · Exit ${escapeHtml(shortHash(item.exit_evidence?.digest))}</p>
      <p>${sourceEvents.length ? `${sourceEvents.length} source event ${sourceEvents.length === 1 ? "ID" : "IDs"} recorded` : "No source event IDs supplied by the canonical record"}</p>
    </section>
    ${blockers.length ? `<section class="workflow-blockers"><p class="section-kicker">Blockers</p>${blockers.map((blocker) => `<p>${escapeHtml(blocker)}</p>`).join("")}</section>` : ""}`;
}

function nextWorkflowAction(item) {
  if (item.state === "waiting_approval") return "Founder approval required";
  if (item.state === "blocked") return "Resolve the recorded blocker";
  if (item.state === "stalled") return "Inspect heartbeat and recover safely";
  if (item.state === "queued") return "Await governed lease";
  if (item.state === "running") return "Await current execution evidence";
  if (["succeeded", "failed", "cancelled"].includes(item.state)) return "Inspect terminal evidence";
  return "Await canonical state";
}

function renderWorkflowFlow(projection, data) {
  const items = projection?.items || [];
  if (!items.length) return renderLiveFlow(data);
  const stages = [
    { label: "Queued", states: ["queued"] },
    { label: "In progress", states: ["running"] },
    { label: "Waiting", states: ["waiting_approval", "blocked"] },
    { label: "Needs attention", states: ["stalled"] },
    { label: "Terminal", states: ["succeeded", "failed", "cancelled"] },
  ];
  return `<div class="live-flow-scroll"><div class="live-flow-map" aria-label="Workflow stages">${stages.map((stage) => {
    const matches = items.filter((item) => stage.states.includes(item.state));
    return `<section class="live-flow-stage ${stage.states.includes("running") ? "stage-running" : ""}"><div class="live-flow-stage-heading"><h3>${escapeHtml(stage.label)}</h3><span>${matches.length}</span></div>${matches.length ? matches.slice(0, 4).map((item) => `<button class="live-flow-node" data-workflow-id="${escapeHtml(item.instance_id)}"><span class="live-node-top"><span class="live-node-phase">${escapeHtml(humanize(item.workflow?.name))}</span>${statusBadge(item.state)}</span><strong class="live-node-label">${escapeHtml(item.title)}</strong><span class="live-node-meta">${escapeHtml(item.machine || "Machine unreported")} · ${escapeHtml(item.current_leaf?.phase || nextWorkflowAction(item))}</span></button>`).join("") : '<p class="stage-empty">No instances</p>'}</section>`;
  }).join('<span class="flow-connector" aria-hidden="true"></span>')}</div></div>`;
}

function renderCodexAuth() {
  const container = document.getElementById("codex-auth-recovery");
  const recoveries = state.dashboard?.codex_auth_recoveries || [];
  if (!recoveries.length) {
    container.innerHTML = empty("The shared Codex runtime has not reported yet.");
    return;
  }
  container.innerHTML = recoveries.map((item) => {
    const needsLogin = item.state !== "healthy";
    const code = item.device_code
      ? `<p class="mono">${escapeHtml(item.device_code)}</p><p class="muted">Expires ${formatDate(item.code_expires_at)}</p>`
      : "";
    return `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(humanize(item.runtime_key))}</strong><div class="entity-meta"><span>Attempt ${item.generation}</span><span>Probe ${relativeTime(item.last_probe_at)}</span></div>${code}<p>${escapeHtml(item.failure_summary || "Real Codex probe passed.")}</p></div><div class="entity-side">${statusBadge(item.state)}${needsLogin ? `<button class="secondary compact" data-codex-auth-retry="${item.id}">New code</button>` : ""}${item.verification_uri ? `<a class="button-link" href="${escapeHtml(item.verification_uri)}" target="_blank" rel="noreferrer">Sign in</a>` : ""}</div></article>`;
  }).join("");
  container.querySelectorAll("[data-codex-auth-retry]").forEach((button) => {
    button.addEventListener("click", async () => {
      if (state.demo) return toast("Actions are disabled in demonstration mode.");
      await mutate(
        `/api/codex-auth/recoveries/${button.dataset.codexAuthRetry}/retry`,
        { reason: "Founder requested a replacement Codex device code in Mission Control." },
        "Replacement Codex device code requested."
      );
      await loadDashboard();
    });
  });
}

function metric(value, label, context) {
  return `<div class="metric"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span><small>${escapeHtml(context)}</small></div>`;
}

function machineCells(machines) {
  return machines.map((machine) => {
    return `<div class="machine-cell">
      <span class="machine-symbol">${machine.symbol}</span>
      <div><strong>${escapeHtml(machine.label)} · ${escapeHtml(machine.role)}</strong><small><span>${machine.registeredAgents} registered · ${machine.onlineAgents} active</span><span>Telemetry ${escapeHtml(machine.telemetryStatus)}</span></small></div>
      ${statusBadge(machine.presence)}
    </div>`;
  }).join("");
}

function machineProfile(machine) {
  const value = String(machine || "").toLowerCase();
  if (value.includes("vm1")) return { order: 10, label: "VM1", role: "Engineering", symbol: "V1" };
  if (value.includes("vm2")) return { order: 20, label: "VM2", role: "Control plane", symbol: "V2" };
  if (value.includes("exec1")) return { order: 30, label: "EXEC1", role: "Independent watchdog", symbol: "E1" };
  if (value.includes("exec2")) return { order: 40, label: "EXEC2", role: "Lagos execution", symbol: "E2" };
  if (value.includes("mac")) return { order: 50, label: "Mac", role: "Founder control", symbol: "MC" };
  return { order: 45, label: humanize(machine), role: "Fleet host", symbol: String(machine || "??").slice(0, 2).toUpperCase() };
}

function machineInventory(data) {
  const inventory = new Map();
  (data.fleet_health?.machines || []).forEach((machine) => {
    inventory.set(machine.machine, {
      ...machineProfile(machine.machine),
      key: machine.machine,
      presence: machine.presence || "offline",
      health: machine.status || "unknown",
      telemetryStatus: machine.telemetry_status || "unknown",
      lastObservedAt: machine.last_observed_at,
      registeredAgents: machine.registered_agents || 0,
      onlineAgents: machine.online_agents || 0,
      agentCountsAuthoritative: machine.registered_agents != null,
      incidents: machine.incidents || [],
    });
  });
  (data.agents || []).forEach((agent) => {
    const hasFleetRecord = inventory.has(agent.machine);
    const current = inventory.get(agent.machine) || {
      ...machineProfile(agent.machine), key: agent.machine, presence: "offline", health: "unknown",
      telemetryStatus: "missing", lastObservedAt: null, registeredAgents: 0, onlineAgents: 0, incidents: [],
    };
    if (!hasFleetRecord || !current.agentCountsAuthoritative) current.registeredAgents = (data.agents || []).filter((item) => item.machine === agent.machine).length;
    if (agentStatus(agent) === "online") {
      current.presence = "online";
      if (!hasFleetRecord || !current.agentCountsAuthoritative) current.onlineAgents += 1;
    } else if (current.presence === "offline" && agentStatus(agent) === "degraded") {
      current.presence = "degraded";
    }
    inventory.set(agent.machine, current);
  });
  const local = data.mission_control;
  if (local?.machine) {
    inventory.set(local.machine, {
      ...machineProfile(local.machine), key: local.machine, label: local.display_name || "Mac",
      role: local.role || "Founder control", presence: local.presence || "online", health: "healthy",
      telemetryStatus: "local", lastObservedAt: local.observed_at, registeredAgents: 1, onlineAgents: 1, incidents: [],
    });
  }
  return [...inventory.values()].sort((left, right) => left.order - right.order || left.label.localeCompare(right.label));
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

function renderLiveFlow(data) {
  const activeStates = new Set(["queued", "waiting_approval", "running", "blocked", "stalled"]);
  const operations = data.operations || [];
  const tasks = data.tasks || [];
  const operationStages = [
    { label: "Queued", states: ["queued"] },
    { label: "In progress", states: ["running"] },
    { label: "Waiting", states: ["waiting_approval", "blocked"] },
    { label: "Needs attention", states: ["stalled"] },
  ];
  if (operations.length) {
    const columns = operationStages.map((stage) => {
      const items = operations.filter((item) => stage.states.includes(item.state));
      return `<section class="live-flow-stage ${stage.states.includes("running") ? "stage-running" : ""}">
        <div class="live-flow-stage-heading"><h3>${escapeHtml(stage.label)}</h3><span>${items.length}</span></div>
        ${items.length ? items.slice(0, 4).map((item) => liveOperationNode(item, data.agents || [])).join("") : '<p class="stage-empty">No processes</p>'}
      </section>`;
    });
    const finished = operations.filter((item) => !activeStates.has(item.state)).slice(0, 3);
    columns.push(`<section class="live-flow-stage stage-terminal"><div class="live-flow-stage-heading"><h3>Recently finished</h3><span>${finished.length}</span></div>${finished.map((item) => liveOperationNode(item, data.agents || [])).join("") || '<p class="stage-empty">No recent receipts</p>'}</section>`);
    return `<div class="live-flow-scroll"><div class="live-flow-map" aria-label="Current operation stages">${columns.join('<span class="flow-connector" aria-hidden="true"></span>')}</div></div>`;
  }
  const stages = [
    { label: "Queued", states: ["queued", "pending_approval"] },
    { label: "Leased", states: ["leased"] },
    { label: "Running", states: ["running"] },
    { label: "Complete", states: ["succeeded", "failed", "released"] },
  ];
  return `<div class="live-flow-scroll"><div class="live-flow-map task-flow-map">${stages.map((stage) => {
    const items = tasks.filter((task) => stage.states.includes(task.status)).slice(0, 3);
    return `<section class="live-flow-stage"><div class="live-flow-stage-heading"><h3>${escapeHtml(stage.label)}</h3><span>${tasks.filter((task) => stage.states.includes(task.status)).length}</span></div>${items.map((task) => `<button class="live-flow-node" data-task-id="${task.id}"><span class="live-node-label">${escapeHtml(task.title)}</span><span class="live-node-meta">${escapeHtml(task.task_number)} · ${escapeHtml(humanize(task.status))}</span></button>`).join("") || '<p class="stage-empty">No tasks</p>'}</section>`;
  }).join('<span class="flow-connector" aria-hidden="true"></span>')}</div></div>`;
}

function liveOperationNode(operation, agents) {
  const agent = agents.find((item) => String(item.id) === String(operation.owner_id) || item.slug === operation.owner_id);
  const determinate = operation.progress_mode === "determinate" && Number(operation.progress_total) > 0;
  const progress = determinate ? Math.max(0, Math.min(100, Math.round(operation.progress_current / operation.progress_total * 100))) : null;
  return `<button class="live-flow-node" type="button" data-operation-id="${escapeHtml(operation.id)}">
    <span class="live-node-top"><span class="live-node-phase">${escapeHtml(humanize(operation.phase || operation.kind))}</span>${statusBadge(operation.state)}</span>
    <strong class="live-node-label">${escapeHtml(operation.title)}</strong>
    <span class="live-node-meta">${escapeHtml(operation.machine || "Machine unreported")} · ${escapeHtml(agent?.display_name || operation.owner_id || operation.owner_type || "Service")}</span>
    ${progress !== null ? `<span class="live-node-progress"><span style="width:${progress}%"></span></span><span class="live-node-meta">${progress}% · ${operation.progress_current}/${operation.progress_total} ${escapeHtml(operation.progress_unit || "")}</span>` : ""}
    <span class="live-node-meta">Heartbeat ${relativeTime(operation.heartbeat_at)}</span>
  </button>`;
}

function fleetRows(machines) {
  if (!machines.length) return empty("No registered machines.");
  return machines.map((machine) => `<article class="entity-row">
    <div class="entity-primary"><strong>${escapeHtml(machine.label)} · ${escapeHtml(machine.role)}</strong><div class="entity-meta"><span class="mono">${escapeHtml(machine.key)}</span><span>${machine.registeredAgents} registered agents</span><span>${machine.incidents.length} active incidents</span><span>Last evidence ${relativeTime(machine.lastObservedAt)}</span></div></div>
    <div class="entity-side">${statusBadge(machine.presence)}${machine.telemetryStatus === "stale" ? statusBadge("telemetry stale") : ""}</div>
  </article>`).join("");
}

function renderCommandVenues(telemetry = {}) {
  const venues = telemetry.venues || [];
  const episodes = venues.reduce((total, item) => total + Number(item.projection?.trade_episodes?.length || 0), 0);
  const incidents = venues.reduce((total, item) => total + Number(item.projection?.incidents?.length || 0), 0);
  document.getElementById("command-venue-summary").innerHTML = [
    metric(venues.length, "Venue accounts", "Canonical replay only"),
    metric(venues.filter((item) => item.status === "current").length, "Current", "Digest-bound projections"),
    metric(episodes, "Trade episodes", "Backtest-compatible replay"),
    metric(incidents, "Incidents", "Reconciliation and integrity"),
  ].join("");
  document.getElementById("command-venues").innerHTML = venues.length ? venues.slice(0, 4).map((item) => `<article class="entity-row">
    <div class="entity-primary"><strong>${escapeHtml(item.venue)} · ${escapeHtml(item.environment)}</strong><div class="entity-meta"><span>${escapeHtml(item.account_pseudonym)}</span><span>${item.projection?.event_count || 0} events</span><span>Observed ${relativeTime(item.observed_at)}</span><span class="mono">${shortHash(item.projection_digest)}</span></div></div>
    <div class="entity-side">${statusBadge(item.status)}</div>
  </article>`).join("") : empty("No canonical venue replay has been published.");
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
  machineInventory(data).filter((machine) => machine.presence === "offline").slice(0, 2).forEach((machine) => {
    items.push({ severity: "critical", title: `${machine.label} offline`, detail: machine.key, machine });
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
      else if (item.machine) navigate("infrastructure");
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
  const autonomyScope = scopes.find((scope) => scope.scope_type === "workflow" && scope.scope_key === "autonomous-research");
  const paused = Boolean(autonomyScope?.is_paused);
  const heroContext = paused
    ? "Drain paused: no new work starts; active work may finish."
    : "Discovering, engineering, testing, and retaining evidence under bounded authority.";
  document.getElementById("autonomy-hero-title").textContent = paused ? "Research admission is paused" : "Research loop is active";
  document.getElementById("autonomy-hero-context").textContent = heroContext;
  document.getElementById("autonomy-hero").classList.toggle("is-paused", paused);
  document.getElementById("autonomy-hero-control").innerHTML = autonomyControlButton(paused);
  bindAutonomyControl(document.getElementById("autonomy-hero-control"));

  const scopeRows = scopes.length ? scopes.map((scope) => `
    <div class="control-row"><div><strong>${escapeHtml(scope.scope_type)} · ${escapeHtml(scope.scope_key)}</strong><div class="entity-meta">${escapeHtml(scope.reason || "No restriction")}</div></div>${statusBadge(scope.is_paused ? "paused" : "active")}</div>
  `).join("") : "";
  const container = document.getElementById("controls");
  container.innerHTML = scopeRows || empty("No granular control scopes are registered.");
}

function autonomyControlButton(paused) {
  return `${statusBadge(paused ? "paused" : "active")}<button class="${paused ? "secondary" : "danger"} compact" type="button" data-autonomy-control="${paused ? "resume" : "pause"}">${paused ? "Resume" : "Pause"}</button>`;
}

function bindAutonomyControl(container) {
  container?.querySelector("[data-autonomy-control]")?.addEventListener("click", async (event) => {
    if (state.demo) return toast("Actions are disabled in demonstration mode.");
    const action = event.currentTarget.dataset.autonomyControl;
    const explanation = action === "pause"
      ? "Pause new autonomous work after allowing active work to finish."
      : "Resume governed autonomous research admission.";
    const reason = window.prompt(`${explanation}\n\nReason:`);
    if (!reason || reason.trim().length < 10) return toast("A reason of at least 10 characters is required.");
    await mutate(
      `/api/control/${action}`,
      { scope_type: "workflow", scope_key: "autonomous-research", reason: reason.trim() },
      action === "pause" ? "Autonomous research is draining." : "Autonomous research resumed."
    );
    await loadDashboard();
  });
}

const autonomyStageDefinitions = [
  { id: "discover", step: "01", label: "Discover", detail: "Literature, prior failures, market observations, and portfolio gaps become predictive questions.", match: /discover|question|mandate|senior.research|research.intelligence|hypothesis.intake/i, agents: /director|senior.research|discovery|intelligence/i },
  { id: "synthesize", step: "02", label: "Synthesize", detail: "The senior researcher challenges novelty, predictive meaning, and falsifiability before compute is spent.", match: /synthes|senior.research|predictive|falsif|research.brief/i, agents: /senior.research|research.intelligence|director/i },
  { id: "represent", step: "03", label: "Represent", detail: "Point-in-time data availability, universe, transformation, timeframe, and eligibility are selected.", match: /represent|dataset|data.feasib|resampl|universe|availability|scientific.assurance/i, agents: /data|represent|scientific|research/i },
  { id: "specify", step: "04", label: "Specify", detail: "A falsifiable hypothesis becomes a typed strategy intent and bounded native implementation.", match: /strateg|engineer|specif|compile|scaffold|implement/i, agents: /engineer|coder|strategy/i },
  { id: "review", step: "05", label: "Challenge", detail: "Independent evaluators test causal timing, leakage, implementation semantics, and reproducibility.", match: /review|causal|leakage|evaluator|qualif/i, agents: /review|causal|evaluator|critic/i },
  { id: "execute", step: "06", label: "Test", detail: "Bulletproof runs bounded variants, walk-forward evaluation, costs, and selection-bias checks.", match: /backtest|bulletproof|execut|trial|walk.forward|cost.stress/i, agents: /executor|capacity|bulletproof|worker/i },
  { id: "retain", step: "07", label: "Retain", detail: "Positive, negative, invalid, and failed outcomes receive immutable BT-009 evidence and enter memory.", match: /bt.?009|retain|memory|terminal|publish|outcome/i, agents: /memory|publisher|director|executor/i },
  { id: "admit", step: "08", label: "Promote", detail: "Only candidates that survive every preregistered gate may enter prospective shadow monitoring.", match: /shadow|admission|promot|candidate|risk.?004/i, agents: /risk|shadow|admission|monitor/i },
];

function renderAutonomy() {
  if (!state.dashboard) return;
  const workflows = state.workflows?.items || [];
  const scopes = state.dashboard.control_scopes || [];
  const paused = Boolean(scopes.find((scope) => scope.scope_type === "workflow" && scope.scope_key === "autonomous-research")?.is_paused);
  const activeStates = new Set(["queued", "running", "waiting_approval", "blocked", "stalled"]);
  const active = workflows.filter((item) => activeStates.has(item.state));
  const native = workflows.filter((item) => item.native_backtest?.state === "running");
  const terminal = workflows.filter((item) => ["succeeded", "failed", "cancelled"].includes(item.state));
  const alpha = state.dashboard.alpha_discovery || {};
  const cycles = alpha.cycles || state.dashboard.research_cycles || [];
  const campaigns = state.dashboard.alpha_campaigns || [];

  document.getElementById("autonomy-state-title").textContent = paused ? "Admission paused; active work is draining" : "The governed research loop is active";
  document.getElementById("autonomy-state-context").textContent = paused
    ? "No new autonomous work may start. Existing leases retain their bounded authority until completion."
    : "Live records move through discovery, representation, engineering, independent challenge, testing, retention, and admission.";
  document.getElementById("autonomy-page-control").innerHTML = autonomyControlButton(paused);
  bindAutonomyControl(document.getElementById("autonomy-page-control"));
  document.getElementById("autonomy-snapshot-age").textContent = document.getElementById("snapshot-age")?.textContent || "Live state";
  document.getElementById("autonomy-metrics").innerHTML = [
    autonomyMetric(active.length, "active workflow leaves"),
    autonomyMetric(cycles.filter((item) => !["completed", "failed", "cancelled"].includes(item.status)).length, "questions in motion"),
    autonomyMetric(native.length, "native backtests running"),
    autonomyMetric(terminal.length, "retained outcomes"),
  ].join("");

  const stageModels = autonomyStageDefinitions.map((definition) => autonomyStageModel(definition, workflows, cycles, campaigns));
  document.getElementById("autonomy-canvas").innerHTML = `<div class="autonomy-flow">${stageModels.map((stage, index) => `${autonomyStageNode(stage)}${index < stageModels.length - 1 ? autonomyConnector(stage) : ""}`).join("")}</div><div class="autonomy-feedback" aria-label="Retained outcomes inform the next discovery cycle"><span aria-hidden="true">↶</span><strong>Learning loop</strong><small>Every terminal result updates novelty, failure memory, and the next question.</small></div>`;
  bindAutonomyStageControls();
  renderAutonomyInspector(stageModels);
  renderAutonomyAgents();
}

function autonomyMetric(value, label) {
  return `<div><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`;
}

function autonomyStageModel(definition, workflows, cycles, campaigns) {
  const matches = workflows.filter((item) => definition.match.test(autonomyWorkflowText(item)));
  const live = matches.filter((item) => ["queued", "running", "waiting_approval", "blocked", "stalled"].includes(item.state));
  let observedCount = matches.length;
  if (definition.id === "discover") observedCount += cycles.length;
  if (definition.id === "execute") observedCount += campaigns.filter((item) => Number(item.trial_count || 0) > 0).length;
  const stateName = live.some((item) => item.state === "stalled" || item.state === "blocked")
    ? "attention"
    : live.length
      ? "active"
      : matches.some((item) => item.state === "succeeded")
        ? "complete"
        : observedCount
          ? "observed"
          : "idle";
  return { ...definition, matches, live, observedCount, state: stateName };
}

function autonomyWorkflowText(item) {
  return [item.title, item.instance_kind, item.workflow?.name, item.current_leaf?.kind, item.current_leaf?.phase, item.next_action, ...(item.stages || []).map((stage) => stage.name)].filter(Boolean).join(" ");
}

function autonomyStageNode(stage) {
  const selected = stage.id === state.selectedAutonomyStage;
  return `<button class="autonomy-stage stage-${stage.state} ${selected ? "selected" : ""}" type="button" data-autonomy-stage="${stage.id}" aria-pressed="${selected}">
    <span class="autonomy-stage-number">${stage.step}</span>
    <span class="autonomy-stage-state"><i aria-hidden="true"></i>${escapeHtml(humanize(stage.state))}</span>
    <strong>${escapeHtml(stage.label)}</strong>
    <small>${escapeHtml(stage.detail)}</small>
    <span class="autonomy-stage-count">${stage.live.length ? `${stage.live.length} live` : `${stage.observedCount} observed`}</span>
  </button>`;
}

function autonomyConnector(stage) {
  const active = stage.state === "active";
  return `<span class="autonomy-connector ${active ? "is-live" : ""}" aria-hidden="true"><i></i></span>`;
}

function bindAutonomyStageControls() {
  document.querySelectorAll("[data-autonomy-stage]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selectedAutonomyStage = button.dataset.autonomyStage;
      renderAutonomy();
      document.getElementById("autonomy-inspector")?.focus({ preventScroll: true });
    });
  });
}

function renderAutonomyInspector(stageModels) {
  const stage = stageModels.find((item) => item.id === state.selectedAutonomyStage) || stageModels[0];
  const agents = autonomyAgentsFor(stage);
  const records = stage.matches.slice(0, 5);
  const container = document.getElementById("autonomy-inspector");
  container.tabIndex = -1;
  container.innerHTML = `<div class="autonomy-inspector-heading"><span>${escapeHtml(stage.step)}</span><div><p class="section-kicker">Selected stage</p><h2>${escapeHtml(stage.label)}</h2></div>${statusBadge(stage.state)}</div>
    <p class="autonomy-inspector-detail">${escapeHtml(stage.detail)}</p>
    <section><h3>Observed work</h3>${records.length ? records.map((item) => `<button class="autonomy-record" type="button" data-workflow-id="${escapeHtml(item.instance_id)}"><span>${escapeHtml(item.title)}</span><small>${escapeHtml(item.current_leaf?.phase || nextWorkflowAction(item))}</small>${statusBadge(item.state)}</button>`).join("") : '<p class="muted">No canonical workflow record is currently bound to this stage.</p>'}</section>
    <section><h3>Agents in range</h3>${agents.length ? agents.slice(0, 4).map((agent) => `<button class="autonomy-agent-row" type="button" data-agent-id="${escapeHtml(agent.id)}">${agentBot(agent, "small")}<span><strong>${escapeHtml(agent.display_name || agent.slug)}</strong><small>${escapeHtml(agent.role || agent.hermes_profile || "Governed specialist")}</small></span>${statusBadge(agentStatus(agent))}</button>`).join("") : '<p class="muted">No registered agent role currently matches this stage.</p>'}</section>`;
  container.querySelectorAll("[data-workflow-id]").forEach((button) => { button.onclick = () => openWorkflow(button.dataset.workflowId); });
  container.querySelectorAll("[data-agent-id]").forEach((button) => { button.onclick = () => openAgent(button.dataset.agentId); });
}

function autonomyAgentsFor(stage) {
  return (state.dashboard.agents || []).filter((agent) => stage.agents.test([agent.slug, agent.display_name, agent.role, agent.hermes_profile, ...(agent.capabilities || [])].filter(Boolean).join(" ")));
}

function renderAutonomyAgents() {
  const seen = new Set();
  const agents = autonomyStageDefinitions.flatMap((stage) => autonomyAgentsFor(stage)).filter((agent) => {
    if (seen.has(agent.id)) return false;
    seen.add(agent.id);
    return true;
  });
  document.getElementById("autonomy-agents").innerHTML = agents.length ? agents.slice(0, 10).map((agent) => `<button class="autonomy-agent-chip" type="button" data-agent-id="${escapeHtml(agent.id)}">${agentBot(agent, "medium")}<span><strong>${escapeHtml(agent.display_name || agent.slug)}</strong><small>${escapeHtml(agent.machine || "Machine unreported")}</small></span>${statusBadge(agentStatus(agent))}</button>`).join("") : empty("No research-loop agent bindings are visible in the current snapshot.");
  document.querySelectorAll("#autonomy-agents [data-agent-id]").forEach((button) => { button.onclick = () => openAgent(button.dataset.agentId); });
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
  const allItems = center.items || [];
  const classifyApproval = (item) => {
    const status = item.approval.status;
    if (status === "expired") return "expired";
    if (["approved", "rejected", "consumed", "revoked"].includes(status)) return "decided";
    if (!item.current || (item.changed_fields || []).length) return "superseded";
    return item.actionable ? "actionable" : "blocked";
  };
  const items = state.approvalView === "all" ? allItems : allItems.filter((item) => classifyApproval(item) === state.approvalView);
  const counts = center.counts || {};
  document.getElementById("approval-summary").innerHTML = [
    metric(counts.actionable || 0, "Ready", "Current and executable"),
    metric(counts.blocked || 0, "Blocked", "Prerequisite or state mismatch"),
    metric(counts.decided || 0, "Decided", "Receipts retained"),
  ].join("");
  document.getElementById("approval-list").innerHTML = items.length ? items.map((item) => {
    const approval = item.approval;
    const task = item.task || {};
    const canResend = task.approval_required && ["pending_approval", "queued"].includes(task.status) && ["pending", "expired"].includes(approval.status);
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
      <div class="approval-actions"><a class="secondary button-link" href="?view=approvals&amp;approval=${encodeURIComponent(approval.id)}">Review link</a>${canResend ? `<button class="secondary" data-resend-approval="${task.id}">${approval.status === "expired" ? "Reissue review" : "Resend to Telegram"}</button>` : ""}${approval.status === "pending" ? `<button class="secondary danger" data-decision="reject" data-id="${approval.id}">Reject</button><button class="command" data-decision="approve" data-id="${approval.id}" ${item.actionable ? "" : "disabled"}>Review & approve</button>` : `<button class="secondary" data-decision="review" data-id="${approval.id}">View receipt</button>`}</div>
    </article>`;
  }).join("") : empty("No approval gates recorded.");
  document.querySelectorAll("[data-decision]").forEach((button) => {
    button.addEventListener("click", () => openDecision(button.dataset.id, button.dataset.decision));
  });
  document.querySelectorAll("[data-resend-approval]").forEach((button) => {
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await mutate(
          `/api/tasks/${button.dataset.resendApproval}/resend-approval`,
          { reason: "Founder requested a fresh approval review link from Mission Control." },
          "A fresh Telegram approval link was queued.",
        );
        await loadDashboard();
      } finally {
        button.disabled = false;
      }
    });
  });
  if (requestedApproval && !state.requestedApprovalOpened) {
    const requested = allItems.find((item) => String(item.approval.id) === requestedApproval);
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
  showDecisionError("");
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
    <dt>Scope</dt><dd class="mono">${escapeHtml(JSON.stringify(approval.scope || {}))}</dd>
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
  const filter = document.getElementById("agent-filter").value.trim().toLowerCase();
  const allAgents = state.dashboard.agents || [];
  const agents = allAgents.filter((agent) => {
    const deployment = activeDeployment(agent.id);
    const manifest = deployment?.package?.manifest;
    const haystack = [agent.display_name, agent.slug, agent.machine, agent.role, agent.hermes_profile, ...(agent.capabilities || []), ...(manifest?.task_types || [])].join(" ").toLowerCase();
    return !filter || haystack.includes(filter);
  });
  document.getElementById("agent-count").textContent = `${agents.length} of ${allAgents.length} agents`;
  document.getElementById("agent-matrix").innerHTML = agents.length ? agents.map((agent) => {
    const deployment = activeDeployment(agent.id);
    const charter = (state.dashboard.agent_charters || []).find((item) => String(item.agent_id) === String(agent.id) && item.status === "active");
    const grants = (state.dashboard.agent_capability_grants || []).filter((item) => String(item.agent_id) === String(agent.id) && item.status === "active");
    const workloadIdentity = (state.dashboard.workload_identities?.identities || []).find((item) => String(item.agent_id) === String(agent.id) && item.status === "active");
    const manifest = deployment?.package?.manifest;
    const assigned = (state.dashboard.tasks || []).filter((task) => String(task.assigned_agent_id || "") === String(agent.id)).sort((a, b) => new Date(b.updated_at) - new Date(a.updated_at));
    const currentTask = assigned.find((task) => activeStatuses.has(task.status));
    const latestTask = currentTask || assigned[0];
    return `
    <button class="agent-card" type="button" data-agent-id="${agent.id}">
      <span class="agent-card-top">${agentBot(agent, "large")}<span class="agent-presence">${statusBadge(agentStatus(agent))}</span></span>
      <span class="agent-name">${escapeHtml(agent.display_name || agent.slug)}</span>
      <span class="agent-machine">${escapeHtml(agent.machine)} · heartbeat ${relativeTime(agent.last_heartbeat_at)}</span>
      <span class="agent-role">${escapeHtml(manifest?.role || agent.role || agent.hermes_profile || "Worker")}</span>
      <span class="agent-assignment"><span>${currentTask ? "Working now" : latestTask ? "Most recent task" : "No task assigned"}</span><strong>${escapeHtml(latestTask?.title || "Available for governed work")}</strong></span>
      <span class="agent-card-footer"><span>${(agent.capabilities || []).length} capabilities</span><span>Risk ceiling ${manifest?.risk_ceiling ?? agent.risk_ceiling ?? "–"}</span><span>${grants.length} active grants · ${workloadIdentity ? `${workloadIdentity.scopes.length} scopes` : "no workload identity"}</span><span>${deployment ? `Package ${escapeHtml(deployment.package.version)}` : "No active package"} · ${charter ? `Charter ${escapeHtml(charter.version)}` : "No active charter"}</span></span>
    </button>`;
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

function executionRows(items, columns, emptyMessage) {
  if (!items.length) return empty(emptyMessage);
  return `<table><thead><tr>${columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("")}</tr></thead><tbody>${items.map((item) => `<tr>${columns.map((column) => `<td class="${column.mono ? "mono" : ""}">${escapeHtml(column.value(item) ?? "–")}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}

async function loadVenueEvents() {
  const requestId = ++state.venueEventsRequestId;
  const environment = state.executionEnvironment;
  state.venueEventsLoading = true;
  state.venueEventsError = null;
  renderExecutionEventHistory();
  try {
    if (state.demo) {
      state.venueEvents = demoVenueEventHistory();
    } else {
      const query = environment === "all" ? "" : `?environment=${encodeURIComponent(environment)}`;
      state.venueEvents = await request(`/api/execution/events${query}`);
    }
  } catch (error) {
    if (requestId !== state.venueEventsRequestId) return;
    state.venueEvents = null;
    state.venueEventsError = error.message;
  } finally {
    if (requestId !== state.venueEventsRequestId) return;
    state.venueEventsLoading = false;
    renderExecution();
  }
}

function executionEnvironmentMessage(events) {
  const environments = [...new Set(events.map((item) => item.environment))];
  if (state.executionEnvironment === "demo") return ["Demo evidence only", "Venue-confirmed demo activity. No live capital or order authority is implied."];
  if (state.executionEnvironment === "live") return ["Live-environment published evidence", "This is an immutable replay, not a live stream or proof of a currently open position."];
  if (state.executionEnvironment === "shadow") return ["Shadow evidence only", "Prospective simulated decisions; no venue order authority."];
  if (environments.length > 1) return ["Mixed environment replay", "Every event retains an explicit shadow, demo, or live label. Environments are never merged."];
  return ["Published replay", "Immutable event evidence; publication freshness is shown separately from venue environment."];
}

function eventLatency(event) {
  const exchange = new Date(event.exchange_time).getTime();
  const observed = new Date(event.observed_time).getTime();
  if (!Number.isFinite(exchange) || !Number.isFinite(observed)) return "Not measured";
  return `${Math.max(0, observed - exchange).toLocaleString()} ms`;
}

function eventPrimaryId(event) {
  return event.execution_id || event.venue_order_id || event.client_order_id || event.correlation_id || event.event_id;
}

function validatedExchangeUrl(event) {
  const candidate = event.payload?.exchange_url;
  if (!candidate || event.environment === "shadow") return null;
  try {
    const url = new URL(candidate);
    const allowed = {
      bybit: { demo: new Set(["testnet.bybit.com"]), live: new Set(["www.bybit.com", "bybit.com"]) },
      binance: { demo: new Set(["testnet.binancefuture.com"]), live: new Set(["www.binance.com", "binance.com"]) },
    };
    return url.protocol === "https:" && allowed[event.venue]?.[event.environment]?.has(url.hostname) ? url.href : null;
  } catch (_) {
    return null;
  }
}

function safeExecutionPayload(value) {
  const forbidden = new Set(["api_key", "apikey", "secret", "token", "password", "private_key", "signature", "raw_payload"]);
  if (Array.isArray(value)) return value.map(safeExecutionPayload);
  if (!value || typeof value !== "object") return value;
  return Object.fromEntries(Object.entries(value).filter(([key]) => {
    const normalized = key.toLowerCase().replaceAll("-", "_");
    return !forbidden.has(normalized) && !normalized.includes("credential");
  }).map(([key, nested]) => [key, safeExecutionPayload(nested)]));
}

function venueEventRow(event) {
  const label = humanize(event.event_type);
  const primaryId = eventPrimaryId(event);
  const eventKey = event.evidence?.event_digest || event.event_id;
  return `<button class="venue-event" type="button" data-venue-event="${escapeHtml(eventKey)}">
    <span class="venue-event-marker event-${escapeHtml(event.event_type)}" aria-hidden="true"></span>
    <span class="venue-event-time mono">${escapeHtml(new Date(event.observed_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }))}</span>
    <span class="venue-event-main"><strong>${escapeHtml(label)}</strong><small>${escapeHtml(event.instrument_id)} · ${escapeHtml(primaryId)}</small></span>
    <span class="venue-event-meta"><span class="environment-label environment-${escapeHtml(event.environment)}">${escapeHtml(event.environment)}</span><small>${escapeHtml(eventLatency(event))}</small></span>
  </button>`;
}

function renderExecutionEventHistory() {
  const count = document.getElementById("execution-event-count");
  const status = document.getElementById("execution-event-status");
  const timeline = document.getElementById("execution-timeline");
  if (!count || !status || !timeline) return;
  if (state.venueEventsLoading) {
    count.textContent = "Loading event evidence";
    status.innerHTML = '<div class="timeline-state"><strong>Reconstructing immutable replay</strong><span>Verifying event and receipt identities…</span></div>';
    timeline.innerHTML = '<div class="timeline-skeleton" aria-hidden="true"><span></span><span></span><span></span></div>';
    return;
  }
  if (state.venueEventsError) {
    count.textContent = "Unavailable";
    status.innerHTML = `<div class="timeline-state attention" role="alert"><strong>Event history unavailable</strong><span>${escapeHtml(state.venueEventsError)}</span><button class="secondary" type="button" id="retry-venue-events">Retry</button></div>`;
    timeline.innerHTML = "";
    document.getElementById("retry-venue-events").onclick = loadVenueEvents;
    return;
  }
  if (!state.venueEvents) {
    count.textContent = "Not loaded";
    status.innerHTML = '<div class="timeline-state"><strong>Event projection not requested</strong><span>Open Execution to load exact venue evidence.</span></div>';
    timeline.innerHTML = "";
    return;
  }
  const events = state.venueEvents.events || [];
  const coverage = state.venueEvents.replay_coverage || [];
  const legacy = coverage.filter((item) => item.coverage === "legacy_summary_only").length;
  const newest = events.reduce((latest, item) => !latest || new Date(item.observed_time) > new Date(latest) ? item.observed_time : latest, null);
  const [heading, detail] = executionEnvironmentMessage(events);
  count.textContent = `${events.length} ${events.length === 1 ? "event" : "events"}`;
  status.innerHTML = `<div class="timeline-state"><div><strong>${escapeHtml(heading)}</strong><span>${escapeHtml(detail)}</span></div><div class="timeline-facts">${newest ? `<span>Newest event ${relativeTime(newest)}</span>` : ""}<span>${coverage.length} source ${coverage.length === 1 ? "replay" : "replays"}</span><span>${state.venueEvents.counts?.duplicates_suppressed || 0} duplicates suppressed</span>${legacy ? `<span class="attention-text">${legacy} legacy summary-only</span>` : ""}</div></div>`;
  timeline.innerHTML = events.length ? events.map(venueEventRow).join("") : empty(legacy ? "The selected immutable replay predates event-envelope retention. Aggregate venue state remains available above; no synthetic timeline was created." : "No canonical events were published for this environment.");
  timeline.querySelectorAll("[data-venue-event]").forEach((button) => {
    button.onclick = () => openVenueEvent(button.dataset.venueEvent);
  });
}

function openVenueEvent(eventKey) {
  const events = state.venueEvents?.events || [];
  const event = events.find((item) => (item.evidence?.event_digest || item.event_id) === eventKey);
  if (!event) return;
  const identifiers = [event.correlation_id, event.client_order_id, event.venue_order_id, event.execution_id].filter(Boolean);
  const related = events.filter((candidate) => {
    const sameSource = candidate.venue === event.venue
      && candidate.environment === event.environment
      && candidate.account_pseudonym === event.account_pseudonym;
    const differentEvent = (candidate.evidence?.event_digest || candidate.event_id) !== eventKey;
    return sameSource && differentEvent && identifiers.some((id) => [candidate.correlation_id, candidate.client_order_id, candidate.venue_order_id, candidate.execution_id].includes(id));
  });
  const exchangeUrl = validatedExchangeUrl(event);
  const evidence = event.evidence || {};
  const identifierRows = [
    ["Correlation", event.correlation_id], ["Client order", event.client_order_id], ["Venue order", event.venue_order_id], ["Execution", event.execution_id],
  ].filter(([, value]) => value).map(([label, value]) => `<div class="copy-identity"><span>${escapeHtml(label)}</span><code>${escapeHtml(value)}</code><button class="text-button" type="button" data-copy-value="${escapeHtml(value)}">Copy</button></div>`).join("");
  openInspector("Venue event replay", humanize(event.event_type), `
    <section class="venue-event-hero"><div><span class="environment-label environment-${escapeHtml(event.environment)}">${escapeHtml(event.environment)}</span><span class="published-replay-label">Published replay</span></div><strong>${escapeHtml(event.venue)} · ${escapeHtml(event.account_pseudonym)}</strong><p>${escapeHtml(event.instrument_id)} · sequence ${event.sequence}</p></section>
    <section class="detail-section"><h3>Identity</h3>${identifierRows || '<p class="muted">No order correlation identifiers were published for this event.</p>'}${exchangeUrl ? `<a class="button-link secondary" href="${escapeHtml(exchangeUrl)}" target="_blank" rel="noopener noreferrer">Open validated ${escapeHtml(event.environment)} venue</a>` : '<p class="evidence-note">No validated environment-specific exchange link was published. Use the copyable IDs above.</p>'}</section>
    <section class="detail-section"><h3>Clocks and stream</h3><dl class="detail-grid"><dt>Exchange time</dt><dd>${formatDate(event.exchange_time)}</dd><dt>Observed time</dt><dd>${formatDate(event.observed_time)}</dd><dt>Observed latency</dt><dd>${escapeHtml(eventLatency(event))}</dd><dt>Stream</dt><dd>${escapeHtml(event.stream)}</dd><dt>Cursor</dt><dd class="mono">${escapeHtml(event.cursor)}</dd><dt>Correction of</dt><dd class="mono">${escapeHtml(event.correction_of || "None")}</dd></dl></section>
    <section class="detail-section"><h3>Related lifecycle</h3>${related.map((item) => `<button class="inspector-reference" type="button" data-related-event="${escapeHtml(item.evidence?.event_digest || item.event_id)}"><span><strong>${escapeHtml(humanize(item.event_type))}</strong><small>${formatDate(item.observed_time)} · ${escapeHtml(eventPrimaryId(item))}</small></span><span aria-hidden="true">›</span></button>`).join("") || '<p class="muted">No other event shares the published identifiers.</p>'}</section>
    <section class="detail-section"><h3>Sanitized canonical payload</h3><pre class="event-payload">${escapeHtml(JSON.stringify(safeExecutionPayload(event.payload || {}), null, 2))}</pre></section>
    <section class="detail-section"><h3>Immutable source evidence</h3><dl class="detail-grid"><dt>Receipt</dt><dd class="mono">${escapeHtml(evidence.receipt_digest)}</dd><dt>Projection</dt><dd class="mono">${escapeHtml(evidence.projection_digest)}</dd><dt>Event</dt><dd class="mono">${escapeHtml(evidence.event_digest)}</dd><dt>Raw reference</dt><dd class="mono">${escapeHtml(evidence.raw_reference_digest)}</dd><dt>Receipt path</dt><dd class="mono">${escapeHtml(evidence.receipt_path)}</dd><dt>Replay path</dt><dd class="mono">${escapeHtml(evidence.replay_path)}</dd></dl></section>`);
  document.querySelectorAll("#inspector-body [data-copy-value]").forEach((button) => { button.onclick = () => copyExecutionIdentity(button.dataset.copyValue); });
  document.querySelectorAll("#inspector-body [data-related-event]").forEach((button) => { button.onclick = () => openVenueEvent(button.dataset.relatedEvent); });
}

async function copyExecutionIdentity(value) {
  try {
    await navigator.clipboard.writeText(value);
    toast("Identifier copied.");
  } catch (_) {
    toast("Clipboard unavailable. Select the visible identifier to copy it.");
  }
}

function renderExecution() {
  if (!state.dashboard) return;
  const telemetry = state.dashboard.execution_telemetry || { venues: [], counts: {}, claim_boundary: "No canonical venue replay has been published." };
  const venues = (telemetry.venues || []).filter((item) => state.executionEnvironment === "all" || item.environment === state.executionEnvironment);
  const projections = venues.map((item) => ({ replay: item, view: item.projection || {} }));
  const orders = projections.flatMap(({ replay, view }) => (view.orders || []).map((item) => ({ ...item, environment: replay.environment, venue: replay.venue })));
  const fills = projections.flatMap(({ replay, view }) => (view.fills || []).map((item) => ({ ...item, environment: replay.environment, venue: replay.venue })));
  const positions = projections.flatMap(({ replay, view }) => (view.positions || []).map((item) => ({ ...item, environment: replay.environment, venue: replay.venue })));
  const cash = projections.flatMap(({ replay, view }) => (view.cash || []).map((item) => ({ ...item, environment: replay.environment, venue: replay.venue })));
  const episodes = projections.flatMap(({ replay, view }) => (view.trade_episodes || []).map((item) => ({ ...item, environment: replay.environment, venue: replay.venue })));
  const incidents = projections.flatMap(({ replay, view }) => (view.incidents || []).map((item) => ({ ...item, environment: replay.environment, venue: replay.venue })));
  const degraded = venues.filter((item) => item.status === "degraded").length;
  const stale = venues.filter((item) => item.status === "stale" || item.projection?.stale).length;
  document.getElementById("execution-overview-status").innerHTML = `<strong>${venues.length ? `${venues.length} canonical venue ${venues.length === 1 ? "replay" : "replays"}` : "Awaiting canonical telemetry"}</strong><span>${escapeHtml(telemetry.claim_boundary || "")}</span>`;
  document.getElementById("execution-summary").innerHTML = [
    metric(venues.length, "Venue accounts", "Pseudonymous, environment-bound"),
    metric(orders.length, "Orders", `${fills.length} canonical fills`),
    metric(positions.length, "Positions", `${episodes.length} completed episodes`),
    metric(degraded + stale, "Need attention", `${degraded} degraded · ${stale} stale`),
  ].join("");
  document.getElementById("execution-freshness").textContent = telemetry.generated_at ? `Read ${relativeTime(telemetry.generated_at)}` : "No publication";
  document.getElementById("execution-venues").innerHTML = venues.length ? venues.map((item) => {
    const view = item.projection || {};
    const breaks = (view.sequence_gaps || []).length + (view.reconciliation_discrepancies || []).length;
    return `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(item.venue)} · ${escapeHtml(item.account_pseudonym)}</strong><div class="entity-meta"><span class="environment-label environment-${escapeHtml(item.environment)}">${escapeHtml(item.environment)}</span><span>${view.event_count || 0} events</span><span>${view.duplicate_event_count || 0} duplicates suppressed</span><span>Fees ${escapeHtml(view.fees || "0")}</span><span>Funding ${escapeHtml(view.funding || "0")}</span><span>${breaks} reconciliation breaks</span><span>Observed ${relativeTime(item.observed_at)}</span></div></div><div class="entity-side">${statusBadge(item.status)}</div></article>`;
  }).join("") : empty("No replay has been published for this environment.");
  const exposure = [...positions, ...cash.map((item) => ({ ...item, instrument_id: item.asset, quantity: item.balance, entry_price: "cash" }))];
  document.getElementById("execution-positions").innerHTML = executionRows(exposure, [
    { label: "Environment", value: (item) => item.environment }, { label: "Venue", value: (item) => item.venue },
    { label: "Instrument / asset", value: (item) => item.instrument_id }, { label: "Quantity / balance", value: (item) => item.quantity, mono: true },
    { label: "Entry", value: (item) => item.entry_price, mono: true },
  ], "No canonical positions or cash balances.");
  const lifecycle = [...orders.map((item) => ({ ...item, record_type: "order" })), ...fills.map((item) => ({ ...item, record_type: "fill", client_order_id: item.execution_id, status: item.price }))];
  document.getElementById("execution-orders").innerHTML = executionRows(lifecycle, [
    { label: "Type", value: (item) => item.record_type }, { label: "Environment", value: (item) => item.environment },
    { label: "Venue", value: (item) => item.venue }, { label: "ID", value: (item) => item.client_order_id, mono: true },
    { label: "Side", value: (item) => item.side }, { label: "Quantity", value: (item) => item.quantity, mono: true },
    { label: "Status / price", value: (item) => item.status, mono: true },
  ], "No canonical orders or fills.");
  document.getElementById("execution-episodes").innerHTML = executionRows(episodes, [
    { label: "Environment", value: (item) => item.environment }, { label: "Venue", value: (item) => item.venue },
    { label: "Instrument", value: (item) => item.instrument_id }, { label: "Side", value: (item) => item.side },
    { label: "Quantity", value: (item) => item.quantity, mono: true }, { label: "Entry", value: (item) => item.entry_price, mono: true },
    { label: "Exit", value: (item) => item.exit_price, mono: true }, { label: "Gross PnL", value: (item) => item.gross_pnl, mono: true },
    { label: "Closed", value: (item) => item.closed_at },
  ], "No completed trade episodes.");
  const provenance = projections.map(({ replay, view }) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(replay.venue)} ${escapeHtml(replay.environment)} replay</strong><div class="entity-meta"><span>Receipt <code>${shortHash(replay.receipt_digest)}</code></span><span>Projection <code>${shortHash(replay.projection_digest)}</code></span><span>Event head <code>${shortHash(view.event_head_digest)}</code></span><span>${(view.sequence_gaps || []).length} gaps</span><span>${(view.reconciliation_discrepancies || []).length} discrepancies</span></div></div>${statusBadge(replay.status)}</article>`);
  const incidentRows = incidents.map((item) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(item.kind || "Venue incident")}</strong><div class="entity-meta"><span>${escapeHtml(item.venue)}</span><span>${escapeHtml(item.environment)}</span><span>${escapeHtml(item.summary || item.reason || "Canonical incident recorded")}</span></div></div>${statusBadge("critical")}</article>`);
  document.getElementById("execution-provenance").innerHTML = [...incidentRows, ...provenance].join("") || empty("No incidents or replay receipts published.");
  renderExecutionEventHistory();
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

async function loadBacktests() {
  if (state.backtestLoading) { state.backtestReload = true; return; }
  state.backtestLoading = true;
  document.getElementById("backtest-previous").disabled = true;
  document.getElementById("backtest-next").disabled = true;
  const view = document.getElementById("backtest-view").value;
  const tier = document.getElementById("backtest-tier").value;
  try {
    const page = await request(`/api/research/backtests?category=${view}&tier=${tier}&offset=${state.backtestOffset}`);
    if (view === document.getElementById("backtest-view").value && tier === document.getElementById("backtest-tier").value && page.offset === state.backtestOffset) {
      state.backtestPage = page;
      renderBacktests();
    }
  } catch (error) {
    document.getElementById("backtest-count").textContent = "Unavailable";
    document.getElementById("backtest-coverage").textContent = `Backtest queue unavailable: ${error.message}`;
  } finally {
    state.backtestLoading = false;
    if (state.backtestReload) { state.backtestReload = false; loadBacktests(); }
  }
}

function renderBacktests() {
  const page = state.backtestPage || state.dashboard?.backtest_activity || { unavailable: true };
  const utilization = state.dashboard?.research_utilization || { items: [], unavailable: true };
  const capacity = utilization.items || [];
  const workerBudget = capacity.reduce((sum, item) => sum + Number(item.worker_budget || 0), 0);
  const activeWorkers = capacity.reduce((sum, item) => sum + Number(item.active_workers || 0), 0);
  const pendingWork = capacity.reduce((sum, item) => sum + Number(item.queue_counts?.PENDING || 0), 0);
  const lockedWork = capacity.reduce((sum, item) => sum + Number(item.queue_counts?.LOCKED || 0), 0);
  document.getElementById("research-utilization-summary").innerHTML = [
    [activeWorkers, `active workers / ${workerBudget} budget`],
    [lockedWork, "running jobs"],
    [pendingWork, "queued jobs"],
    [capacity.filter((item) => item.fresh).length, `current machines / ${capacity.length}`],
  ].map(([value, label]) => `<div class="machine-cell"><div><strong>${escapeHtml(String(value))}</strong><small>${escapeHtml(label)}</small></div></div>`).join("");
  document.getElementById("research-utilization-items").innerHTML = capacity.length ? capacity.map((item) => {
    const governed = item.work_kind_counts?.governed_alpha_assignment || {};
    const screens = item.work_kind_counts?.disc010_signal_screen || {};
    const jobs = (item.allocations || []).map((job) => `${humanize(job.item_type)} · ${job.workers} workers`).join(" · ");
    return `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(item.machine)} · ${escapeHtml(humanize(item.state))}</strong><div class="entity-meta"><span>${item.active_workers} / ${item.worker_budget} workers</span><span>${governed.LOCKED || 0} governed running</span><span>${screens.LOCKED || 0} surveillance running</span><span>${item.queue_counts?.PENDING || 0} queued</span><span>${item.fresh ? "Current" : `Stale ${formatDuration(item.age_seconds)}`}</span><span class="mono">${shortHash(item.record_digest)}</span></div>${jobs ? `<p>${escapeHtml(jobs)}</p>` : ""}</div>${statusBadge(item.fresh && !["eligible_queue_empty", "resource_blocked"].includes(item.state) ? "healthy" : "warning")}</article>`;
  }).join("") : empty(utilization.unavailable ? "Native capacity telemetry is unavailable." : "No native capacity snapshot has been published.");
  document.getElementById("research-utilization-boundary").textContent = utilization.claim_boundary || "";
  const items = page.items || [];
  const container = document.getElementById("backtest-items");
  const completed = page.counts?.completed_backtests || 0;
  document.getElementById("backtest-count").textContent = page.unavailable ? "Unavailable" : `${completed} completed · ${page.total || 0} execution records`;
  const content = items.length ? items.map(backtestCard).join("") : empty(page.unavailable ? "Backtest queue unavailable." : "No backtests in this view.");
  const signature = JSON.stringify(items);
  if (container.dataset.signature !== signature) {
    container.innerHTML = content;
    container.dataset.signature = signature;
    container.querySelectorAll("[data-backtest-open]").forEach((button) => { button.onclick = () => openBacktest(button.dataset.backtestOpen); });
  }
  document.getElementById("backtest-coverage").textContent = page.unavailable ? "" : `${page.offset || 0}-${(page.offset || 0) + items.length} of ${page.total || 0} · Updated ${relativeTime(page.generated_at)}`;
  document.getElementById("backtest-previous").disabled = !state.backtestOffset;
  document.getElementById("backtest-next").disabled = !page.has_more;
}

function backtestCard(item) {
  const completed = item.execution_evidence === "native_terminal_receipt" && item.terminal_receipt?.present;
  const terminalWithoutReceipt = item.category === "finished" && !completed;
  const gates = Object.values(item.gate_states || {});
  const passed = gates.filter((value) => value === "passed").length;
  const failed = gates.filter((value) => value === "failed").length;
  const notRun = gates.filter((value) => value === "not_run").length;
  const classification = completed ? "Completed backtest" : terminalWithoutReceipt ? "Terminal task · receipt missing" : `${humanize(item.category)} execution`;
  const instruments = item.scientific_contract?.dataset?.instruments || [item.instrument].filter(Boolean);
  return `<article class="backtest-card ${completed ? "receipt-complete" : terminalWithoutReceipt ? "receipt-missing" : ""}" data-backtest-id="${escapeHtml(item.task_id)}">
    <header class="backtest-card-heading"><div><span class="backtest-classification">${escapeHtml(classification)}</span><h3>${escapeHtml(item.question)}</h3></div>${statusBadge(completed ? item.outcome || "completed" : item.status)}</header>
    <div class="backtest-card-facts"><span>${escapeHtml(item.tier || "Tier unrecorded")}</span><span>${escapeHtml(instruments.join(", ") || "Universe unrecorded")}</span><span>${escapeHtml(item.scientific_contract?.representation?.research_timeframe || "Timeframe unrecorded")}</span><span>${formatDate(item.window_start)} – ${formatDate(item.window_end)}</span></div>
    <div class="backtest-gate-summary" aria-label="Gate summary"><span class="gate-pass">${passed} passed</span><span class="gate-fail">${failed} failed</span><span class="gate-unrun">${notRun} not run</span></div>
    ${terminalWithoutReceipt ? '<p class="backtest-boundary">This terminal task is retained for diagnosis and is not counted as a completed backtest.</p>' : ""}
    ${item.failed_gates?.length ? `<p class="operation-error">${item.failed_gates.map((gate) => escapeHtml(humanize(gate))).join(" · ")}</p>` : ""}
    <footer><span class="mono">${completed ? `Receipt ${shortHash(item.terminal_receipt.digest)}` : `Task ${escapeHtml(item.task_number)}`}</span><button class="secondary" type="button" data-backtest-open="${escapeHtml(item.task_id)}">Inspect evidence</button></footer>
  </article>`;
}

function openBacktest(id) {
  const item = (state.backtestPage?.items || state.dashboard?.backtest_activity?.items || []).find((candidate) => String(candidate.task_id) === String(id));
  if (!item) return;
  state.backtestDetail = item;
  const contract = item.scientific_contract || {};
  const dataset = contract.dataset || {};
  const representation = contract.representation || {};
  const strategy = contract.strategy || {};
  const search = contract.search || {};
  const execution = contract.execution || {};
  const evaluation = contract.evaluation || {};
  const receipt = item.terminal_receipt || {};
  openInspector(receipt.present ? "Completed native backtest" : "Execution record", item.question, `
    <section class="detail-section backtest-truth-banner ${receipt.present ? "complete" : "missing"}"><h3>Scientific status</h3><p><strong>${receipt.present ? escapeHtml(humanize(item.outcome || item.disposition || "terminal outcome")) : "No native terminal BT-009 receipt"}</strong></p><p>${receipt.present ? "This record counts as a completed backtest. It does not imply shadow admission or capital authority." : "This task remains visible for diagnosis but does not count as a completed backtest."}</p></section>
    <section class="detail-section"><h3>Hypothesis and specification</h3><dl class="detail-grid"><dt>Task</dt><dd><button class="text-button" type="button" data-task-id="${escapeHtml(item.task_id)}">${escapeHtml(item.task_number)}</button></dd><dt>Hypothesis</dt><dd>${escapeHtml(contract.hypothesis?.id || "Not recorded")}</dd><dt>Hypothesis digest</dt><dd class="mono">${escapeHtml(contract.hypothesis?.digest || "Not recorded")}</dd><dt>Question digest</dt><dd class="mono">${escapeHtml(contract.hypothesis?.question_digest || "Not recorded")}</dd><dt>Tier</dt><dd>${escapeHtml(item.tier || "Not recorded")}</dd><dt>Execution class</dt><dd>${escapeHtml(humanize(item.execution_class || "qualification"))}</dd></dl></section>
    <section class="detail-section"><h3>Dataset, universe and representation</h3><dl class="detail-grid"><dt>Dataset</dt><dd>${escapeHtml(dataset.key || "Not recorded")}</dd><dt>Dataset digest</dt><dd class="mono">${escapeHtml(dataset.digest || "Not recorded")}</dd><dt>Venue</dt><dd>${escapeHtml(dataset.venue || "Not recorded")}</dd><dt>Universe</dt><dd>${escapeHtml((dataset.instruments || []).join(", ") || "Not recorded")}</dd><dt>Source bars</dt><dd>${escapeHtml(representation.source_timeframe || "Not recorded")}</dd><dt>Research bars</dt><dd>${escapeHtml(representation.research_timeframe || "Not recorded")}</dd><dt>Resampling</dt><dd>${escapeHtml(humanize(representation.resampling_policy || "not recorded"))}</dd><dt>Window</dt><dd>${formatDate(representation.window_start)} – ${formatDate(representation.window_end)}</dd><dt>Representation receipt</dt><dd class="mono">${escapeHtml(representation.contract_digest || "Not recorded")}</dd></dl></section>
    <section class="detail-section"><h3>Strategy, search and execution</h3><dl class="detail-grid"><dt>Source commit</dt><dd class="mono">${escapeHtml(strategy.source_commit || "Not recorded")}</dd><dt>Code digest</dt><dd class="mono">${escapeHtml(strategy.code_digest || "Not recorded")}</dd><dt>Variant budget</dt><dd>${search.maximum_variants ?? "Not recorded"}</dd><dt>Variants run</dt><dd>${search.declared_variants ?? item.trial_count ?? "Not recorded"}</dd><dt>Selected variant</dt><dd>${search.selected_variant_index ?? "Not selected"}</dd><dt>Selection basis</dt><dd>${escapeHtml(humanize(search.selection_basis || "not recorded"))}</dd><dt>Trial</dt><dd class="mono">${escapeHtml(execution.trial_id || "Not recorded")}</dd><dt>Workers</dt><dd>${execution.worker_allocation ?? "Not recorded"}</dd><dt>Run interval</dt><dd>${formatDate(execution.started_at)} – ${formatDate(execution.ended_at)}</dd></dl></section>
    <section class="detail-section"><h3>Evaluation gates</h3><div class="backtest-gate-grid">${Object.entries(item.gate_states || {}).map(([gate, value]) => `<div><span>${escapeHtml(humanize(gate))}</span>${statusBadge(value)}</div>`).join("")}</div>${item.failed_gates?.length ? `<p class="operation-error">${item.failed_gates.map((gate) => escapeHtml(humanize(gate))).join(" · ")}</p>` : ""}<dl class="detail-grid compact"><dt>OOS trades</dt><dd>${evaluation.metrics?.oos_trades ?? "Not recorded"}</dd><dt>OOS mean net R</dt><dd>${evaluation.metrics?.oos_mean_net_r ?? "Not recorded"}</dd><dt>Double-cost OOS</dt><dd>${evaluation.metrics?.double_cost_oos_mean_net_r ?? "Not recorded"}</dd><dt>Splits</dt><dd>${evaluation.splits ? escapeHtml(JSON.stringify(evaluation.splits)) : "Not recorded"}</dd><dt>Costs</dt><dd>${evaluation.costs ? escapeHtml(JSON.stringify(evaluation.costs)) : "Not recorded"}</dd><dt>Leakage review</dt><dd>${statusBadge(evaluation.leakage_review || "not_run")}</dd><dt>Selection-bias receipt</dt><dd class="mono">${escapeHtml(evaluation.selection_bias_audit_digest || "Not recorded")}</dd></dl></section>
    <section class="detail-section"><h3>Terminal receipt</h3><dl class="detail-grid"><dt>Present</dt><dd>${yesNo(receipt.present)}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(receipt.digest || "Not recorded")}</dd><dt>Schema</dt><dd>${escapeHtml(receipt.schema_version || "Not recorded")}</dd><dt>Bundle</dt><dd class="mono">${escapeHtml(receipt.bundle_digest || "Not recorded")}</dd><dt>Promotion</dt><dd>${escapeHtml(humanize(item.promotion || "not established"))}</dd></dl></section>
    <section class="detail-section"><h3>Exact reports and artifacts</h3>${(item.artifacts || []).map((artifact) => `<button class="inspector-reference" type="button" data-artifact-id="${escapeHtml(artifact.id)}"><span><strong>${escapeHtml(artifact.name)}</strong><small>${escapeHtml(humanize(artifact.artifact_type))} · ${escapeHtml(artifact.verification_status || "registered")}</small></span><span aria-hidden="true">›</span></button>`).join("") || '<p class="muted">No canonical artifacts are registered for this task.</p>'}</section>
  `);
  document.querySelectorAll("#inspector-body [data-task-id]").forEach((button) => { button.onclick = () => openTask(button.dataset.taskId); });
  document.querySelectorAll("#inspector-body [data-artifact-id]").forEach((button) => { button.onclick = () => openArtifact(button.dataset.artifactId); });
}

for (const id of ["backtest-view", "backtest-tier"]) {
  document.getElementById(id).addEventListener("change", () => { state.backtestOffset = 0; loadBacktests(); });
}
document.getElementById("backtest-previous").addEventListener("click", () => { state.backtestOffset = Math.max(0, state.backtestOffset - 50); loadBacktests(); });
document.getElementById("backtest-next").addEventListener("click", () => { state.backtestOffset += 50; loadBacktests(); });

function alphaMandates() {
  return state.dashboard?.alpha_discovery?.mandates || [];
}

function alphaMandateKind(mandate) {
  return mandate?.specification?.mandate_kind || "canonical_weekly";
}

function canonicalMandateTemplates() {
  const rank = { active: 0, awaiting_approval: 1, superseded: 2, expired: 3 };
  return alphaMandates()
    .filter((item) => ["canonical_weekly", "canonical_monthly"].includes(alphaMandateKind(item)))
    .sort((left, right) => (rank[left.status] ?? 9) - (rank[right.status] ?? 9) || new Date(right.created_at) - new Date(left.created_at));
}

function mandateOption(mandate) {
  const cadence = alphaMandateKind(mandate) === "canonical_monthly" ? "Monthly" : "Weekly";
  return `<option value="${escapeHtml(mandate.id)}">${escapeHtml(cadence)} · ${escapeHtml(mandate.mandate_key)} · ${shortHash(mandate.mandate_digest)}</option>`;
}

function setMandateFeedback(id, message, tone = "") {
  const element = document.getElementById(id);
  if (!element) return;
  element.textContent = message || "";
  element.className = `mandate-feedback${tone ? ` is-${tone}` : ""}`;
}

function renderMandateWorkbench() {
  const mandates = alphaMandates();
  const active = mandates.filter((item) => item.status === "active" && ["canonical_weekly", "canonical_monthly"].includes(alphaMandateKind(item)));
  const templates = canonicalMandateTemplates();
  const select = document.querySelector("#alpha-mandate-form [name='source_mandate_id']");
  const objective = document.querySelector("#alpha-mandate-form [name='objective']");
  const submit = document.querySelector("#alpha-mandate-form button[type='submit']");
  select.innerHTML = templates.length ? templates.map(mandateOption).join("") : '<option value="">No canonical template available</option>';
  select.disabled = !templates.length;
  submit.disabled = !templates.length;
  if (!objective.value && templates[0]?.objective) objective.value = templates[0].objective;
  document.getElementById("alpha-mandate-workbench-state").textContent = active.length ? `${active.length} active` : "Authority required";
  document.getElementById("alpha-mandate-workbench-copy").textContent = active.length
    ? `${active.map((item) => `${alphaMandateKind(item) === "canonical_monthly" ? "Monthly" : "Weekly"} authority ${shortHash(item.mandate_digest)}`).join(" · ")} is available for materialization and execution.`
    : "Discovery can retain ideas, but materialization and execution pause until an exact bounded mandate is activated.";
}

async function prepareAlphaMandate({ sourceId, cadence, objective, feedbackId }) {
  const source = alphaMandates().find((item) => item.id === sourceId);
  const normalizedObjective = String(objective || "").trim();
  if (!source) {
    setMandateFeedback(feedbackId, "Choose a canonical mandate template first.", "error");
    return null;
  }
  if (normalizedObjective.length < 20) {
    setMandateFeedback(feedbackId, "The research objective must contain at least 20 characters.", "error");
    return null;
  }
  setMandateFeedback(feedbackId, `Preparing a bounded ${cadence} mandate from ${shortHash(source.mandate_digest)}…`);
  try {
    const prepared = await mutate("/api/research/alpha-discovery/mandates/renew", {
      source_mandate_id: source.id,
      expected_source_mandate_digest: source.mandate_digest,
      cadence,
      objective: normalizedObjective,
    }, `${humanize(cadence)} mandate prepared for exact-digest review.`);
    await loadDashboard();
    setMandateFeedback(feedbackId, `${prepared.mandate_key} is prepared. Review and activate its exact digest before use.`, "success");
    openMandateApproval(prepared);
    return prepared;
  } catch (error) {
    setMandateFeedback(feedbackId, error.message || "The mandate could not be prepared.", "error");
    return null;
  }
}

function openMandateApproval(mandate) {
  if (!mandate || mandate.status !== "awaiting_approval") return;
  const form = document.getElementById("mandate-approval-form");
  form.reset();
  form.elements.mandate_id.value = mandate.id;
  form.elements.mandate_digest.value = mandate.mandate_digest;
  document.getElementById("mandate-approval-error").hidden = true;
  const cadence = alphaMandateKind(mandate) === "canonical_monthly" ? "Monthly · 30 days" : "Weekly · 7 days";
  document.getElementById("mandate-approval-summary").innerHTML = `<p><strong>${escapeHtml(mandate.objective)}</strong></p><dl><dt>Cadence</dt><dd>${cadence}</dd><dt>Valid until</dt><dd>${formatDate(mandate.valid_until)}</dd><dt>Authority</dt><dd>No capital, orders, shadow admission, code changes, or self-evaluation</dd><dt>Exact digest</dt><dd class="mono">${escapeHtml(mandate.mandate_digest)}</dd></dl>`;
  document.getElementById("mandate-dialog").showModal();
}

function renderProposalMandatePanel(preferredMandateId = null) {
  const form = document.getElementById("proposal-form");
  const active = alphaMandates().filter((item) => item.status === "active" && ["canonical_weekly", "canonical_monthly"].includes(alphaMandateKind(item)));
  const awaiting = alphaMandates().filter((item) => item.status === "awaiting_approval" && ["canonical_weekly", "canonical_monthly"].includes(alphaMandateKind(item)));
  const templates = canonicalMandateTemplates();
  const activeSelect = form.elements.mandate_id;
  activeSelect.innerHTML = active.length ? active.map(mandateOption).join("") : '<option value="">No active mandate</option>';
  activeSelect.disabled = !active.length;
  const preferred = active.find((item) => item.id === preferredMandateId);
  if (preferred) activeSelect.value = preferred.id;
  form.elements.mandate_source_id.innerHTML = templates.length ? templates.map(mandateOption).join("") : '<option value="">No canonical template available</option>';
  form.elements.mandate_source_id.disabled = !templates.length;
  document.getElementById("proposal-mandate-create").hidden = active.length > 0;
  document.getElementById("proposal-mandate-state").textContent = active.length ? "Ready to bind" : awaiting.length ? "Activation pending" : "Authority required";
  if (active.length) {
    setMandateFeedback("proposal-mandate-feedback", "The selected active digest will be bound only when this proposal is materialized.", "success");
  } else if (awaiting.length) {
    document.getElementById("proposal-mandate-create").hidden = false;
    setMandateFeedback("proposal-mandate-feedback", `${awaiting.length} prepared mandate${awaiting.length === 1 ? " is" : "s are"} awaiting activation.`);
  } else {
    setMandateFeedback("proposal-mandate-feedback", templates.length ? "Prepare a weekly or monthly mandate, then activate its exact digest." : "No canonical template is available. Register a reviewed no-capital template before continuing.", templates.length ? "" : "error");
  }
}

function renderResearch() {
  renderBacktests();
  if (!state.demo) loadBacktests();
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
  const alphaDiscovery = state.dashboard.alpha_discovery || { mandates: [], cycles: [], founder_ideas: [], throughput: {}, stalls: [], agents: [] };
  const signalSurveillance = state.dashboard.signal_surveillance || { counts: {}, items: [], claim_boundary: "No canonical DISC-010 receipt is registered." };
  const dossiers = state.dashboard.evidence_dossiers || [];
  const lifecycleStates = state.dashboard.evidence_lifecycle_states || [];
  const blockedRegister = state.dashboard.blocked_artifact_register || { total: 0, counts_by_classification: {}, items: [] };
  const surveillanceSources = state.dashboard.surveillance_sources || [];
  const surveillanceCandidates = state.dashboard.surveillance_candidates || [];
  const surveillanceDigests = state.dashboard.surveillance_digests || [];
  const scientificReviewQueue = state.dashboard.scientific_review_queue || [];
  const scientificBenchmarks = state.dashboard.scientific_benchmarks || [];
  const mathematicsCapabilities = state.dashboard.mathematics_capabilities || [];
  const scientificAssurance = state.dashboard.scientific_assurance || { counts: {}, requests: [], receipts: [] };
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
  const assuranceCounts = scientificAssurance.counts || {};
  document.getElementById("scientific-assurance-status").innerHTML = statusBadge(((assuranceCounts.needs_attention || 0) + (assuranceCounts.abstained || 0)) > 0 ? "needs_attention" : "operational");
  document.getElementById("scientific-assurance").innerHTML = (scientificAssurance.requests || []).length ? (scientificAssurance.requests || []).slice(0, 12).map((item) => `
    <article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(item.purpose)}</strong><div class="entity-meta"><span>${escapeHtml(humanize(item.required_level))}</span><span class="mono">${shortHash(item.expression_digest)}</span><span>${relativeTime(item.created_at)}</span></div><p>${escapeHtml(item.expression)}</p></div>${statusBadge(item.status)}</article>`).join("") : empty("No equation has required just-in-time assurance yet.");
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
  const activeMandates = (alphaDiscovery.mandates || []).filter((item) => item.status === "active");
  document.getElementById("alpha-discovery-status").textContent = `${activeMandates.length} active mandate${activeMandates.length === 1 ? "" : "s"} · ${(alphaDiscovery.stalls || []).length} stalls`;
  renderMandateWorkbench();
  const throughput = alphaDiscovery.throughput || {};
  const throughputKeys = ["generated", "rejected", "duplicated", "accepted", "compiled", "tested", "falsified", "invalid", "failed", "awaiting_engineering", "shadow_candidates"];
  document.getElementById("alpha-discovery-throughput").innerHTML = throughputKeys.map((key) => `<div class="machine-cell"><div><strong>${throughput[key] || 0}</strong><small>${escapeHtml(humanize(key))}</small></div></div>`).join("");
  document.getElementById("alpha-discovery-mandates").innerHTML = (alphaDiscovery.mandates || []).length ? alphaDiscovery.mandates.map((mandate) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(mandate.mandate_key)} · v${escapeHtml(mandate.version)}</strong><div class="entity-meta"><span>${escapeHtml(humanize(alphaMandateKind(mandate)))}</span><span>${mandate.cycle_count} cycles</span><span>${mandate.hypothesis_count} hypotheses</span><span>${mandate.trial_count} trials</span><span>Expires ${formatDate(mandate.valid_until)}</span><span class="mono">${shortHash(mandate.mandate_digest)}</span></div><p>${escapeHtml(mandate.objective)}</p></div><div class="entity-side">${mandate.status === "awaiting_approval" ? `<button class="primary compact" data-alpha-mandate-approve="${mandate.id}">Review and activate</button>` : ""}${statusBadge(mandate.status)}</div></article>`).join("") : empty("No bounded weekly or monthly research mandate has been registered.");
  document.getElementById("alpha-founder-ideas").innerHTML = (alphaDiscovery.founder_ideas || []).length ? alphaDiscovery.founder_ideas.map((idea) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(idea.idea)}</strong><div class="entity-meta"><span>${idea.constraints?.minimum_history_days || 365} day minimum</span><span>${idea.constraints?.maximum_variants || 8} variants maximum</span><span>${escapeHtml((idea.constraints?.universe_slices || []).join(" / "))}</span><span class="mono">${shortHash(idea.idea_digest)}</span></div></div>${statusBadge(idea.status)}</article>`).join("") : empty("No founder hypothesis is queued. Ask Hermes in chat to challenge and test an idea.");
  document.getElementById("alpha-discovery-agents").innerHTML = (alphaDiscovery.agents || []).length ? alphaDiscovery.agents.map((agent) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(humanize(agent.slug))}</strong><div class="entity-meta"><span>${escapeHtml(humanize(agent.status))}</span><span>Heartbeat ${relativeTime(agent.last_heartbeat_at)}</span></div></div>${statusBadge(agent.presence)}</article>`).join("") : empty("The supervised RI director and senior researcher have not been deployed.");
  const activeDiscoveryCycles = (alphaDiscovery.cycles || []).filter((cycle) => cycle.mandate_status === "active");
  document.getElementById("alpha-discovery-cycles").innerHTML = activeDiscoveryCycles.length ? activeDiscoveryCycles.slice(0, 12).map((cycle) => `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(cycle.mandate_key || "Active mandate")} · cycle ${cycle.ordinal} · ${escapeHtml(humanize(cycle.phase))}</strong><div class="entity-meta"><span>Next: ${escapeHtml(humanize(cycle.next_action))}</span><span>${cycle.metrics?.generated || 0} generated</span><span>${cycle.metrics?.rejected || 0} rejected</span><span>Heartbeat ${relativeTime(cycle.heartbeat_at)}</span></div></div>${statusBadge(cycle.status)}</article>`).join("") : empty("No active ALPHA-004 discovery cycle has started.");
  const signalCounts = signalSurveillance.counts || {};
  const signalItems = signalSurveillance.items || [];
  document.getElementById("signal-surveillance-status").textContent = `${signalCounts.families || 0} families · ${signalCounts.question_candidates || 0} questions`;
  document.getElementById("signal-surveillance-summary").innerHTML = ["families", "trials", "evaluated", "invalid", "question_candidates"].map((key) => `<div class="machine-cell"><div><strong>${signalCounts[key] || 0}</strong><small>${escapeHtml(humanize(key))}</small></div></div>`).join("");
  document.getElementById("signal-surveillance-items").innerHTML = signalItems.length ? signalItems.slice(0, 12).map((item) => {
    const questions = item.question_candidates || [];
    return `<article class="entity-row"><div class="entity-primary"><strong>${escapeHtml(item.family_id)}</strong><div class="entity-meta"><span>${escapeHtml((item.basket || []).join(", "))}</span><span>${escapeHtml(item.research_timeframe)}</span><span>${item.evaluated_count}/${item.trial_count} evaluated</span><span>${questions.length} candidate questions</span><span class="mono">${shortHash(item.receipt_digest)}</span></div>${questions.map((candidate) => { const contract = candidate.contract || {}; return `<p>${escapeHtml(contract.predictor_instrument || "unknown")} ${escapeHtml(humanize(contract.predictor || "predictor"))} → ${escapeHtml(contract.target_instrument || "unknown")} ${escapeHtml(humanize(contract.relation || "relation"))} return · effect ${number(candidate.validation_effect)} · p ${number(candidate.validation_empirical_p_value)}</p>`; }).join("")}</div>${statusBadge(questions.length ? "question_candidate" : "retained_null")}</article>`;
  }).join("") : empty("No canonical native signal-screen receipt has been published yet.");
  document.getElementById("signal-surveillance-boundary").textContent = signalSurveillance.claim_boundary || "";
  document.querySelectorAll("[data-alpha-mandate-approve]").forEach((button) => {
    button.addEventListener("click", () => {
      const mandate = (alphaDiscovery.mandates || []).find((item) => item.id === button.dataset.alphaMandateApprove);
      if (!mandate) return;
      openMandateApproval(mandate);
    });
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

async function openTask(id) {
  const summary = state.dashboard.tasks.find((item) => String(item.id) === String(id));
  let task = summary;
  try {
    const detail = await request(`/api/tasks/${encodeURIComponent(id)}`);
    task = detail.task || summary || detail;
  } catch (error) {
    toast(`Full task evidence is unavailable: ${error.message}`);
  }
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

function openOperation(id) {
  const operation = (state.dashboard?.operations || []).find((item) => String(item.id) === String(id));
  if (!operation) return;
  const progress = operation.progress_mode === "determinate" && operation.progress_total
    ? `${operation.progress_current}/${operation.progress_total} ${operation.progress_unit || ""}`
    : "Not reported";
  openInspector("Live process", operation.title, `
    <section class="detail-section"><h3>Current stage</h3><dl class="detail-grid">
      <dt>State</dt><dd>${statusBadge(operation.state)}</dd>
      <dt>Phase</dt><dd>${escapeHtml(humanize(operation.phase || "Unreported"))}</dd>
      <dt>Kind</dt><dd>${escapeHtml(humanize(operation.kind))}</dd>
      <dt>Machine</dt><dd>${escapeHtml(operation.machine || "Unreported")}</dd>
      <dt>Owner</dt><dd>${escapeHtml(operation.owner_type || "Unreported")} ${escapeHtml(operation.owner_id || "")}</dd>
      <dt>Started</dt><dd>${formatDate(operation.started_at)}</dd>
      <dt>Heartbeat</dt><dd>${relativeTime(operation.heartbeat_at)}</dd>
      <dt>Progress</dt><dd>${escapeHtml(progress)}</dd>
      <dt>Updated</dt><dd>${formatDate(operation.updated_at)}</dd>
      <dt>Input digest</dt><dd class="mono">${escapeHtml(operation.input_digest || "Not recorded")}</dd>
    </dl></section>
    ${operation.error_summary ? `<section class="detail-section"><h3>Current issue</h3><p>${escapeHtml(operation.error_summary)}</p></section>` : ""}
    <section class="detail-section"><h3>Process context</h3><pre class="json-view">${escapeHtml(JSON.stringify(operation.detail || {}, null, 2))}</pre></section>
  `);
}

async function openAgent(id) {
  const agent = state.dashboard.agents.find((item) => String(item.id) === String(id));
  if (!agent) return;
  state.agentDetail = null;
  state.agentDetailTab = "overview";
  state.agentDetailLoading = true;
  openInspector("Agent", agent.display_name || agent.slug, agentInspectorLoading());
  try {
    state.agentDetail = await request(`/api/agents/${encodeURIComponent(id)}/detail?offset=0&limit=25`);
    renderAgentInspector();
  } catch (error) {
    document.getElementById("inspector-body").innerHTML = `<section class="agent-inspector-error" role="alert"><h3>Agent evidence unavailable</h3><p>${escapeHtml(error.message)}</p><button class="secondary" type="button" id="retry-agent-detail">Retry</button></section>`;
    document.getElementById("retry-agent-detail").onclick = () => openAgent(id);
  } finally {
    state.agentDetailLoading = false;
  }
}

function agentInspectorLoading() {
  return `<div class="agent-detail-loading" role="status" aria-live="polite"><span class="loading-line wide"></span><span class="loading-line"></span><span class="loading-line short"></span><span class="sr-only">Loading canonical agent evidence</span></div>`;
}

function agentBot(agent, size = "medium") {
  const role = [agent?.slug, agent?.display_name, agent?.role, agent?.hermes_profile, ...(agent?.capabilities || [])].filter(Boolean).join(" ").toLowerCase();
  const kind = role.match(/review|causal|critic|evaluator/) ? "reviewer"
    : role.match(/data|represent|scientific/) ? "data"
      : role.match(/engineer|coder|strategy/) ? "engineer"
        : role.match(/execut|worker|capacity|bulletproof/) ? "executor"
          : role.match(/director|senior|research|discover/) ? "researcher"
            : "operator";
  return `<span class="agent-bot bot-${kind} bot-${size}" aria-hidden="true"><i class="bot-antenna"></i><i class="bot-head"><b></b><b></b><em></em></i><i class="bot-body"></i></span>`;
}

function renderAgentInspector({ focusTab = false } = {}) {
  const detail = state.agentDetail;
  if (!detail) return;
  const tabs = ["overview", "now", "history", "workflows", "governance"];
  const active = tabs.includes(state.agentDetailTab) ? state.agentDetailTab : "overview";
  const body = document.getElementById("inspector-body");
  body.innerHTML = `
    <div class="agent-inspector-summary">
      <div class="agent-inspector-identity">${agentBot(detail.agent, "large")}<div><strong>${escapeHtml(detail.agent.display_name || detail.agent.slug)}</strong><span>${escapeHtml(detail.agent.machine || "Machine unreported")}</span></div></div>
      ${statusBadge(detail.agent.presence || detail.agent.status || "unknown")}
    </div>
    <div class="agent-inspector-tabs" role="tablist" aria-label="Agent evidence">
      ${tabs.map((tab) => `<button type="button" role="tab" id="agent-tab-${tab}" aria-controls="agent-panel" aria-selected="${tab === active}" tabindex="${tab === active ? "0" : "-1"}" data-agent-tab="${tab}">${escapeHtml(humanize(tab))}</button>`).join("")}
    </div>
    <div id="agent-panel" class="agent-inspector-panel" role="tabpanel" aria-labelledby="agent-tab-${active}" tabindex="0">${agentInspectorPanel(detail, active)}</div>`;
  bindAgentInspectorControls();
  if (focusTab) document.getElementById(`agent-tab-${active}`)?.focus();
}

function agentInspectorPanel(detail, tab) {
  const agent = detail.agent;
  if (tab === "now") {
    const lease = detail.current_lease;
    const leaseTaskId = canonicalLeaseTaskId(lease, detail.task_history.items);
    return `<section class="detail-section"><h3>Current assignment</h3>${lease ? `<button class="entity-row" type="button" ${leaseTaskId ? `data-task-id="${escapeHtml(leaseTaskId)}"` : "disabled"}><span class="entity-primary"><strong>${escapeHtml(lease.title || lease.operation_key || "Governed work")}</strong><span class="entity-meta"><span>${escapeHtml(humanize(lease.phase || lease.status || "running"))}</span><span>${escapeHtml(lease.machine || agent.machine || "Machine unreported")}</span></span></span><span class="entity-side">${statusBadge(lease.status || "running")}</span></button>` : '<p class="muted">No current lease or active assigned task is recorded.</p>'}</section>
      <section class="detail-section"><h3>Task status evidence</h3>${sourceEvidence(detail.provenance?.task_status)}</section>
      <section class="detail-section"><h3>Latest heartbeat</h3><dl class="detail-grid"><dt>Observed</dt><dd>${formatDate(agent.last_heartbeat_at)}</dd><dt>History</dt><dd>${escapeHtml(humanize(detail.heartbeat_history.availability))}</dd></dl><p class="evidence-boundary">${escapeHtml(detail.heartbeat_history.claim_boundary)}</p></section>
      ${referenceSection(detail.references)}`;
  }
  if (tab === "history") {
    const history = detail.task_history;
    return `<section class="detail-section"><h3>Canonical task history</h3><div class="agent-history-list">${history.items.length ? history.items.map(agentHistoryRow).join("") : '<p class="muted">No assigned tasks are recorded.</p>'}</div>${history.has_more ? '<button class="secondary agent-load-more" type="button" id="agent-history-more">Load more tasks</button>' : '<p class="history-end">End of available task history</p>'}</section><section class="detail-section"><h3>History source</h3>${sourceEvidence(detail.provenance?.task_status)}</section>`;
  }
  if (tab === "workflows") {
    const memberships = detail.workflow_memberships || [];
    return `<section class="detail-section"><h3>Workflow membership</h3>${memberships.length ? memberships.map((item) => `<button class="entity-row" type="button" data-workflow-id="${escapeHtml(item.instance_id)}"><span class="entity-primary"><strong>${escapeHtml(item.title)}</strong><span class="entity-meta"><span>${escapeHtml(item.machine || "Machine unreported")}</span><span>${escapeHtml(item.current_leaf?.phase || "No current leaf")}</span></span></span><span class="entity-side">${statusBadge(item.state)}</span></button>`).join("") : '<p class="muted">No workflow ownership is recorded in the current projection.</p>'}</section>`;
  }
  if (tab === "governance") {
    const charter = detail.charter;
    const identity = detail.workload_identity;
    const relationship = detail.reporting_relationship || {};
    return `<section class="detail-section"><h3>Charter</h3><dl class="detail-grid"><dt>Role</dt><dd>${escapeHtml(charter?.role || "No active charter")}</dd><dt>Responsibilities</dt><dd>${listOrNone(charter?.responsibilities)}</dd><dt>Allowed tasks</dt><dd>${listOrNone(charter?.allowed_task_types)}</dd><dt>Risk ceiling</dt><dd>${charter?.risk_ceiling ?? agent.risk_ceiling ?? "Not recorded"}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(charter?.manifest_digest || "Not recorded")}</dd></dl></section>
      <section class="detail-section"><h3>Capabilities and grants</h3><div class="capabilities">${(agent.capabilities || []).map((item) => `<span class="capability">${escapeHtml(item)}</span>`).join("") || '<span class="muted">None recorded.</span>'}</div><div class="agent-grant-list">${(detail.grants || []).map((grant) => `<div class="inspector-row"><span>${escapeHtml(grant.capability || "Capability grant")}</span><strong>${escapeHtml(grant.machine || "Any governed machine")}</strong><small>risk ${grant.risk_ceiling ?? "unrecorded"} · expires ${formatDate(grant.expires_at)}</small></div>`).join("") || '<p class="muted">No active grants.</p>'}</div></section>
      <section class="detail-section"><h3>Workload identity</h3><dl class="detail-grid"><dt>Audience</dt><dd>${escapeHtml(identity?.audience || "Not recorded")}</dd><dt>Scopes</dt><dd>${listOrNone(identity?.scopes)}</dd><dt>Owner</dt><dd>${escapeHtml(identity?.accountable_owner || "Not recorded")}</dd></dl></section>
      <section class="detail-section"><h3>Reporting relationship</h3><p>${relationship.status === "recorded" ? escapeHtml(relationship.description || relationship.manager || "Recorded by source") : "Unknown. Mission Control does not infer an organization chart from tasks or deployments."}</p></section>`;
  }
  const deployment = detail.deployment;
  return `<section class="detail-section"><h3>Identity</h3><dl class="detail-grid"><dt>Slug</dt><dd class="mono">${escapeHtml(agent.slug)}</dd><dt>Machine</dt><dd>${escapeHtml(agent.machine || "Not recorded")}</dd><dt>Presence</dt><dd>${statusBadge(agent.presence || agent.status || "unknown")}</dd><dt>Enabled</dt><dd>${yesNo(agent.is_enabled)}</dd><dt>Runtime</dt><dd>${escapeHtml([agent.runtime, agent.runtime_version].filter(Boolean).join(" ") || "Not recorded")}</dd><dt>Last heartbeat</dt><dd>${formatDate(agent.last_heartbeat_at)} · ${relativeTime(agent.last_heartbeat_at)}</dd></dl></section>
    <section class="detail-section"><h3>Presence evidence</h3>${sourceEvidence(detail.provenance?.presence)}</section>
    <section class="detail-section"><h3>Active deployment</h3><dl class="detail-grid"><dt>Package</dt><dd>${escapeHtml(deployment ? `${deployment.package_name} ${deployment.package_version || ""}` : "None")}</dd><dt>Source commit</dt><dd class="mono">${escapeHtml(deployment?.source_commit || "Not recorded")}</dd><dt>Manifest digest</dt><dd class="mono">${escapeHtml(deployment?.manifest_digest || "Not recorded")}</dd></dl></section><p class="evidence-boundary">${escapeHtml(detail.claim_boundary)}</p>`;
}

function sourceEvidence(source) {
  if (!source) return '<p class="muted">Source metadata unavailable.</p>';
  return `<dl class="source-evidence"><dt>Source</dt><dd class="mono">${escapeHtml(source.source_identity)}</dd><dt>Class</dt><dd>${escapeHtml(humanize(source.fact_class))}</dd><dt>Freshness</dt><dd>${statusBadge(source.freshness)}</dd><dt>Timestamp</dt><dd>${formatDate(source.source_timestamp)}</dd><dt>Threshold</dt><dd>${source.freshness_threshold_seconds}s</dd>${source.reason ? `<dt>Reason</dt><dd>${escapeHtml(humanize(source.reason))}</dd>` : ""}</dl>`;
}

function referenceSection(references) {
  const artifacts = references?.artifacts || [];
  const logs = references?.logs || [];
  return `<section class="detail-section"><h3>Artifacts and logs</h3>${artifacts.map((item) => `<button class="inspector-reference" type="button" data-artifact-id="${escapeHtml(item.id)}"><span><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(humanize(item.artifact_type))} · ${escapeHtml(item.verification_status || "registered")}</small></span><span aria-hidden="true">›</span></button>`).join("") || '<p class="muted">No linked artifacts in this task window.</p>'}${logs.map((item) => `<div class="inspector-reference static"><span><strong>Operation log</strong><small class="mono">${escapeHtml(item.reference)}</small></span></div>`).join("")}</section>`;
}

function agentHistoryRow(item) {
  return `<button class="entity-row" type="button" data-task-id="${escapeHtml(item.id)}"><span class="entity-primary"><strong>${escapeHtml(item.title)}</strong><span class="entity-meta"><span class="mono">${escapeHtml(item.task_number)}</span><span>${item.attempt_count ?? 0}/${item.max_attempts ?? 0} attempts</span><span>${formatDate(item.updated_at)}</span></span></span><span class="entity-side">${statusBadge(item.status)}</span></button>`;
}

function agentInitials(agent) {
  return (agent.display_name || agent.slug || "A").split(/[\s-]+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function canonicalLeaseTaskId(lease, tasks) {
  if (!lease) return null;
  const direct = tasks.find((item) => String(item.id) === String(lease.id));
  if (direct) return direct.id;
  const operationTaskId = String(lease.operation_key || "").match(/^task:(.+)$/)?.[1];
  return tasks.some((item) => String(item.id) === operationTaskId) ? operationTaskId : null;
}

function bindAgentInspectorControls() {
  document.querySelectorAll("[data-agent-tab]").forEach((button) => {
    button.onclick = () => {
      state.agentDetailTab = button.dataset.agentTab;
      renderAgentInspector({ focusTab: true });
    };
    button.onkeydown = (event) => {
      const tabs = [...document.querySelectorAll("[data-agent-tab]")];
      const index = tabs.indexOf(button);
      let next = null;
      if (event.key === "ArrowRight") next = tabs[(index + 1) % tabs.length];
      if (event.key === "ArrowLeft") next = tabs[(index - 1 + tabs.length) % tabs.length];
      if (event.key === "Home") next = tabs[0];
      if (event.key === "End") next = tabs.at(-1);
      if (!next) return;
      event.preventDefault();
      state.agentDetailTab = next.dataset.agentTab;
      renderAgentInspector({ focusTab: true });
    };
  });
  document.querySelectorAll("#agent-panel [data-task-id]").forEach((button) => { button.onclick = () => openTask(button.dataset.taskId); });
  document.querySelectorAll("#agent-panel [data-artifact-id]").forEach((button) => { button.onclick = () => openArtifact(button.dataset.artifactId); });
  document.querySelectorAll("#agent-panel [data-workflow-id]").forEach((button) => { button.onclick = () => { closeInspector(); openWorkflow(button.dataset.workflowId); }; });
  const more = document.getElementById("agent-history-more");
  if (more) more.onclick = loadMoreAgentHistory;
}

async function loadMoreAgentHistory() {
  const detail = state.agentDetail;
  const button = document.getElementById("agent-history-more");
  if (!detail || !button) return;
  button.disabled = true;
  button.textContent = "Loading…";
  try {
    const history = detail.task_history;
    const next = await request(`/api/agents/${encodeURIComponent(detail.agent.id)}/detail?offset=${history.offset + history.items.length}&limit=${history.limit}`);
    detail.task_history.items.push(...next.task_history.items);
    detail.task_history.has_more = next.task_history.has_more;
    renderAgentInspector();
  } catch (error) {
    button.disabled = false;
    button.textContent = "Retry loading tasks";
    toast(error.message);
  }
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
  const mandatePanel = document.getElementById("proposal-mandate-panel");
  const contract = proposal.proposal.proposed_task?.input_contract || {};
  const needsMandate = create && proposal.proposal.proposed_task?.task_type === "founder_hypothesis_intake";
  mandatePanel.hidden = !needsMandate;
  if (needsMandate) {
    form.elements.mandate_objective.value = proposal.proposal.summary || proposal.interpretation || "";
    renderProposalMandatePanel(contract.mandate_id || null);
  }
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
  const artifact = (state.dashboard?.artifacts || []).find((item) => String(item.id) === String(id))
    || (state.agentDetail?.references?.artifacts || []).find((item) => String(item.id) === String(id))
    || (state.backtestDetail?.artifacts || []).find((item) => String(item.id) === String(id));
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
    if (state.demo) {
      renderGraph(state.dashboard?.graph || { nodes: [], edges: [], scope: "demonstration" });
      return;
    }
    state.graphExtent = "global";
    const parameters = new URLSearchParams({ scope: state.graphScope, limit: "100" });
    renderGraph(await request(`/api/knowledge/graph?${parameters}`));
    saveGraphViewState();
  } catch (error) {
    document.getElementById("graph").innerHTML = empty(`Knowledge graph unavailable: ${error.message}`);
  }
}

async function loadLibraryCatalog() {
  const container = document.getElementById("library-catalog");
  if (!container) return;
  container.innerHTML = '<p class="stage-empty">Loading the indexed title catalog…</p>';
  try {
    if (state.demo) {
      state.libraryCatalog = {
        canonical: [
          { id: "demo-source-1", title: "Advances in Financial Machine Learning", project: "systematic-research", origin: "Synthetic demo catalog", content_digest: "a68317817f2b39c760f1c4743050ad6a5d5719b51db543c5b0eb9983b4d398c8", kind: "canonical", access_class: "internal" },
          { id: "demo-source-2", title: "Market Microstructure and Trading Strategies", project: "systematic-research", origin: "Synthetic demo catalog", content_digest: "8914a183e66b1aefa292d8f8728e0be1dbef2be0e8d0d8a6f21fc893c97b42aa", kind: "canonical", access_class: "internal" },
        ], private: [], generated_at: new Date().toISOString(), pagination: { offset: 0, limit: 30, total: 2, has_more: false }, counts: { canonical: 2, private: 0 },
      };
    } else {
      const query = document.getElementById("library-filter").value.trim();
      const kind = document.getElementById("library-kind").value;
      const parameters = new URLSearchParams({ kind, offset: String(state.libraryOffset), limit: String(state.libraryLimit) });
      if (query) parameters.set("q", query);
      state.libraryCatalog = await request(`/api/knowledge/catalog?${parameters}`);
    }
    renderLibraryCatalog();
    if (!state.libraryDeepLinkOpened && requestedLibrarySource && ["canonical", "private"].includes(requestedLibraryKind)) {
      state.libraryDeepLinkOpened = true;
      await openLibrarySource(requestedLibraryKind, requestedLibrarySource, { citation: requestedLibraryCitation, updateUrl: false });
    }
  } catch (error) {
    state.libraryCatalog = null;
    container.innerHTML = empty(`Source catalog unavailable: ${error.message}`);
    document.getElementById("library-catalog-count").textContent = "Unavailable";
  }
}

function renderLibraryCatalog() {
  const data = state.libraryCatalog;
  const container = document.getElementById("library-catalog");
  if (!data || !container) return;
  const canonical = (data.canonical || []).map((item) => ({ ...item, catalog_kind: "canonical" }));
  const privateSources = (data.private || []).map((item) => ({ ...item, catalog_kind: "private" }));
  const all = [...canonical, ...privateSources].sort((left, right) => String(left.title).localeCompare(String(right.title)));
  const pagination = data.pagination || { offset: 0, limit: all.length || 1, total: all.length, has_more: false };
  document.getElementById("library-catalog-count").textContent = `${pagination.total} title${pagination.total === 1 ? "" : "s"}`;
  const snapshot = data.generated_at ? `Index refreshed ${relativeTime(data.generated_at)}` : "Index refresh time unavailable";
  const counts = data.counts || { canonical: canonical.length, private: privateSources.length };
  container.innerHTML = all.length ? `<div class="library-catalog-status"><span>${escapeHtml(snapshot)}</span><span>${counts.canonical} canonical · ${counts.private} private</span>${data.canonical_error ? `<span class="catalog-warning">Canonical catalog unavailable: ${escapeHtml(data.canonical_error)}</span>` : ""}</div>${all.map((item) => `<button class="library-source-row" type="button" data-library-id="${escapeHtml(item.id)}" data-library-kind="${item.catalog_kind}">
    <span class="library-source-kind" aria-hidden="true">${item.catalog_kind === "canonical" ? "Research" : "Private"}</span>
    <span class="library-source-title"><strong>${escapeHtml(item.title)}</strong><span>${escapeHtml(item.project || item.confidentiality || "Private library")} · ${item.catalog_kind === "canonical" ? escapeHtml(item.access_class || "canonical") : "Mac-local index"}</span></span>
    <span class="library-source-meta">${escapeHtml(item.origin || "Source origin unavailable")}<small>${escapeHtml(shortHash(item.content_digest || item.digest || ""))}</small></span>
    <span class="row-open" aria-hidden="true">›</span>
  </button>`).join("")}` : empty(document.getElementById("library-filter").value ? "No titles match this filter." : "No sources have been indexed yet.");
  container.querySelectorAll("[data-library-id]").forEach((button) => {
    button.onclick = () => openLibrarySource(button.dataset.libraryKind, button.dataset.libraryId);
  });
  renderLibraryPagination(pagination);
}

function renderLibraryPagination(pagination) {
  const nav = document.getElementById("library-pagination");
  const first = pagination.total ? pagination.offset + 1 : 0;
  const last = Math.min(pagination.offset + pagination.limit, pagination.total);
  nav.innerHTML = `<button class="secondary" type="button" data-library-page="previous" ${pagination.offset <= 0 ? "disabled" : ""}>← Previous</button><span>${first}–${last} of ${pagination.total}</span><button class="secondary" type="button" data-library-page="next" ${pagination.has_more ? "" : "disabled"}>Next →</button>`;
  nav.querySelectorAll("[data-library-page]").forEach((button) => {
    button.onclick = () => {
      state.libraryOffset = button.dataset.libraryPage === "next" ? pagination.offset + pagination.limit : Math.max(0, pagination.offset - pagination.limit);
      loadLibraryCatalog();
    };
  });
}

async function openLibrarySource(kind, id, { citation = null, updateUrl = true } = {}) {
  const data = state.libraryCatalog || {};
  const item = kind === "canonical"
    ? (data.canonical || []).find((source) => String(source.id) === String(id))
    : (data.private || []).find((source) => String(source.id) === String(id));
  state.libraryListScroll = document.getElementById("library-catalog").scrollTop;
  document.getElementById("library-browser").hidden = true;
  const reader = document.getElementById("library-reader");
  reader.hidden = false;
  document.getElementById("library-reader-title").textContent = item?.title || "Loading source…";
  document.getElementById("library-reader-status").innerHTML = '<span class="reader-loading">Loading authorized content…</span>';
  document.getElementById("library-document").innerHTML = '<p class="stage-empty">Resolving source lineage and first text range…</p>';
  if (updateUrl) updateLibrarySourceUrl(kind, id, citation);
  if (state.demo) {
    renderUnavailableDemoSource(item, kind, id);
    return;
  }
  state.libraryReader = { kind, id, item, unit: "line", ranges: [], outline: [], find: "", loading: false };
  try {
    await fetchLibraryRangeAt(1, { reset: true });
    renderLibraryReader();
    if (citation) await jumpToLibraryCitation(citation);
    document.getElementById("library-reader-title").focus?.();
  } catch (error) {
    document.getElementById("library-reader-status").innerHTML = '<span class="quality-label uncertain">Unavailable</span>';
    document.getElementById("library-document").innerHTML = empty(`Source content unavailable: ${error.message}`);
  }
}

function sourceContentUrl(reader, start) {
  const parameters = new URLSearchParams({ start: String(start), limit: String(reader.unit === "page" ? 5 : 200) });
  if (reader.kind === "canonical") parameters.set("unit", reader.unit);
  return `/api/knowledge/sources/${reader.kind}/${encodeURIComponent(reader.id)}/content?${parameters}`;
}

async function fetchLibraryRangeAt(start, options = {}) {
  const reader = state.libraryReader;
  if (!reader || reader.loading) return null;
  reader.loading = true;
  try {
    const response = await request(sourceContentUrl(reader, start));
    if (options.reset) reader.ranges = [];
    reader.ranges.push(response);
    reader.outline = response.outline || reader.outline;
    reader.source = response;
    return response;
  } finally {
    reader.loading = false;
  }
}

async function loadNextLibraryRange() {
  const next = state.libraryReader?.ranges.at(-1)?.range?.next_start;
  if (!next) return;
  document.getElementById("library-load-more").disabled = true;
  try {
    await fetchLibraryRangeAt(next);
    renderLibraryReader();
  } finally {
    document.getElementById("library-load-more").disabled = false;
  }
}

async function loadAllLibraryRanges() {
  const reader = state.libraryReader;
  if (!reader) return;
  const button = document.getElementById("library-load-all");
  button.disabled = true;
  const seen = new Set(reader.ranges.map((range) => range.range.start));
  try {
    while (reader.ranges.at(-1)?.range?.next_start) {
      const next = reader.ranges.at(-1).range.next_start;
      if (seen.has(next)) throw new Error("Source pagination repeated a range boundary.");
      seen.add(next);
      button.textContent = `Loading from ${reader.unit === "page" ? "page" : "line"} ${next}…`;
      await fetchLibraryRangeAt(next);
    }
    renderLibraryReader();
  } finally {
    button.disabled = false;
    button.textContent = "Load all available text";
  }
}

function renderLibraryReader() {
  const reader = state.libraryReader;
  if (!reader?.source) return;
  const source = reader.source;
  document.getElementById("library-reader-title").textContent = source.title;
  document.getElementById("library-reader-kicker").textContent = source.source_kind === "canonical" ? "Canonical research source" : "Private local source";
  document.getElementById("library-reader-subtitle").textContent = `${source.source_metadata.project || source.source_metadata.origin || "Local index"} · version ${source.version} · ${shortHash(source.source_digest)}`;
  const quality = source.lineage.quality || "unknown";
  document.getElementById("library-reader-status").innerHTML = `<span class="quality-label ${escapeHtml(quality)}">${escapeHtml(humanize(quality))}</span><span>${source.source_kind === "canonical" ? "Extracted text" : "Native text"}</span>`;
  document.querySelectorAll("[data-library-unit]").forEach((button) => {
    const active = button.dataset.libraryUnit === reader.unit;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
    button.disabled = source.source_kind === "private" && button.dataset.libraryUnit === "page";
  });
  renderLibraryDocument();
  renderLibraryOutline();
  renderLibraryProvenance();
  const last = reader.ranges.at(-1)?.range;
  document.getElementById("library-load-more").hidden = !last?.next_start;
  document.getElementById("library-load-all").hidden = !last?.next_start;
  document.getElementById("library-range-status").textContent = last ? `${humanize(last.unit)} ${reader.ranges[0].range.start}–${last.end} of ${last.total}${last.truncated_by_size ? " · response size bounded" : ""}` : "";
}

function renderLibraryDocument() {
  const reader = state.libraryReader;
  const documentBody = document.getElementById("library-document");
  if (!reader?.ranges.length) return;
  if (reader.unit === "page") {
    documentBody.innerHTML = reader.ranges.map((range) => `<section class="source-page" id="source-P${range.range.start}" tabindex="-1"><header><strong>Extracted page range ${range.range.start}–${range.range.end}</strong><button class="text-button" type="button" data-copy-citation="${escapeHtml(range.citation)}">Copy citation</button></header><pre>${highlightLibraryText(range.content, reader.find)}</pre><p class="source-extraction-boundary">Extracted text. This is not an image of the original page.</p></section>`).join("");
  } else {
    const lines = [];
    reader.ranges.forEach((range) => range.content.split("\n").forEach((text, index) => lines.push({ number: range.range.start + index, text, citation: range.citation })));
    documentBody.innerHTML = `<div class="source-lines">${lines.map((line) => `<div class="source-line" id="source-L${line.number}" data-source-line="${line.number}"><a href="#source-L${line.number}" class="source-line-number" aria-label="Line ${line.number}" data-line-citation="L${line.number}">${line.number}</a><span>${highlightLibraryText(line.text, reader.find) || "&nbsp;"}</span></div>`).join("")}</div>`;
  }
  documentBody.querySelectorAll("[data-copy-citation]").forEach((button) => button.onclick = () => copyLibraryCitation(button.dataset.copyCitation));
  documentBody.querySelectorAll("[data-line-citation]").forEach((link) => link.onclick = (event) => {
    event.preventDefault();
    updateLibrarySourceUrl(reader.kind, reader.id, link.dataset.lineCitation);
    copyLibraryCitation(`${reader.source.citation.split("#")[0]}#${link.dataset.lineCitation}`);
  });
}

function renderLibraryOutline() {
  const outline = document.getElementById("library-outline");
  const items = state.libraryReader?.outline || [];
  outline.innerHTML = items.length ? items.map((item) => `<button type="button" style="--outline-indent:${Math.max(0, Number(item.level || 1) - 1) * 8}px" data-outline-unit="${escapeHtml(item.unit)}" data-outline-position="${Number(item.position)}"><span>${escapeHtml(item.label)}</span><small>${escapeHtml(item.unit)} ${Number(item.position)}</small></button>`).join("") : '<p class="muted">No structural outline was extracted.</p>';
  outline.querySelectorAll("[data-outline-position]").forEach((button) => button.onclick = () => jumpToLibraryPosition(button.dataset.outlineUnit, Number(button.dataset.outlinePosition)));
}

function renderLibraryProvenance() {
  const source = state.libraryReader.source;
  const lineage = source.lineage || {};
  const assets = source.original_assets || [];
  const pageAsset = assets.map((asset) => ({ ...asset, safeUrl: authorizedLibraryAssetUrl(asset) })).find((asset) => asset.safeUrl);
  document.getElementById("library-provenance").innerHTML = `<section><p class="section-kicker">Source record</p><dl><dt>Access</dt><dd>${escapeHtml(source.access_class || "unknown")}</dd><dt>Version</dt><dd>${escapeHtml(source.version)}</dd><dt>Source digest</dt><dd class="mono">${escapeHtml(source.source_digest)}</dd><dt>Text digest</dt><dd class="mono">${escapeHtml(source.content_digest)}</dd></dl></section><section><p class="section-kicker">Extraction</p><dl><dt>Parser</dt><dd>${escapeHtml((lineage.parsers || [lineage.parser]).filter(Boolean).join(", ") || "Not recorded")}</dd><dt>Quality</dt><dd>${escapeHtml(humanize(lineage.quality || "unknown"))}</dd><dt>Confidence</dt><dd>${lineage.minimum_confidence == null ? "Not recorded" : `${Math.round(lineage.minimum_confidence * 100)}–${Math.round(lineage.maximum_confidence * 100)}%`}</dd></dl>${(lineage.uncertainties || []).map((item) => `<p class="source-uncertainty">${escapeHtml(humanize(item))}</p>`).join("")}</section><section><p class="section-kicker">Original asset</p>${pageAsset ? `<figure class="source-page-asset"><img src="${escapeHtml(pageAsset.safeUrl)}" alt="Authorized original source page" loading="lazy"><figcaption>Authorized original page asset. Compare it with the extracted text in the reading pane.</figcaption></figure>` : '<p class="source-asset-unavailable"><strong>Original page unavailable</strong><span>The reading pane shows stored or extracted text only. It is not a facsimile of the source.</span></p>'}</section>${source.source_kind === "canonical" ? '<button id="library-explore-source" class="secondary" type="button">Explore source relationships</button>' : '<p class="local-only-boundary">Local-only content remains on this Mission Control host.</p>'}`;
  const explore = document.getElementById("library-explore-source");
  if (explore) explore.onclick = async () => {
    const id = state.libraryReader.id;
    closeLibraryReader();
    setResearchMode("explore");
    await queryGraphRoot(id);
  };
}

function authorizedLibraryAssetUrl(asset) {
  if (asset?.availability !== "authorized_page_asset" || !asset.url) return null;
  try {
    const url = new URL(asset.url, window.location.origin);
    if (url.origin !== window.location.origin || !url.pathname.startsWith("/api/knowledge/assets/")) return null;
    return `${url.pathname}${url.search}`;
  } catch (_) {
    return null;
  }
}

async function switchLibraryUnit(unit) {
  const reader = state.libraryReader;
  if (!reader || reader.unit === unit || (reader.kind === "private" && unit === "page")) return;
  reader.unit = unit;
  reader.find = "";
  document.getElementById("library-find").value = "";
  document.getElementById("library-document").innerHTML = '<p class="stage-empty">Loading range…</p>';
  await fetchLibraryRangeAt(1, { reset: true });
  renderLibraryReader();
}

async function jumpToLibraryPosition(unit, position) {
  const reader = state.libraryReader;
  if (!reader) return;
  if (reader.unit !== unit) {
    reader.unit = unit;
    await fetchLibraryRangeAt(position, { reset: true });
    renderLibraryReader();
  } else if (!document.getElementById(`source-${unit === "page" ? "P" : "L"}${position}`)) {
    await fetchLibraryRangeAt(position, { reset: true });
    renderLibraryReader();
  }
  const marker = unit === "page" ? "P" : "L";
  document.getElementById(`source-${marker}${position}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  updateLibrarySourceUrl(reader.kind, reader.id, `${marker}${position}`);
}

async function jumpToLibraryCitation(citation) {
  const match = /^([LP])(\d+)$/.exec(citation || "");
  if (match) await jumpToLibraryPosition(match[1] === "P" ? "page" : "line", Number(match[2]));
}

async function findInLibraryDocument(event) {
  event.preventDefault();
  const query = document.getElementById("library-find").value.trim();
  if (!state.libraryReader || !query) return;
  if (state.libraryReader.unit !== "line") await switchLibraryUnit("line");
  if (state.libraryReader.ranges[0]?.range?.start !== 1) {
    await fetchLibraryRangeAt(1, { reset: true });
  }
  state.libraryReader.find = query;
  await loadAllLibraryRanges();
  renderLibraryDocument();
  const matches = [...document.querySelectorAll(".source-line")].filter((line) => line.textContent.toLowerCase().includes(query.toLowerCase()));
  document.getElementById("library-find-status").textContent = `${matches.length} match${matches.length === 1 ? "" : "es"}`;
  matches[0]?.scrollIntoView({ behavior: "smooth", block: "center" });
}

function highlightLibraryText(value, query) {
  if (!query) return escapeHtml(value);
  const lower = String(value).toLowerCase();
  const needle = query.toLowerCase();
  let cursor = 0;
  let output = "";
  while (needle && lower.indexOf(needle, cursor) !== -1) {
    const index = lower.indexOf(needle, cursor);
    output += escapeHtml(String(value).slice(cursor, index));
    output += `<mark>${escapeHtml(String(value).slice(index, index + needle.length))}</mark>`;
    cursor = index + needle.length;
  }
  return output + escapeHtml(String(value).slice(cursor));
}

async function copyLibraryCitation(citation) {
  try {
    await navigator.clipboard.writeText(citation);
    toast("Citation copied.");
  } catch (_) {
    toast(citation);
  }
}

function updateLibrarySourceUrl(kind, id, citation = null) {
  const url = new URL(window.location.href);
  url.searchParams.set("view", "knowledge");
  url.searchParams.set("workspace", "library");
  url.searchParams.set("sourceKind", kind);
  url.searchParams.set("source", id);
  if (citation) url.searchParams.set("cite", citation);
  else url.searchParams.delete("cite");
  window.history.replaceState({}, "", url);
}

function closeLibraryReader() {
  const selectedId = state.libraryReader?.id;
  state.libraryReader = null;
  document.getElementById("library-reader").hidden = true;
  document.getElementById("library-browser").hidden = false;
  const url = new URL(window.location.href);
  ["sourceKind", "source", "cite"].forEach((key) => url.searchParams.delete(key));
  window.history.replaceState({}, "", url);
  window.requestAnimationFrame(() => {
    const catalog = document.getElementById("library-catalog");
    catalog.scrollTop = state.libraryListScroll;
    catalog.querySelector(`[data-library-id="${CSS.escape(String(selectedId || ""))}"]`)?.focus();
  });
}

function renderUnavailableDemoSource(item, kind, id) {
  state.libraryReader = { kind, id, item, unit: "line", ranges: [], outline: [], find: "" };
  document.getElementById("library-reader-title").textContent = item?.title || "Demonstration source";
  document.getElementById("library-reader-status").innerHTML = '<span class="quality-label uncertain">Demonstration only</span>';
  document.getElementById("library-document").innerHTML = empty("Synthetic catalog entries have no source text and cannot be presented as evidence.");
  document.getElementById("library-outline").innerHTML = '<p class="muted">No canonical outline.</p>';
  document.getElementById("library-provenance").innerHTML = '<p class="source-asset-unavailable"><strong>Evidence unavailable</strong><span>Leave demonstration mode to read authorized source content.</span></p>';
  document.getElementById("library-load-more").hidden = true;
  document.getElementById("library-load-all").hidden = true;
}

function renderGraph(graph) {
  state.graphData = graph;
  renderResearchWorkspaceStatus();
  syncGraphControls();
  document.querySelectorAll("[data-graph-view]").forEach((item) => {
    const active = item.dataset.graphView === state.graphView;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  const selectedType = document.getElementById("graph-object-type").value;
  const nodes = (graph.nodes || []).filter((node) => !selectedType || String(node.object_type || node.kind) === selectedType).slice(0, 100);
  const nodeMap = new Map(nodes.map((node) => [String(node.id), node]));
  const edges = (graph.edges || []).filter((edge) => nodeMap.has(String(edge.source)) && nodeMap.has(String(edge.target))).slice(0, 240);
  if (!nodes.length) {
    document.getElementById("graph").innerHTML = empty("Build the canonical graph projection to explore research lineage.");
    return;
  }
  if (!nodeMap.has(String(state.graphSelectedId))) state.graphSelectedId = String(nodes[0].id);
  const selected = nodeMap.get(String(state.graphSelectedId));
  document.getElementById("graph-expand").disabled = !selected;
  const positions = graphPositions(nodes, edges);
  const visual = `
    <div class="graph-canvas-shell">
      <div class="graph-canvas-toolbar" role="group" aria-label="Graph zoom controls">
        <button type="button" class="icon-button" data-graph-zoom="in" aria-label="Zoom in" title="Zoom in">+</button>
        <button type="button" class="icon-button" data-graph-zoom="out" aria-label="Zoom out" title="Zoom out">−</button>
        <button type="button" class="icon-button graph-fit" data-graph-zoom="fit" aria-label="Fit graph" title="Fit graph">Fit</button>
      </div>
      <svg id="knowledge-graph-svg" class="knowledge-graph-svg" width="900" height="520" viewBox="0 0 900 520" role="application" aria-labelledby="graph-svg-title graph-svg-desc" aria-label="Interactive evidence graph. Drag nodes to arrange, drag the background to pan, and scroll to zoom.">
        <title id="graph-svg-title">Canonical research relationship graph</title>
        <desc id="graph-svg-desc">${nodes.length} evidence nodes and ${edges.length} visible relationships. Use the Relationships view for a keyboard-first adjacency list.</desc>
        <defs><marker id="graph-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"></path></marker></defs>
        <g id="graph-viewport" transform="translate(${state.graphTransform.x} ${state.graphTransform.y}) scale(${state.graphTransform.scale})">
          <g class="graph-links">${edges.map((edge) => graphEdgeSvg(edge, positions, graphEdgeInFocusedPath(edge))).join("")}</g>
          <g class="graph-nodes">${nodes.map((node, index) => graphNodeSvg(node, positions.get(String(node.id)), index, String(node.id) === String(state.graphSelectedId), state.graphPath.includes(String(node.id)))).join("")}</g>
        </g>
      </svg>
      <div class="graph-legend"><span><i class="legend-shape claim"></i>Claim</span><span><i class="legend-shape result"></i>Result</span><span><i class="legend-shape source"></i>Source</span><span><i class="legend-line supports"></i>Supports</span><span><i class="legend-line contradicts"></i>Contradicts</span></div>
    </div>`;
  const relationships = `
    <div class="graph-adjacency" role="list" aria-label="Visible graph relationships">
      ${edges.length ? edges.map((edge) => graphRelationshipRow(edge, nodeMap, graphEdgeInFocusedPath(edge))).join("") : empty("The selected bounded view contains no explicit relationships.")}
    </div>`;
  document.getElementById("graph").innerHTML = `
    <div class="projection-meta"><span>${escapeHtml(state.graphExtent === "global" ? "Global map" : "Local focus")}</span><span>${escapeHtml(state.graphScope)} boundary</span><span>${escapeHtml(graph.projection_version || "local-knowledge-v1")}</span><span>${nodes.length.toLocaleString()} / 100 nodes</span><span>${edges.length.toLocaleString()} relationships</span><span class="mono">${escapeHtml(shortHash(graph.query_digest || graph.corpus_digest || ""))}</span>${graph.truncated ? `<span>${escapeHtml(graph.truncation?.reasons?.length ? `Bounded: ${graph.truncation.reasons.map(humanize).join(", ")}` : "Bounded at query limit")}</span>` : ""}<span>${graph.built_at || graph.generated_at ? `Published ${escapeHtml(relativeTime(graph.built_at || graph.generated_at))}` : "Projection time unavailable"}</span></div>
    <div class="graph-workspace">
      <div class="graph-primary">${state.graphView === "visual" ? visual : relationships}</div>
      ${graphSelectionPanel(selected, edges, nodeMap)}
    </div>`;
  bindGraphInteractions(nodeMap);
  populateGraphPathControls(nodes);
  renderGraphFindResults();
  saveGraphViewState();
}

function restoreGraphViewState() {
  try {
    const saved = JSON.parse(window.localStorage.getItem("hermes.graph-view.v1") || "{}");
    if (["canonical", "private"].includes(saved.scope)) state.graphScope = saved.scope;
    if (["global", "local"].includes(saved.extent)) state.graphExtent = saved.extent;
    if (["visual", "list"].includes(saved.view)) state.graphView = saved.view;
    if (["incoming", "outgoing", "both"].includes(saved.direction)) state.graphDirection = saved.direction;
    if ([1, 2, 3].includes(Number(saved.depth))) state.graphDepth = Number(saved.depth);
    state.graphPredicate = String(saved.predicate || "");
    state.graphObjectType = String(saved.objectType || "");
    state.graphSelectedId = saved.selectedId ? String(saved.selectedId) : null;
  } catch (_) {
    window.localStorage.removeItem("hermes.graph-view.v1");
  }
}

function saveGraphViewState() {
  const payload = {
    scope: state.graphScope,
    extent: state.graphExtent,
    view: state.graphView,
    direction: document.getElementById("graph-direction")?.value || state.graphDirection || "both",
    depth: Number(document.getElementById("graph-depth")?.value || state.graphDepth || 2),
    predicate: document.getElementById("graph-predicate")?.value || "",
    objectType: document.getElementById("graph-object-type")?.value || "",
    selectedId: state.graphSelectedId,
  };
  window.localStorage.setItem("hermes.graph-view.v1", JSON.stringify(payload));
}

function syncGraphControls() {
  document.getElementById("graph-scope").value = state.graphScope;
  if (state.graphDirection) document.getElementById("graph-direction").value = state.graphDirection;
  if (state.graphDepth) document.getElementById("graph-depth").value = String(state.graphDepth);
  if (state.graphPredicate != null) document.getElementById("graph-predicate").value = state.graphPredicate;
  if (state.graphObjectType != null) document.getElementById("graph-object-type").value = state.graphObjectType;
  const mentions = document.querySelector('#graph-predicate option[value="mentions"]');
  mentions.disabled = state.graphScope !== "private";
  if (state.graphScope !== "private" && document.getElementById("graph-predicate").value === "mentions") document.getElementById("graph-predicate").value = "";
  document.querySelectorAll("[data-graph-extent]").forEach((item) => {
    const active = item.dataset.graphExtent === state.graphExtent;
    item.classList.toggle("active", active);
    item.setAttribute("aria-pressed", String(active));
  });
  document.getElementById("graph-boundary").textContent = state.demo
    ? "Synthetic demonstration relationships only. No item in this map is canonical evidence."
    : state.graphScope === "canonical"
    ? "Canonical control-plane evidence only. Views are capped at 100 nodes and never mix access boundaries."
    : "Private Mac-local notes only. Opaque identities never cross into the canonical graph.";
}

function populateGraphPathControls(nodes) {
  const options = nodes.map((node) => `<option value="${escapeHtml(node.id)}">${escapeHtml(truncate(node.label || node.name || node.id, 64))}</option>`).join("");
  const source = document.getElementById("graph-path-source");
  const target = document.getElementById("graph-path-target");
  const priorSource = source.value || state.graphSelectedId || "";
  const priorTarget = target.value;
  source.innerHTML = `<option value="">Select source</option>${options}`;
  target.innerHTML = `<option value="">Select target</option>${options}`;
  if (nodes.some((node) => String(node.id) === String(priorSource))) source.value = priorSource;
  if (nodes.some((node) => String(node.id) === String(priorTarget))) target.value = priorTarget;
}

function graphEdgeInFocusedPath(edge) {
  if (state.graphPath.length < 2) return false;
  for (let index = 0; index < state.graphPath.length - 1; index += 1) {
    const left = state.graphPath[index];
    const right = state.graphPath[index + 1];
    if ((String(edge.source) === left && String(edge.target) === right) || (String(edge.source) === right && String(edge.target) === left)) return true;
  }
  return false;
}

function clearGraphPath() {
  state.graphPath = [];
  document.getElementById("graph-path-status").textContent = "Path focus cleared.";
  document.getElementById("graph-clear-path").hidden = true;
  if (state.graphData) renderGraph(state.graphData);
}

async function queryGraphPath(event) {
  event.preventDefault();
  const source = document.getElementById("graph-path-source").value;
  const target = document.getElementById("graph-path-target").value;
  const status = document.getElementById("graph-path-status");
  if (!source || !target || source === target) {
    status.textContent = "Choose two different visible records.";
    return;
  }
  status.textContent = "Tracing explicit relations…";
  try {
    const predicate = document.getElementById("graph-predicate").value;
    const objectType = document.getElementById("graph-object-type").value;
    const graph = await request("/api/knowledge/graph/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scope: state.graphScope, root_ids: [source], target_id: target, mode: "paths",
        predicates: predicate ? [predicate] : [], object_types: objectType ? [objectType] : [],
        direction: document.getElementById("graph-direction").value,
        max_depth: Math.max(2, Number(document.getElementById("graph-depth").value)), max_nodes: 100, page_size: 100,
      }),
    });
    state.graphExtent = "local";
    state.graphPath = (graph.paths?.[0] || []).map(String);
    state.graphSelectedId = source;
    state.graphTransform = { scale: 1, x: 0, y: 0 };
    renderGraph(graph);
    status.textContent = state.graphPath.length ? `Path found across ${state.graphPath.length - 1} relation${state.graphPath.length === 2 ? "" : "s"}.` : "No explicit path exists inside the selected direction, filters, depth, and access boundary.";
    document.getElementById("graph-clear-path").hidden = !state.graphPath.length;
  } catch (error) {
    status.textContent = `Path query unavailable: ${error.message}`;
  }
}

function openGraphEdgeInspector(edge, nodeMap) {
  const source = nodeMap.get(String(edge.source));
  const target = nodeMap.get(String(edge.target));
  const provenance = edge.provenance_object_id || edge.provenance_id;
  openInspector("Relationship evidence", humanize(edge.predicate || edge.relation || "related"), `<section class="detail-section"><h3>Directed relation</h3><p class="edge-statement"><strong>${escapeHtml(source?.label || source?.name || edge.source)}</strong><span>${escapeHtml(humanize(edge.predicate || edge.relation || "related"))}</span><strong>${escapeHtml(target?.label || target?.name || edge.target)}</strong></p><dl class="detail-grid"><dt>Boundary</dt><dd>${escapeHtml(state.graphScope)}</dd><dt>Access</dt><dd>${statusBadge(edge.access_class || "private")}</dd><dt>Valid from</dt><dd>${escapeHtml(edge.valid_from || "Unbounded")}</dd><dt>Valid until</dt><dd>${escapeHtml(edge.valid_until || "Current")}</dd><dt>Record digest</dt><dd class="mono">${escapeHtml(edge.record_digest || "Unavailable")}</dd><dt>Provenance</dt><dd class="mono">${escapeHtml(provenance || "Unavailable")}</dd></dl></section>${provenance && state.graphScope === "canonical" ? `<div class="inspector-actions"><button class="secondary" id="replay-edge-provenance" type="button">Replay provenance</button></div><div id="edge-provenance-result"></div>` : '<p class="local-only-boundary">Private relationship evidence remains local to this Mission Control host.</p>'}`);
  const replay = document.getElementById("replay-edge-provenance");
  if (replay) replay.onclick = async () => {
    replay.disabled = true;
    try {
      const result = await request(`/api/research/copilot/citations/${encodeURIComponent(provenance)}`);
      document.getElementById("edge-provenance-result").innerHTML = `<pre class="citation-replay">${escapeHtml(JSON.stringify(result, null, 2))}</pre>`;
    } catch (error) {
      document.getElementById("edge-provenance-result").innerHTML = empty(error.message);
    } finally {
      replay.disabled = false;
    }
  };
}

function graphPositions(nodes, edges) {
  const ids = nodes.map((node) => String(node.id));
  const signature = `${ids.join("|")}::${edges.map((edge) => `${edge.source}>${edge.target}`).join("|")}`;
  if (signature === state.graphLayoutSignature && state.graphLayout.size) return state.graphLayout;
  const positions = new Map();
  const center = { x: 450, y: 260 };
  nodes.forEach((node, index) => {
    const angle = index * 2.399963;
    const radius = Math.min(220, 36 + Math.sqrt(index) * 30);
    positions.set(String(node.id), { x: center.x + Math.cos(angle) * radius, y: center.y + Math.sin(angle) * radius * .78 });
  });
  const usableEdges = edges.filter((edge) => positions.has(String(edge.source)) && positions.has(String(edge.target)));
  for (let iteration = 0; iteration < 72; iteration += 1) {
    const forces = new Map(ids.map((id) => [id, { x: 0, y: 0 }]));
    for (let left = 0; left < ids.length; left += 1) {
      const a = positions.get(ids[left]);
      for (let right = left + 1; right < ids.length; right += 1) {
        const b = positions.get(ids[right]);
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const distance2 = Math.max(dx * dx + dy * dy, 36);
        const force = Math.min(2.6, 720 / distance2);
        const fx = dx / Math.sqrt(distance2) * force;
        const fy = dy / Math.sqrt(distance2) * force;
        forces.get(ids[left]).x += fx;
        forces.get(ids[left]).y += fy;
        forces.get(ids[right]).x -= fx;
        forces.get(ids[right]).y -= fy;
      }
    }
    for (const edge of usableEdges) {
      const source = positions.get(String(edge.source));
      const target = positions.get(String(edge.target));
      const dx = target.x - source.x;
      const dy = target.y - source.y;
      const distance = Math.max(Math.hypot(dx, dy), 1);
      const force = (distance - 105) * .006;
      const fx = dx / distance * force;
      const fy = dy / distance * force;
      forces.get(String(edge.source)).x += fx;
      forces.get(String(edge.source)).y += fy;
      forces.get(String(edge.target)).x -= fx;
      forces.get(String(edge.target)).y -= fy;
    }
    const cooling = 1 - iteration / 88;
    for (const id of ids) {
      const position = positions.get(id);
      const force = forces.get(id);
      position.x = Math.max(28, Math.min(872, position.x + force.x * cooling + (center.x - position.x) * .006));
      position.y = Math.max(28, Math.min(492, position.y + force.y * cooling + (center.y - position.y) * .006));
    }
  }
  state.graphLayoutSignature = signature;
  state.graphLayout = positions;
  return positions;
}

function graphNodeSvg(node, position, index, selected, inPath = false) {
  const type = String(node.object_type || node.kind || "evidence");
  const label = String(node.label || node.name || node.id);
  const shape = type === "claim" ? `<rect x="-8" y="-8" width="16" height="16" rx="2"></rect>` : type === "result" ? `<path d="M 0 -10 L 10 0 L 0 10 L -10 0 Z"></path>` : `<circle r="8"></circle>`;
  return `<g class="graph-node-svg type-${escapeHtml(type)}${selected ? " selected" : ""}${inPath ? " path-focus" : ""}" transform="translate(${position.x} ${position.y})" data-graph-node="${escapeHtml(node.id)}" tabindex="0" role="button" aria-pressed="${selected}" aria-label="${escapeHtml(label)}, ${escapeHtml(type)}${inPath ? ", on focused path" : ""}">${shape}${(index < 14 || selected || inPath) ? `<text x="12" y="4">${escapeHtml(truncate(label, 34))}</text>` : ""}</g>`;
}

function graphEdgeSvg(edge, positions, inPath = false) {
  const source = positions.get(String(edge.source));
  const target = positions.get(String(edge.target));
  return `<line class="graph-link predicate-${escapeHtml(edge.predicate || edge.relation || "related")}${inPath ? " path-focus" : ""}" data-graph-edge="${escapeHtml(edge.id || `${edge.source}:${edge.target}:${edge.predicate}`)}" data-edge-source="${escapeHtml(edge.source)}" data-edge-target="${escapeHtml(edge.target)}" x1="${source.x}" y1="${source.y}" x2="${target.x}" y2="${target.y}" marker-end="url(#graph-arrow)" tabindex="0" role="button" aria-label="Inspect ${escapeHtml(humanize(edge.predicate || edge.relation || "related"))} relationship"><title>${escapeHtml(humanize(edge.predicate || edge.relation || "related"))}</title></line>`;
}

function graphRelationshipRow(edge, nodeMap, inPath = false) {
  const source = nodeMap.get(String(edge.source));
  const target = nodeMap.get(String(edge.target));
  return `<div class="graph-relationship${inPath ? " path-focus" : ""}" role="listitem"><button type="button" data-graph-node="${escapeHtml(source.id)}">${escapeHtml(source.label || source.name)}</button><button class="relationship-predicate ${escapeHtml(edge.predicate || edge.relation)}" type="button" data-graph-edge="${escapeHtml(edge.id || `${edge.source}:${edge.target}:${edge.predicate}`)}" aria-label="Inspect ${escapeHtml(humanize(edge.predicate || edge.relation))} relationship">${escapeHtml(humanize(edge.predicate || edge.relation))}</button><button type="button" data-graph-node="${escapeHtml(target.id)}">${escapeHtml(target.label || target.name)}</button></div>`;
}

function graphSelectionPanel(node, edges, nodeMap) {
  const related = edges.filter((edge) => String(edge.source) === String(node.id) || String(edge.target) === String(node.id));
  return `<aside class="graph-selection" aria-label="Selected graph node">
    <p class="section-kicker">Selected evidence</p><h3>${escapeHtml(node.label || node.name)}</h3>
    <dl class="detail-grid"><dt>Type</dt><dd>${escapeHtml(node.object_type || node.kind)}</dd><dt>Project</dt><dd>${escapeHtml(node.project || "Local knowledge")}</dd><dt>Access</dt><dd>${statusBadge(node.access_class || "private")}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(shortHash(node.content_digest || ""))}</dd><dt>Visible links</dt><dd>${related.length.toLocaleString()}</dd></dl>
    <div class="graph-selection-actions"><button class="secondary" type="button" data-graph-replay="${escapeHtml(node.id)}">Replay evidence</button><button class="text-button" type="button" data-graph-neighbors="${escapeHtml(node.id)}">Expand neighbors</button></div>
    <div class="selection-neighbors">${related.slice(0, 6).map((edge) => { const other = nodeMap.get(String(edge.source) === String(node.id) ? String(edge.target) : String(edge.source)); return `<button type="button" data-graph-node="${escapeHtml(other.id)}"><span>${escapeHtml(humanize(edge.predicate || edge.relation))}</span>${escapeHtml(other.label || other.name)}</button>`; }).join("") || `<span class="muted">No visible neighbors.</span>`}</div>
  </aside>`;
}

function bindGraphInteractions(nodeMap) {
  const root = document.getElementById("graph");
  root.onclick = (event) => {
    const zoom = event.target.closest("[data-graph-zoom]");
    if (zoom) {
      if (zoom.dataset.graphZoom === "fit") state.graphTransform = { scale: 1, x: 0, y: 0 };
      else state.graphTransform.scale = Math.max(.45, Math.min(2.8, state.graphTransform.scale * (zoom.dataset.graphZoom === "in" ? 1.2 : .8)));
      return renderGraph(state.graphData);
    }
    const replay = event.target.closest("[data-graph-replay]");
    if (replay) return replayGraphEvidence(nodeMap.get(replay.dataset.graphReplay));
    const neighbors = event.target.closest("[data-graph-neighbors]");
    if (neighbors) return queryGraphRoot(neighbors.dataset.graphNeighbors);
    const edgeElement = event.target.closest("[data-graph-edge]");
    if (edgeElement) {
      const edge = (state.graphData?.edges || []).find((item) => String(item.id || `${item.source}:${item.target}:${item.predicate}`) === String(edgeElement.dataset.graphEdge));
      if (edge) return openGraphEdgeInspector(edge, nodeMap);
    }
    if (state.graphDragging) return;
    const element = event.target.closest("[data-graph-node]");
    if (!element) return;
    const node = nodeMap.get(String(element.dataset.graphNode));
    if (!node) return;
    state.graphSelectedId = String(node.id);
    addResearchContext({ id: node.id, label: node.label || node.name, type: node.object_type || node.kind, digest: node.content_digest });
    renderGraph(state.graphData);
  };
  root.onkeydown = (event) => {
    const edgeElement = event.target.closest("[data-graph-edge]");
    if (edgeElement && ["Enter", " "].includes(event.key)) {
      event.preventDefault();
      edgeElement.click();
      return;
    }
    const element = event.target.closest("[data-graph-node]");
    if (!element) return;
    if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(event.key)) {
      event.preventDefault();
      const nodes = [...root.querySelectorAll("[data-graph-node]")];
      const index = nodes.indexOf(element);
      const step = ["ArrowRight", "ArrowDown"].includes(event.key) ? 1 : -1;
      nodes[(index + step + nodes.length) % nodes.length]?.focus();
      return;
    }
    if (!["Enter", " "].includes(event.key)) return;
    event.preventDefault();
    const node = nodeMap.get(String(element.dataset.graphNode));
    if (!node) return;
    state.graphSelectedId = String(node.id);
    addResearchContext({ id: node.id, label: node.label || node.name, type: node.object_type || node.kind, digest: node.content_digest });
    renderGraph(state.graphData);
  };

  const svg = document.getElementById("knowledge-graph-svg");
  if (!svg) return;
  let gesture = null;
  const graphPoint = (event) => {
    const bounds = svg.getBoundingClientRect();
    const screenX = (event.clientX - bounds.left) / bounds.width * 900;
    const screenY = (event.clientY - bounds.top) / bounds.height * 520;
    return { x: (screenX - state.graphTransform.x) / state.graphTransform.scale, y: (screenY - state.graphTransform.y) / state.graphTransform.scale, screenX, screenY };
  };
  svg.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    const node = event.target.closest(".graph-node-svg");
    gesture = { kind: node ? "node" : "pan", id: node?.dataset.graphNode, x: event.clientX, y: event.clientY, start: graphPoint(event), moved: false };
    svg.setPointerCapture(event.pointerId);
  });
  svg.addEventListener("pointermove", (event) => {
    if (!gesture) return;
    const dx = event.clientX - gesture.x;
    const dy = event.clientY - gesture.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) gesture.moved = true;
    if (!gesture.moved) return;
    if (gesture.kind === "node") {
      const point = graphPoint(event);
      state.graphLayout.set(String(gesture.id), { x: point.x, y: point.y });
      updateGraphSvgPositions();
    } else {
      const bounds = svg.getBoundingClientRect();
      state.graphTransform.x += dx / bounds.width * 900;
      state.graphTransform.y += dy / bounds.height * 520;
      gesture.x = event.clientX;
      gesture.y = event.clientY;
      document.getElementById("graph-viewport").setAttribute("transform", `translate(${state.graphTransform.x} ${state.graphTransform.y}) scale(${state.graphTransform.scale})`);
    }
  });
  svg.addEventListener("pointerup", (event) => {
    if (!gesture) return;
    if (gesture.moved) {
      state.graphDragging = true;
      renderGraph(state.graphData);
      window.setTimeout(() => { state.graphDragging = false; }, 0);
    }
    gesture = null;
    if (svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId);
  });
  svg.addEventListener("pointercancel", () => { gesture = null; });
  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const point = graphPoint(event);
    const oldScale = state.graphTransform.scale;
    const newScale = Math.max(.45, Math.min(2.8, oldScale * (event.deltaY < 0 ? 1.12 : .89)));
    state.graphTransform.x = point.screenX - point.x * newScale;
    state.graphTransform.y = point.screenY - point.y * newScale;
    state.graphTransform.scale = newScale;
    document.getElementById("graph-viewport").setAttribute("transform", `translate(${state.graphTransform.x} ${state.graphTransform.y}) scale(${newScale})`);
  }, { passive: false });
}

function updateGraphSvgPositions() {
  document.querySelectorAll(".graph-node-svg[data-graph-node]").forEach((element) => {
    const position = state.graphLayout.get(String(element.dataset.graphNode));
    if (position) element.setAttribute("transform", `translate(${position.x} ${position.y})`);
  });
  document.querySelectorAll(".graph-link[data-edge-source]").forEach((element) => {
    const source = state.graphLayout.get(String(element.dataset.edgeSource));
    const target = state.graphLayout.get(String(element.dataset.edgeTarget));
    if (!source || !target) return;
    element.setAttribute("x1", source.x);
    element.setAttribute("y1", source.y);
    element.setAttribute("x2", target.x);
    element.setAttribute("y2", target.y);
  });
}

function renderGraphFindResults() {
  const input = document.getElementById("graph-find");
  const results = document.getElementById("graph-find-results");
  if (!input || !results) return;
  const query = input.value.trim().toLowerCase();
  const nodes = state.graphData?.nodes || [];
  const matches = query ? nodes.filter((node) => `${node.label || node.name || ""} ${node.object_type || node.kind || ""}`.toLowerCase().includes(query)).slice(0, 8) : [];
  document.getElementById("graph-find-count").textContent = query ? `${matches.length} match${matches.length === 1 ? "" : "es"}` : "";
  results.innerHTML = matches.map((node) => `<button class="graph-find-result" type="button" role="option" data-graph-find-id="${escapeHtml(node.id)}"><strong>${escapeHtml(node.label || node.name)}</strong><span>${escapeHtml(humanize(node.object_type || node.kind || "evidence"))}</span></button>`).join("");
  results.querySelectorAll("[data-graph-find-id]").forEach((button) => {
    button.onclick = () => {
      const node = nodes.find((item) => String(item.id) === String(button.dataset.graphFindId));
      if (!node) return;
      state.graphSelectedId = String(node.id);
      addResearchContext({ id: node.id, label: node.label || node.name, type: node.object_type || node.kind, digest: node.content_digest });
      renderGraph(state.graphData);
      results.innerHTML = "";
    };
  });
}

async function replayGraphEvidence(node) {
  if (state.graphScope === "private") {
    openInspector("Private graph evidence", node.label || node.name, `<section class="detail-section"><h3>Local evidence identity</h3><dl class="detail-grid"><dt>Type</dt><dd>${escapeHtml(node.object_type || node.kind || "private evidence")}</dd><dt>Access</dt><dd>${statusBadge("private")}</dd><dt>Digest</dt><dd class="mono">${escapeHtml(node.content_digest || "Unavailable")}</dd></dl></section><p class="local-only-boundary">Private graph content remains on this Mission Control host. Open the matching source from the Library to inspect its stored text.</p>`);
    return;
  }
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
    const objectType = document.getElementById("graph-object-type").value;
    const graph = await request("/api/knowledge/graph/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scope: state.graphScope, root_ids: [rootId], mode: "neighborhood", predicates: predicate ? [predicate] : [], object_types: objectType ? [objectType] : [],
        direction: document.getElementById("graph-direction").value,
        max_depth: Number(document.getElementById("graph-depth").value), max_nodes: 100, page_size: 100,
      }),
    });
    state.graphExtent = "local";
    state.graphPath = [];
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
  return agent.presence || agent.status || "offline";
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

function showDecisionError(message) {
  const element = document.getElementById("decision-error");
  element.textContent = message;
  element.hidden = !message;
  if (message) toast(message);
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

function renderSnapshotAge() {
  const element = document.getElementById("snapshot-age");
  if (!element) return;
  if (!state.dashboardFetchedAt) {
    element.textContent = "Waiting for live state";
    return;
  }
  const age = Math.max(0, Math.floor((Date.now() - state.dashboardFetchedAt) / 1000));
  const ageLabel = age < 5 ? "just now" : `${age < 60 ? `${age}s` : `${Math.floor(age / 60)}m`} ago`;
  const provenance = state.dashboard?.provenance;
  const freshness = provenance?.freshness || "unknown";
  const sources = Object.values(provenance?.sources || {});
  const uncertain = sources.filter((item) => item.freshness === "unknown" || item.freshness === "unavailable").length;
  const stateLabel = humanize(freshness);
  const received = `received ${ageLabel}`;
  element.textContent = state.dashboardRefreshError
    ? `Refresh failed · ${stateLabel} snapshot ${received}`
    : `${stateLabel} snapshot · ${received}${uncertain ? ` · ${uncertain} source${uncertain === 1 ? "" : "s"} unverified` : ""}`;
  element.title = state.dashboardRefreshError
    || provenance?.reason
    || `Mission Control received this snapshot at ${new Date(state.dashboardFetchedAt).toLocaleString()}`;
  element.classList.toggle("snapshot-stale", freshness === "stale" || age > 45 || Boolean(state.dashboardRefreshError));
  element.classList.toggle("snapshot-unknown", freshness === "unknown" || freshness === "partial" || freshness === "unavailable");
}

function renderConnectionStatus() {
  const label = document.getElementById("health");
  const dot = document.getElementById("health-dot");
  if (state.demo) {
    label.textContent = "Demo isolated";
    dot.classList.remove("ok");
    return;
  }
  const freshness = state.dashboard?.provenance?.freshness || "unknown";
  label.textContent = freshness === "current"
    ? "Control plane reachable · sources current"
    : `Control plane reachable · source freshness ${humanize(freshness)}`;
  dot.classList.toggle("ok", freshness === "current");
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

function demoWorkflowProjection() {
  const operations = state.dashboard?.operations || [];
  return {
    schema_version: "mission-control-workflow-projection-v1",
    items: operations.map((operation) => ({
      instance_id: `operation:${operation.id}`,
      instance_kind: "operation",
      workflow: { name: operation.kind, version: null },
      state: operation.state,
      stale: operation.state === "stalled",
      title: operation.title,
      project: operation.project,
      owner: { type: operation.owner_type, id: operation.owner_id },
      machine: operation.machine,
      stages: [{ name: operation.phase, state: operation.state }],
      current_leaf: ["running", "queued", "waiting_approval", "blocked", "stalled"].includes(operation.state) ? {
        kind: "operation", id: operation.id, state: operation.state, phase: operation.phase, heartbeat_at: operation.heartbeat_at,
      } : null,
      native_backtest: null,
      entry_evidence: { digest: operation.input_digest, source_event_ids: [] },
      exit_evidence: { digest: operation.record_digest, source_event_ids: [] },
      source_event_ids: [],
      blockers: operation.error_summary ? [operation.error_summary] : [],
      retries: { retryable: Boolean(operation.retryable), attempt: null, max_attempts: null },
      terminal_outcome: ["succeeded", "failed", "cancelled"].includes(operation.state) ? operation.state : null,
      updated_at: operation.updated_at || operation.heartbeat_at,
    })),
  };
}

function demoVenueEventHistory() {
  const base = Date.now() - 38_000;
  const digest = (character) => character.repeat(64);
  const evidence = (eventCharacter) => ({
    replay_id: "c2107e96-4c87-4ca0-a09e-d1bb244cf338",
    replay_path: "/v1/execution/replays/c2107e96-4c87-4ca0-a09e-d1bb244cf338",
    receipt_id: "db0bb60f-60f8-49ad-ac26-3a25ce34894f",
    receipt_path: "/v1/research/quantitative-receipts/db0bb60f-60f8-49ad-ac26-3a25ce34894f",
    receipt_digest: digest("d"), projection_digest: digest("b"), event_digest: digest(eventCharacter), raw_reference_digest: digest("a"),
  });
  const common = { venue: "bybit", environment: "demo", account_pseudonym: "bybit-demo-71f2", instrument_id: "bybit:linear:BTCUSDT", stream: "private-orders", correction_of: null, reconciliation_id: null };
  const make = (sequence, event_type, source_kind, payload, ids = {}) => ({
    ...common, event_id: `demo-event-${sequence}`, event_type, source_kind, payload, ...ids,
    exchange_time: new Date(base + sequence * 4_000).toISOString(), observed_time: new Date(base + sequence * 4_000 + 84 + sequence * 7).toISOString(), sequence, cursor: String(sequence), evidence: evidence(String(sequence)),
  });
  const allEvents = [
    make(1, "signal_decision", "decision", { decision_domain: "signal", verdict: "enter", symbol: "BTCUSDT" }, { correlation_id: "demo-trace-024", client_order_id: null, venue_order_id: null, execution_id: null }),
    make(2, "risk_decision", "decision", { decision_domain: "risk", verdict: "allow", bounded_notional: "5.00" }, { correlation_id: "demo-trace-024", client_order_id: null, venue_order_id: null, execution_id: null }),
    make(3, "oms_command", "intent", { action: "submit", side: "buy", quantity: "0.001" }, { correlation_id: "demo-trace-024", client_order_id: "mc-demo-024", venue_order_id: null, execution_id: null }),
    make(4, "venue_acknowledgement", "order", { status: "new", side: "buy", quantity: "0.001" }, { correlation_id: "demo-trace-024", client_order_id: "mc-demo-024", venue_order_id: "venue-8f210", execution_id: null }),
    make(5, "fill", "fill", { fill_status: "partial", side: "buy", quantity: "0.0004", price: "66420.5" }, { correlation_id: "demo-trace-024", client_order_id: "mc-demo-024", venue_order_id: "venue-8f210", execution_id: "exec-a31" }),
    make(6, "fill", "fill", { fill_status: "filled", side: "buy", quantity: "0.0006", price: "66421.0" }, { correlation_id: "demo-trace-024", client_order_id: "mc-demo-024", venue_order_id: "venue-8f210", execution_id: "exec-a32" }),
    make(7, "position", "position", { quantity: "0.001", entry_price: "66420.8" }, { correlation_id: "demo-trace-024", client_order_id: "mc-demo-024", venue_order_id: "venue-8f210", execution_id: null }),
    { ...make(8, "reconciliation", "reconciliation", { positions: { "bybit:linear:BTCUSDT": "0.001" }, cash: { USDT: "99.92" } }, { correlation_id: "demo-trace-024", client_order_id: "mc-demo-024", venue_order_id: "venue-8f210", execution_id: null }), reconciliation_id: "demo-recon-024" },
  ];
  const events = state.executionEnvironment === "all" || state.executionEnvironment === "demo" ? allEvents : [];
  return {
    schema_version: "mission-control-venue-event-history-v1", generated_at: new Date().toISOString(), environment: state.executionEnvironment === "all" ? null : state.executionEnvironment, venue: null, replay_id: null, events,
    counts: { events: events.length, replays: events.length ? 1 : 0, complete_replays: events.length ? 1 : 0, legacy_summary_only_replays: 0, duplicates_suppressed: 1 },
    replay_coverage: events.length ? [{ replay_id: evidence("1").replay_id, venue: "bybit", environment: "demo", account_pseudonym: common.account_pseudonym, coverage: "complete", event_count: allEvents.length, duplicates_suppressed: 1, source_receipt_digest: evidence("1").receipt_digest, reason: null }] : [],
    claim_boundary: "Demonstration-only immutable replay. No live capital or order authority.",
  };
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
      { id: "agent-exec1", slug: "exec1-fleet-observer", display_name: "EXEC1 Fleet Observer", machine: "exec1-execution", role: "Read-only execution-host observability", status: "online", is_enabled: true, risk_ceiling: 0, capabilities: ["fleet-observation", "resource-health", "service-health"] },
      { id: "agent-exec2", slug: "exec2-lagos-fleet-observer", display_name: "EXEC2 Lagos Fleet Observer", machine: "exec2-lagos", role: "Read-only venue-host observability", status: "online", is_enabled: true, risk_ceiling: 0, capabilities: ["fleet-observation", "resource-health", "service-health"] },
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
    fleet_health: {
      generated_at: now,
      machines: [
        { machine: "vm1-developer", status: "healthy", last_observed_at: now, metrics: { cpu_utilization_percent: 12, memory_available_percent: 64, disk_used_percent: 42, cpu_pressure_avg10: 0, io_pressure_avg10: 0 }, incidents: [] },
        { machine: "vm2-deployment", status: "healthy", last_observed_at: now, metrics: { cpu_utilization_percent: 18, memory_available_percent: 71, disk_used_percent: 28, cpu_pressure_avg10: 0, io_pressure_avg10: 0, control_plane_backup_verified: true, control_plane_backup_failed: false, control_plane_backup_age_seconds: 3600 }, incidents: [] },
        { machine: "exec1-execution", status: "healthy", last_observed_at: now, metrics: { cpu_utilization_percent: 4, memory_available_percent: 82, disk_used_percent: 8, cpu_pressure_avg10: 0, io_pressure_avg10: 0 }, incidents: [] },
        { machine: "exec2-lagos", status: "healthy", last_observed_at: now, metrics: { cpu_utilization_percent: 3, memory_available_percent: 88, disk_used_percent: 6, cpu_pressure_avg10: 0, io_pressure_avg10: 0 }, incidents: [] },
      ],
    },
    operations: [
      { id: "op-rebuild", operation_key: "graph-rebuild:demo", kind: "knowledge_graph_rebuild", title: "Rebuild canonical knowledge graph", project: "systematic-research", machine: "vm2-deployment", owner_type: "service", owner_id: "swarm-api", state: "running", phase: "project-edges", progress_mode: "determinate", progress_current: 684210, progress_total: 1368759, progress_unit: "edges", heartbeat_at: now, started_at: new Date(Date.now() - 16 * 60_000).toISOString(), completed_at: null, cancellable: false, retryable: false, error_summary: null, links: {}, detail: {}, input_digest: null, record_digest: "b".repeat(64), created_at: now, updated_at: now },
      { id: "op-approval", operation_key: "task:demo-approval", kind: "infrastructure_operation", title: "Rotate the application database certificate", project: "invariance-research", machine: "vm2-deployment", owner_type: "task", owner_id: "demo-approval", state: "waiting_approval", phase: "approval", progress_mode: "indeterminate", progress_current: null, progress_total: null, progress_unit: null, heartbeat_at: now, started_at: null, completed_at: null, cancellable: false, retryable: false, error_summary: null, links: {}, detail: {}, input_digest: "c".repeat(64), record_digest: "d".repeat(64), created_at: now, updated_at: now },
      { id: "op-complete", operation_key: "task:demo-complete", kind: "research_experiment", title: "Validate the bounded BTC momentum hypothesis", project: "bulletproof_bt", machine: "vm1-developer", owner_type: "task", owner_id: "demo-complete", state: "succeeded", phase: "complete", progress_mode: "determinate", progress_current: 1, progress_total: 1, progress_unit: "task", heartbeat_at: now, started_at: new Date(Date.now() - 25 * 60_000).toISOString(), completed_at: now, cancellable: false, retryable: false, error_summary: null, links: {}, detail: {}, input_digest: "e".repeat(64), record_digest: "f".repeat(64), created_at: now, updated_at: now },
    ],
    execution_telemetry: {
      generated_at: now,
      environment: null,
      counts: { current: 1, stale: 0, degraded: 0 },
      claim_boundary: "Canonical replay evidence only. Displayed venue state grants no capital, allocation, promotion, or order authority.",
      venues: [{
        id: "replay-demo", receipt_digest: "8".repeat(64), projection_digest: "9".repeat(64), schema_digest: "7".repeat(64),
        venue: "bybit", environment: "demo", account_pseudonym: "acct-demo-7", observed_at: now, status: "current",
        projection: {
          event_count: 9, duplicate_event_count: 1, stale: false, sequence_gaps: [], reconciliation_discrepancies: [],
          event_head_digest: "6".repeat(64), fees: "0.10", funding: "-0.02", incidents: [],
          orders: [{ client_order_id: "o1", status: "filled", side: "buy", quantity: "1" }],
          fills: [{ execution_id: "f1", client_order_id: "o1", side: "buy", quantity: "1", price: "100" }],
          positions: [{ instrument_id: "bybit:linear:BTCUSDT", quantity: "0", entry_price: "0" }],
          cash: [{ asset: "USDT", balance: "1009.88" }],
          trade_episodes: [{ instrument_id: "bybit:linear:BTCUSDT", opened_at: now, closed_at: now, side: "long", quantity: "1", entry_price: "100", exit_price: "110", gross_pnl: "10", status: "closed" }],
        },
      }],
    },
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
        { id: 6, name: "EXEC1", kind: "machine" },
      ],
      edges: [
        { source: 1, target: 2, relation: "engineered_on" },
        { source: 1, target: 3, relation: "operates_on" },
        { source: 1, target: 4, relation: "directed_from" },
        { source: 5, target: 2, relation: "executed_on" },
        { source: 1, target: 6, relation: "venue_executes_on" },
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
        allowed_machines: [agentId === "agent-infra" ? "vm2-deployment" : agentId === "agent-exec1" ? "exec1-execution" : "vm1-developer"],
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
  renderSnapshotAge();
  if (!state.demo && state.overviewPollingFallback && document.visibilityState === "visible") {
    loadDashboard({ silent: true });
  }
}, 15000);
window.setInterval(() => {
  if (!state.demo && state.activeView === "work") loadConversations();
}, 10000);
window.setInterval(() => {
  if (!state.demo && state.activeView === "research") loadBacktests();
}, 15000);
document.addEventListener("visibilitychange", () => {
  if (state.demo) return;
  if (document.visibilityState === "visible") {
    state.overviewPollingFallback = true;
    startOverviewEvents();
    loadDashboard({ silent: true });
  } else {
    stopOverviewEvents();
  }
});
loadDashboard();
