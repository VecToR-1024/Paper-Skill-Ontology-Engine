from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from path_utils import portable_path


ROOT = Path(__file__).resolve().parents[1]
DYNAMIC = ROOT / "dynamic"


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
            candidates = [(project_dir / path_value).resolve(), (ROOT / path_value).resolve()]
            path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
        artifacts.append(
            {
                "artifact_id": artifact_id,
                "artifact_type": str(artifact.get("artifact_type", "")),
                "path": portable_path(path, project_dir, ROOT),
                "exists": str(path.exists()).lower(),
            }
        )
    return artifacts


def default_invocation_id(expert_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    short_name = expert_name.replace("_expert", "").replace("_", "-")
    return f"EX-{short_name}-{timestamp}"


def worker_packet(expert_name: str, invocation_id: str, paper_id: str) -> str:
    return f"""# Isolated Expert Worker Packet

invocation_id: {invocation_id}
paper_id: {paper_id}
expert: {expert_name}

## Instructions

- Read `runner_manifest.yml` first.
- Read `input_snapshot/paper.yml`, `expert_brief.md`, `expert_output_contract.md`, `action_policy.yml`, and `task.md`.
- Use listed artifacts only when needed.
- Do not modify `paper.yml`, `event_log.yml`, or project state.
- Do not append events.
- Write outputs to `outputs/`.
- Ensure the main runtime records the actual execution backend with `record_expert_execution.py`; preparing this packet does not prove isolation.
- Do not create project-level HTML overview/draft pages or other side files unless the task explicitly asks for them.
- Any durable file outside this invocation's report must be proposed with `artifact.created` so the main runtime can record it in the event log.

## Expected Outputs

- `outputs/report.md`
- `outputs/proposals.yml`

`proposals.yml` must follow `expert_output_contract.md` and `action_policy.yml`. If no state change is needed, write:

```yaml
proposals: []
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare an isolated expert invocation packet.")
    parser.add_argument("project_dir")
    parser.add_argument("expert_name")
    parser.add_argument("--task", default="Run the expert on the frozen paper state and produce report/proposals.")
    parser.add_argument("--invocation-id")
    parser.add_argument("--mode", choices=["isolated_worker", "multi_agent_review"])
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    experts_doc = load_yaml(DYNAMIC / "experts.yml")
    invocation_policy = load_yaml(DYNAMIC / "invocation_policy.yml")
    experts = experts_doc["experts"]
    if args.expert_name not in experts:
        raise ValueError(f"unknown expert: {args.expert_name}")

    expert = experts[args.expert_name]
    default_mode = invocation_policy["expert_defaults"].get(args.expert_name, "isolated_worker")
    mode = args.mode or default_mode
    if mode == "multi_agent_review":
        raise ValueError("use prepare_review_run.py for multi_agent_review")

    project_dir = Path(args.project_dir).resolve()
    state_path = project_dir / "state" / "paper.yml"
    if not state_path.exists():
        raise FileNotFoundError(f"missing state snapshot: {state_path}")
    state = load_yaml(state_path)
    paper_id = paper_id_from_state(state)

    invocation_id = args.invocation_id or default_invocation_id(args.expert_name)
    run_dir = project_dir / "expert_invocations" / invocation_id
    if args.reset and run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    snapshot_dir = run_dir / "input_snapshot"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(state_path, snapshot_dir / "paper.yml")

    brief_path = ROOT / expert["brief_path"]
    shutil.copy2(brief_path, run_dir / "expert_brief.md")
    shutil.copy2(DYNAMIC / "expert_output_contract.md", run_dir / "expert_output_contract.md")
    shutil.copy2(DYNAMIC / "action_policy.yml", run_dir / "action_policy.yml")
    write_text(run_dir / "task.md", args.task.strip() + "\n")
    write_text(run_dir / "worker_packet.md", worker_packet(args.expert_name, invocation_id, paper_id))
    (run_dir / "outputs").mkdir(exist_ok=True)

    manifest = {
        "invocation_id": invocation_id,
        "paper_id": paper_id,
        "expert_name": args.expert_name,
        "actor": expert.get("actor"),
        "mode": mode,
        "requested_mode": mode,
        "isolation": "not_verified",
        "execution": {
            "backend": "unassigned",
            "isolation_verified": False,
            "recorded_at": None,
            "recorded_by": None,
            "reason": None,
        },
        "input_snapshot": {
            "paper_yml": "input_snapshot/paper.yml",
        },
        "required_reads": {
            "expert_brief": "expert_brief.md",
            "expert_output_contract": "expert_output_contract.md",
            "action_policy": "action_policy.yml",
            "task": "task.md",
            "worker_packet": "worker_packet.md",
        },
        "artifacts": collect_artifacts(project_dir, state),
        "expected_outputs": invocation_policy["packet_contract"]["expected_outputs"],
        "commit_rule": invocation_policy["packet_contract"]["commit_rule"],
        "notes": [
            "Worker must not write event_log.yml or state/paper.yml.",
            "Main agent/runtime validates outputs/proposals.yml before appending events.",
            "High-impact proposals must include rationale and references required by action_policy.yml.",
            "Do not create untracked project-level HTML pages such as outputs/paper-overview.html or outputs/paper-draft.html.",
            "Persistent files must be represented by artifact.created proposals.",
            "requested_mode is intent only; execution.backend records what actually ran.",
        ],
    }
    write_yaml(run_dir / "runner_manifest.yml", manifest)

    print(f"expert_invocation_dir: {run_dir}")
    print(f"paper_id: {paper_id}")
    print(f"expert_name: {args.expert_name}")
    print(f"mode: {mode}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
