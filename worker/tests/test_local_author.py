from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from swarm_worker.local_author import LocalAuthor, LocalAuthorError, LocalAuthorPolicy


class Response:
    def __init__(self, message: dict) -> None:
        self._message = message

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"message": self._message}


class Client:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = messages
        self.requests: list[dict] = []

    def post(self, _url: str, *, json: dict) -> Response:
        self.requests.append(json)
        return Response(self.messages.pop(0))


def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repository"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(
        ["git", "config", "user.email", "worker@example.invalid"],
        cwd=repo,
        check=True,
    )
    subprocess.run(["git", "config", "user.name", "Worker Test"], cwd=repo, check=True)
    (repo / "src").mkdir()
    (repo / "tests").mkdir()
    (repo / "src" / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "tests" / "test_value.py").write_text(
        "from src.value import VALUE\n\ndef test_value():\n    assert VALUE == 2\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "base"], cwd=repo, check=True)
    return repo


def policy(repo: Path) -> LocalAuthorPolicy:
    return LocalAuthorPolicy(
        repository=repo,
        allowed_paths=("src", "tests"),
        context_paths=("src", "tests"),
        max_files_changed=2,
        max_diff_lines=30,
        max_turns=6,
    )


def call(name: str, arguments: dict) -> dict:
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": name, "arguments": arguments}}],
    }


def test_local_author_writes_tests_and_finishes_with_bounded_tools(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    client = Client(
        [
            call("read_file", {"path": "src/value.py"}),
            call("write_file", {"path": "src/value.py", "content": "VALUE = 2\n"}),
            call("git_diff", {}),
            call("run_tests", {"paths": ["tests/test_value.py"]}),
            call("finish", {"summary": "Updated and verified the value."}),
        ]
    )
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=client,
    )

    summary = author.run("Make the test pass.")

    assert summary == "Updated and verified the value."
    assert (repo / "src" / "value.py").read_text() == "VALUE = 2\n"
    assert all(request["stream"] is False for request in client.requests)
    assert all(request["options"]["temperature"] == 0.1 for request in client.requests)
    assert all(request["options"]["num_predict"] == 1024 for request in client.requests)
    assert all(request["options"]["num_thread"] == 16 for request in client.requests)
    assert client.requests[0]["messages"][0]["content"].startswith("/no_think")
    assert "tool calls only" in client.requests[0]["messages"][0]["content"]


def test_local_author_rejects_write_outside_scope(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=Client(
            [
                call("write_file", {"path": "secret.env", "content": "x"}),
                {"role": "assistant", "content": "unsafe request rejected"},
            ]
        ),
    )

    with pytest.raises(LocalAuthorError, match="unsafe request rejected"):
        author.run("Escape scope.")
    assert not (repo / "secret.env").exists()


def test_local_author_requires_diff_and_test_evidence(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=Client(
            [
                call("write_file", {"path": "src/value.py", "content": "VALUE = 2\n"}),
                call("finish", {"summary": "done"}),
                {"role": "assistant", "content": "verification missing"},
            ]
        ),
    )

    with pytest.raises(LocalAuthorError, match="stopped without calling finish"):
        author.run("Skip verification.")


def test_local_author_rejects_non_test_execution_path(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=Client(
            [
                call("run_tests", {"paths": ["src/value.py"]}),
                {"role": "assistant", "content": "test path rejected"},
            ]
        ),
    )

    with pytest.raises(LocalAuthorError, match="test path rejected"):
        author.run("Run arbitrary code.")


def test_local_author_accepts_strict_serialized_tool_call(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    client = Client(
        [
            call("write_file", {"path": "src/value.py", "content": "VALUE = 2\n"}),
            call("git_diff", {}),
            call("run_tests", {"paths": ["tests/test_value.py"]}),
            {
                "role": "assistant",
                "content": '{"name":"finish","arguments":{"summary":"verified"}}',
            },
        ]
    )
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=client,
    )

    assert author.run("Use serialized tool form.") == "verified"


