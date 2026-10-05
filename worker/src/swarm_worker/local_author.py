from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

import httpx


class LocalAuthorError(RuntimeError):
    """The bounded local author failed closed."""


@dataclass(frozen=True)
class LocalAuthorPolicy:
    repository: Path
    allowed_paths: tuple[str, ...]
    context_paths: tuple[str, ...]
    max_files_changed: int
    max_diff_lines: int
    max_turns: int
    max_file_bytes: int = 512_000
    max_tool_output_chars: int = 24_000


class LocalAuthor:
    """A least-authority Ollama tool loop for repository-scoped authoring."""

    _TOOLS: ClassVar[list[dict[str, Any]]] = [
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List repository files under an allowed or context path.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a repository file within the approved boundary.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search approved repository files using a regular expression.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["pattern", "path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write one complete UTF-8 file inside an allowed path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "replace_text",
                "description": "Replace one exact text occurrence in an allowed file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "old": {"type": "string"},
                        "new": {"type": "string"},
                    },
                    "required": ["path", "old", "new"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "append_file",
                "description": "Append a bounded UTF-8 chunk to an allowed file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "git_diff",
                "description": "Inspect the current bounded working-tree diff.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_tests",
                "description": "Run focused pytest paths within the approved repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 8,
                        }
                    },
                    "required": ["paths"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Finish after inspecting the diff and running focused tests.",
                "parameters": {
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                },
            },
        },
    ]

    def __init__(
        self,
        policy: LocalAuthorPolicy,
        *,
        base_url: str,
        model: str,
        num_ctx: int,
        timeout_seconds: float,
        audit_log: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        endpoint = httpx.URL(base_url)
        if endpoint.scheme != "http" or endpoint.host not in {"127.0.0.1", "localhost"}:
            raise ValueError("Local author endpoint must be loopback HTTP.")
        self.policy = policy
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.num_ctx = num_ctx
        self._client = client or httpx.Client(timeout=timeout_seconds)
        self._owns_client = client is None
        self._audit_log = audit_log
        self._tests_ran = False
        self._tests_passed = False
        self._diff_inspected = False

    @property
    def focused_tests_passed(self) -> bool:
        return self._tests_passed

    def run(self, prompt: str) -> str:
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": (
                    "/no_think\nYou are a bounded local coding author. Work only through "
                    "the supplied "
                    "tools. Every response must contain tool calls only, with no narration or "
                    "analysis. Act immediately. Inspect relevant context before editing. Make "
                    "the smallest complete "
                    "implementation within allowed paths. Prefer exact replacement for existing "
                    "files and bounded append chunks for a long new file. You have no authority "
                    "to push, merge, "
                    "deploy, use credentials, access external networks, weaken scientific gates, "
                    "or claim test success without run_tests evidence. Call git_diff and run_tests "
                    "before finish. If the task cannot be completed safely, finish with an honest "
                    "explanation and make no speculative changes."
                ),
            },
            {
                "role": "user",
                "content": prompt + self._preloaded_context(),
            },
        ]
        try:
            for _turn in range(self.policy.max_turns):
                response = self._client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "tools": self._TOOLS,
                        "stream": False,
                        "think": False,
                        "options": {
                            "num_ctx": self.num_ctx,
                            "num_predict": 1024,
                            "num_thread": 16,
                            "temperature": 0.1,
                        },
                    },
                )
                response.raise_for_status()
                message = response.json().get("message")
                if not isinstance(message, dict):
                    raise LocalAuthorError("Local model returned no assistant message.")
                messages.append(message)
                calls = message.get("tool_calls") or []
                if not calls:
                    calls = self._serialized_tool_calls(message.get("content"))
                if not calls:
                    raise LocalAuthorError(
                        "Local model stopped without calling finish: "
                        f"{str(message.get('content', ''))[:1000]}"
                    )
                for call in calls:
                    function = call.get("function") if isinstance(call, dict) else None
                    if not isinstance(function, dict):
                        raise LocalAuthorError(
                            "Local model emitted an invalid tool call."
                        )
                    name = function.get("name")
                    arguments = function.get("arguments") or {}
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    if not isinstance(name, str) or not isinstance(arguments, dict):
                        raise LocalAuthorError(
                            "Local model emitted invalid tool arguments."
                        )
                    if name == "finish":
                        try:
                            result = self._finish(str(arguments.get("summary", "")))
                            self._audit(name, arguments, result)
                            return result
                        except LocalAuthorError as exc:
                            result = f"ERROR: {exc}"
                    else:
                        try:
                            result = self._dispatch(name, arguments)
                        except (LocalAuthorError, re.error) as exc:
                            result = f"ERROR: {exc}"
                    self._audit(name, arguments, result)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": result[: self.policy.max_tool_output_chars],
                        }
                    )
            if self._diff_inspected and self._tests_ran:
                return self._finish(
                    "Local draft retained after the bounded turn budget; "
                    f"focused_tests_passed={self._tests_passed}."
                )
            raise LocalAuthorError("Local author exceeded its bounded turn budget.")
        finally:
            if self._owns_client:
                self._client.close()

    def _preloaded_context(self) -> str:
        """Inline small exact files to avoid costly discovery turns on CPU models."""
        budget = min(self.policy.max_tool_output_chars, 24_000)
        parts: list[str] = []
        used = 0
        for relative in dict.fromkeys(
            self.policy.allowed_paths + self.policy.context_paths
        ):
            try:
                path = self._read_path(relative)
                content = path.read_text(encoding="utf-8", errors="replace")
            except (LocalAuthorError, OSError):
                continue
            block = f"\n--- {relative} ---\n{content}"
            if used + len(block) > budget:
                continue
            parts.append(block)
            used += len(block)
        if not parts:
            return ""
        return (
            "\n\nExact initial snapshots of small approved files follow. Use them "
            "directly; re-read only if a later write makes that necessary.\n"
            + "".join(parts)
        )

    def _audit(self, name: str, arguments: dict[str, Any], result: str) -> None:
        if self._audit_log is None:
            return
        safe_arguments = {
            key: value
            for key, value in arguments.items()
            if key in {"path", "paths", "pattern"}
        }
        entry = {
            "at": datetime.now(UTC).isoformat(),
            "tool": name,
            "arguments": safe_arguments,
            "result_chars": len(result),
            "error": result.startswith("ERROR:"),
        }
        self._audit_log.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
        self._audit_log.chmod(0o600)

    @staticmethod
    def _serialized_tool_calls(content: object) -> list[dict[str, object]]:
        """Accept the strict JSON tool form emitted by some local templates."""
        if not isinstance(content, str) or len(content) > 100_000:
            return []
        documents: list[object] = []
        try:
            documents = [json.loads(content)]
        except json.JSONDecodeError:
            try:
                documents = [
                    json.loads(line) for line in content.splitlines() if line.strip()
                ]
            except json.JSONDecodeError:
                return []
        calls: list[dict[str, object]] = []
        for document in documents:
            if not isinstance(document, dict):
                return []
            name = document.get("name")
            arguments = document.get("arguments")
            if not isinstance(name, str) or not isinstance(arguments, dict):
                return []
            calls.append({"function": {"name": name, "arguments": arguments}})
        return calls

    def _dispatch(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "list_files":
            requested = str(arguments.get("path", ""))
            if requested in {"", ".", "./"}:
                roots = [
                    self._read_path(prefix, allow_directory=True)
                    for prefix in dict.fromkeys(
                        self.policy.allowed_paths + self.policy.context_paths
                    )
                    if (self.policy.repository / prefix).exists()
                ]
            else:
                roots = [self._read_path(requested, allow_directory=True)]
            files = sorted(
                {
                    str(path.relative_to(self.policy.repository))
                    for root in roots
                    for path in ([root] if root.is_file() else root.rglob("*"))
                    if path.is_file() and ".git" not in path.parts
                }
            )
            return "\n".join(files[:500]) or "(no files)"
        if name == "read_file":
            path = self._read_path(str(arguments.get("path", "")))
            if path.stat().st_size > self.policy.max_file_bytes:
                raise LocalAuthorError(f"File exceeds read budget: {path.name}")
            return path.read_text(encoding="utf-8", errors="replace")
        if name == "search":
            pattern = str(arguments.get("pattern", ""))
            if len(pattern) > 300:
                raise LocalAuthorError("Search pattern exceeds budget.")
            expression = re.compile(pattern)
            root = self._read_path(str(arguments.get("path", "")), allow_directory=True)
            matches: list[str] = []
            candidates = [root] if root.is_file() else sorted(root.rglob("*"))
            for path in candidates:
                if not path.is_file() or ".git" in path.parts:
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                for number, line in enumerate(text.splitlines(), start=1):
                    if expression.search(line):
                        relative = path.relative_to(self.policy.repository)
                        matches.append(f"{relative}:{number}:{line}")
                        if len(matches) >= 200:
                            return "\n".join(matches)
            return "\n".join(matches) or "(no matches)"
        if name == "write_file":
            relative = str(arguments.get("path", ""))
            content = str(arguments.get("content", ""))
            if len(content.encode("utf-8")) > self.policy.max_file_bytes:
                raise LocalAuthorError("File write exceeds byte budget.")
            path = self._write_path(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return f"wrote {relative}"
        if name == "replace_text":
            relative = str(arguments.get("path", ""))
            old = str(arguments.get("old", ""))
            new = str(arguments.get("new", ""))
            path = self._write_path(relative)
            if not path.is_file() or not old:
                raise LocalAuthorError(
                    "Exact replacement requires an existing file and text."
                )
            content = path.read_text(encoding="utf-8")
            if content.count(old) != 1:
                raise LocalAuthorError("Exact replacement text must occur once.")
            updated = content.replace(old, new, 1)
            if len(updated.encode("utf-8")) > self.policy.max_file_bytes:
                raise LocalAuthorError("Replacement exceeds file byte budget.")
            path.write_text(updated, encoding="utf-8")
            return f"replaced text in {relative}"
        if name == "append_file":
            relative = str(arguments.get("path", ""))
            content = str(arguments.get("content", ""))
            path = self._write_path(relative)
            existing = path.read_text(encoding="utf-8") if path.is_file() else ""
            if len((existing + content).encode("utf-8")) > self.policy.max_file_bytes:
                raise LocalAuthorError("Append exceeds file byte budget.")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(content)
            return f"appended {len(content)} characters to {relative}"
        if name == "git_diff":
            self._diff_inspected = True
            result = self._run(
                ["git", "diff", "--no-ext-diff", "--", *self.policy.allowed_paths]
            )
            return result.stdout or "(no tracked diff; untracked files may exist)"
        if name == "run_tests":
            paths = arguments.get("paths")
            if not isinstance(paths, list) or not paths:
                raise LocalAuthorError("At least one focused pytest path is required.")
            safe = [self._test_path(str(item)) for item in paths]
            virtualenv = os.environ.get("VIRTUAL_ENV")
            python = (
                str(Path(virtualenv) / "bin" / "python")
                if virtualenv and (Path(virtualenv) / "bin" / "python").is_file()
                else sys.executable
            )
            result = self._run(
                [python, "-m", "pytest", "-q", *safe],
                timeout=600,
                check=False,
            )
            self._tests_ran = True
            self._tests_passed = result.returncode == 0
            output = f"exit_code={result.returncode}\n{result.stdout}\n{result.stderr}"
            return output
        raise LocalAuthorError(f"Unknown local-author tool: {name}")

    def _finish(self, summary: str) -> str:
        if not self._diff_inspected:
            raise LocalAuthorError("Local author did not inspect its diff.")
        if not self._tests_ran:
            raise LocalAuthorError("Local author did not run focused tests.")
        status = self._run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"]
        )
        changed = self._status_paths(status.stdout)
        if not changed:
            raise LocalAuthorError("Local author produced no changes.")
        if len(changed) > self.policy.max_files_changed:
            raise LocalAuthorError("Local author exceeded the changed-file budget.")
        for path in changed:
            self._write_path(path)
        diff = self._complete_diff(changed)
        if len(diff.splitlines()) > self.policy.max_diff_lines:
            raise LocalAuthorError("Local author exceeded the diff-line budget.")
        self._run(["git", "diff", "--check", "--", *changed])
        return summary.strip() or "Local author completed the bounded change."

    def _read_path(self, relative: str, *, allow_directory: bool = False) -> Path:
        path = self._resolved(relative)
        if not self._in_prefixes(
            relative, self.policy.allowed_paths + self.policy.context_paths
        ):
            raise LocalAuthorError(f"Read path is outside approved context: {relative}")
        if not path.exists() or (not allow_directory and not path.is_file()):
            raise LocalAuthorError(f"Read path does not exist: {relative}")
        return path

    def _write_path(self, relative: str) -> Path:
        path = self._resolved(relative)
        if not self._in_prefixes(relative, self.policy.allowed_paths):
            raise LocalAuthorError(f"Write path is outside approved scope: {relative}")
        return path

    def _test_path(self, relative: str) -> str:
        self._read_path(relative)
        if not (relative.startswith("tests/") or "/tests/" in relative):
            raise LocalAuthorError("run_tests accepts only repository test paths.")
        return relative

    def _resolved(self, relative: str) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
            raise LocalAuthorError(f"Unsafe repository path: {relative}")
        path = (self.policy.repository / candidate).resolve()
        if not path.is_relative_to(self.policy.repository.resolve()):
            raise LocalAuthorError(f"Repository path escapes workspace: {relative}")
        return path

    @staticmethod
    def _in_prefixes(relative: str, prefixes: tuple[str, ...]) -> bool:
        return any(
            relative == prefix or relative.startswith(f"{prefix.rstrip('/')}/")
            for prefix in prefixes
        )

    def _run(
        self,
        args: list[str],
        *,
        timeout: int = 60,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "LANG",
                "LC_ALL",
                "PATH",
                "PYTHONPATH",
                "TZ",
                "VIRTUAL_ENV",
            }
        }
        environment.update(
            {
                "HOME": str(self.policy.repository.parent),
                "NO_PROXY": "127.0.0.1,localhost",
                "PYTHONDONTWRITEBYTECODE": "1",
                "no_proxy": "127.0.0.1,localhost",
            }
        )
        return subprocess.run(
            args,
            cwd=self.policy.repository,
            check=check,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )

    @staticmethod
    def _status_paths(status: str) -> list[str]:
        entries = [item for item in status.split("\0") if item]
        paths: list[str] = []
        index = 0
        while index < len(entries):
            entry = entries[index]
            code = entry[:2]
            path = entry[3:]
            if "R" in code or "C" in code:
                index += 1
                path = entries[index]
            paths.append(path)
            index += 1
        return sorted(set(paths))

    def _complete_diff(self, changed: list[str]) -> str:
        parts: list[str] = []
        for path in changed:
            tracked = (
                self._run(
                    ["git", "ls-files", "--error-unmatch", "--", path],
                    check=False,
                ).returncode
                == 0
            )
            args = (
                ["git", "diff", "--no-ext-diff", "HEAD", "--", path]
                if tracked
                else ["git", "diff", "--no-index", "--", "/dev/null", path]
            )
            result = self._run(args, check=False)
            if result.returncode not in {0, 1}:
                raise LocalAuthorError(f"Unable to inspect diff for {path}.")
            parts.append(result.stdout)
        return "".join(parts)


