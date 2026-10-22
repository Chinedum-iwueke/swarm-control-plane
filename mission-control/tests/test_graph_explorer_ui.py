from pathlib import Path


STATIC_ROOT = Path(__file__).parents[1] / "src" / "hermes_mission_control" / "static"
PROJECT_ROOT = Path(__file__).parents[1]


def test_graph_explorer_exposes_bounded_scope_path_and_accessible_edge_controls() -> None:
    html = (STATIC_ROOT / "index.html").read_text(encoding="utf-8")
    script = (STATIC_ROOT / "app.js").read_text(encoding="utf-8")

    for marker in (
        'data-graph-extent="global"',
        'data-graph-extent="local"',
        'id="graph-scope"',
        'id="graph-object-type"',
        'id="graph-path-form"',
        'id="graph-path-source"',
        'id="graph-path-target"',
        'id="graph-path-status"',
    ):
        assert marker in html

    assert 'max_nodes: 100, page_size: 100' in script
    assert 'mode: "paths"' in script
    assert "openGraphEdgeInspector" in script
    assert 'role="list" aria-label="Visible graph relationships"' in script
    assert '["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"]' in script
    assert 'window.localStorage.setItem("hermes.graph-view.v1"' in script
    assert "Projection time unavailable" in script


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
