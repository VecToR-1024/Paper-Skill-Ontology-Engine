from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any

import yaml

from path_utils import portable_path


ROOT = Path(__file__).resolve().parents[1]
ROLE_REFERENCE = ROOT / "references" / "review" / "reviewer_roles.md"
ROLE_NAMES = {
    "methodologist": "Methodologist",
    "domain_expert": "Domain Expert",
    "general_reviewer": "General Reviewer",
}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def paper_id_from_state(state: dict[str, Any]) -> str:
    papers = state.get("objects", {}).get("Paper", {})
    if not papers:
        raise ValueError("state has no Paper object")
    return next(iter(papers))


def collect_artifacts(project_dir: Path, state: dict[str, Any]) -> list[dict[str, str]]:
    artifacts = []
    for artifact_id, artifact in state.get("objects", {}).get("Artifact", {}).items():
        path_value = artifact.get("path")
        if not path_value:
            continue
        path = Path(path_value)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
            if not path.exists():
                path = (project_dir / path_value).resolve()
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": str(artifact.get("artifact_type", "")),
                "path": portable_path(path, project_dir, ROOT),
                "exists": str(path.exists()).lower(),
            }
        )
    return artifacts


def role_packet(role_key: str, review_id: str, paper_id: str, manifest_path: str) -> str:
    role_title = ROLE_NAMES[role_key]
    return f"""# {role_title} Review Packet

review_id: {review_id}
paper_id: {paper_id}
role: {role_key}
input_manifest: {manifest_path}

## Isolation Rules

- Read only the frozen input snapshot and this role packet.
- Do not read other reviewer outputs.
- Do not modify paper.yml, event_log.yml, or project state.
- Do not append events.
- Write a role report and optional role proposal draft only.

## Expected Output Files

- `role_outputs/{role_key}_report.md`
- `role_outputs/{role_key}_findings.yml`

## Findings YAML Shape

```yaml
role: {role_key}
summary: "<one sentence>"
confidence: 1-5
findings:
  - cluster_key: "<stable issue key, e.g. missing_baseline>"
    title: "<short title>"
    category: missing_evidence | overclaim | unclear_contribution | citation_gap | method_risk | experiment_risk | style_violation
    severity: P0 | P1 | P2
    evidence: "<specific evidence from frozen input>"
    suggested_action: "<actionable fix>"
    target_object_type: Claim | Evidence | ReasoningStep | Method | Dataset | Experiment | Metric | Result | Citation | Section | Paper | Artifact | Extraction | Venue
    target_object_id: "<id of the smallest affected semantic object>"
    missing_literature_role: "<required for citation_gap: predecessor | direct_competitor | later_extension | limitation>"
    section_id: "<optional>"
    claim_id: "<optional>"
```

Prefer `target_object_type` + `target_object_id` over paper-level findings. Use `Paper` only for truly global concerns.

## Role Reference

See `references/review/reviewer_roles.md` for the role checklist.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare a frozen mock-review run directory.")
    parser.add_argument("project_dir")
    parser.add_argument("--review-id", default="RV-001")
    parser.add_argument("--runner-backend", default="manual_packets", choices=["codex_subagent", "openai_parallel_calls", "manual_packets", "single_agent_fallback"])
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    state_path = project_dir / "state" / "paper.yml"
    if not state_path.exists():
        raise FileNotFoundError(f"missing state snapshot: {state_path}")
    state = load_yaml(state_path)
    paper_id = paper_id_from_state(state)
    run_dir = project_dir / "reviews" / args.review_id
    if args.reset and run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    snapshot_dir = run_dir / "input_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(state_path, snapshot_dir / "paper.yml")
    if ROLE_REFERENCE.exists():
        shutil.copy2(ROLE_REFERENCE, snapshot_dir / "reviewer_roles.md")

    manifest = {
        "review_id": args.review_id,
        "paper_id": paper_id,
        "runner_backend": args.runner_backend,
        "isolation": "true_multi_agent" if args.runner_backend in {"codex_subagent", "openai_parallel_calls"} else "simulated" if args.runner_backend == "single_agent_fallback" else "manual_packets",
        "input_snapshot": {
            "paper_yml": "input_snapshot/paper.yml",
            "reviewer_roles": "input_snapshot/reviewer_roles.md",
        },
        "artifacts": collect_artifacts(project_dir, state),
        "role_packets": {role: f"role_packets/{role}.md" for role in ROLE_NAMES},
        "role_outputs_dir": "role_outputs",
        "notes": [
            "Reviewer agents must not write event_log.yml or paper.yml.",
            "AC aggregation is the only step that creates final proposals.",
        ],
    }
    write_yaml(run_dir / "runner_manifest.yml", manifest)
    for role in ROLE_NAMES:
        write_text(run_dir / "role_packets" / f"{role}.md", role_packet(role, args.review_id, paper_id, "runner_manifest.yml"))
    (run_dir / "role_outputs").mkdir(exist_ok=True)

    print(f"review_run_dir: {run_dir}")
    print(f"paper_id: {paper_id}")
    print(f"runner_backend: {args.runner_backend}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
