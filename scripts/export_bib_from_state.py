from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from event_log import append_event, load_registry, make_event, next_offset, project_state, read_events, validate_event_log, write_yaml


def read_state(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a state mapping")
    return data


def objects(state: dict[str, Any], object_type: str) -> dict[str, dict[str, Any]]:
    return state.get("objects", {}).get(object_type, {}) or {}


def first_paper(state: dict[str, Any]) -> dict[str, Any]:
    papers = objects(state, "Paper")
    if not papers:
        raise ValueError("state contains no Paper object")
    return papers[sorted(papers)[0]]


def bibtex_key(value: Any, fallback: str, used: set[str]) -> str:
    raw = str(value or fallback or "ref").strip()
    key = re.sub(r"[\s,{}\\]+", "-", raw).strip("-")
    key = re.sub(r"[^A-Za-z0-9_.:/-]+", "", key)
    if not key:
        key = "ref"
    candidate = key
    suffix = 2
    while candidate in used:
        candidate = f"{key}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def bibtex_value(value: Any) -> str:
    text = str(value).strip()
    replacements = {
        "\\": r"\\",
        "{": r"\{",
        "}": r"\}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }
    return "".join(replacements.get(char, char) for char in text)


def citation_is_exportable(citation: dict[str, Any]) -> bool:
    fields = ("title", "authors", "year", "uri", "citation_key")
    return any(citation.get(field) not in (None, "") for field in fields)


def render_bibtex(citations: dict[str, dict[str, Any]]) -> str:
    if not citations:
        raise ValueError("no Citation objects found; refusing to write an empty bibliography")

    lines: list[str] = []
    used_keys: set[str] = set()
    for index, citation_id in enumerate(sorted(citations), start=1):
        citation = citations[citation_id]
        if not citation_is_exportable(citation):
            raise ValueError(f"Citation {citation_id} has no exportable bibliographic fields")
        key = bibtex_key(citation.get("citation_key"), citation_id or f"ref{index}", used_keys)
        fields: list[tuple[str, Any]] = [
            ("author", citation.get("authors")),
            ("title", citation.get("title")),
            ("year", citation.get("year")),
            ("url", citation.get("uri")),
        ]
        lines.append(f"@misc{{{key},")
        rendered_fields = [(name, value) for name, value in fields if value not in (None, "")]
        for field_index, (name, value) in enumerate(rendered_fields):
            comma = "," if field_index < len(rendered_fields) - 1 else ""
            lines.append(f"  {name} = {{{bibtex_value(value)}}}{comma}")
        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def project_relative_path(project_dir: Path, out_path: Path) -> str:
    resolved_project = project_dir.resolve()
    resolved_out = out_path.resolve()
    try:
        return resolved_out.relative_to(resolved_project).as_posix()
    except ValueError:
        return str(resolved_out)


def append_bib_artifact_event(project_dir: Path, out_path: Path, state: dict[str, Any]) -> None:
    registry = load_registry()
    log_path = project_dir / "events" / "event_log.yml"
    offset = next_offset(log_path)
    paper = first_paper(state)
    artifact_id = f"A-bibliography-bib-{offset:03d}"
    event = make_event(
        offset=offset,
        actor="assembly_expert",
        function="export_bib_from_state",
        action_type="artifact.created",
        object_type="Artifact",
        object_id=artifact_id,
        payload={
            "artifact_id": artifact_id,
            "paper_id": paper["paper_id"],
            "artifact_type": "bibliography_bib",
            "path": project_relative_path(project_dir, out_path),
            "description": "BibTeX bibliography exported from Citation objects in paper.yml state.",
            "produced_by": "export_bib_from_state.py",
        },
    )
    append_event(log_path, event, registry)
    events = read_events(log_path)
    errors = validate_event_log(events, registry)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        raise ValueError("event log failed validation after bibliography export")
    write_yaml(project_dir / "state" / "paper.yml", project_state(events, log_path.parent))


def main() -> int:
    parser = argparse.ArgumentParser(description="Export Citation objects from paper.yml state into a BibTeX artifact.")
    parser.add_argument("project_dir")
    parser.add_argument("--state", default="state/paper.yml")
    parser.add_argument("--out", default="artifacts/references.bib")
    parser.add_argument("--append-event", action="store_true", help="Record exported bibliography as a bibliography_bib Artifact event.")
    args = parser.parse_args()

    try:
        project_dir = Path(args.project_dir).resolve()
        state_path = project_dir / args.state
        out_path = project_dir / args.out
        state = read_state(state_path)
        bibtex = render_bibtex(objects(state, "Citation"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(bibtex, encoding="utf-8")
        if args.append_event:
            append_bib_artifact_event(project_dir, out_path, state)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"exported bibtex: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
