#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from swarm_worker.workspace import (
    TaskWorkspace,
    WorkspaceManager,
    WorkspaceMetadata,
    WorkspacePlan,
)

TERMINAL_STATUSES = {"succeeded", "failed", "cancelled"}


def _workspace(metadata_path: Path, metadata: WorkspaceMetadata) -> TaskWorkspace:
    attempt = metadata_path.parent.resolve()
    plan = WorkspacePlan(
        task_id=metadata.task_id,
        task_number=metadata.task_number,
        attempt_number=metadata.attempt_number,
        repository=metadata.repository,
        source_repository=metadata.source_repository,
        attempt_directory=attempt,
        workspace_repository=metadata.workspace_repository,
        logs_directory=attempt / "logs",
        artifacts_directory=attempt / "artifacts",
        metadata_path=metadata_path.resolve(),
        base_ref=metadata.base_ref,
        resolved_base_commit=metadata.resolved_base_commit,
    )
    return TaskWorkspace(plan=plan, metadata=metadata)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--older-than-days", type=int, default=30)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.older_than_days < 1:
        parser.error("--older-than-days must be positive")

    token = os.environ.get("SWARM_ORCHESTRATOR_TOKEN")
    api_url = os.environ.get("SWARM_API_URL", "").rstrip("/")
    if not token or not api_url:
        print("Protected operator environment is required.", file=sys.stderr)
        return 2
    repository_root = Path(
        os.environ.get("SWARM_REPOSITORY_ROOT", "/home/omenka/Projects")
    )
    workspace_root = Path(
        os.environ.get(
            "SWARM_WORKSPACE_ROOT",
            "/home/omenka/Projects/swarm-agent-workspaces",
        )
    )
    cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)
    manager = WorkspaceManager(repository_root, workspace_root)
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(
        base_url=api_url,
        headers=headers,
        timeout=30.0,
    ) as client:
        for metadata_path in sorted(
            workspace_root.glob("*/attempt-*/metadata.json")
        ):
            metadata = WorkspaceMetadata.model_validate_json(
                metadata_path.read_text(encoding="utf-8")
            )
            if metadata.created_at > cutoff:
                continue
            response = client.get(f"/v1/tasks/{metadata.task_id}")
            response.raise_for_status()
            status = response.json()["task"]["status"]
            if status not in TERMINAL_STATUSES:
                continue
            workspace = _workspace(metadata_path, metadata)
            action = "REMOVE" if args.apply else "CANDIDATE"
            print(
                action,
                metadata.task_id,
                metadata.task_number,
                status,
                workspace.plan.attempt_directory,
            )
            if args.apply:
                manager.cleanup(workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
