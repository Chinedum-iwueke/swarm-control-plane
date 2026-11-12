import json
from pathlib import Path

STATIC_ROOT = Path(__file__).parents[1] / "src" / "hermes_mission_control" / "static"
PROJECT_ROOT = Path(__file__).parents[1]


def test_graph_explorer_exposes_bounded_scope_path_and_accessible_edge_controls() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")
    styles = (STATIC_ROOT / "styles.css").read_text(encoding="utf-8")

    for marker in (
        'data-graph-extent="global"',
        'data-graph-extent="local"',
        'id="graph-scope"',
        'id="graph-object-type"',
        'id="graph-project"',
        'id="graph-as-of"',
        'id="graph-path-form"',
        'id="graph-path-source"',
        'id="graph-path-target"',
        'id="graph-path-status"',
        'id="graph-landscape-summary"',
        '<option value="edition">Edition</option>',
        '<option value="episode">Episode</option>',
        '<option value="run">Run</option>',
        '<option value="hypothesis">Hypothesis</option>',
        '<option value="research_candidate">Research candidate</option>',
    ):
        assert marker in html

    assert 'max_nodes: 100, page_size: 100' in script
    assert 'mode: "paths"' in script
    assert "openGraphEdgeInspector" in script
    assert 'role="list" aria-label="Visible graph relationships"' in script
    assert '["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"]' in script
    assert 'window.localStorage.setItem("hermes.graph-view.v1"' in script
    assert "Projection time unavailable" in script
    assert 'request("/api/knowledge/graph/landscape"' in script
    assert "Representative sample, not corpus completeness" in script
    assert "window.InvarianceGraphLayout.layout" in script
    assert 'request(`/api/knowledge/hybrid-search?' in script
    assert 'request(`/api/knowledge/evidence/' in script
    assert 'role="group" aria-label="Filter landscape by evidence category"' in script
    assert 'data-graph-zoom="selection"' in script
    assert 'data-graph-focus="${escapeHtml(node.id)}"' in script
    assert 'aria-label="Fit selected evidence"' in script
    assert "function graphFocusSets" in script
    assert 'aria-label="Inspect directed ${escapeHtml(label)} relationship"' in script
    assert 'id="graph-presentation"' in html
    assert "function toggleGraphPresentation" in script
    assert "function replayGraphEpisode" in script
    assert 'narrative_policy' not in script  # server policy is rendered, not re-authored
    assert "No inferred causal narrative" in script
    assert "function graphEvidenceExcerpt" in script
    assert "state.graphFocusDepth + 1" in script
    assert "Recorded provenance excerpt" in script
    assert "body.graph-presentation .topbar" in styles
    assert "Synthetic demonstration. Not canonical evidence." in html
    assert ".landscape-facet:focus-visible" in styles
    assert ".graph-edge-group.dimmed, .graph-node-svg.dimmed" in styles
    assert ".graph-edge-label" in styles
    assert "prefers-reduced-motion: reduce" in styles
    assert (STATIC_ROOT / "vendor" / "knowledge-layout.js").exists()

    package = json.loads((PROJECT_ROOT / "package.json").read_text(encoding="utf-8"))
    assert package["dependencies"]["d3-force"] == "3.0.1"
    assert package["devDependencies"]["esbuild"] == "0.28.2"


def test_renderer_benchmark_and_decision_are_reproducible_and_pinned() -> None:
    harness = PROJECT_ROOT / "benchmarks" / "graph-renderers"
    run_script = (harness / "run.sh").read_text(encoding="utf-8")
    decision = (PROJECT_ROOT / "MCUX-016_GRAPH_RENDERER_DECISION.md").read_text(
        encoding="utf-8"
    )

    assert "cytoscape@3.34.4" in run_script
    assert (harness / "fixture.js").exists()
    assert (harness / "benchmark.html").exists()
    assert (harness / "result.json").exists()
    assert "Retain the dependency-free SVG renderer" in decision
    assert "does not claim Obsidian parity" in decision


def test_landscape_renderer_benchmark_meets_bounded_interaction_budget() -> None:
    result = json.loads(
        (
            PROJECT_ROOT
            / "benchmarks"
            / "knowledge-landscape"
            / "renderer-result.json"
        ).read_text(encoding="utf-8")
    )

    assert result["fixture"] == {"nodes": 100, "edges": 121, "object_types": 9}
    assert result["cold_layout_ms"]["p95"] < 100
    assert result["warm_rerender_ms"]["p95"] < 50
    assert result["keyboard_nodes"] == 100
    assert result["deterministic_layout"] is True
    assert result["mobile_viewport"]["horizontal_overflow"] is False
    focus = result["evidence_focus_verification"]
    assert focus["surface"] == "explicitly-labelled-synthetic-demo"
    assert focus["unrelated_nodes_dimmed"] == 4
    assert focus["unrelated_edges_dimmed"] == 4
    assert focus["fit_to_selection_scale"] == 1.55
    assert focus["keyboard_traversal"] is True
