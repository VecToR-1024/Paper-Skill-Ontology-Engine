from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from event_log import append_event, load_registry, make_event, project_state, read_events, validate_event_log, write_yaml


ROOT = Path(__file__).resolve().parents[1]

LATEX_ROOT_NAMES = ("main.tex", "paper.tex", "manuscript.tex")
MARKDOWN_ROOT_NAMES = ("paper.md", "manuscript.md", "README.md")
SECTION_TYPE_ALIASES = {
    "abstract": "abstract",
    "introduction": "introduction",
    "background": "background",
    "related work": "related_work",
    "literature review": "related_work",
    "method": "method",
    "methods": "method",
    "methods and approaches": "method",
    "experiment": "experiments",
    "experiments": "experiments",
    "results": "results",
    "analysis": "analysis",
    "discussion": "discussion",
    "future work": "future_work",
    "conclusion": "conclusion",
    "limitations": "limitations",
    "ethics": "ethics",
    "appendix": "appendix",
    "references": "references",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".eps"}


@dataclass(frozen=True)
class SourceInfo:
    input_path: Path
    project_root: Path
    manuscript_path: Path
    source_kind: str


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def to_workspace_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def slugify(value: str, fallback: str = "untitled") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value[:64] or fallback


def stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{slugify(value)}"


def latex_command_value(text: str, command: str) -> str | None:
    match = re.search(rf"\\{command}\s*\{{(?P<value>.*?)\}}", text, flags=re.DOTALL)
    if not match:
        return None
    return clean_inline_text(match.group("value"))


