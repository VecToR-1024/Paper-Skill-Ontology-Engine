from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from event_log import load_yaml


WORK_FIELDS = (
    "external_work_id",
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
    "source_provider",
    "provider_work_id",
    "metadata",
)


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def load_metadata_file(path: Path) -> dict[str, Any]:
    if path.suffix.lower() in {".yml", ".yaml"}:
        data = load_yaml(path, {})
    elif path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError("metadata source file must be YAML or JSON")
    if not isinstance(data, dict):
        raise ValueError("metadata source file must contain a mapping")
    return data


def non_empty_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def validate_source_uri(value: Any) -> str:
    uri = non_empty_text(value)
    parsed = urlparse(uri or "")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("metadata_source_uri must be an absolute http(s) URI")
    return str(uri)


def project_paper_id(state: dict[str, Any]) -> str:
    papers = state.get("objects", {}).get("Paper", {})
    if not papers:
        raise ValueError("project state contains no Paper object")
    return str(next(iter(papers)))


def artifact_id_for(external_work_id: str, source_uri: str, abstract: str) -> str:
    digest = hashlib.sha1(f"{external_work_id}|{source_uri}|{abstract}".encode("utf-8")).hexdigest()[:12]
    return f"A-work-metadata-{digest}"


def build_proposals(
    project_dir: Path,
    external_work_id: str,
    source_file: Path,
    *,
    source_uri_override: str | None = None,
    retrieved_at_override: str | None = None,
) -> list[dict[str, Any]]:
    state_path = project_dir / "state" / "paper.yml"
    state = load_yaml(state_path, {"objects": {}, "links": []})
    external_works = state.get("objects", {}).get("ExternalWork", {})
    if external_work_id not in external_works:
        raise ValueError(f"unknown ExternalWork id: {external_work_id}")

    source_data = load_metadata_file(source_file)
    source_uri = validate_source_uri(source_uri_override or source_data.get("metadata_source_uri"))
    abstract = non_empty_text(source_data.get("abstract"))
    if abstract is None:
        raise ValueError("metadata source file must contain a non-empty abstract")
    retrieved_at = (
        non_empty_text(retrieved_at_override)
        or non_empty_text(source_data.get("metadata_retrieved_at"))
        or datetime.now(timezone.utc).isoformat()
    )

    artifact_id = artifact_id_for(external_work_id, source_uri, abstract)
    artifact_dir = project_dir / "artifacts" / "external-work-metadata"
    artifact_path = artifact_dir / f"{artifact_id}{source_file.suffix.lower()}"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    if source_file.resolve() != artifact_path.resolve():
        shutil.copy2(source_file, artifact_path)

    current = external_works[external_work_id]
    payload = {field: current[field] for field in WORK_FIELDS if field in current}
    payload.update(
        {
            "external_work_id": external_work_id,
            "title": current["title"],
            "source_provider": current["source_provider"],
            "abstract": abstract,
            "metadata_quality": (
                "full_text" if current.get("metadata_quality") == "full_text" else "abstract"
            ),
            "metadata_source_uri": source_uri,
            "metadata_retrieved_at": retrieved_at,
        }
    )
    current_metadata = payload.get("metadata")
    if current_metadata is not None and not isinstance(current_metadata, dict):
        raise ValueError("ExternalWork metadata must be a mapping before enrichment")
    metadata = dict(current_metadata or {})
    metadata["enrichment_artifact_id"] = artifact_id
    payload["metadata"] = metadata

    relative_artifact_path = artifact_path.relative_to(project_dir).as_posix()
    paper_id = project_paper_id(state)
    return [
        {
            "action_type": "artifact.created",
            "actor": "system",
            "payload": {
                "artifact_id": artifact_id,
                "paper_id": paper_id,
                "artifact_type": "external_work_metadata",
                "path": relative_artifact_path,
                "description": f"Metadata enrichment source for {external_work_id}",
                "produced_by": "import_work_metadata",
            },
        },
        {
            "action_type": "external_work.upserted",
            "actor": "system",
            "function": "upsert_object",
            "payload": payload,
        },
        {
            "action_type": "link.created",
            "actor": "system",
            "payload": {
                "link_type": "artifact_documents_external_work",
                "from_object_type": "Artifact",
                "from_object_id": artifact_id,
                "to_object_type": "ExternalWork",
                "to_object_id": external_work_id,
            },
        },
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import an auditable official-source abstract and enrich an existing ExternalWork."
    )
    parser.add_argument("project_dir")
    parser.add_argument("external_work_id")
    parser.add_argument("metadata_source_file")
    parser.add_argument("--metadata-source-uri")
    parser.add_argument("--retrieved-at")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    source_file = Path(args.metadata_source_file).resolve()
    try:
        proposals = build_proposals(
            project_dir,
            args.external_work_id,
            source_file,
            source_uri_override=args.metadata_source_uri,
            retrieved_at_override=args.retrieved_at,
        )
        output_path = Path(args.out).resolve()
        write_yaml(output_path, {"proposals": proposals})
    except (FileNotFoundError, KeyError, ValueError, OSError) as exc:
        print(f"metadata_enrichment_error: {exc}")
        return 1

    print(f"metadata_enrichment_proposals: {output_path}")
    print(f"external_work_id: {args.external_work_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