def _load_policy(path: Path) -> LocalAuthorPolicy:
    document = json.loads(path.read_text(encoding="utf-8"))
    return LocalAuthorPolicy(
        repository=Path(document["repository"]),
        allowed_paths=tuple(document["allowed_paths"]),
        context_paths=tuple(document["context_paths"]),
        max_files_changed=int(document["max_files_changed"]),
        max_diff_lines=int(document["max_diff_lines"]),
        max_turns=int(document["max_turns"]),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run one bounded local authoring turn."
    )
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--num-ctx", type=int, required=True)
    parser.add_argument("--timeout-seconds", type=float, required=True)
    parser.add_argument("--output-last-message", type=Path, required=True)
    parser.add_argument("--audit-log", type=Path)
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    prompt = __import__("sys").stdin.read()
    author = LocalAuthor(
        _load_policy(args.policy),
        base_url=args.base_url,
        model=args.model,
        num_ctx=args.num_ctx,
        timeout_seconds=args.timeout_seconds,
        audit_log=args.audit_log,
    )
    try:
        summary = author.run(prompt)
    except (LocalAuthorError, httpx.HTTPError, subprocess.SubprocessError) as exc:
        print(
            f"local_author_failed: {type(exc).__name__}: {exc}",
            file=__import__("sys").stderr,
        )
        return 2
    args.output_last_message.write_text(summary + "\n", encoding="utf-8")
    args.output_last_message.chmod(0o600)
    if args.result is not None:
        args.result.write_text(
            json.dumps(
                {
                    "model": args.model,
                    "focused_tests_passed": author.focused_tests_passed,
                    "summary": summary,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        args.result.chmod(0o600)
    print(json.dumps({"event": "local_author_complete", "model": args.model}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
