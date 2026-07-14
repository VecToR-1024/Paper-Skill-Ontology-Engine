from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
KINETIC = ROOT / "kinetic"
DYNAMIC = ROOT / "dynamic"

POLICY_REFERENCE_KEYS = {
    "paper_ids",
    "section_ids",
    "claim_ids",
    "evidence_ids",
    "reasoning_step_ids",
    "method_ids",
    "dataset_ids",
    "experiment_ids",
    "metric_ids",
    "result_ids",
    "citation_ids",
    "review_ids",
    "issue_ids",
    "decision_ids",
    "venue_ids",
    "search_run_ids",
    "external_work_ids",
    "search_result_ids",
    "source_span_ids",
    "extraction_ids",
    "artifact_ids",
    "event_ids",
}


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data


def main() -> int:
    properties = load_yaml(ONTOLOGY / "properties.yml")
    objects_doc = load_yaml(ONTOLOGY / "objects.yml")
    links_doc = load_yaml(ONTOLOGY / "links.yml")
    constraints_doc = load_yaml(ONTOLOGY / "constraints.yml")
    event_schema = load_yaml(KINETIC / "event_schema.yml")
    actions_doc = load_yaml(KINETIC / "actions.yml")
    functions_doc = load_yaml(KINETIC / "functions.yml")
    experts_doc = load_yaml(DYNAMIC / "experts.yml")
    workflows_doc = load_yaml(DYNAMIC / "workflows.yml")
    approval_doc = load_yaml(DYNAMIC / "approval_policy.yml")
    action_policy_doc = load_yaml(DYNAMIC / "action_policy.yml")
    invocation_doc = load_yaml(DYNAMIC / "invocation_policy.yml")
    routing_doc = load_yaml(DYNAMIC / "routing_policy.yml")

    objects = set(objects_doc["objects"])
    enums = set(properties["enums"])
    common_props = set(properties["common_properties"])
    links = set(links_doc["links"])
    functions = set(functions_doc["functions"])
    actions = set(actions_doc["action_types"])
    experts = set(experts_doc["experts"])
    errors: list[str] = []

    for object_name, obj in objects_doc["objects"].items():
        common = obj.get("common")
        if common and common not in common_props:
            errors.append(f"{object_name}: unknown common property set {common}")
        for prop_name, spec in obj.get("properties", {}).items():
            if spec.get("type") == "enum" and spec.get("enum") not in enums:
                errors.append(f"{object_name}.{prop_name}: unknown enum {spec.get('enum')}")
            if spec.get("type") == "ref" and spec.get("target") not in objects:
                errors.append(f"{object_name}.{prop_name}: unknown target {spec.get('target')}")

    for link_name, link in links_doc["links"].items():
        targets = link["to"] if isinstance(link["to"], list) else [link["to"]]
        if link["from"] not in objects:
            errors.append(f"{link_name}: unknown from object {link['from']}")
        for target in targets:
            if target not in objects:
                errors.append(f"{link_name}: unknown to object {target}")

    for constraint in constraints_doc["constraints"]:
        object_type = constraint.get("object_type") or constraint.get("scope_object")
        if object_type and object_type not in objects:
            errors.append(f"{constraint['id']}: unknown object {object_type}")
        link_type = constraint.get("link_type")
        if link_type and link_type not in links:
            errors.append(f"{constraint['id']}: unknown link {link_type}")

    for field_name, spec in event_schema["event_envelope"]["fields"].items():
        if spec.get("type") == "enum" and spec.get("enum") not in enums:
            errors.append(f"event_envelope.{field_name}: unknown enum {spec.get('enum')}")

    for action_name, action in actions_doc["action_types"].items():
        object_type = action["object_type"]
        if object_type != "Link" and object_type not in objects:
            errors.append(f"{action_name}: unknown object type {object_type}")
        default_function = action.get("default_function") or action.get("function")
        allowed_functions = action.get("allowed_functions") or ([default_function] if default_function else [])
        if not default_function:
            errors.append(f"{action_name}: missing default_function")
        elif default_function not in functions:
            errors.append(f"{action_name}: unknown default_function {default_function}")
        if default_function and default_function not in allowed_functions:
            errors.append(f"{action_name}: default_function must be included in allowed_functions")
        for function_name in allowed_functions:
            if function_name not in functions:
                errors.append(f"{action_name}: unknown allowed function {function_name}")
        for field_name, enum_name in action.get("enum_payload", {}).items():
            if enum_name not in enums:
                errors.append(f"{action_name}.{field_name}: unknown enum {enum_name}")

    for expert_name, expert in experts_doc["experts"].items():
        actor = expert.get("actor")
        if actor and actor not in properties["enums"]["ActorType"]["values"]:
            errors.append(f"{expert_name}: unknown actor {actor}")
        brief_path = ROOT / expert["brief_path"]
        if not brief_path.exists():
            errors.append(f"{expert_name}: missing brief {expert['brief_path']}")
        for object_type in expert.get("reads", []) + expert.get("writes", []):
            if object_type not in objects:
                errors.append(f"{expert_name}: unknown object {object_type}")
        for action_type in expert.get("may_emit_actions", []):
            if action_type not in actions:
                errors.append(f"{expert_name}: unknown action {action_type}")

    for workflow_name, workflow in workflows_doc["workflows"].items():
        for expert_name in workflow.get("experts", []):
            if expert_name not in experts:
                errors.append(f"{workflow_name}: unknown expert {expert_name}")
        for function_name in workflow.get("functions", []):
            if function_name not in functions:
                errors.append(f"{workflow_name}: unknown function {function_name}")
        for action_type in workflow.get("may_emit_actions", []):
            if action_type not in actions:
                errors.append(f"{workflow_name}: unknown action {action_type}")

    approval_policy = approval_doc["approval_policy"]
    for action_type in approval_policy.get("action_overrides", {}):
        if action_type not in actions:
            errors.append(f"approval_policy: unknown action {action_type}")
    for action_type in approval_policy.get("issue_gates", {}).get("P0", {}).get("blocks", []):
        if action_type not in actions:
            errors.append(f"approval_policy P0 gate: unknown action {action_type}")
    for decision_type in approval_policy.get("decision_type_overrides", {}):
        if decision_type not in properties["enums"]["DecisionType"]["values"]:
            errors.append(f"approval_policy: unknown decision type {decision_type}")

    action_policy = action_policy_doc.get("action_policies", {})
    rationale_fields = set(action_policy_doc.get("rationale_fields", {}))
    for action_type, policy in action_policy.items():
        if action_type not in actions:
            errors.append(f"action_policy: unknown action {action_type}")
        elif policy.get("requires_human_gate") and not actions_doc["action_types"][action_type].get("approval_required"):
            errors.append(f"action_policy.{action_type}: requires_human_gate but action approval_required is false")
        for field_name in policy.get("required_rationale", []):
            if field_name not in rationale_fields:
                errors.append(f"action_policy.{action_type}: unknown rationale field {field_name}")
        for reference_key in policy.get("required_references_any", []):
            if not isinstance(reference_key, str):
                errors.append(f"action_policy.{action_type}: required_references_any must contain strings")
            elif reference_key not in POLICY_REFERENCE_KEYS:
                errors.append(f"action_policy.{action_type}: unknown reference key {reference_key}")
        for reference_key in policy.get("anchor_reference_keys", []):
            if not isinstance(reference_key, str):
                errors.append(f"action_policy.{action_type}: anchor_reference_keys must contain strings")
            elif reference_key not in POLICY_REFERENCE_KEYS:
                errors.append(f"action_policy.{action_type}: unknown anchor reference key {reference_key}")

    invocation_policy = invocation_doc
    modes = set(invocation_policy.get("modes", {}))
    for name, mode in invocation_policy.get("defaults", {}).items():
        if mode not in modes:
            errors.append(f"invocation_policy.defaults.{name}: unknown mode {mode}")
    for expert_name, mode in invocation_policy.get("expert_defaults", {}).items():
        if expert_name not in experts:
            errors.append(f"invocation_policy: unknown expert {expert_name}")
        if mode not in modes:
            errors.append(f"invocation_policy.{expert_name}: unknown mode {mode}")

    decision_contract = ROOT / routing_doc["decision_contract"]
    if not decision_contract.exists():
        errors.append(f"routing_policy: missing decision contract {routing_doc['decision_contract']}")
    for next_step_type in routing_doc.get("next_step_types", []):
        if not isinstance(next_step_type, str):
            errors.append("routing_policy.next_step_types must contain strings")

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Semantic + kinetic + dynamic layer validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
