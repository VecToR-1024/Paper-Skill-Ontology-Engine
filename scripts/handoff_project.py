from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from export_project_visualization import build_project_data, render_html, write_json
from path_utils import portable_path
from validate_project_acceptance import (
    load_yaml,
    normalized_project_rel,
    resolve_project_path,
    validate_project,
)


MANIFEST_SCHEMA_VERSION = "0.1.0"
DEFAULT_MANIFEST_NAME = "handoff_manifest.yml"
ACCEPTED_HANDOFF_STATUSES = {"accepted", "accepted_with_warnings"}
VISUALIZATION_OUTPUT_FILES = (
    ("visualization_events", "events.json"),
    ("visualization_objects", "objects.json"),
    ("visualization_graph", "graph.json"),
    ("visualization_story", "story.json"),
    ("visualization_bundle", "visualization.json"),
)


def file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def project_rel(project_dir: Path, path: Path) -> str:
    return portable_path(path, project_dir, Path(__file__).resolve().parents[1])


def artifact_entries(project_dir: Path, state: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = state.get("objects", {}).get("Artifact", {}) if isinstance(state, dict) else {}
    entries: list[dict[str, Any]] = []
    for artifact_id, artifact in sorted(artifacts.items()):
        path_value = artifact.get("path")
        resolved = resolve_project_path(project_dir, path_value) if isinstance(path_value, str) else None
        entry: dict[str, Any] = {
            "artifact_id": artifact_id,
            "artifact_type": artifact.get("artifact_type"),
            "path": normalized_project_rel(project_dir, path_value) if isinstance(path_value, str) else None,
            "exists": bool(resolved and resolved.exists()),
        }
        if resolved and resolved.exists() and resolved.is_file():
            entry["sha256"] = file_sha256(resolved)
        entries.append(entry)
    return entries


def output_entry(project_dir: Path, label: str, path: Path) -> dict[str, Any]:
    return {
        "label": label,
        "path": project_rel(project_dir, path),
        "exists": path.exists(),
        "sha256": file_sha256(path),
    }


def planned_output_entry(project_dir: Path, label: str, path: Path) -> dict[str, Any]:
    return {
        "label": label,
        "path": project_rel(project_dir, path),
        "exists": False,
        "sha256": None,
        "generated_by_handoff": False,
    }


def acceptance_label(status: Any) -> str:
    labels = {
        "accepted": "Accepted",
        "accepted_with_warnings": "Accepted with warnings",
        "failed": "Failed",
        "not_checked": "Not checked",
    }
    return labels.get(str(status), "Unknown")


def acceptance_data_from_manifest(
    project_dir: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    validation = manifest.get("validation", {}) if isinstance(manifest.get("validation"), dict) else {}
    status = manifest.get("acceptance_status", "unknown")
    return {
        "status": status,
        "label": acceptance_label(status),
        "manifest_path": project_rel(project_dir, manifest_path),
        "generated_at": manifest.get("generated_at"),
        "error_count": validation.get("error_count"),
        "warning_count": validation.get("warning_count"),
    }


def resolve_visualization_dir(args: argparse.Namespace, project_dir: Path) -> Path:
    if not args.visualization_out_dir:
        return project_dir / "visualization"
    out_dir = Path(args.visualization_out_dir)
    if not out_dir.is_absolute():
        out_dir = (project_dir / out_dir).resolve()
    return out_dir


def export_visualization(
    project_dir: Path,
    out_dir: Path,
    manifest_path: Path,
    manifest: dict[str, Any],
) -> Path:
    data = build_project_data(project_dir)
    data["acceptance"] = acceptance_data_from_manifest(project_dir, manifest_path, manifest)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "events.json", data["events"])
    write_json(out_dir / "objects.json", data["objects"])
    write_json(out_dir / "graph.json", data["graph"])
    write_json(out_dir / "story.json", data["story"])
    write_json(out_dir / "visualization.json", data)
    index_path = out_dir / "index.html"
    index_path.write_text(render_html(data), encoding="utf-8")
    return index_path


def update_formal_output(manifest: dict[str, Any], output: dict[str, Any]) -> None:
    outputs = manifest.setdefault("formal_outputs", [])
    for index, existing in enumerate(outputs):
        if existing.get("label") == output.get("label"):
            outputs[index] = output
            return
    outputs.append(output)


def validation_command(args: argparse.Namespace, project_dir: Path) -> list[str]:
    command = [
        "scripts/run_python.cmd",
        "scripts/validate_project_acceptance.py",
        portable_path(project_dir, Path(__file__).resolve().parents[1]),
        "--max-section-content-chars",
        str(args.max_section_content_chars),
        "--max-total-section-content-chars",
        str(args.max_total_section_content_chars),
    ]
    if args.allow_no_citations:
        command.append("--allow-no-citations")
    return command


def build_manifest(
    args: argparse.Namespace,
    project_dir: Path,
    manifest_path: Path,
    visualization_index: Path,
) -> dict[str, Any]:
    report = validate_project(
        project_dir,
        max_section_content_chars=args.max_section_content_chars,
        max_total_section_content_chars=args.max_total_section_content_chars,
        allow_no_citations=args.allow_no_citations,
    )
    state_path = project_dir / "state" / "paper.yml"
    event_log_path = project_dir / "events" / "event_log.yml"
    state = load_yaml(state_path) if state_path.exists() else {"objects": {}, "links": []}
    manifest_output = output_entry(project_dir, "handoff_manifest", manifest_path)
    manifest_output["exists"] = True
    manifest_output["sha256"] = None
    manifest_output["generated_by_handoff"] = True

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_type": "project_handoff",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": portable_path(project_dir, Path(__file__).resolve().parents[1]),
        "acceptance_status": report["acceptance_status"],
        "validation": {
            "command": validation_command(args, project_dir),
            "error_count": len(report["errors"]),
            "warning_count": len(report["warnings"]),
            "report": report,
        },
        "source_of_truth": {
            "event_log": output_entry(project_dir, "event_log", event_log_path),
            "state_projection": output_entry(project_dir, "paper_state", state_path),
            "event_count": report["event_count"],
        },
        "formal_outputs": [
            manifest_output,
            planned_output_entry(project_dir, "visualization", visualization_index),
        ],
        "expert_executions": report.get("expert_executions", []),
        "artifacts": artifact_entries(project_dir, state or {}),
    }


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def print_summary(manifest: dict[str, Any], manifest_path: Path) -> None:
    validation = manifest["validation"]
    print(f"handoff_status: {manifest['acceptance_status']}")
    print(f"manifest: {manifest_path}")
    print(f"errors: {validation['error_count']}")
    print(f"warnings: {validation['warning_count']}")
    for error in validation["report"]["errors"]:
        print(f"- {error}")
    for warning in validation["report"]["warnings"]:
        print(f"- warning: {warning}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a formal handoff manifest after project acceptance validation.")
    parser.add_argument("project_dir")
    parser.add_argument("--manifest", help=f"Manifest path. Defaults to <project_dir>/{DEFAULT_MANIFEST_NAME}.")
    parser.add_argument("--max-section-content-chars", type=int, default=1500)
    parser.add_argument("--max-total-section-content-chars", type=int, default=3000)
    parser.add_argument("--allow-no-citations", action="store_true")
    parser.add_argument("--fail-on-warnings", action="store_true")
    parser.add_argument(
        "--visualization-out-dir",
        help="Visualization output directory. Defaults to <project_dir>/visualization.",
    )
    parser.add_argument(
        "--skip-visualization-export",
        action="store_true",
        help="Write the manifest without exporting the formal visualization.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    manifest_path = Path(args.manifest) if args.manifest else project_dir / DEFAULT_MANIFEST_NAME
    if not manifest_path.is_absolute():
        manifest_path = (project_dir / manifest_path).resolve()
    visualization_dir = resolve_visualization_dir(args, project_dir)
    visualization_index = visualization_dir / "index.html"

    manifest = build_manifest(args, project_dir, manifest_path, visualization_index)
    write_yaml(manifest_path, manifest)
    if (
        manifest["acceptance_status"] in ACCEPTED_HANDOFF_STATUSES
        and not args.skip_visualization_export
    ):
        export_visualization(project_dir, visualization_dir, manifest_path, manifest)
        visualization_output = output_entry(project_dir, "visualization", visualization_index)
        visualization_output["generated_by_handoff"] = True
        update_formal_output(manifest, visualization_output)
        for label, filename in VISUALIZATION_OUTPUT_FILES:
            update_formal_output(
                manifest,
                {
                    **output_entry(project_dir, label, visualization_dir / filename),
                    "generated_by_handoff": True,
                },
            )
        write_yaml(manifest_path, manifest)

    if args.json:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print_summary(manifest, manifest_path)

    if manifest["acceptance_status"] == "failed":
        return 1
    if args.fail_on_warnings and manifest["acceptance_status"] == "accepted_with_warnings":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
