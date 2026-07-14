from __future__ import annotations

import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SEVERITY_RANK = {"P0": 0, "P1": 1, "P2": 2}


def load_yaml(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return default if data is None else data


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "issue"


def strongest(severities: list[str]) -> str:
    return sorted(severities, key=lambda item: SEVERITY_RANK.get(item, 9))[0]


def escalated_severity(base: str, role_count: int, isolation: str) -> str:
    if isolation != "true_multi_agent":
        return base
    if role_count >= 3:
        return "P0" if base in {"P0", "P1"} else "P1"
    if role_count == 2 and base == "P2":
        return "P1"
    return base


def issue_target_from_finding(finding: dict[str, Any]) -> tuple[str, str] | None:
    target_type = finding.get("target_object_type")
    target_id = finding.get("target_object_id")
    if target_type and target_id:
        return str(target_type), str(target_id)
    if finding.get("claim_id"):
        return "Claim", str(finding["claim_id"])
    if finding.get("section_id"):
        return "Section", str(finding["section_id"])
    return None


def role_output_files(run_dir: Path) -> list[Path]:
    output_dir = run_dir / "role_outputs"
    return sorted(output_dir.glob("*_findings.yml")) + sorted(output_dir.glob("*_findings.yaml"))


def read_role_outputs(run_dir: Path) -> list[dict[str, Any]]:
    outputs = []
    for path in role_output_files(run_dir):
        data = load_yaml(path, {})
        if isinstance(data, dict):
            data["_path"] = str(path)
            outputs.append(data)
    return outputs


def cluster_findings(outputs: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for output in outputs:
        role = output.get("role") or Path(output.get("_path", "unknown")).stem.replace("_findings", "")
        for finding in output.get("findings", []) or []:
            if not isinstance(finding, dict):
                continue
            key = finding.get("cluster_key") or finding.get("title") or finding.get("category") or "unclustered"
            enriched = dict(finding)
            enriched["role"] = role
            clusters[slug(str(key))].append(enriched)
    return clusters


def make_issue(cluster_key: str, findings: list[dict[str, Any]], paper_id: str, isolation: str) -> dict[str, Any]:
    roles = sorted({str(item.get("role", "unknown")) for item in findings})
    severities = [str(item.get("severity", "P2")) for item in findings]
    base = strongest(severities)
    severity = escalated_severity(base, len(roles), isolation)
    first = findings[0]
    evidence_parts = [f"[{item.get('role', 'unknown')}] {item.get('evidence', item.get('title', ''))}" for item in findings]
    payload: dict[str, Any] = {
        "issue_id": f"I-review-{cluster_key}",
        "paper_id": paper_id,
        "category": first.get("category", "method_risk"),
        "severity": severity,
        "issue_status": "open",
        "evidence": " | ".join(part for part in evidence_parts if part.strip()),
        "suggested_action": first.get("suggested_action", "Review and decide how to address this risk."),
    }
    if first.get("section_id"):
        payload["section_id"] = first["section_id"]
    if first.get("claim_id"):
        payload["claim_id"] = first["claim_id"]
    if first.get("missing_literature_role"):
        payload["missing_literature_role"] = first["missing_literature_role"]
    target = issue_target_from_finding(first)
    if target:
        payload["target_object_type"], payload["target_object_id"] = target
    return {
        "action_type": "issue.created",
        "payload": payload,
        "references": {
            "review_roles": roles,
            "cluster_key": cluster_key,
            "independent_role_count": len(roles),
            "isolation": isolation,
        },
    }


def aggregate_report(review_id: str, paper_id: str, isolation: str, clusters: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# Mock Review Aggregate Report",
        "",
        f"review_id: {review_id}",
        f"paper_id: {paper_id}",
        f"isolation: {isolation}",
        "",
        "## Independent Signals",
        "",
        "| Cluster | Roles | Suggested Severity | Summary |",
        "|---|---|---|---|",
    ]
    for key, findings in clusters.items():
        roles = ", ".join(sorted({str(item.get("role", "unknown")) for item in findings}))
        severity = escalated_severity(strongest([str(item.get("severity", "P2")) for item in findings]), len(set(roles.split(", "))), isolation)
        title = findings[0].get("title", key)
        lines.append(f"| {key} | {roles} | {severity} | {title} |")
    if not clusters:
        lines.append("| none | none | P2 | No structured findings were provided. |")
    lines.extend(["", "## Notes", "", "- Final event proposals are produced by AC aggregation, not by reviewer agents."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate role review outputs into final action proposals.")
    parser.add_argument("review_run_dir")
    parser.add_argument("--out", help="Output proposals YAML path. Defaults to review_run_dir/ac_proposals.yml.")
    args = parser.parse_args()

    run_dir = Path(args.review_run_dir).resolve()
    manifest = load_yaml(run_dir / "runner_manifest.yml", {})
    review_id = manifest.get("review_id", run_dir.name)
    paper_id = manifest.get("paper_id")
    if not paper_id:
        raise ValueError("runner_manifest.yml is missing paper_id")
    isolation = manifest.get("isolation", "manual_packets")
    outputs = read_role_outputs(run_dir)
    clusters = cluster_findings(outputs)
    report_path = run_dir / "aggregate_report.md"
    write_text(report_path, aggregate_report(review_id, paper_id, isolation, clusters))

    proposals: list[dict[str, Any]] = [
        {
            "action_type": "review.created",
            "payload": {
                "review_id": review_id,
                "paper_id": paper_id,
                "review_type": "mock_peer_review",
                "reviewer_role": "AC_aggregator",
                "summary": f"Aggregated {len(outputs)} role outputs into {len(clusters)} issue clusters ({isolation}).",
            },
        },
        {
            "action_type": "artifact.created",
            "payload": {
                "artifact_id": f"A-{review_id}-aggregate-report",
                "paper_id": paper_id,
                "artifact_type": "review_report",
                "path": str(report_path.relative_to(ROOT)).replace("\\", "/"),
                "description": "AC aggregate mock review report.",
                "produced_by": "aggregate_review_reports.py",
            },
        },
    ]
    for key, findings in clusters.items():
        proposals.append(make_issue(key, findings, paper_id, isolation))

    out_path = Path(args.out).resolve() if args.out else run_dir / "ac_proposals.yml"
    write_yaml(out_path, {"proposals": proposals})
    print(f"role_outputs: {len(outputs)}")
    print(f"clusters: {len(clusters)}")
    print(f"aggregate_report: {report_path}")
    print(f"proposals: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
