from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from typing import Any

import yaml

from event_log import load_yaml


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def resolve_project_path(project_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    return (project_dir / path).resolve()


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-") or "source"


def text_hash(text: str) -> str:
    normalized = "\n".join(line.rstrip() for line in text.strip().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def locator_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".tex":
        return "tex_block"
    if suffix in {".md", ".markdown"}:
        return "paragraph"
    return "paragraph"


def split_blocks(text: str) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    current: list[str] = []
    start_line: int | None = None

    def flush(end_line: int) -> None:
        nonlocal current, start_line
        if not current or start_line is None:
            current = []
            start_line = None
            return
        block_text = "\n".join(current).strip()
        if block_text:
            blocks.append(
                {
                    "text": block_text,
                    "start_line": start_line,
                    "end_line": end_line,
                }
            )
        current = []
        start_line = None

    for line_number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            if start_line is None:
                start_line = line_number
            current.append(line)
        else:
            flush(line_number - 1)
    flush(len(text.splitlines()))
    return blocks


def excerpt(text: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def load_project_state(project_dir: Path) -> dict[str, Any]:
    state_path = project_dir / "state" / "paper.yml"
    state = load_yaml(state_path, {"objects": {}, "links": []})
    if not isinstance(state, dict):
        raise ValueError(f"project state must be a mapping: {state_path}")
    return state


def artifact_record(state: dict[str, Any], artifact_id: str) -> dict[str, Any]:
    artifact = state.get("objects", {}).get("Artifact", {}).get(artifact_id)
    if not isinstance(artifact, dict):
        raise ValueError(f"unknown Artifact id: {artifact_id}")
    return artifact


def source_span_proposals(
    project_dir: Path,
    artifact_id: str,
    *,
    excerpt_chars: int = 280,
) -> list[dict[str, Any]]:
    state = load_project_state(project_dir)
    artifact = artifact_record(state, artifact_id)
    paper_id = artifact.get("paper_id")
    path_value = artifact.get("path")
    if not isinstance(paper_id, str) or not paper_id.strip():
        raise ValueError(f"Artifact {artifact_id} has no paper_id")
    if not isinstance(path_value, str) or not path_value.strip():
        raise ValueError(f"Artifact {artifact_id} has no path")

    source_path = resolve_project_path(project_dir, path_value)
    if not source_path.exists():
        raise FileNotFoundError(f"Artifact {artifact_id} path does not exist: {source_path}")
    text = source_path.read_text(encoding="utf-8", errors="ignore")
    blocks = split_blocks(text)
    locator_type = locator_type_for(source_path)
    artifact_slug = slug(artifact_id)

    proposals: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        span_id = f"SPAN-{artifact_slug}-{index:04d}"
        payload = {
            "source_span_id": span_id,
            "paper_id": paper_id,
            "artifact_id": artifact_id,
            "locator_type": locator_type,
            "locator": {
                "block_index": index,
                "start_line": block["start_line"],
                "end_line": block["end_line"],
            },
            "text_excerpt": excerpt(block["text"], excerpt_chars),
            "text_hash": text_hash(block["text"]),
        }
        proposals.append(
            {
                "action_type": "source_span.created",
                "actor": "system",
                "payload": payload,
                "references": {"artifact_ids": [artifact_id]},
            }
        )
    return proposals


def main() -> int:
    parser = argparse.ArgumentParser(description="Create SourceSpan proposals from a recorded text artifact.")
    parser.add_argument("project_dir")
    parser.add_argument("artifact_id")
    parser.add_argument("--out", required=True, help="Output proposals YAML path.")
    parser.add_argument("--excerpt-chars", type=int, default=280)
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    proposals = source_span_proposals(
        project_dir,
        args.artifact_id,
        excerpt_chars=args.excerpt_chars,
    )
    out_path = Path(args.out).resolve()
    write_yaml(out_path, {"proposals": proposals})
    print(f"source_span proposals: {len(proposals)}")
    print(f"proposal file: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
