from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DYNAMIC = ROOT / "dynamic"
KINETIC = ROOT / "kinetic"


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an LLM-produced route_decision.yml.")
    parser.add_argument("route_decision")
    args = parser.parse_args()

    decision_doc = load_yaml(Path(args.route_decision))
    workflows_doc = load_yaml(DYNAMIC / "workflows.yml")
    experts_doc = load_yaml(DYNAMIC / "experts.yml")
    invocation_doc = load_yaml(DYNAMIC / "invocation_policy.yml")
    actions_doc = load_yaml(KINETIC / "actions.yml")
    routing_doc = load_yaml(DYNAMIC / "routing_policy.yml")

    decision = decision_doc.get("route_decision") if isinstance(decision_doc, dict) else None
    errors: list[str] = []
    if not isinstance(decision, dict):
        errors.append("missing route_decision mapping")
    else:
        for field in routing_doc["route_output"]["required_fields"]:
            if field not in decision:
                errors.append(f"missing required field: {field}")

    if errors:
        print("Route decision validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    assert isinstance(decision, dict)
    suite_triggered = bool(decision.get("suite_triggered"))
    workflows = workflows_doc["workflows"]
    experts = experts_doc["experts"]
    modes = invocation_doc["modes"]
    actions = actions_doc["action_types"]
    next_step_types = set(routing_doc["next_step_types"])

    if suite_triggered:
        workflow = decision.get("workflow")
        if workflow not in workflows:
            errors.append(f"unknown workflow: {workflow}")
        workflow_experts = workflows.get(workflow, {}).get("experts", []) if workflow in workflows else []
        primary_expert = decision.get("primary_expert")
        expertless_workflow = workflow in workflows and not workflow_experts
        if expertless_workflow:
            if primary_expert is not None:
                errors.append(f"{workflow}: primary_expert must be null for expertless workflow")
        elif primary_expert not in experts:
            errors.append(f"unknown primary_expert: {primary_expert}")
        invocation_mode = decision.get("invocation_mode")
        if expertless_workflow:
            if invocation_mode is not None:
                errors.append(f"{workflow}: invocation_mode must be null for expertless workflow")
        elif invocation_mode not in modes:
            errors.append(f"unknown invocation_mode: {invocation_mode}")

        secondary_experts = decision.get("secondary_experts") or []
        if not isinstance(secondary_experts, list):
            errors.append("secondary_experts must be a list")
        else:
            for expert_name in secondary_experts:
                if expert_name not in experts:
                    errors.append(f"unknown secondary_expert: {expert_name}")

        allowed_actions = decision.get("allowed_actions") or []
        if not isinstance(allowed_actions, list):
            errors.append("allowed_actions must be a list")
        else:
            workflow_actions = set(workflows.get(workflow, {}).get("may_emit_actions", []))
            if expertless_workflow:
                legal_actions = workflow_actions
            else:
                expert_actions = set(experts.get(primary_expert, {}).get("may_emit_actions", []))
                legal_actions = workflow_actions & expert_actions
            for action in allowed_actions:
                if action not in actions:
                    errors.append(f"unknown allowed action: {action}")
                elif workflow in workflows and action not in legal_actions:
                    if expertless_workflow:
                        errors.append(f"allowed action is outside workflow action surface: {action}")
                    elif primary_expert in experts:
                        errors.append(f"allowed action is outside workflow/expert intersection: {action}")
    else:
        for nullable_field in ("workflow", "primary_expert", "invocation_mode"):
            if decision.get(nullable_field) is not None:
                errors.append(f"{nullable_field} must be null when suite_triggered is false")
        if decision.get("allowed_actions") not in ([], None):
            errors.append("allowed_actions must be empty when suite_triggered is false")

    next_step = decision.get("next_step")
    if not isinstance(next_step, dict):
        errors.append("next_step must be a mapping")
    elif next_step.get("type") not in next_step_types:
        errors.append(f"unknown next_step.type: {next_step.get('type')}")

    rationale = decision.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        errors.append("rationale must be a non-empty string")

    if errors:
        print("Route decision validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Route decision validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
