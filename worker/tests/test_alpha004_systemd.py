from pathlib import Path

ROOT = Path(__file__).parents[1]
UNITS = (
    "invariance-swarm-alpha004-intelligence.service",
    "invariance-swarm-alpha004-researcher.service",
    "invariance-swarm-alpha004-representation.service",
)


def test_alpha004_units_allow_only_disposable_workspace_bookkeeping() -> None:
    for name in UNITS:
        unit = (ROOT / "systemd" / name).read_text(encoding="utf-8")

        assert "ReadOnlyPaths=/home/omenka/Projects/swarm-control-plane" in unit
        assert "ReadWritePaths=/home/omenka/Projects/swarm-agent-workspaces" in unit
        assert (
            "ReadWritePaths=-/home/omenka/Projects/swarm-control-plane/"
            ".git/worktrees" in unit
        )
        assert "NoNewPrivileges=true" in unit
        assert "CapabilityBoundingSet=" in unit
        assert "ProtectSystem=strict" in unit
        assert "BindReadOnlyPaths=" not in unit
        assert "ReadWritePaths=/etc/invariance-swarm/codex-worker" not in unit
        assert (
            "ReadWritePaths=/var/lib/invariance-swarm/codex-discovery-runtime" in unit
        )
        assert unit.index(
            "EnvironmentFile=/etc/invariance-swarm/codex-discovery-runtime.env"
        ) > unit.index("EnvironmentFile=/etc/invariance-swarm/alpha004-")


def test_runtime_installer_seeds_writable_isolated_credentials_once():
    source = (ROOT / "systemd/install-alpha004-research-agents.sh").read_text()
    assert 'if [[ ! -s "$runtime/auth.json" ]]' in source
    assert "codex-worker/auth.json" in source
    assert 'chown omenka:omenka "$runtime/auth.json"' in source
    assert 'test ! -L "$runtime"' in source
    assert 'test ! -L "$runtime/auth.json"' in source


def test_discovery_director_has_single_named_runtime_lifecycle() -> None:
    unit = (
        ROOT / "systemd/invariance-swarm-alpha-discovery-director.service"
    ).read_text(encoding="utf-8")
    runtime_name = "invariance-swarm-alpha-discovery-director-runtime"

    assert f"ExecStartPre=-/usr/bin/docker rm -f {runtime_name}" in unit
    assert f"--name {runtime_name} api python -m app.workers.alpha_discovery" in unit
    assert f"ExecStop=-/usr/bin/docker stop --timeout 30 {runtime_name}" in unit
    assert f"ExecStopPost=-/usr/bin/docker rm -f {runtime_name}" in unit

    installer = (
        ROOT / "systemd/install-alpha-discovery-director.sh"
    ).read_text(encoding="utf-8")
    assert 'index($0, "app.workers.alpha_discovery")' in installer
    assert 'docker rm -f "${legacy_directors[@]}"' in installer
    assert "grep -c 'app.workers.alpha_discovery'" in installer
    assert 'systemctl restart "$unit"' in installer
    assert 'systemctl enable --now "$unit"' not in installer
