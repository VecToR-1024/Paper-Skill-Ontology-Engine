from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from event_log import load_registry, project_state, read_events, validate_event_log
from path_utils import portable_path
from validate_literature_coverage import validate_literature_coverage_state


ROOT = Path(__file__).resolve().parents[1]
DURABLE_DIRS = ("artifacts", "outputs")
DURABLE_SUFFIXES = {
    ".bib",
    ".csv",
    ".docx",
    ".html",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".pdf",
    ".png",
    ".svg",
    ".tex",
    ".tsv",
    ".txt",
    ".yml",
    ".yaml",
}
MANUSCRIPT_ARTIFACT_TYPES = {"draft_md", "manuscript_md", "manuscript_tex", "manuscript_pdf"}
PLACEHOLDER_MARKERS = (
    "[待补充]",
    "待补充",
    "待引用",
    "TODO",
    "TBD",
    "<citation>",
    "<source>",
)


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def path_display(path: Path) -> str:
    return portable_path(path, ROOT)


def collect_expert_executions(project_dir: Path) -> list[dict[str, Any]]:
    executions: list[dict[str, Any]] = []
    invocation_root = project_dir / "expert_invocations"
    if not invocation_root.exists():
        return executions
    for manifest_path in sorted(invocation_root.glob("*/runner_manifest.yml")):
        manifest = load_yaml(manifest_path) or {}
        execution = manifest.get("execution") if isinstance(manifest, dict) else None
        if not isinstance(execution, dict):
            execution = {
                "backend": "legacy_unrecorded",
                "isolation_verified": False,
                "recorded_at": None,
                "recorded_by": None,
                "reason": None,
            }
        output_dir = manifest_path.parent / "outputs"
        executions.append(
            {
                "invocation_id": manifest.get("invocation_id", manifest_path.parent.name),
                "expert_name": manifest.get("expert_name"),
                "requested_mode": manifest.get("requested_mode", manifest.get("mode")),
                "backend": execution.get("backend", "unassigned"),
                "isolation_verified": bool(execution.get("isolation_verified")),
                "recorded_at": execution.get("recorded_at"),
                "recorded_by": execution.get("recorded_by"),
                "reason": execution.get("reason"),
                "report_exists": (output_dir / "report.md").exists(),
                "proposals_exist": (output_dir / "proposals.yml").exists(),
            }
        )
    return executions


