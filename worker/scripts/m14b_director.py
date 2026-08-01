from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

import httpx
import yaml
from pydantic import BaseModel, ConfigDict, Field


class Candidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=10, max_length=1000)
    rationale: str = Field(min_length=10, max_length=2000)
    mechanism: str = Field(min_length=3, max_length=1000)
    data_requirements: list[str] = Field(min_length=1, max_length=20)
    falsification_conditions: list[str] = Field(min_length=1, max_length=20)
    citation_chunk_ids: list[str] = Field(min_length=1, max_length=20)
    information_value: float = Field(ge=0, le=1)
    feasibility: float = Field(ge=0, le=1)


class CandidateBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[Candidate] = Field(min_length=2, max_length=10)


def api_client(token_name: str) -> httpx.Client:
    api_url = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ[token_name]
    return httpx.Client(
        base_url=api_url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )


def qualify(args: argparse.Namespace) -> dict:
    profile = yaml.safe_load(Path(args.profile).read_text(encoding="utf-8"))
    document_keys = sorted(set(args.document_key))
    cases = [
        {
            "question": case["question"],
            "expected_document_keys": document_keys,
            "expected_terms": case["expected_terms"],
        }
        for case in profile["evaluation_cases"]
    ]
    suffix = hashlib.sha256("\n".join(document_keys).encode()).hexdigest()[:12]
    with api_client("SWARM_ORCHESTRATOR_TOKEN") as api:
        evaluation = api.post(
            "/v1/research/knowledge/evaluations",
            json={
                "evaluation_key": f"{profile['domain_key']}-{profile['version']}-{suffix}",
                "cases": cases,
                "minimum_recall": profile["activation_policy"]["minimum_recall"],
                "evaluated_by": "founder-operator",
            },
        )
        evaluation.raise_for_status()
        evaluation_document = evaluation.json()
        if not evaluation_document["passed"]:
            raise RuntimeError(
                "Domain retrieval exam failed; profile was not activated."
            )
        response = api.post(
            "/v1/research/domains",
            json={
                "domain_key": profile["domain_key"],
                "version": profile["version"],
                "title": profile["title"],
                "description": profile["description"],
                "document_keys": document_keys,
                "required_evidence_types": profile["required_source_classes"],
                "evaluation_id": evaluation_document["id"],
                "qualified_roles": profile["qualified_roles"],
                "created_by": "founder-operator",
            },
        )
        response.raise_for_status()
        return response.json()


def propose(args: argparse.Namespace) -> dict:
    with api_client("SWARM_AGENT_TOKEN") as api:
        profile_response = api.get(
            f"/v1/agent/research/intelligence/domains/{args.domain_profile_id}"
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        if profile["status"] != "active":
            raise RuntimeError("The selected domain profile is not active.")
        search = api.post(
            "/v1/agent/research/intelligence/search",
            json={"query": args.objective, "limit": 20, "evidence_types": []},
        )
        search.raise_for_status()
        evidence = search.json()
        allowed = set(profile["document_keys"])
        passages = [
            item for item in evidence["passages"] if item["document_key"] in allowed
        ]
        if len(passages) < 2:
            raise RuntimeError("Insufficient cited domain evidence for Director run.")
        batch = invoke_codex(profile, args.objective, evidence, passages)
        response = api.post(
            "/v1/agent/research/intelligence/runs",
            json={
                "domain_profile_id": profile["id"],
                "objective": args.objective,
                "candidates": [
                    item.model_dump(mode="json") for item in batch.candidates
                ],
            },
        )
        response.raise_for_status()
        return response.json()


def invoke_codex(
    profile: dict, objective: str, evidence: dict, passages: list[dict]
) -> CandidateBatch:
    codex = os.environ.get("SWARM_CODEX_BINARY", "/usr/bin/codex")
    codex_home = Path(os.environ["SWARM_CODEX_HOME"])
    model = os.environ.get("SWARM_CODEX_MODEL", "gpt-5.6-sol")
    with tempfile.TemporaryDirectory(prefix="m14b-") as temporary:
        root = Path(temporary)
        schema = root / "candidates.schema.json"
        output = root / "candidates.json"
        schema.write_text(
            json.dumps(CandidateBatch.model_json_schema()), encoding="utf-8"
        )
        context = {
            "domain": profile,
            "objective": objective,
            "passages": [
                {
                    key: item[key]
                    for key in (
                        "chunk_id",
                        "document_key",
                        "citation",
                        "text",
                    )
                }
                for item in passages
            ],
            "similar_hypotheses": evidence["similar_hypotheses"],
            "prior_failures": evidence["prior_failures"],
        }
        prompt = (
            "You are the restricted Hermes Research Intelligence Director. Propose "
            "five falsifiable systematic-research questions grounded only in the "
            "provided passages. Every candidate must cite passage chunk_id values. "
            "Prefer questions with high information value, feasible data, and low "
            "duplication with prior hypotheses. You have no execution or approval "
            f"authority.\n\n{json.dumps(context, ensure_ascii=True)}"
        )
        completed = subprocess.run(
            [
                codex,
                "exec",
                "--sandbox",
                "read-only",
                "--ephemeral",
                "--ignore-user-config",
                "--skip-git-repo-check",
                "--model",
                model,
                "--output-schema",
                str(schema),
                "--output-last-message",
                str(output),
                "-C",
                str(root),
                "-",
            ],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
            env={
                "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                "HOME": str(codex_home),
                "CODEX_HOME": str(codex_home),
                "LANG": os.environ.get("LANG", "C.UTF-8"),
            },
        )
        if completed.returncode != 0:
            raise RuntimeError("Director model invocation failed.")
        return CandidateBatch.model_validate_json(output.read_text(encoding="utf-8"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="M14B research intelligence operator")
    commands = root.add_subparsers(dest="command", required=True)
    qualification = commands.add_parser("qualify")
    qualification.add_argument("--profile", required=True)
    qualification.add_argument("--document-key", action="append", required=True)
    proposal = commands.add_parser("propose")
    proposal.add_argument("--domain-profile-id", required=True)
    proposal.add_argument("--objective", required=True)
    return root


def main() -> int:
    args = parser().parse_args()
    result = qualify(args) if args.command == "qualify" else propose(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
