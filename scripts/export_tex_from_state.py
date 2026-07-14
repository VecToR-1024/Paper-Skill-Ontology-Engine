from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from event_log import append_event, load_registry, make_event, next_offset, project_state, read_events, validate_event_log, write_yaml

ROOT = Path(__file__).resolve().parents[1]


def read_state(path: Path) -> dict[str, Any]:
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a state mapping")
    return data


def tex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in value)


def tex_escape_text(value: str) -> str:
    replacements = {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(char, char) for char in value)


def objects(state: dict[str, Any], object_type: str) -> dict[str, dict[str, Any]]:
    return state.get("objects", {}).get(object_type, {})


def first_paper(state: dict[str, Any]) -> dict[str, Any]:
    papers = objects(state, "Paper")
    if not papers:
        raise ValueError("state contains no Paper object")
    return papers[sorted(papers)[0]]


def section_sort_key(section: dict[str, Any]) -> tuple[int, str]:
    return (int(section.get("order_index") or 9999), section.get("section_id") or "")


def records_for_section(state: dict[str, Any], object_type: str, section_id: str) -> list[dict[str, Any]]:
    return [
        record
        for record in objects(state, object_type).values()
        if record.get("section_id") == section_id
    ]


def all_unsectioned_methods(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [record for record in objects(state, "Method").values() if not record.get("section_id")]


def sentence(value: str) -> str:
    value = value.strip()
    if not value:
        return value
    if value[-1] not in ".!?。！？":
        return value + "."
    return value


def resolve_text_path(project_dir: Path, path_value: str) -> Path | None:
    path = Path(path_value)
    if path.is_absolute():
        return path if path.exists() else None

    candidates = [
        project_dir / path,
        Path.cwd() / path,
        ROOT / path,
        project_dir.parent / path,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.exists():
            return resolved
    return None


def read_content_path(section: dict[str, Any], project_dir: Path) -> tuple[str | None, str | None]:
    path_value = section.get("content_path")
    if not path_value:
        return None, None
    path = resolve_text_path(project_dir, str(path_value))
    if path is None:
        return None, None
    return path.read_text(encoding="utf-8"), path.suffix.lower()


def strip_latex_abstract(content: str) -> str:
    match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", content, flags=re.DOTALL)
    if match:
        return match.group(1).strip()
    return content.strip()


def markdown_inline_to_tex(line: str) -> str:
    code_spans: list[str] = []

    def stash_code(match: re.Match[str]) -> str:
        code_spans.append(r"\texttt{" + tex_escape(match.group(1)) + "}")
        return f"@@CODE{len(code_spans) - 1}@@"

    line = re.sub(r"`([^`]+)`", stash_code, line)
    line = tex_escape_text(line)
    line = re.sub(r"\*\*([^*]+)\*\*", r"\\textbf{\1}", line)
    line = re.sub(r"__([^_]+)__", r"\\textbf{\1}", line)
    for index, code in enumerate(code_spans):
        line = line.replace(tex_escape_text(f"@@CODE{index}@@"), code)
    return line


def markdown_to_tex(content: str, *, heading_offset: int = 0) -> list[str]:
    lines: list[str] = []
    in_itemize = False

    def close_itemize() -> None:
        nonlocal in_itemize
        if in_itemize:
            lines.append(r"\end{itemize}")
            lines.append("")
            in_itemize = False

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            close_itemize()
            if lines and lines[-1] != "":
                lines.append("")
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            close_itemize()
            level = len(heading.group(1)) + heading_offset
            title = tex_escape(heading.group(2).strip())
            if level <= 1:
                lines.append(rf"\section{{{title}}}")
            elif level == 2:
                lines.append(rf"\subsection{{{title}}}")
            else:
                lines.append(rf"\subsubsection{{{title}}}")
            continue

        bullet = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet:
            if not in_itemize:
                lines.append(r"\begin{itemize}")
                in_itemize = True
            lines.append(r"\item " + markdown_inline_to_tex(bullet.group(1)))
            continue

        close_itemize()
        lines.append(markdown_inline_to_tex(stripped))

    close_itemize()
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def render_content_text(content: str, suffix: str | None, *, heading_offset: int = 0) -> list[str]:
    if suffix == ".md":
        lines = markdown_to_tex(content, heading_offset=heading_offset)
    else:
        lines = [content.strip()]
    return lines + [""]


def section_content(section: dict[str, Any], project_dir: Path) -> tuple[str | None, str | None]:
    if section.get("content"):
        return str(section["content"]), None
    return read_content_path(section, project_dir)


def render_abstract(section: dict[str, Any], paper: dict[str, Any], state: dict[str, Any], project_dir: Path) -> list[str]:
    content, suffix = section_content(section, project_dir)
    if content and suffix == ".tex" and r"\begin{abstract}" in content:
        content = strip_latex_abstract(content)
    content = content or paper.get("main_claim")
    if not content:
        claims = records_for_section(state, "Claim", section["section_id"])
        content = " ".join(sentence(claim["text"]) for claim in claims)
    if content and suffix == ".md":
        content = "\n".join(markdown_to_tex(content, heading_offset=2))
    return [
        r"\begin{abstract}",
        content or "% TODO: Write abstract.",
        r"\end{abstract}",
        "",
    ]


def render_section_body(section: dict[str, Any], state: dict[str, Any], project_dir: Path) -> list[str]:
    section_id = section["section_id"]
    content, suffix = section_content(section, project_dir)
    if content:
        return render_content_text(content, suffix, heading_offset=1)

    lines: list[str] = []
    claims = records_for_section(state, "Claim", section_id)
    methods = records_for_section(state, "Method", section_id)
    experiments = records_for_section(state, "Experiment", section_id)
    results = records_for_section(state, "Result", section_id)
    issues = records_for_section(state, "Issue", section_id)

    if section.get("section_type") == "method" and not methods:
        methods = all_unsectioned_methods(state)

    if claims:
        lines.append(r"\paragraph{Claims.}")
        for claim in claims:
            lines.append(sentence(claim["text"]))
        lines.append("")

    if methods:
        lines.append(r"\paragraph{Methods.}")
        for method in methods:
            summary = method.get("summary") or method.get("role_in_paper") or ""
            lines.append(rf"\textbf{{{tex_escape(method['name'])}.}} {sentence(summary)}")
        lines.append("")

    if experiments:
        lines.append(r"\paragraph{Experiments.}")
        for experiment in experiments:
            purpose = experiment.get("purpose") or experiment.get("protocol_summary") or ""
            lines.append(rf"\textbf{{{tex_escape(experiment['name'])}.}} {sentence(purpose)}")
        lines.append("")

    if results:
        lines.append(r"\paragraph{Results.}")
        for result in results:
            lines.append(sentence(result["summary"]))
        lines.append("")

    if issues:
        lines.append("% Open issues for author review:")
        for issue in issues:
            lines.append(f"% TODO [{issue.get('severity', 'P?')}] {issue.get('evidence', '')}")
        lines.append("")

    if not lines:
        lines.append("% TODO: Draft this section.")
        lines.append("")
    return lines


def latest_manuscript_artifact(state: dict[str, Any], project_dir: Path) -> tuple[dict[str, Any], Path] | None:
    candidates = []
    for artifact in objects(state, "Artifact").values():
        if artifact.get("artifact_type") not in {"manuscript_md", "draft_md"}:
            continue
        path_value = artifact.get("path")
        if not path_value:
            continue
        path = resolve_text_path(project_dir, str(path_value))
        if path is not None and path.suffix.lower() == ".md":
            candidates.append((artifact, path))
    if not candidates:
        return None
    candidates.sort(key=lambda item: str(item[0].get("created_at") or item[0].get("artifact_id") or ""))
    return candidates[-1]


def sections_have_text(sections: list[dict[str, Any]], project_dir: Path) -> bool:
    for section in sections:
        if section.get("section_type") == "title":
            continue
        content, _suffix = section_content(section, project_dir)
        if content and content.strip():
            return True
    return False


def render_tex(state: dict[str, Any], project_dir: Path) -> str:
    paper = first_paper(state)
    sections = sorted(objects(state, "Section").values(), key=section_sort_key)
    title = tex_escape(paper.get("title") or paper.get("paper_id") or "Untitled Paper")

    lines = [
        r"\documentclass{article}",
        r"\usepackage[utf8]{inputenc}",
        r"\usepackage{booktabs}",
        "",
        rf"\title{{{title}}}",
        r"\author{}",
        r"\date{}",
        "",
        r"\begin{document}",
        r"\maketitle",
        "",
    ]

    manuscript_artifact = latest_manuscript_artifact(state, project_dir)
    if manuscript_artifact and not sections_have_text(sections, project_dir):
        _artifact, path = manuscript_artifact
        lines.extend(markdown_to_tex(path.read_text(encoding="utf-8")))
        lines.append("")
        lines.append(r"\end{document}")
        lines.append("")
        return "\n".join(lines)

    rendered_any_section = False
    for section in sections:
        section_type = section.get("section_type")
        title_text = section.get("title") or section_type or section["section_id"]
        if section_type == "title":
            continue
        if section_type == "abstract":
            lines.extend(render_abstract(section, paper, state, project_dir))
            rendered_any_section = True
            continue
        lines.append(rf"\section{{{tex_escape(title_text)}}}")
        lines.extend(render_section_body(section, state, project_dir))
        rendered_any_section = True

    if not rendered_any_section:
        lines.extend([
            r"\begin{abstract}",
            paper.get("main_claim") or "% TODO: Write abstract.",
            r"\end{abstract}",
            "",
            r"\section{Introduction}",
            "% TODO: Draft introduction.",
            "",
        ])

    citations = objects(state, "Citation")
    bib_artifacts = [
        artifact for artifact in objects(state, "Artifact").values()
        if artifact.get("artifact_type") == "bibliography_bib"
    ]
    if bib_artifacts:
        stem = Path(bib_artifacts[0]["path"]).stem
        lines.extend([r"\bibliographystyle{plain}", rf"\bibliography{{{tex_escape(stem)}}}", ""])
    elif citations:
        lines.append(r"\begin{thebibliography}{9}")
        for index, citation in enumerate(citations.values(), start=1):
            key = citation.get("citation_key") or f"ref{index}"
            title = citation.get("title") or "Untitled reference"
            authors = citation.get("authors") or ""
            year = citation.get("year") or ""
            lines.append(rf"\bibitem{{{tex_escape(key)}}} {tex_escape(authors)}. {tex_escape(title)}. {tex_escape(str(year))}.")
        lines.extend([r"\end{thebibliography}", ""])

    lines.append(r"\end{document}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export paper.yml state into an editable LaTeX manuscript draft.")
    parser.add_argument("project_dir")
    parser.add_argument("--state", default="state/paper.yml")
    parser.add_argument("--out", default="artifacts/exported_manuscript.tex")
    parser.add_argument("--append-event", action="store_true", help="Record exported manuscript as an Artifact event.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    state_path = project_dir / args.state
    out_path = project_dir / args.out
    state = read_state(state_path)
    tex = render_tex(state, project_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(tex, encoding="utf-8")

    if args.append_event:
        registry = load_registry()
        log_path = project_dir / "events" / "event_log.yml"
        offset = next_offset(log_path)
        paper = first_paper(state)
        artifact_id = f"A-exported-manuscript-{offset:03d}"
        event = make_event(
            offset=offset,
            actor="assembly_expert",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=artifact_id,
            payload={
                "artifact_id": artifact_id,
                "paper_id": paper["paper_id"],
                "artifact_type": "manuscript_tex",
                "path": str(out_path.relative_to(project_dir.parent.parent)).replace("\\", "/")
                if project_dir.parent.parent in out_path.parents
                else str(out_path),
                "description": "LaTeX manuscript exported from paper.yml state.",
                "produced_by": "export_tex_from_state.py",
            },
        )
        append_event(log_path, event, registry)
        events = read_events(log_path)
        errors = validate_event_log(events, registry)
        if errors:
            for error in errors:
                print(error)
            return 1
        write_yaml(project_dir / "state" / "paper.yml", project_state(events, log_path.parent))

    print(f"exported tex: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
