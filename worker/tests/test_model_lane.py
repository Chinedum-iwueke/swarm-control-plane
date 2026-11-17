import pytest

from swarm_worker.model_lane import provider_key, route_command, worker_providers


def test_default_subscription_does_not_inject_api_credentials(monkeypatch):
    monkeypatch.delenv("SWARM_OPENAI_BILLING_LANE", raising=False)
    env = {"CODEX_HOME": "/subscription"}
    assert provider_key() == "codex"
    assert route_command(["codex", "exec", "hello"], env) == ("codex", "exec", "hello")
    assert env == {"CODEX_HOME": "/subscription"}
    assert worker_providers(["alpha_discovery"]) == ["codex"]
    assert worker_providers(["alpha_research"]) == []


def test_api_lane_requires_separate_home_and_key(monkeypatch, tmp_path):
    monkeypatch.setenv("SWARM_OPENAI_BILLING_LANE", "api")
    monkeypatch.delenv("SWARM_OPENAI_API_KEY_FILE", raising=False)
    with pytest.raises(ValueError):
        route_command(["codex", "exec"], {"CODEX_HOME": "/subscription"})
    key = tmp_path / "key"
    key.write_text("test-secret")
    monkeypatch.setenv("SWARM_OPENAI_API_KEY_FILE", str(key))
    monkeypatch.setenv("SWARM_OPENAI_API_CODEX_HOME", "/api-only")
    env = {"CODEX_HOME": "/subscription"}
    command = route_command(["codex", "exec", "hello"], env)
    assert provider_key() == "openai-api"
    assert "test-secret" not in " ".join(command)
    assert env["CODEX_HOME"] == "/api-only"
    assert env["INVARIANCE_OPENAI_API_KEY"] == "test-secret"
    deterministic = {}
    assert route_command(["pytest"], deterministic) == ("pytest",)
    assert deterministic == {}


def test_unknown_lane_fails_closed():
    with pytest.raises(ValueError):
        provider_key({"SWARM_OPENAI_BILLING_LANE": "free-fallback"})


@pytest.mark.asyncio
@pytest.mark.parametrize("allowed", [True, False])
async def test_call_gate_obeys_control_plane(monkeypatch, allowed):
    import httpx

    from swarm_worker.model_lane import model_call_allowed

    monkeypatch.setenv("SWARM_API_URL", "https://control.invalid/v1")
    monkeypatch.setenv("SWARM_AGENT_TOKEN", "test-token")

    def respond(request):
        assert request.url.path == "/v1/agent/provider-capacity/codex/permit"
        return httpx.Response(200, json={"allowed": allowed})

    client = httpx.AsyncClient(transport=httpx.MockTransport(respond))
    monkeypatch.setattr("swarm_worker.model_lane.httpx.AsyncClient", lambda **_: client)
    assert await model_call_allowed() is allowed


@pytest.mark.asyncio
async def test_call_gate_fails_closed_when_control_plane_is_unavailable(monkeypatch):
    import httpx

    from swarm_worker.model_lane import model_call_allowed

    monkeypatch.setenv("SWARM_API_URL", "https://control.invalid")
    monkeypatch.setenv("SWARM_AGENT_TOKEN", "test-token")
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(503))
    )
    monkeypatch.setattr("swarm_worker.model_lane.httpx.AsyncClient", lambda **_: client)
    assert await model_call_allowed() is False


@pytest.mark.asyncio
async def test_capacity_permit_preserves_server_recovery_revision(monkeypatch):
    import httpx
    from swarm_worker.model_lane import model_capacity_permit

    monkeypatch.setenv('SWARM_API_URL', 'https://control.invalid')
    monkeypatch.setenv('SWARM_AGENT_TOKEN', 'test-token')
    client = httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={'allowed': True, 'recovery_token': 'codex:record:3:closed'})))
    monkeypatch.setattr('swarm_worker.model_lane.httpx.AsyncClient', lambda **_: client)
    assert await model_capacity_permit() == {'allowed': True, 'recovery_token': 'codex:record:3:closed'}
