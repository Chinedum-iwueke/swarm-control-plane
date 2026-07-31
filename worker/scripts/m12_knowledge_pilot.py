from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "worker"
HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def chunks(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    sections: list[dict[str, Any]] = []
    heading = "Document"
    start = 1
    body: list[str] = []
    ordinal = 0

    def emit(end: int) -> None:
        nonlocal ordinal, body
        passage = "\n".join(body).strip()
        if passage:
            sections.append(
                {
                    "ordinal": ordinal,
                    "section": heading,
                    "page": None,
                    "line_start": start,
                    "line_end": end,
                    "text": passage,
                    "text_digest": digest(passage.encode()),
                    "metadata": {"format": "markdown"},
                }
            )
            ordinal += 1
        body = []

    for number, line in enumerate(lines, 1):
        match = HEADING.match(line)
        if match:
            emit(number - 1)
            heading = match.group(2)
            start = number
        body.append(line)
    emit(len(lines))
    return sections


def pdf_chunks(path: Path) -> list[dict[str, Any]]:
    completed = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    passages = []
    line_cursor = 1
    for ordinal, page_text in enumerate(completed.stdout.split("\f")):
        passage = page_text.strip()
        if not passage:
            continue
        page_lines = passage.splitlines()
        heading = next(
            (line.strip() for line in page_lines if line.strip()),
            f"Page {ordinal + 1}",
        )
        passages.append(
            {
                "ordinal": len(passages),
                "section": heading[:500],
                "page": ordinal + 1,
                "line_start": line_cursor,
                "line_end": line_cursor + len(page_lines) - 1,
                "text": passage,
                "text_digest": digest(passage.encode()),
                "metadata": {"format": "pdf", "page_exact": "true"},
            }
        )
        line_cursor += len(page_lines)
    return passages


def client() -> httpx.Client:
    url = os.environ["SWARM_API_URL"].rstrip("/")
    token = os.environ["SWARM_ORCHESTRATOR_TOKEN"]
    return httpx.Client(
        base_url=url, headers={"Authorization": f"Bearer {token}"}, timeout=30
    )


def ingest(api: httpx.Client) -> dict[str, Any]:
    manifest = json.loads((WORKER / "knowledge/m12-corpus.json").read_text())
    output = []
    for item in manifest["documents"]:
        path = ROOT / item["path"]
        content = path.read_bytes()
        payload = {
            **{
                key: value
                for key, value in item.items()
                if key not in {"path", "format"}
            },
            "version": digest(content)[:16],
            "source_uri": item["path"],
            "content_digest": digest(content),
            "metadata": {
                "repository": "swarm-control-plane",
                "format": item["format"],
            },
            "ingested_by": "research-librarian",
        }
        response = api.post("/v1/research/knowledge/documents", json=payload)
        response.raise_for_status()
        document = response.json()
        passages = (
            pdf_chunks(path) if item["format"] == "pdf" else chunks(content.decode())
        )
        for passage in passages:
            chunk_response = api.post(
                f"/v1/research/knowledge/documents/{document['id']}/chunks",
                json=passage,
            )
            chunk_response.raise_for_status()
        output.append(
            {
                "document_key": item["document_key"],
                "document_id": document["id"],
                "chunk_count": len(passages),
            }
        )
    return {"documents": output, "deferred_sources": manifest["deferred_sources"]}


def evaluate(api: httpx.Client) -> dict[str, Any]:
    payload = json.loads((WORKER / "knowledge/m12-evaluation.json").read_text())
    payload["evaluated_by"] = "retrieval-evaluator"
    response = api.post("/v1/research/knowledge/evaluations", json=payload)
    response.raise_for_status()
    result = response.json()
    if not result["passed"]:
        raise RuntimeError("M12 fixed retrieval evaluation failed")
    return result


def pilot(api: httpx.Client) -> dict[str, Any]:
    question = "Why must Invariance retain negative trials and use independent review?"
    search = api.post(
        "/v1/research/knowledge/search", json={"query": question, "limit": 8}
    )
    search.raise_for_status()
    result = search.json()
    governing = next(
        (
            passage
            for passage in result["passages"]
            if passage["evidence_type"] == "governing_requirement"
        ),
        None,
    )
    prior = next(
        (
            passage
            for passage in result["passages"]
            if passage["evidence_type"] == "prior_result"
        ),
        None,
    )
    if governing is None or prior is None:
        raise RuntimeError("Pilot retrieval did not return both required evidence classes")
    payload = {
        "question": question,
        "summary": "Negative evidence must remain part of institutional memory, and research promotion requires review separated from execution.",
        "claims": [
            {
                "text": "The operating model requires failed and negative research outcomes to remain auditable.",
                "evidence_class": "source_passage",
                "citation_chunk_ids": [governing["chunk_id"]],
            },
            {
                "text": "M11 enforces an independent review boundary before a result decision is recorded.",
                "evidence_class": "prior_result",
                "citation_chunk_ids": [prior["chunk_id"]],
            },
            {
                "text": "This combination should reduce repeated dead-end research, but that benefit remains an inference until measured.",
                "evidence_class": "agent_inference",
                "citation_chunk_ids": [],
            },
        ],
        "created_by": "research-intelligence-agent",
    }
    response = api.post("/v1/research/knowledge/briefs", json=payload)
    response.raise_for_status()
    return {"search": result, "brief": response.json()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("ingest", "evaluate", "pilot", "all"))
    args = parser.parse_args()
    with client() as api:
        result: dict[str, Any] = {}
        if args.command in {"ingest", "all"}:
            result["ingestion"] = ingest(api)
        if args.command in {"evaluate", "all"}:
            result["evaluation"] = evaluate(api)
        if args.command in {"pilot", "all"}:
            result["pilot"] = pilot(api)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
