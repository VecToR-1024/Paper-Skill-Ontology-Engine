from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from event_log import load_yaml


SEARCH_PROVIDERS = {
    "semantic_scholar",
    "crossref",
    "arxiv",
    "openalex",
    "manual",
    "web",
    "other",
}

SEARCH_STATUSES = {"succeeded", "partial", "failed"}

WORK_FIELDS = {
    "provider_work_id",
    "title",
    "authors",
    "year",
    "venue",
    "doi",
    "arxiv_id",
    "uri",
    "abstract",
    "metadata_quality",
    "metadata_source_uri",
    "metadata_retrieved_at",
}

RESULT_FIELDS = {"rank", "score", "snippet"}


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def sha1_short(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def clean_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, list):
        value = "; ".join(str(item).strip() for item in value if str(item).strip())
    text = str(value).strip()
    return text or None


def maybe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def maybe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_provider(value: Any) -> str:
    provider = clean_string(value) or "manual"
    normalized = provider.lower().replace("-", "_").replace(" ", "_")
    if normalized not in SEARCH_PROVIDERS:
        raise ValueError(f"unknown search provider: {provider}")
    return normalized


def normalize_status(value: Any) -> str:
    status = clean_string(value) or "succeeded"
    normalized = status.lower().replace("-", "_").replace(" ", "_")
    if normalized not in SEARCH_STATUSES:
        raise ValueError(f"unknown search status: {status}")
    return normalized


def load_search_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix in {".yml", ".yaml"}:
        data = load_yaml(path, {})
    elif suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    elif suffix == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        data = {"results": rows}
    else:
        raise ValueError(f"unsupported search result file type: {path.suffix}")

    if isinstance(data, list):
        data = {"results": data}
    if not isinstance(data, dict):
        raise ValueError("search result file must be a mapping, list, or CSV table")
    results = data.get("results")
    if not isinstance(results, list):
        raise ValueError("search result file must contain a results list")
    return data


def load_project_state(project_dir: Path) -> dict[str, Any]:
    state_path = project_dir / "state" / "paper.yml"
    state = load_yaml(state_path, {"objects": {}, "links": []})
    if not isinstance(state, dict):
        raise ValueError(f"project state must be a mapping: {state_path}")
    return state


def infer_paper_id(project_dir: Path, explicit_paper_id: str | None) -> str:
    if explicit_paper_id:
        return explicit_paper_id
    state = load_project_state(project_dir)
    papers = state.get("objects", {}).get("Paper", {})
    if not isinstance(papers, dict) or not papers:
        raise ValueError("cannot infer paper_id: project state contains no Paper object")
    return str(next(iter(papers)))


def project_path_value(project_dir: Path, source_path: Path) -> str:
    resolved = source_path.resolve()
    try:
        return resolved.relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return str(resolved)


def search_run_id_for(provider: str, query: str, searched_at: str | None, source_path: Path) -> str:
    seed = "|".join([provider, query, searched_at or "", source_path.name])
    return f"SR-{sha1_short(seed)}"


def external_work_id_for(provider: str, item: dict[str, Any]) -> str:
    stable_key = (
        clean_string(item.get("doi"))
        or clean_string(item.get("arxiv_id"))
        or clean_string(item.get("provider_work_id"))
        or clean_string(item.get("uri"))
    )
    if stable_key is None:
        title = clean_string(item.get("title")) or "untitled"
        stable_key = "|".join(
            [
                provider,
                title.casefold(),
                str(item.get("year") or ""),
                clean_string(item.get("authors")) or "",
            ]
        )
    return f"EW-{sha1_short(stable_key.casefold())}"


def normalize_work_payload(provider: str, raw_item: Any, rank: int) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(raw_item, dict):
        raise ValueError(f"result {rank} must be a mapping")

    title = clean_string(raw_item.get("title"))
    if title is None:
        raise ValueError(f"result {rank} is missing title")

    work_payload: dict[str, Any] = {
        "external_work_id": external_work_id_for(provider, raw_item),
        "title": title,
        "source_provider": provider,
    }
    for field_name in ("authors", "venue", "doi", "arxiv_id", "uri", "abstract", "provider_work_id"):
        value = clean_string(raw_item.get(field_name))
        if value is not None:
            work_payload[field_name] = value
    year = maybe_int(raw_item.get("year"))
    if year is not None:
        work_payload["year"] = year

    explicit_quality = clean_string(raw_item.get("metadata_quality"))
    if explicit_quality is not None:
        if explicit_quality not in {"title_only", "bibliographic", "abstract", "full_text"}:
            raise ValueError(f"result {rank} has unknown metadata_quality: {explicit_quality}")
        work_payload["metadata_quality"] = explicit_quality
    elif work_payload.get("abstract"):
        work_payload["metadata_quality"] = "abstract"
    elif any(work_payload.get(field) for field in ("authors", "year", "venue", "doi", "arxiv_id", "uri")):
        work_payload["metadata_quality"] = "bibliographic"
    else:
        work_payload["metadata_quality"] = "title_only"

    for field_name in ("metadata_source_uri", "metadata_retrieved_at"):
        value = clean_string(raw_item.get(field_name))
        if value is not None:
            work_payload[field_name] = value

    metadata = {
        key: value
        for key, value in raw_item.items()
        if key not in WORK_FIELDS and key not in RESULT_FIELDS and value not in (None, "")
    }
    if metadata:
        work_payload["metadata"] = metadata

    result_payload = {
        "external_work_id": work_payload["external_work_id"],
        "rank": maybe_int(raw_item.get("rank")) or rank,
    }
    score = maybe_float(raw_item.get("score"))
    if score is not None:
        result_payload["score"] = score
    snippet = clean_string(raw_item.get("snippet"))
    if snippet is not None:
        result_payload["snippet"] = snippet

    return work_payload, result_payload