def latex_environment(text: str, name: str) -> str | None:
    match = re.search(
        rf"\\begin\{{{re.escape(name)}\}}(?P<value>.*?)\\end\{{{re.escape(name)}\}}",
        text,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return clean_inline_text(match.group("value"))


def clean_inline_text(value: str) -> str:
    value = re.sub(r"%.*", "", value)
    value = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", value)
    value = value.replace("{", "").replace("}", "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def section_type_for(title: str) -> str:
    key = re.sub(r"\s+", " ", title.strip().lower())
    return SECTION_TYPE_ALIASES.get(key, "appendix")


def find_source(input_path: Path) -> SourceInfo:
    input_path = input_path.resolve()
    if input_path.is_dir():
        for name in LATEX_ROOT_NAMES:
            candidate = input_path / name
            if candidate.exists():
                return SourceInfo(input_path, input_path, candidate, "latex")
        for name in MARKDOWN_ROOT_NAMES:
            candidate = input_path / name
            if candidate.exists():
                return SourceInfo(input_path, input_path, candidate, "markdown")
        tex_files = sorted(input_path.glob("*.tex"))
        if tex_files:
            return SourceInfo(input_path, input_path, tex_files[0], "latex")
        md_files = sorted(input_path.glob("*.md"))
        if md_files:
            return SourceInfo(input_path, input_path, md_files[0], "markdown")
        raise ValueError(f"No .tex or .md manuscript found under {input_path}")
    suffix = input_path.suffix.lower()
    if suffix == ".tex":
        return SourceInfo(input_path, input_path.parent, input_path, "latex")
    if suffix == ".md":
        return SourceInfo(input_path, input_path.parent, input_path, "markdown")
    raise ValueError(f"Unsupported input file type: {input_path.suffix}")


def default_out_dir(source: SourceInfo) -> Path:
    if source.manuscript_path.parent.name == "artifacts":
        return source.manuscript_path.parent.parent
    return source.project_root.parent / f"{source.manuscript_path.stem}_ingested"


def add_event(
    events: list[dict[str, Any]],
    *,
    actor: str,
    function: str,
    action_type: str,
    object_type: str,
    object_id: str,
    payload: dict[str, Any],
) -> None:
    events.append(
        make_event(
            offset=len(events) + 1,
            actor=actor,
            function=function,
            action_type=action_type,
            object_type=object_type,
            object_id=object_id,
            payload=payload,
        )
    )


def artifact_type_for_manuscript(source_kind: str) -> str:
    return "manuscript_tex" if source_kind == "latex" else "manuscript_md"


def add_paper_and_manuscript(
    events: list[dict[str, Any]],
    *,
    paper_id: str,
    source: SourceInfo,
    title: str,
    abstract: str | None,
    stage: str,
) -> None:
    payload = {
        "paper_id": paper_id,
        "title": title,
        "stage": stage,
    }
    if abstract:
        payload["main_claim"] = abstract[:500]
    add_event(
        events,
        actor="user",
        function="create_object",
        action_type="paper.created",
        object_type="Paper",
        object_id=paper_id,
        payload=payload,
    )
    add_event(
        events,
        actor="user",
        function="create_object",
        action_type="artifact.created",
        object_type="Artifact",
        object_id="A-manuscript-root",
        payload={
            "artifact_id": "A-manuscript-root",
            "paper_id": paper_id,
            "artifact_type": artifact_type_for_manuscript(source.source_kind),
            "path": to_workspace_path(source.manuscript_path),
            "description": f"Root {source.source_kind} manuscript ingested from project input.",
            "produced_by": "ingest_paper_project.py",
        },
    )


def parse_latex_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    if latex_environment(text, "abstract"):
        sections.append(("Abstract", "abstract"))
    for match in re.finditer(r"\\(?P<level>section|subsection)\*?\{(?P<title>[^{}]+)\}", text):
        title = clean_inline_text(match.group("title"))
        if match.group("level") == "section":
            sections.append((title, section_type_for(title)))
    return sections


def parse_markdown_sections(text: str, paper_title: str | None = None) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for match in re.finditer(r"^(?P<level>#{1,3})\s+(?P<title>.+?)\s*$", text, flags=re.MULTILINE):
        if len(match.group("level")) <= 2:
            heading_title = clean_inline_text(match.group("title"))
            if len(match.group("level")) == 1 and paper_title and heading_title.lower() == clean_inline_text(paper_title).lower():
                continue
            sections.append((heading_title, section_type_for(heading_title)))
    return sections


def add_sections(events: list[dict[str, Any]], paper_id: str, manuscript_path: Path, sections: Iterable[tuple[str, str]]) -> None:
    seen: set[str] = set()
    order_index = 1
    for title, section_type in sections:
        section_id = stable_id("S", title)
        if section_id in seen:
            section_id = f"{section_id}-{order_index}"
        seen.add(section_id)
        add_event(
            events,
            actor="writing_expert",
            function="upsert_object",
            action_type="section.upserted",
            object_type="Section",
            object_id=section_id,
            payload={
                "section_id": section_id,
                "paper_id": paper_id,
                "section_type": section_type,
                "title": title,
                "content_path": to_workspace_path(manuscript_path),
                "order_index": order_index,
            },
        )
        order_index += 1


def latex_bibliography_paths(text: str, root: Path) -> list[Path]:
    paths: list[Path] = []
    for match in re.finditer(r"\\(?:bibliography|addbibresource)\s*\{(?P<value>[^{}]+)\}", text):
        for raw_name in match.group("value").split(","):
            raw_name = raw_name.strip()
            if not raw_name:
                continue
            candidate = root / raw_name
            if candidate.suffix.lower() != ".bib":
                candidate = candidate.with_suffix(".bib")
            paths.append(candidate)
    return paths


def markdown_bibliography_paths(text: str, root: Path) -> list[Path]:
    paths: list[Path] = []
    for match in re.finditer(r"(?im)^\s*bibliography\s*:\s*(?P<value>.+?)\s*$", text):
        value = match.group("value").strip().strip("\"'")
        paths.append((root / value).with_suffix(".bib") if Path(value).suffix == "" else root / value)
    for candidate in sorted(root.glob("*.bib")):
        if candidate not in paths:
            paths.append(candidate)
    return paths


def add_bibliography_artifacts(events: list[dict[str, Any]], paper_id: str, paths: Iterable[Path]) -> list[Path]:
    existing_paths: list[Path] = []
    for path in dict.fromkeys(paths):
        if not path.exists():
            continue
        existing_paths.append(path)
        artifact_id = stable_id("A-bib", path.stem)
        add_event(
            events,
            actor="user",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=artifact_id,
            payload={
                "artifact_id": artifact_id,
                "paper_id": paper_id,
                "artifact_type": "bibliography_bib",
                "path": to_workspace_path(path),
                "description": "Bibliography file discovered during project ingest.",
                "produced_by": "ingest_paper_project.py",
            },
        )
    return existing_paths


def parse_bib_entries(path: Path) -> list[dict[str, Any]]:
    text = read_text(path)
    entries: list[dict[str, Any]] = []
    for match in re.finditer(r"@\w+\s*\{\s*(?P<key>[^,\s]+)\s*,(?P<body>.*?)(?=\n@\w+\s*\{|\Z)", text, flags=re.DOTALL):
        key = match.group("key").strip()
        body = match.group("body")
        title = bib_field(body, "title")
        authors = bib_field(body, "author")
        year_raw = bib_field(body, "year")
        uri = bib_field(body, "url") or bib_field(body, "doi")
        entry: dict[str, Any] = {
            "citation_key": key,
            "title": title,
            "authors": authors,
            "uri": uri,
            "role": "background",
        }
        if year_raw and year_raw.isdigit():
            entry["year"] = int(year_raw)
        entries.append({k: v for k, v in entry.items() if v not in (None, "")})
    return entries


def bib_field(body: str, field: str) -> str | None:
    match = re.search(rf"\b{field}\s*=\s*(?:\{{(?P<braced>.*?)\}}|\"(?P<quoted>.*?)\")\s*,", body, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return None
    return clean_inline_text(match.group("braced") or match.group("quoted") or "")


def add_citations(events: list[dict[str, Any]], paper_id: str, bib_paths: Iterable[Path]) -> None:
    seen: set[str] = set()
    for bib_path in bib_paths:
        for entry in parse_bib_entries(bib_path):
            key = entry["citation_key"]
            if key in seen:
                continue
            seen.add(key)
            citation_id = stable_id("Cite", key)
            payload = {"citation_id": citation_id, "paper_id": paper_id, **entry}
            add_event(
                events,
                actor="system",
                function="create_object",
                action_type="citation.created",
                object_type="Citation",
                object_id=citation_id,
                payload=payload,
            )


def resolve_latex_asset(path_value: str, root: Path) -> Path:
    raw = Path(path_value.strip())
    candidate = raw if raw.is_absolute() else root / raw
    if candidate.suffix:
        return candidate
    for ext in IMAGE_EXTENSIONS:
        with_ext = candidate.with_suffix(ext)
        if with_ext.exists():
            return with_ext
    return candidate


def latex_asset_paths(text: str, root: Path) -> tuple[list[Path], list[Path]]:
    included: list[Path] = []
    figures: list[Path] = []
    for match in re.finditer(r"\\(?:input|include)\s*\{(?P<value>[^{}]+)\}", text):
        candidate = root / match.group("value").strip()
        if candidate.suffix.lower() != ".tex":
            candidate = candidate.with_suffix(".tex")
        included.append(candidate)
    for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\s*\{(?P<value>[^{}]+)\}", text):
        figures.append(resolve_latex_asset(match.group("value"), root))
    return included, figures


def markdown_image_paths(text: str, root: Path) -> list[Path]:
    paths: list[Path] = []
    for match in re.finditer(r"!\[[^\]]*\]\((?P<value>[^)]+)\)", text):
        raw = match.group("value").strip().split()[0].strip("\"'")
        if re.match(r"https?://", raw):
            continue
        paths.append((root / raw).resolve())
    return paths


def markdown_table_count(text: str) -> int:
    count = 0
    in_table = False
    for line in text.splitlines():
        is_table_line = bool(re.match(r"^\s*\|.+\|\s*$", line))
        if is_table_line and not in_table:
            count += 1
            in_table = True
        elif not is_table_line:
            in_table = False
    return count


def add_artifacts(events: list[dict[str, Any]], paper_id: str, paths: Iterable[Path], artifact_type: str, description: str) -> None:
    for path in dict.fromkeys(paths):
        if not path.exists():
            continue
        artifact_id = stable_id(f"A-{artifact_type}", path.stem)
        add_event(
            events,
            actor="system",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=artifact_id,
            payload={
                "artifact_id": artifact_id,
                "paper_id": paper_id,
                "artifact_type": artifact_type,
                "path": to_workspace_path(path),
                "description": description,
                "produced_by": "ingest_paper_project.py",
            },
        )


def add_table_artifacts(events: list[dict[str, Any]], paper_id: str, text: str, source_kind: str, manuscript_path: Path) -> None:
    if source_kind == "latex":
        count = len(re.findall(r"\\begin\{(?:table|tabular)\}", text))
        artifact_type = "table_tex"
    else:
        count = markdown_table_count(text)
        artifact_type = "table_md"
    for index in range(1, count + 1):
        artifact_id = f"A-{artifact_type}-{index:03d}"
        add_event(
            events,
            actor="system",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=artifact_id,
            payload={
                "artifact_id": artifact_id,
                "paper_id": paper_id,
                "artifact_type": artifact_type,
                "path": to_workspace_path(manuscript_path),
                "description": f"Table-like block #{index} discovered in the manuscript.",
                "produced_by": "ingest_paper_project.py",
            },
        )


def markdown_title_and_body(text: str, path: Path) -> tuple[str, str | None]:
    frontmatter_title = re.search(r"(?ms)\A---\s*(?P<body>.*?)\s*---", text)
    if frontmatter_title:
        title_match = re.search(r"(?im)^\s*title\s*:\s*(?P<title>.+?)\s*$", frontmatter_title.group("body"))
        if title_match:
            return title_match.group("title").strip().strip("\"'"), None
    heading = re.search(r"^#\s+(?P<title>.+?)\s*$", text, flags=re.MULTILINE)
    if heading:
        return clean_inline_text(heading.group("title")), None
    return path.stem.replace("-", " ").replace("_", " ").title(), None


def build_events(source: SourceInfo, paper_id: str, stage: str) -> list[dict[str, Any]]:
    text = read_text(source.manuscript_path)
    events: list[dict[str, Any]] = []
    if source.source_kind == "latex":
        title = latex_command_value(text, "title") or source.manuscript_path.stem
        abstract = latex_environment(text, "abstract")
        sections = parse_latex_sections(text)
        bib_paths = latex_bibliography_paths(text, source.project_root)
        included, figures = latex_asset_paths(text, source.project_root)
    else:
        title, abstract = markdown_title_and_body(text, source.manuscript_path)
        sections = parse_markdown_sections(text, title)
        bib_paths = markdown_bibliography_paths(text, source.project_root)
        included = []
        figures = markdown_image_paths(text, source.project_root)

    add_paper_and_manuscript(events, paper_id=paper_id, source=source, title=title, abstract=abstract, stage=stage)
    add_sections(events, paper_id, source.manuscript_path, sections)
    existing_bib_paths = add_bibliography_artifacts(events, paper_id, bib_paths)
    add_citations(events, paper_id, existing_bib_paths)
    add_artifacts(events, paper_id, included, "included_tex", "Included LaTeX source discovered during project ingest.")
    add_artifacts(events, paper_id, figures, "figure_image", "Figure/image file referenced by the manuscript.")
    add_table_artifacts(events, paper_id, text, source.source_kind, source.manuscript_path)
    return events


def write_project(events: list[dict[str, Any]], out_dir: Path, reset: bool) -> None:
    registry = load_registry()
    log_path = out_dir / "events" / "event_log.yml"
    state_path = out_dir / "state" / "paper.yml"
    if log_path.exists():
        if not reset:
            raise ValueError(f"{log_path} already exists; pass --reset to replace it")
        log_path.unlink()
    for event in events:
        append_event(log_path, event, registry)
    written_events = read_events(log_path)
    errors = validate_event_log(written_events, registry)
    if errors:
        raise ValueError("event log validation failed:\n" + "\n".join(errors))
    write_yaml(state_path, project_state(written_events))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest a .tex or .md paper project into event log + paper.yml.")
    parser.add_argument("input_path", help="A .tex/.md manuscript file, or a directory containing one.")
    parser.add_argument(
        "--out-dir",
        help="Output project directory. Defaults to an existing project root or a sibling <stem>_ingested directory.",
    )
    parser.add_argument("--paper-id", help="Stable Paper id. Defaults to P-<title slug>.")
    parser.add_argument("--stage", default="checking", choices=["idea", "positioning", "drafting", "checking", "reviewing", "rebuttal", "assembly", "submission"])
    parser.add_argument("--reset", action="store_true", help="Replace an existing event_log.yml in the output directory.")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    source = find_source(Path(args.input_path))
    text = read_text(source.manuscript_path)
    if source.source_kind == "latex":
        title = latex_command_value(text, "title") or source.manuscript_path.stem
    else:
        title, _ = markdown_title_and_body(text, source.manuscript_path)
    paper_id = args.paper_id or stable_id("P", title)
    out_dir = Path(args.out_dir).resolve() if args.out_dir else default_out_dir(source)
    events = build_events(source, paper_id, args.stage)
    write_project(events, out_dir, args.reset)
    print(f"input: {source.manuscript_path}")
    print(f"source_kind: {source.source_kind}")
    print(f"event log: {out_dir / 'events' / 'event_log.yml'}")
    print(f"state: {out_dir / 'state' / 'paper.yml'}")
    print(f"events: {len(events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
