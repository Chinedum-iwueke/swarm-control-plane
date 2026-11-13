/* Read-only dispositions; pagination and evidence semantics belong to the API. */
(() => {
  const el = (id) => document.getElementById(`candidate-blockers-${id}`);
  let offset = 0, revision = 0, refreshed = 0, loading = false, pending = false;
  let signature = "";
  async function load(force = false) {
    if (state.activeView !== "research") return;
    if (!force && Date.now() - refreshed < 30000) return;
    if (loading) { pending = true; return; }
    if (state.demo) {
      el("count").textContent = "Demo: no recorded dispositions";
      el("items").innerHTML = empty("No synthetic candidate blockers supplied.");
      return;
    }
    loading = true;
    const current = revision;
    el("previous").disabled = el("next").disabled = true;
    const params = new URLSearchParams({category: el("category").value, query: el("query").value.trim(), offset});
    try {
      const page = await request(`/api/research/candidate-blockers?${params}`);
      if (current !== revision) { pending = true; return; }
      el("error").hidden = true;
      el("count").textContent = `${page.total} dispositions · ${page.items.length ? page.offset + 1 : 0}–${page.offset + page.items.length}`;
      const nextSignature = JSON.stringify(page);
      if (signature !== nextSignature) {
        const expanded = new Set([...el("items").querySelectorAll("details[open]")].map((item) => item.dataset.id));
        el("items").innerHTML = page.items.length ? page.items.map((item) => `
          <details class="candidate-blocker" data-id="${escapeHtml(item.id)}" ${expanded.has(item.id) ? "open" : ""}>
            <summary><span class="entity-primary"><strong>${escapeHtml(item.question)}</strong><span class="entity-meta">${escapeHtml(item.campaign_key)} · ${escapeHtml(humanize(item.reason))}</span></span>${statusBadge(item.status)}</summary>
            <dl class="detail-grid">
              <dt>Blocker</dt><dd>${escapeHtml(humanize(item.reason))}</dd>
              <dt>Missing evidence</dt><dd>${escapeHtml(item.missing_evidence)}</dd>
              <dt>Responsible component</dt><dd>${escapeHtml(item.responsible_component)} <small>(${escapeHtml(item.owner_basis)})</small></dd>
              <dt>Reconsider when</dt><dd>${escapeHtml(item.retry_condition)}</dd>
              <dt>Recorded</dt><dd>${escapeHtml(formatDate(item.updated_at))}</dd>
              <dt>Record scope</dt><dd>${item.status === "deferred" ? "Retained deferral history; not a claim that no successor exists" : "Current campaign blocker"}</dd>
              <dt>Trials in this disposition</dt><dd>${item.trial_count} · no scientific verdict</dd>
              <dt>Candidate</dt><dd class="mono">${escapeHtml(item.source_candidate_id)}</dd>
              <dt>Evidence</dt><dd class="mono">${item.evidence_digests.length ? item.evidence_digests.map(escapeHtml).join("<br>") : "No digest recorded in this disposition"}</dd>
            </dl>
            ${item.detail && Object.keys(item.detail).length ? `<pre>${escapeHtml(JSON.stringify(item.detail, null, 2))}</pre>` : ""}
          </details>`).join("") : empty("No candidates match this filter.");
        signature = nextSignature;
      }
      el("previous").disabled = page.offset === 0;
      el("next").disabled = !page.has_more;
      refreshed = Date.now();
    } catch (error) {
      el("count").textContent = signature ? "Last loaded data · refresh failed" : "Unavailable";
      el("error").textContent = `Candidate queue unavailable: ${error.message}`;
      el("error").hidden = false;
      refreshed = Date.now();
    } finally {
      loading = false;
      if (pending) { pending = false; load(true); }
    }
  }
  function reset() { offset = 0; revision++; load(true); }
  el("filter").addEventListener("submit", (event) => { event.preventDefault(); reset(); });
  el("category").addEventListener("change", reset);
  el("refresh").addEventListener("click", () => load(true));
  el("previous").addEventListener("click", () => { offset = Math.max(0, offset - 25); revision++; load(true); });
  el("next").addEventListener("click", () => { offset += 25; revision++; load(true); });
  window.loadCandidateBlockers = load;
  load();
})();
