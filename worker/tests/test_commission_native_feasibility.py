from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest

from test_native_requirements_feasibility import contract


@pytest.mark.parametrize("bad_parent", [False, True])
def test_live_commissioning_is_parent_bound_and_reuses_exact_task(tmp_path, monkeypatch, bad_parent):
    path = Path(__file__).parents[1] / "scripts/commission_native_feasibility.py"
    spec = importlib.util.spec_from_file_location("commission_native_feasibility", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = contract()
    old.pop("feasibility_evidence")
    parent = {"id": "parent", "project": "bulletproof-bt", "task_type": "alpha_data_admission",
              "status": "succeeded", "input_contract": old,
              "required_capabilities": ["alpha-data-admission"], "allowed_machines": ["vm1-developer"]}
    review = {"input_contract": {"subject": {"producer_task_id": "other" if bad_parent else "parent", "source_commit": "a" * 40},
              "qualification": {"card": {}, "artifact_bundle": {"representation_plan": old["representation_plan"],
                 "validation_requirements": {}, "dataset_bindings": [], "window": {}}}}}
    before = deepcopy(parent)
    tasks, posts = {}, []

    def respond(request):
        if request.method == "POST":
            payload = json.loads(request.content)
            posts.append(payload)
            tasks["created"] = payload | {"id": "created", "status": "queued", "plan_digest": "c" * 64}
            return httpx.Response(201, json=tasks["created"])
        if request.url.path == "/v1/tasks":
            assert request.url.params["compact"] == "true"
            return httpx.Response(200, json=[{"id": item["id"], "task_number": item["task_number"]} for item in tasks.values()])
        key = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json={"task": {"parent": parent, "review": review, **tasks}[key]})

    original_client = httpx.Client
    monkeypatch.setattr(module.httpx, "Client", lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(respond)))
    monkeypatch.setattr(module.subprocess, "run", lambda *args, **kwargs: None)
    monkeypatch.setenv("SWARM_API_URL", "http://test")
    monkeypatch.setenv("SWARM_ORCHESTRATOR_TOKEN", "test-only-token")
    output = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", [str(path), "--parent-task-id", "parent", "--review-task-id", "review",
        "--source-commit", "b" * 40, "--repository", str(tmp_path), "--output", str(output),
        "--reason", "Founder-authorized no-capital native gate commissioning"])
    if bad_parent:
        with pytest.raises(ValueError, match="not bound"):
            module.main()
        assert not posts
        return
    module.main()
    module.main()
    assert len(posts) == 1
    assert parent == before
    assert posts[0]["risk_level"] == 0 and posts[0]["max_attempts"] == 1
    assert posts[0]["parent_task_id"] == "parent"
    assert posts[0]["input_contract"]["source_commit"] == "b" * 40
    assert output.stat().st_mode & 0o777 == 0o600
    assert json.loads(output.read_text())["scientific_certification"] is False
