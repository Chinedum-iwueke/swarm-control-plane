from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_strategy_engineers_default_to_codex_with_persistent_provider_selector() -> None:
    for name in (
        "invariance-swarm-alpha-strategy-engineer.service",
        "invariance-swarm-alpha-strategy-engineer@.service",
    ):
        unit = (ROOT / "systemd" / name).read_text(encoding="utf-8")
        assert "Environment=SWARM_ENGINEERING_AUTHOR_PROVIDER=codex" in unit
        assert "EnvironmentFile=-/etc/invariance-swarm/strategy-author-provider.env" in unit
        assert "Environment=SWARM_COPILOT_MODEL=auto" in unit
        assert "Environment=SWARM_COPILOT_CODEX_FALLBACK=true" in unit
        assert "ReadWritePaths=/var/lib/invariance-swarm/copilot-author-runtime" in unit
        assert "NoNewPrivileges=true" in unit
        assert "CapabilityBoundingSet=" in unit


def test_installer_requires_authenticated_dedicated_copilot_runtime() -> None:
    installer = (ROOT / "systemd/install-alpha-strategy-engineer.sh").read_text(
        encoding="utf-8"
    )
    assert "/usr/local/bin/copilot login --device-code" in installer
    assert 'test "$copilot_version" = 1.0.105' in installer
    assert "codex_credential_source=/home/omenka/.codex/auth.json" in installer
    assert "/etc/invariance-swarm/codex-worker/auth.json" not in installer
    assert "production-parity rehearsal" in installer
    assert "copilot-hybrid-runtime/config.json" in installer
    assert 'chmod 0600 "$copilot_runtime/config.json"' in installer
    assert 'author_provider="${SWARM_ENGINEERING_AUTHOR_PROVIDER:-codex}"' in installer
    assert 'if [[ "$author_provider" = copilot ]]; then' in installer
    assert '--setenv="SWARM_ENGINEERING_AUTHOR_PROVIDER=$author_provider"' in installer
    assert "codex|copilot|ollama)" in installer
    assert "SWARM_COPILOT_CODEX_FALLBACK=true" in installer
    assert (
        "ReadWritePaths=/var/lib/invariance-swarm/copilot-author-runtime" in installer
    )