def build_proposals(
    project_dir: Path,
    source_path: Path,
    *,
    paper_id: str,
    provider: str | None = None,
    query: str | None = None,
    search_run_id: str | None = None,
    artifact_id: str | None = None,
    record_artifact: bool = True,
) -> list[dict[str, Any]]:
    data = load_search_file(source_path)
    provider_value = normalize_provider(provider or data.get("provider"))
    query_value = clean_string(query or data.get("query")) or source_path.stem
    searched_at = clean_string(data.get("searched_at"))
    status = normalize_status(data.get("status"))
    parameters = data.get("parameters") if isinstance(data.get("parameters"), dict) else None
    run_id = search_run_id or search_run_id_for(provider_value, query_value, searched_at, source_path)
    artifact_id = artifact_id or f"A-search-{sha1_short(run_id)}"

    proposals: list[dict[str, Any]] = []
    if record_artifact:
        proposals.append(
            {
                "action_type": "artifact.created",
                "actor": "system",
                "payload": {
                    "artifact_id": artifact_id,
                    "paper_id": paper_id,
                    "artifact_type": "search_results",
                    "path": project_path_value(project_dir, source_path),
                    "description": f"{provider_value} search results for: {query_value}",
                    "produced_by": "import_search_results",
                },
            }
        )

    search_payload: dict[str, Any] = {
        "search_run_id": run_id,
        "paper_id": paper_id,
        "provider": provider_value,
        "query": query_value,
        "status": status,
    }
    if searched_at:
        search_payload["searched_at"] = searched_at
    if parameters:
        search_payload["parameters"] = parameters
    if record_artifact:
        search_payload["artifact_id"] = artifact_id

    proposals.append(
        {
            "action_type": "search_run.created",
            "actor": "system",
            "payload": search_payload,
        }
    )

    for rank, raw_item in enumerate(data["results"], start=1):
        work_payload, result_payload = normalize_work_payload(provider_value, raw_item, rank)
        result_payload["search_result_id"] = f"SRR-{sha1_short(run_id, 8)}-{rank:04d}"
        result_payload["paper_id"] = paper_id
        result_payload["search_run_id"] = run_id

        proposals.append(
            {
                "action_type": "external_work.upserted",
                "actor": "system",
                "payload": work_payload,
            }
        )
        proposals.append(
            {
                "action_type": "search_result.created",
                "actor": "system",
                "payload": result_payload,
            }
        )
        proposals.append(
            {
                "action_type": "link.created",
                "actor": "system",
                "object_id": f"L-{result_payload['search_result_id']}-run",
                "payload": {
                    "link_type": "search_run_has_result",
                    "from_object_type": "SearchRun",
                    "from_object_id": run_id,
                    "to_object_type": "SearchResult",
                    "to_object_id": result_payload["search_result_id"],
                },
            }
        )
        proposals.append(
            {
                "action_type": "link.created",
                "actor": "system",
                "object_id": f"L-{result_payload['search_result_id']}-work",
                "payload": {
                    "link_type": "search_result_points_to_external_work",
                    "from_object_type": "SearchResult",
                    "from_object_id": result_payload["search_result_id"],
                    "to_object_type": "ExternalWork",
                    "to_object_id": work_payload["external_work_id"],
                },
            }
        )

    return proposals


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create SearchRun, ExternalWork, and SearchResult proposals from structured search results."
    )
    parser.add_argument("project_dir")
    parser.add_argument("search_results_file")
    parser.add_argument("--out", required=True, help="Output proposals YAML path.")
    parser.add_argument("--paper-id", help="Paper id; defaults to the first Paper in state/paper.yml.")
    parser.add_argument("--provider", help="Override search provider.")
    parser.add_argument("--query", help="Override search query.")
    parser.add_argument("--search-run-id", help="Override generated SearchRun id.")
    parser.add_argument("--artifact-id", help="Override generated Artifact id for the search result file.")
    parser.add_argument(
        "--no-artifact",
        action="store_true",
        help="Do not include an artifact.created proposal for the search result file.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    source_path = Path(args.search_results_file).resolve()
    paper_id = infer_paper_id(project_dir, args.paper_id)
    proposals = build_proposals(
        project_dir,
        source_path,
        paper_id=paper_id,
        provider=args.provider,
        query=args.query,
        search_run_id=args.search_run_id,
        artifact_id=args.artifact_id,
        record_artifact=not args.no_artifact,
    )
    out_path = Path(args.out).resolve()
    write_yaml(out_path, {"proposals": proposals})
    print(f"search result proposals: {len(proposals)}")
    print(f"proposal file: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
