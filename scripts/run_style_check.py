from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from event_log import (
    append_event,
    load_registry,
    make_event,
    next_offset,
    project_state,
    read_events,
    validate_event_log,
    write_yaml,
)


ROOT = Path(__file__).resolve().parents[1]
QUICK_SCAN = ROOT / "scripts" / "reused" / "quick_scan.py"


def run_quick_scan(target: Path) -> tuple[int, str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, str(QUICK_SCAN), str(target)],
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout


def summarize_quick_scan(report: str) -> str:
    for line in report.splitlines():
        if line.startswith("总计 "):
            return line.strip()
    return "quick_scan completed; summary line not found"


def severity_from_returncode(returncode: int) -> str:
    return "P1" if returncode else "P2"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run quick_scan and emit style-check events.")
    parser.add_argument("project_dir")
    parser.add_argument("artifact_path")
    parser.add_argument("--paper-id", required=True)
    parser.add_argument("--section-id", required=True)
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    if not project_dir.is_absolute():
        project_dir = (Path.cwd() / project_dir).resolve()
    artifact_path = Path(args.artifact_path)
    if not artifact_path.is_absolute():
        artifact_path = (ROOT / artifact_path).resolve()

    registry = load_registry()
    log_path = project_dir / "events" / "event_log.yml"
    state_path = project_dir / "state" / "paper.yml"
    report_path = project_dir / "artifacts" / "quick_scan_report.txt"

    returncode, report = run_quick_scan(artifact_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")

    offset = next_offset(log_path)
    report_artifact_id = f"A-quick-scan-{offset:03d}"
    review_id = f"R-quick-scan-{offset:03d}"
    issue_id = f"I-quick-scan-{offset:03d}"
    relative_report_path = report_path.resolve().relative_to(ROOT).as_posix()

    events = [
        make_event(
            offset=offset,
            actor="style_expert",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=report_artifact_id,
            payload={
                "artifact_id": report_artifact_id,
                "paper_id": args.paper_id,
                "artifact_type": "quick_scan_report",
                "path": relative_report_path,
                "description": "quick_scan.py mechanical style report.",
                "produced_by": "run_style_check.py",
            },
        ),
        make_event(
            offset=offset + 1,
            actor="style_expert",
            function="create_object",
            action_type="review.created",
            object_type="Review",
            object_id=review_id,
            payload={
                "review_id": review_id,
                "paper_id": args.paper_id,
                "review_type": "style_check",
                "reviewer_role": "quick_scan.py",
                "summary": summarize_quick_scan(report),
            },
        ),
    ]

    if returncode != 0:
        events.append(
            make_event(
                offset=offset + 2,
                actor="style_expert",
                function="create_object",
                action_type="issue.created",
                object_type="Issue",
                object_id=issue_id,
                payload={
                    "issue_id": issue_id,
                    "paper_id": args.paper_id,
                    "category": "style_violation",
                    "severity": severity_from_returncode(returncode),
                    "issue_status": "open",
                    "evidence": summarize_quick_scan(report),
                    "suggested_action": "Open the quick_scan report and address warnings or violations before deeper review.",
                    "section_id": args.section_id,
                    "review_id": review_id,
                },
            )
        )

    for event in events:
        append_event(log_path, event, registry)

    all_events = read_events(log_path)
    errors = validate_event_log(all_events, registry)
    if errors:
        for error in errors:
            print(error)
        return 1
    write_yaml(state_path, project_state(all_events))
    print(f"quick_scan report: {report_path}")
    print(f"events appended: {len(events)}")
    print(f"state updated: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