def resolve_project_path(project_dir: Path, path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path.resolve()
    project_candidate = project_dir / path
    root_candidate = ROOT / path
    if root_candidate.exists():
        return root_candidate.resolve()
    return project_candidate.resolve()


def normalized_project_rel(project_dir: Path, path_value: str) -> str:
    resolved = resolve_project_path(project_dir, path_value)
    try:
        return resolved.relative_to(project_dir.resolve()).as_posix()
    except ValueError:
        return Path(path_value).as_posix().replace("\\", "/")


def artifact_path_set(project_dir: Path, artifacts: dict[str, dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for artifact in artifacts.values():
        path_value = artifact.get("path")
        if isinstance(path_value, str) and path_value.strip():
            paths.add(normalized_project_rel(project_dir, path_value))
    return paths


def scan_durable_files(project_dir: Path) -> list[Path]:
    files: list[Path] = []
    for dirname in DURABLE_DIRS:
        root = project_dir / dirname
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in DURABLE_SUFFIXES:
                files.append(path)
    return sorted(files)


def has_placeholder(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    return any(marker in value for marker in PLACEHOLDER_MARKERS)


def non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_internal_source_ref(source_ref: str) -> bool:
    stripped = source_ref.strip()
    internal_prefixes = (
        "S-",
        "Section ",
        "section ",
        "Abstract sentence",
        "abstract sentence",
        "Claim ",
        "Evidence ",
        "ReasoningStep ",
    )
    return stripped.startswith(internal_prefixes)


def links_by_source(state: dict[str, Any], link_type: str, from_type: str) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for link in state.get("links", []) or []:
        if link.get("status") == "removed":
            continue
        if link.get("link_type") != link_type:
            continue
        if link.get("from_object_type") != from_type:
            continue
        result.setdefault(str(link.get("from_object_id")), []).append(link)
    return result


def text_file_has_citation_hint(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    hints = ("\\cite{", "\\citep{", "\\citet{", "[@", "References", "参考文献")
    return any(hint in text for hint in hints)


def citation_is_traceable(citation: dict[str, Any]) -> bool:
    if non_empty_string(citation.get("uri")):
        return True
    has_key = non_empty_string(citation.get("citation_key"))
    has_title = non_empty_string(citation.get("title"))
    has_authors = non_empty_string(citation.get("authors"))
    has_year = citation.get("year") is not None
    if has_key and (has_title or has_authors or has_year):
        return True
    return has_title and (has_authors or has_year)


def validate_project(
    project_dir: Path,
    max_section_content_chars: int,
    max_total_section_content_chars: int,
    allow_no_citations: bool,
) -> dict[str, Any]:
    project_dir = project_dir.resolve()
    errors: list[str] = []
    warnings: list[str] = []

    log_path = project_dir / "events" / "event_log.yml"
    state_path = project_dir / "state" / "paper.yml"
    if not log_path.exists():
        errors.append(f"missing event log: {path_display(log_path)}")
        events: list[dict[str, Any]] = []
    else:
        events = read_events(log_path)
        registry = load_registry()
        for error in validate_event_log(events, registry):
            errors.append(f"event_log: {error}")

    if not state_path.exists():
        errors.append(f"missing projected state: {path_display(state_path)}")
        state: dict[str, Any] = {"objects": {}, "links": []}
    else:
        state = load_yaml(state_path) or {"objects": {}, "links": []}
        if events:
            replayed = project_state(events, log_path.parent)
            if state != replayed:
                errors.append("state/paper.yml does not match replayed event_log projection")

    objects = state.get("objects", {}) if isinstance(state, dict) else {}
    expert_executions = collect_expert_executions(project_dir)
    for execution in expert_executions:
        backend = execution["backend"]
        if backend == "current_agent_fallback":
            warnings.append(
                f"expert invocation {execution['invocation_id']} used current_agent_fallback; "
                "context isolation was not verified"
            )
        elif backend in {"unassigned", "legacy_unrecorded"} and (
            execution["report_exists"] or execution["proposals_exist"]
        ):
            warnings.append(
                f"expert invocation {execution['invocation_id']} has outputs but no recorded execution backend"
            )
    artifacts = objects.get("Artifact", {}) or {}
    claims = objects.get("Claim", {}) or {}
    citations = objects.get("Citation", {}) or {}
    evidence = objects.get("Evidence", {}) or {}
    external_works = objects.get("ExternalWork", {}) or {}
    results = objects.get("Result", {}) or {}
    search_runs = objects.get("SearchRun", {}) or {}
    sections = objects.get("Section", {}) or {}
    source_spans = objects.get("SourceSpan", {}) or {}
    papers = objects.get("Paper", {}) or {}

    artifact_paths = artifact_path_set(project_dir, artifacts)
    durable_files = scan_durable_files(project_dir)
    untracked_files: list[str] = []
    for file_path in durable_files:
        rel = file_path.relative_to(project_dir).as_posix()
        if rel not in artifact_paths:
            untracked_files.append(rel)
    if untracked_files:
        errors.append(
            "durable files are not recorded as Artifact objects: "
            + ", ".join(untracked_files)
        )

    for artifact_id, artifact in artifacts.items():
        path_value = artifact.get("path")
        artifact_type = artifact.get("artifact_type")
        if not isinstance(path_value, str) or not path_value.strip():
            errors.append(f"Artifact {artifact_id} has no path")
            continue
        rel = normalized_project_rel(project_dir, path_value)
        candidate = resolve_project_path(project_dir, path_value)
        if not candidate.exists():
            errors.append(f"Artifact {artifact_id} path does not exist: {rel}")
        if candidate.suffix.lower() == ".html" and artifact_type != "preview_html":
            errors.append(f"HTML artifact {artifact_id} must use artifact_type preview_html, got {artifact_type}")

    for source_span_id, source_span in source_spans.items():
        artifact_id = source_span.get("artifact_id")
        if artifact_id not in artifacts:
            errors.append(f"SourceSpan {source_span_id} references missing Artifact {artifact_id}")
        if not non_empty_string(source_span.get("text_hash")):
            warnings.append(f"SourceSpan {source_span_id} has no text_hash")
        locator = source_span.get("locator")
        if not isinstance(locator, dict) or not locator:
            warnings.append(f"SourceSpan {source_span_id} has no locator details")

    citation_external_work_links = links_by_source(state, "citation_represents_external_work", "Citation")
    traceable_citation_ids: set[str] = set()
    for citation_id, external_work_links in citation_external_work_links.items():
        if citation_id not in citations:
            errors.append(f"Citation link references missing Citation {citation_id}")
            continue
        for link in external_work_links:
            external_work_id = link.get("to_object_id")
            if external_work_id not in external_works:
                errors.append(f"Citation {citation_id} links to missing ExternalWork {external_work_id}")
            else:
                traceable_citation_ids.add(citation_id)

    for citation_id, citation in citations.items():
        if citation_id not in traceable_citation_ids and not citation_is_traceable(citation):
            errors.append(
                f"Citation {citation_id} is not traceable; expected uri or enough bibliographic metadata"
            )

    literature_coverage = validate_literature_coverage_state(state)
    if search_runs and citations and literature_coverage["unaccounted_roles"]:
        warnings.append(
            "literature positioning coverage is incomplete and has no targeted citation_gap Issue for: "
            + ", ".join(literature_coverage["unaccounted_roles"])
        )

    evidence_citation_links = links_by_source(state, "evidence_uses_citation", "Evidence")
    evidence_span_links = links_by_source(state, "evidence_anchored_to_source_span", "Evidence")
    evidence_ids_with_valid_span: set[str] = set()
    for evidence_id, span_links in evidence_span_links.items():
        if evidence_id not in evidence:
            errors.append(f"SourceSpan link references missing Evidence {evidence_id}")
            continue
        for link in span_links:
            source_span_id = link.get("to_object_id")
            if source_span_id not in source_spans:
                errors.append(f"Evidence {evidence_id} links to missing SourceSpan {source_span_id}")
            else:
                evidence_ids_with_valid_span.add(evidence_id)
    claim_citation_links = links_by_source(state, "claim_uses_citation", "Claim")
    strong_citation_links = [
        ("Evidence", source_id, link)
        for source_id, citation_links in evidence_citation_links.items()
        for link in citation_links
    ] + [
        ("Claim", source_id, link)
        for source_id, citation_links in claim_citation_links.items()
        for link in citation_links
    ]
    for source_type, source_id, link in strong_citation_links:
        citation_id = link.get("to_object_id")
        citation = citations.get(citation_id)
        if citation is None:
            errors.append(f"{source_type} {source_id} links to missing Citation {citation_id}")
        elif citation.get("verification_status") == "tentative":
            errors.append(
                f"tentative Citation {citation_id} cannot be used as support for {source_type} {source_id}"
            )

    for evidence_id, item in evidence.items():
        summary = item.get("summary")
        source_ref = item.get("source_ref")
        if has_placeholder(summary) or has_placeholder(source_ref):
            errors.append(f"Evidence {evidence_id} still contains placeholder text")
        artifact_id = item.get("artifact_id")
        if artifact_id and artifact_id not in artifacts:
            errors.append(f"Evidence {evidence_id} references missing Artifact {artifact_id}")
        has_artifact = bool(artifact_id)
        has_citation_link = bool(evidence_citation_links.get(evidence_id))
        has_source_span_link = evidence_id in evidence_ids_with_valid_span
        has_internal_source = bool(source_ref and is_internal_source_ref(str(source_ref)))
        if not has_artifact and not has_citation_link and not has_source_span_link and not has_internal_source:
            if source_ref:
                errors.append(
                    f"Evidence {evidence_id} has source_ref but no artifact_id, SourceSpan, or evidence_uses_citation link"
                )
            else:
                errors.append(
                    f"Evidence {evidence_id} has no auditable source; expected artifact_id, SourceSpan, "
                    "internal source_ref, or evidence_uses_citation link"
                )

    claim_evidence_links = links_by_source(state, "claim_supported_by_evidence", "Claim")
    claim_span_links = links_by_source(state, "claim_anchored_to_source_span", "Claim")
    for claim_id, claim in claims.items():
        has_evidence_support = bool(claim_evidence_links.get(claim_id))
        has_source_span_support = bool(claim_span_links.get(claim_id))
        if has_evidence_support or has_source_span_support:
            continue
        paper_id = claim.get("paper_id")
        paper = papers.get(paper_id, {}) if isinstance(paper_id, str) else {}
        is_submission_stage = paper.get("stage") == "submission"
        is_strong = claim.get("strength") == "strong"
        message = f"Claim {claim_id} has no Evidence or SourceSpan support"
        if is_submission_stage and is_strong:
            errors.append(f"Strong {message}")
        else:
            warnings.append(message)

    result_span_links = links_by_source(state, "result_anchored_to_source_span", "Result")
    for result_id, result in results.items():
        if result.get("artifact_id") or result_span_links.get(result_id):
            continue
        warnings.append(f"Result {result_id} has no Artifact or SourceSpan support")

    total_section_content_chars = 0
    sections_with_inline_content = 0
    for section_id, section in sections.items():
        content = section.get("content")
        if isinstance(content, str) and len(content) > max_section_content_chars:
            errors.append(
                f"Section {section_id} stores {len(content)} chars in state; use a section/draft artifact with content_path"
            )
        if isinstance(content, str) and content.strip():
            total_section_content_chars += len(content)
            sections_with_inline_content += 1

    if total_section_content_chars > max_total_section_content_chars:
        errors.append(
            f"Sections store {total_section_content_chars} total chars inline across "
            f"{sections_with_inline_content} sections; move draft/manuscript text into artifacts"
        )

    total_event_section_content_chars = 0
    for event in events:
        if event.get("action_type") == "section.upserted":
            content = (event.get("payload") or {}).get("content")
            if isinstance(content, str) and len(content) > max_section_content_chars:
                errors.append(
                    f"{event.get('event_id')} section.upserted stores {len(content)} chars in event payload"
                )
            if isinstance(content, str) and content.strip():
                total_event_section_content_chars += len(content)
    if total_event_section_content_chars > max_total_section_content_chars:
        errors.append(
            f"section.upserted events store {total_event_section_content_chars} total chars inline; "
            "write long drafts as artifacts and store paths in events"
        )

    has_manuscript_artifact = any(
        artifact.get("artifact_type") in MANUSCRIPT_ARTIFACT_TYPES for artifact in artifacts.values()
    )
    has_manuscript_file = any(path.name.lower() in {"manuscript.md", "exported_manuscript.tex"} for path in durable_files)
    has_citation_hint = any(
        path.suffix.lower() in {".md", ".tex"} and text_file_has_citation_hint(path)
        for path in durable_files
    )
    if not allow_no_citations and (has_manuscript_artifact or has_manuscript_file or has_citation_hint) and not citations:
        errors.append("manuscript/draft files exist but no Citation objects are recorded")

    acceptance_status = "failed" if errors else ("accepted_with_warnings" if warnings else "accepted")

    return {
        "project_dir": portable_path(project_dir, ROOT),
        "acceptance_status": acceptance_status,
        "event_count": len(events),
        "artifact_count": len(artifacts),
        "citation_count": len(citations),
        "evidence_count": len(evidence),
        "external_work_count": len(external_works),
        "source_span_count": len(source_spans),
        "literature_coverage": literature_coverage,
        "expert_executions": expert_executions,
        "durable_file_count": len(durable_files),
        "inline_section_content_chars": total_section_content_chars,
        "errors": errors,
        "warnings": warnings,
    }


def print_text_report(report: dict[str, Any]) -> None:
    print(f"Project acceptance: {report['acceptance_status']}")
    print(f"project_dir: {report['project_dir']}")
    print(
        "counts: "
        f"events={report['event_count']}, "
        f"artifacts={report['artifact_count']}, "
        f"citations={report['citation_count']}, "
        f"external_works={report['external_work_count']}, "
        f"evidence={report['evidence_count']}, "
        f"durable_files={report['durable_file_count']}"
    )
    if report["errors"]:
        print("errors:")
        for error in report["errors"]:
            print(f"- {error}")
    if report["warnings"]:
        print("warnings:")
        for warning in report["warnings"]:
            print(f"- {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a generated research-paper-suite project for acceptance.")
    parser.add_argument("project_dir")
    parser.add_argument("--max-section-content-chars", type=int, default=1500)
    parser.add_argument("--max-total-section-content-chars", type=int, default=3000)
    parser.add_argument("--allow-no-citations", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    report = validate_project(
        Path(args.project_dir),
        max_section_content_chars=args.max_section_content_chars,
        max_total_section_content_chars=args.max_total_section_content_chars,
        allow_no_citations=args.allow_no_citations,
    )
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
