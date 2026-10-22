from __future__ import annotations

import hashlib
from typing import Any


class SourceContentError(ValueError):
    pass


async def canonical_source_content(
    client: Any,
    object_id: str,
    *,
    unit: str = "line",
    start: int = 1,
    limit: int = 100,
) -> dict[str, Any]:
    """Resolve bounded canonical text through access-checked evidence lineage."""
    root = await client.research_evidence_object(object_id)
    if root.get("object_type") != "source":
        raise SourceContentError("Canonical object is not a source.")

    objects: dict[str, dict[str, Any]] = {str(root["object_id"]): root}
    frontier = [root]
    for _ in range(3):
        next_frontier: list[dict[str, Any]] = []
        for item in frontier:
            lineage = await client.research_evidence_lineage(str(item["object_id"]))
            for child in lineage.get("descendants", []):
                child_id = str(child.get("object_id", ""))
                if child_id and child_id not in objects:
                    objects[child_id] = child
                    next_frontier.append(child)
        frontier = next_frontier
        if not frontier:
            break

    scientific = sorted(
        (item for item in objects.values() if item.get("object_type") == "scientific_object"),
        key=_scientific_order,
    )
    pages: dict[int, list[dict[str, Any]]] = {}
    for item in scientific:
        payload = item.get("payload") or {}
        text = payload.get("content_text")
        if not isinstance(text, str) or not text:
            continue
        page = _positive_int((payload.get("coordinates") or {}).get("page"), 1)
        pages.setdefault(page, []).append(item)

    if unit == "page":
        full_units = [
            (page, "\n".join(str((item.get("payload") or {})["content_text"]) for item in items))
            for page, items in sorted(pages.items())
        ]
        selected_units = [item for item in full_units if item[0] >= start][:limit]
        content = "\n\n".join(value for _, value in selected_units)
        end = selected_units[-1][0] if selected_units else 0
        total = max(pages, default=0)
        next_start = next((page for page, _ in full_units if page > end), None)
    else:
        full_text = "\n".join(
            str((item.get("payload") or {})["content_text"])
            for item in scientific
            if isinstance((item.get("payload") or {}).get("content_text"), str)
            and (item.get("payload") or {}).get("content_text")
        )
        all_lines = full_text.splitlines()
        total = len(all_lines)
        end = min(total, start + limit - 1)
        content = "\n".join(all_lines[start - 1 : end]) if start <= total else ""
        next_start = end + 1 if end < total else None

    content, size_truncated = _bounded_text(content)
    citation = f"canonical:{root['object_id']}@{root['content_version']}"
    marker = "P" if unit == "page" else "L"
    citation += f"#{marker}{start}-{marker}{end}"
    artifacts = [item for item in objects.values() if item.get("object_type") == "artifact"]
    parsers = sorted(
        {
            str((item.get("payload") or {}).get("extraction_method"))
            for item in scientific
            if (item.get("payload") or {}).get("extraction_method")
        }
    )
    confidences = [
        float((item.get("payload") or {}).get("extraction_confidence"))
        for item in scientific
        if isinstance(
            (item.get("payload") or {}).get("extraction_confidence"), (int, float)
        )
    ]
    extraction_types = sorted(
        {
            str((item.get("payload") or {}).get("scientific_type"))
            for item in scientific
            if (item.get("payload") or {}).get("scientific_type")
        }
    )
    outline = _canonical_outline(scientific, pages)
    full_content = "\n".join(
        str((item.get("payload") or {}).get("content_text") or "")
        for item in scientific
    )
    payload = root.get("payload") or {}
    return {
        "schema_version": "mission-control-source-content-v1.0.0",
        "source_kind": "canonical",
        "source_id": str(root["object_id"]),
        "version": str(root["content_version"]),
        "source_digest": root["content_digest"],
        "content_digest": hashlib.sha256(full_content.encode("utf-8")).hexdigest(),
        "title": payload.get("title") or "Untitled source",
        "access_class": root.get("access_class"),
        "content": content,
        "range": {
            "unit": unit,
            "start": start,
            "end": end,
            "total": total,
            "limit": limit,
            "next_start": next_start,
            "truncated_by_size": size_truncated,
        },
        "citation": citation,
        "citations": [citation],
        "source_metadata": {
            "project": root.get("project"),
            "origin": payload.get("origin"),
            "rights": payload.get("rights"),
            "acquired_at": payload.get("acquired_at"),
            "created_at": root.get("created_at"),
        },
        "lineage": {
            "source_object_id": str(root["object_id"]),
            "scientific_object_ids": [str(item["object_id"]) for item in scientific],
            "artifact_object_ids": [str(item["object_id"]) for item in artifacts],
            "parsers": parsers,
            "scientific_types": extraction_types,
            "minimum_confidence": min(confidences) if confidences else None,
            "maximum_confidence": max(confidences) if confidences else None,
            "quality": _quality_label(confidences),
            "uncertainties": (
                []
                if confidences and min(confidences) >= 0.9
                else ["extraction_requires_source_comparison"]
            ),
        },
        "outline": outline,
        "original_assets": [
            {
                "object_id": str(item["object_id"]),
                "media_type": (item.get("payload") or {}).get("media_type"),
                "digest": item.get("content_digest"),
                "availability": "reference_only",
                "reason": "original_asset_delivery_not_configured",
            }
            for item in artifacts
        ]
        or [
            {
                "availability": "unavailable",
                "reason": "canonical_original_asset_unavailable",
            }
        ],
    }


def _scientific_order(item: dict[str, Any]) -> tuple[int, int, str]:
    coordinates = (item.get("payload") or {}).get("coordinates") or {}
    return (
        _positive_int(coordinates.get("page"), 1),
        _positive_int(coordinates.get("line_start"), 1),
        str(item.get("object_id", "")),
    )


def _positive_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed > 0 else fallback


def _bounded_text(value: str) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= 64 * 1024:
        return value, False
    return encoded[: 64 * 1024].decode("utf-8", errors="ignore"), True


def _canonical_outline(
    scientific: list[dict[str, Any]], pages: dict[int, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    sections = []
    for item in scientific:
        payload = item.get("payload") or {}
        if payload.get("scientific_type") != "section":
            continue
        coordinates = payload.get("coordinates") or {}
        text = str(payload.get("content_text") or "").splitlines()
        if text:
            sections.append(
                {
                    "label": text[0][:200],
                    "level": 1,
                    "unit": "page",
                    "position": _positive_int(coordinates.get("page"), 1),
                    "citation": str(item.get("object_id")),
                }
            )
    if sections:
        return sections[:500]
    return [
        {
            "label": f"Page {page}",
            "level": 1,
            "unit": "page",
            "position": page,
            "citation": f"P{page}",
        }
        for page in sorted(pages)[:500]
    ]


def _quality_label(confidences: list[float]) -> str:
    if not confidences:
        return "unknown"
    minimum = min(confidences)
    if minimum >= 0.98:
        return "high"
    if minimum >= 0.9:
        return "reviewed"
    return "uncertain"
