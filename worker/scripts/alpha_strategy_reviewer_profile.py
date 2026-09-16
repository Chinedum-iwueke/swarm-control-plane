#!/usr/bin/env python3
"""Register a review-only profile for an already signed, deployed worker identity."""

import argparse
import json
import os
from pathlib import Path

import httpx

ROLES = {"spec": "strategy_spec", "causality": "causality_leakage"}


def ensure_profile(client, state, role, provider, model_family):
    kind = ROLES[role]
    if state["slug"] != f"vm1-alpha-{role}-reviewer":
        raise ValueError("Worker state does not match the selected reviewer role")
    payload = {
        "agent_id": state["agent_id"],
        "profile_version": "1.0.0",
        "review_kinds": [kind],
        "capabilities": [f"alpha-strategy-review-{kind}"],
        "provider": provider,
        "model_family": model_family,
        "context_group": f"alpha-independent-{role}-reviewer-v1",
        "registered_by": "founder-operator",
    }

    def matching():
        response = client.get("/v1/evaluator-routing/profiles")
        response.raise_for_status()
        return [
            item
            for item in response.json()
            if item["agent_id"] == state["agent_id"]
            and item["profile_version"] == payload["profile_version"]
        ]

    matches = matching()
    if not matches:
        response = client.post("/v1/evaluator-routing/profiles", json=payload)
        if response.status_code == 409:
            matches = matching()
            if not matches:
                response.raise_for_status()
        else:
            response.raise_for_status()
            matches = [response.json()]
    if len(matches) != 1:
        raise RuntimeError("Reviewer profile identity is ambiguous")
    profile = matches[0]
    if (
        any(profile.get(key) != value for key, value in payload.items())
        or profile.get("status") != "active"
        or profile.get("machine") != "vm1-developer"
        or profile.get("package_id") != state["package_id"]
        or profile.get("package_digest") != state["manifest_digest"]
    ):
        raise RuntimeError(
            "Existing reviewer profile differs from the deployed identity"
        )
    return profile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--role", choices=ROLES, required=True)
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model-family", required=True)
    args = parser.parse_args()
    if args.state.stat().st_mode & 0o077:
        raise RuntimeError("Reviewer state must not be group/world accessible")
    state = json.loads(args.state.read_text(encoding="utf-8"))
    base = os.environ["SWARM_API_URL"].rstrip("/").removesuffix("/v1")
    with httpx.Client(
        base_url=base,
        timeout=60,
        headers={"Authorization": f"Bearer {os.environ['SWARM_ORCHESTRATOR_TOKEN']}"},
    ) as client:
        profile = ensure_profile(
            client, state, args.role, args.provider, args.model_family
        )
    print(
        json.dumps(
            {
                "profile_id": profile["id"],
                "agent_id": profile["agent_id"],
                "profile_digest": profile["profile_digest"],
                "review_kinds": profile["review_kinds"],
                "action_authority": False,
            }
        )
    )


if __name__ == "__main__":
    main()