def test_local_author_accepts_json_lines_tool_batch(tmp_path: Path) -> None:
    calls = LocalAuthor._serialized_tool_calls(
        '{"name":"git_diff","arguments":{}}\n'
        '{"name":"run_tests","arguments":{"paths":["tests/test_value.py"]}}'
    )

    assert [item["function"]["name"] for item in calls] == [
        "git_diff",
        "run_tests",
    ]


def test_root_listing_only_exposes_approved_context(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    (repo / "secret.env").write_text("secret", encoding="utf-8")
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=Client([]),
    )

    listing = author._dispatch("list_files", {"path": "."})

    assert "src/value.py" in listing
    assert "tests/test_value.py" in listing
    assert "secret.env" not in listing


def test_local_author_rejects_non_loopback_endpoint(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="loopback HTTP"):
        LocalAuthor(
            policy(repository(tmp_path)),
            base_url="https://untrusted.example",
            model="test",
            num_ctx=8192,
            timeout_seconds=5,
            client=Client([]),
        )


def test_replace_and_append_stay_inside_write_scope(tmp_path: Path) -> None:
    repo = repository(tmp_path)
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=Client([]),
    )

    assert "replaced" in author._dispatch(
        "replace_text", {"path": "src/value.py", "old": "VALUE = 1", "new": "VALUE = 2"}
    )
    assert "appended" in author._dispatch(
        "append_file", {"path": "src/value.py", "content": "FLAG = True\n"}
    )
    assert (repo / "src/value.py").read_text() == "VALUE = 2\nFLAG = True\n"
    with pytest.raises(LocalAuthorError, match="outside approved scope"):
        author._dispatch("append_file", {"path": "secret.env", "content": "TOKEN=x\n"})


def test_subprocess_environment_excludes_worker_credentials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = repository(tmp_path)
    monkeypatch.setenv("SWARM_AGENT_TOKEN", "must-not-reach-tests")
    monkeypatch.setenv("CODEX_HOME", "/sensitive/codex")
    (repo / "tests" / "test_environment.py").write_text(
        "import os\n\n"
        "def test_credentials_are_absent():\n"
        "    assert 'SWARM_AGENT_TOKEN' not in os.environ\n"
        "    assert 'CODEX_HOME' not in os.environ\n",
        encoding="utf-8",
    )
    author = LocalAuthor(
        policy(repo),
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        client=Client([]),
    )

    result = author._dispatch("run_tests", {"paths": ["tests/test_environment.py"]})

    assert "exit_code=0" in result


def test_small_exact_files_are_preloaded_and_audit_omits_content(
    tmp_path: Path,
) -> None:
    repo = repository(tmp_path)
    audit = tmp_path / "audit.jsonl"
    exact_policy = LocalAuthorPolicy(
        repository=repo,
        allowed_paths=("src/value.py",),
        context_paths=("tests/test_value.py",),
        max_files_changed=1,
        max_diff_lines=30,
        max_turns=6,
    )
    client = Client(
        [
            call("write_file", {"path": "src/value.py", "content": "VALUE = 2\n"}),
            call("git_diff", {}),
            call("run_tests", {"paths": ["tests/test_value.py"]}),
            call("finish", {"summary": "verified"}),
        ]
    )
    author = LocalAuthor(
        exact_policy,
        base_url="http://127.0.0.1:11434",
        model="test",
        num_ctx=8192,
        timeout_seconds=5,
        audit_log=audit,
        client=client,
    )

    assert author.run("Repair the producer.") == "verified"
    initial = client.requests[0]["messages"][1]["content"]
    assert "--- src/value.py ---" in initial
    assert "--- tests/test_value.py ---" in initial
    entries = [
        __import__("json").loads(line) for line in audit.read_text().splitlines()
    ]
    assert [entry["tool"] for entry in entries] == [
        "write_file",
        "git_diff",
        "run_tests",
        "finish",
    ]
    assert "content" not in entries[0]["arguments"]
