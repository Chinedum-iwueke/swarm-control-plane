from pathlib import Path

ROOT = Path(__file__).parents[1]
UNITS = (
    "invariance-swarm-alpha004-intelligence.service",
    "invariance-swarm-alpha004-researcher.service",
)


def test_alpha004_units_allow_only_disposable_workspace_bookkeeping() -> None:
    for name in UNITS:
        unit = (ROOT / "systemd" / name).read_text(encoding="utf-8")

        assert "ReadOnlyPaths=/home/omenka/Projects/swarm-control-plane" in unit
        assert (
            "ReadWritePaths=/home/omenka/Projects/swarm-agent-workspaces" in unit
        )
        assert (
            "ReadWritePaths=-/home/omenka/Projects/swarm-control-plane/"
            ".git/worktrees" in unit
        )
        assert "NoNewPrivileges=true" in unit
        assert "CapabilityBoundingSet=" in unit
