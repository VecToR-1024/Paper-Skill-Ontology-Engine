from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ONTOLOGY = ROOT / "ontology"
KINETIC = ROOT / "kinetic"


def load_yaml(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return copy.deepcopy(default)
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return copy.deepcopy(default) if data is None else data


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def resolve_artifact_path(path_value: str, base_dir: Path | None = None) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    if base_dir is not None:
        candidate = (base_dir / path).resolve()
        if candidate.exists():
            return candidate
    return (ROOT / path).resolve()


def load_registry() -> dict[str, Any]:
    return {
        "properties": load_yaml(ONTOLOGY / "properties.yml"),
        "objects": load_yaml(ONTOLOGY / "objects.yml"),
        "links": load_yaml(ONTOLOGY / "links.yml"),
        "constraints": load_yaml(ONTOLOGY / "constraints.yml"),
        "event_schema": load_yaml(KINETIC / "event_schema.yml"),
        "actions": load_yaml(KINETIC / "actions.yml"),
        "functions": load_yaml(KINETIC / "functions.yml"),
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def event_id_for_offset(offset: int) -> str:
    return f"EVT-{offset:06d}"


def read_events(log_path: Path) -> list[dict[str, Any]]:
    data = load_yaml(log_path, {"events": []})
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError(f"{log_path} must contain an 'events' list")
    return data["events"]


def write_events(log_path: Path, events: list[dict[str, Any]]) -> None:
    write_yaml(log_path, {"events": events})


def make_event(
    *,
    offset: int,
    actor: str,
    function: str,
    action_type: str,
    object_type: str,
    object_id: str,
    payload: dict[str, Any],
    references: dict[str, Any] | None = None,
    rationale: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "offset": offset,
        "event_id": event_id_for_offset(offset),
        "timestamp": now_iso(),
        "actor": actor,
        "function": function,
        "action_type": action_type,
        "object_type": object_type,
        "object_id": object_id,
        "payload": payload,
    }
    if references:
        event["references"] = references
    if rationale:
        event["rationale"] = rationale
    if approval:
        event["approval"] = approval
    return event


def action_default_function(action: dict[str, Any]) -> str | None:
    return action.get("default_function") or action.get("function")


def action_allowed_functions(action: dict[str, Any]) -> set[str]:
    allowed = action.get("allowed_functions")
    if isinstance(allowed, list):
        return set(allowed)
    default = action_default_function(action)
    return {default} if default else set()


def approval_satisfies_required_gate(approval: Any) -> bool:
    if not isinstance(approval, dict):
        return False
    status = approval.get("status")
    approved_by = approval.get("approved_by")
    if status is None:
        return bool(approved_by)
    return str(status).lower() in {"approved", "user_approved"} and bool(approved_by)


def validate_required_approval(event: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    actions = registry["actions"]["action_types"]
    action_type = event.get("action_type")
    action = actions.get(action_type)
    if not action or not action.get("approval_required"):
        return []
    if approval_satisfies_required_gate(event.get("approval")):
        return []
    return [
        f"{action_type}: human approval is required before appending this event "
        "(expected approval.status=approved and approval.approved_by)"
    ]


def validate_issue_target(payload: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target_type = payload.get("target_object_type")
    target_id = payload.get("target_object_id")
    has_target_type = target_type is not None
    has_target_id = target_id is not None

    if has_target_type != has_target_id:
        errors.append("issue.created: target_object_type and target_object_id must be provided together")
        return errors
    if not has_target_type:
        return errors

    allowed = set(registry["properties"]["enums"].get("IssueTargetType", {}).get("values", []))
    objects = registry["objects"]["objects"]
    if target_type not in allowed:
        errors.append(f"issue.created.target_object_type: invalid issue target type {target_type}")
    if target_type not in objects:
        errors.append(f"issue.created.target_object_type: unknown object type {target_type}")
    if not isinstance(target_id, str) or not target_id.strip():
        errors.append("issue.created.target_object_id: must be a non-empty string")

    legacy_field_by_type = {
        "Section": "section_id",
        "Claim": "claim_id",
    }
    legacy_field = legacy_field_by_type.get(str(target_type))
    if legacy_field and payload.get(legacy_field) and payload[legacy_field] != target_id:
        errors.append(
            f"issue.created: {legacy_field} conflicts with target_object_id {target_id}"
        )
    return errors


def validate_event(event: dict[str, Any], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    envelope = registry["event_schema"]["event_envelope"]
    actions = registry["actions"]["action_types"]
    objects = registry["objects"]["objects"]
    links = registry["links"]["links"]
    enums = registry["properties"]["enums"]
    functions = registry["functions"]["functions"]

    for field in envelope["required"]:
        if field not in event:
            errors.append(f"missing envelope field: {field}")

    if errors:
        return errors

    action_type = event["action_type"]
    if action_type not in actions:
        errors.append(f"unknown action_type: {action_type}")
        return errors

    action = actions[action_type]
    object_type = event["object_type"]
    if object_type != action["object_type"]:
        errors.append(
            f"object_type mismatch: event has {object_type}, action expects {action['object_type']}"
        )
    if object_type != "Link" and object_type not in objects:
        errors.append(f"unknown object_type: {object_type}")

    function = event["function"]
    if function not in functions:
        errors.append(f"unknown function: {function}")
    allowed_functions = action_allowed_functions(action)
    if allowed_functions and function not in allowed_functions:
        errors.append(f"{action_type}: function {function} is not in allowed_functions {sorted(allowed_functions)}")

    payload = event["payload"]
    if not isinstance(payload, dict):
        errors.append("payload must be a mapping")
        return errors

    for field in action.get("required_payload", []):
        if field not in payload:
            errors.append(f"{action_type}: missing payload field {field}")

    for field, enum_name in action.get("enum_payload", {}).items():
        if field in payload and enum_name in enums:
            values = set(enums[enum_name]["values"])
            if payload[field] not in values:
                errors.append(f"{action_type}.{field}: invalid enum value {payload[field]}")
        elif field in payload:
            errors.append(f"{action_type}.{field}: unknown enum {enum_name}")

    if action_type == "issue.created":
        errors.extend(validate_issue_target(payload, registry))

    if object_type != "Link":
        object_schema = objects[object_type]
        primary_key = object_schema["primary_key"]
        if primary_key in payload and payload[primary_key] != event["object_id"]:
            errors.append(
                f"object_id mismatch: envelope has {event['object_id']}, payload {primary_key} is {payload[primary_key]}"
            )

    if object_type == "Link":
        link_type = payload.get("link_type")
        if link_type not in links:
            errors.append(f"unknown link_type: {link_type}")
        else:
            link = links[link_type]
            from_type = payload.get("from_object_type")
            to_type = payload.get("to_object_type")
            allowed_to = link["to"] if isinstance(link["to"], list) else [link["to"]]
            if from_type != link["from"]:
                errors.append(f"{link_type}: from_object_type must be {link['from']}")
            if to_type not in allowed_to:
                errors.append(f"{link_type}: to_object_type must be one of {allowed_to}")

    return errors


def validate_event_log(events: list[dict[str, Any]], registry: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_offset = 1
    seen_ids: set[str] = set()
    for event in events:
        offset = event.get("offset")
        event_id = event.get("event_id")
        if offset != expected_offset:
            errors.append(f"offset error: expected {expected_offset}, got {offset}")
        expected_id = event_id_for_offset(expected_offset)
        if event_id != expected_id:
            errors.append(f"event_id error at offset {expected_offset}: expected {expected_id}, got {event_id}")
        if event_id in seen_ids:
            errors.append(f"duplicate event_id: {event_id}")
        seen_ids.add(event_id)
        errors.extend(f"{event_id}: {error}" for error in validate_event(event, registry))
        expected_offset += 1
    return errors


def append_event(log_path: Path, event: dict[str, Any], registry: dict[str, Any]) -> None:
    events = read_events(log_path)
    next_offset = len(events) + 1
    if event.get("offset") != next_offset:
        raise ValueError(f"event offset must be {next_offset}")
    errors = validate_event(event, registry)
    errors.extend(validate_required_approval(event, registry))
    if errors:
        raise ValueError("invalid event:\n" + "\n".join(errors))
    events.append(event)
    write_events(log_path, events)


def next_offset(log_path: Path) -> int:
    return len(read_events(log_path)) + 1


def apply_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("objects", {})
    state.setdefault("links", [])
    action_type = event["action_type"]
    object_type = event["object_type"]
    object_id = event["object_id"]
    payload = event["payload"]
    actor = event["actor"]
    timestamp = event["timestamp"]

    if object_type == "Link":
        link_record = {
            "link_type": payload["link_type"],
            "from_object_type": payload["from_object_type"],
            "from_object_id": payload["from_object_id"],
            "to_object_type": payload["to_object_type"],
            "to_object_id": payload["to_object_id"],
            "status": "active",
            "created_at": timestamp,
            "created_by": actor,
        }
        if action_type == "link.created":
            state["links"].append(link_record)
        elif action_type == "link.removed":
            for existing in state["links"]:
                if all(existing.get(key) == link_record[key] for key in ("link_type", "from_object_type", "from_object_id", "to_object_type", "to_object_id")):
                    existing["status"] = "removed"
                    existing["updated_at"] = timestamp
        return state

    bucket = state["objects"].setdefault(object_type, {})
    record = bucket.get(object_id)
    if record is None:
        record = {
            "id": object_id,
            "created_at": timestamp,
            "created_by": actor,
            "status": "active",
        }
        bucket[object_id] = record
    else:
        record["updated_at"] = timestamp

    for key, value in payload.items():
        record[key] = value

    return state


def checkpoint_base_state(events: list[dict[str, Any]], base_dir: Path | None = None) -> dict[str, Any] | None:
    if not events:
        return None
    first = events[0]
    if first.get("action_type") != "checkpoint.created":
        return None
    payload = first.get("payload", {})
    checkpoint_path = payload.get("path")
    if not checkpoint_path:
        return None
    state = load_yaml(resolve_artifact_path(checkpoint_path, base_dir), {"objects": {}, "links": []})
    if not isinstance(state, dict):
        raise ValueError(f"checkpoint state must be a mapping: {checkpoint_path}")
    return state


def project_state(events: list[dict[str, Any]], base_dir: Path | None = None) -> dict[str, Any]:
    base_state = checkpoint_base_state(events, base_dir)
    state: dict[str, Any] = copy.deepcopy(base_state) if base_state is not None else {"objects": {}, "links": []}
    for event in events:
        state = apply_event(state, event)
    return state


def demo(out_dir: Path) -> None:
    registry = load_registry()
    log_path = out_dir / "events" / "event_log.yml"
    state_path = out_dir / "state" / "paper.yml"
    if log_path.exists():
        log_path.unlink()

    demo_events = [
        make_event(
            offset=1,
            actor="user",
            function="create_object",
            action_type="paper.created",
            object_type="Paper",
            object_id="P-001",
            payload={"paper_id": "P-001", "title": "Demo Paper", "field": "AI", "stage": "drafting"},
        ),
        make_event(
            offset=2,
            actor="writing_expert",
            function="upsert_object",
            action_type="section.upserted",
            object_type="Section",
            object_id="S-abstract",
            payload={
                "section_id": "S-abstract",
                "paper_id": "P-001",
                "section_type": "abstract",
                "title": "Abstract",
                "content_path": "artifacts/abstract-v1.md",
                "order_index": 1,
            },
        ),
        make_event(
            offset=3,
            actor="writing_expert",
            function="create_object",
            action_type="claim.created",
            object_type="Claim",
            object_id="C-001",
            payload={
                "claim_id": "C-001",
                "paper_id": "P-001",
                "section_id": "S-abstract",
                "text": "The proposed method improves robustness across model families.",
                "strength": "strong",
            },
        ),
        make_event(
            offset=4,
            actor="review_expert",
            function="create_object",
            action_type="issue.created",
            object_type="Issue",
            object_id="I-001",
            payload={
                "issue_id": "I-001",
                "paper_id": "P-001",
                "category": "overclaim",
                "severity": "P0",
                "issue_status": "open",
                "evidence": "The claim says across model families, but no evidence object has been linked yet.",
                "suggested_action": "Narrow the claim or add evidence.",
                "target_object_type": "Claim",
                "target_object_id": "C-001",
                "section_id": "S-abstract",
                "claim_id": "C-001",
            },
        ),
        make_event(
            offset=5,
            actor="router",
            function="create_link",
            action_type="link.created",
            object_type="Link",
            object_id="L-001",
            payload={
                "link_type": "issue_targets_object",
                "from_object_type": "Issue",
                "from_object_id": "I-001",
                "to_object_type": "Claim",
                "to_object_id": "C-001",
            },
        ),
    ]

    for event in demo_events:
        append_event(log_path, event, registry)
    events = read_events(log_path)
    errors = validate_event_log(events, registry)
    if errors:
        raise ValueError("demo log failed validation:\n" + "\n".join(errors))
    write_yaml(state_path, project_state(events))
    print(f"demo event log: {log_path}")
    print(f"demo state: {state_path}")


def cmd_validate_log(args: argparse.Namespace) -> int:
    registry = load_registry()
    events = read_events(Path(args.log))
    errors = validate_event_log(events, registry)
    if errors:
        print("Event log validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Event log validation: ok")
    return 0


def cmd_project(args: argparse.Namespace) -> int:
    events = read_events(Path(args.log))
    state = project_state(events, Path(args.log).resolve().parent)
    write_yaml(Path(args.out), state)
    print(f"Projected state: {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Event log utilities for research-paper-suite.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    demo_parser = subparsers.add_parser("demo", help="Create a demo event log and projected state.")
    demo_parser.add_argument("out_dir")

    validate_parser = subparsers.add_parser("validate-log", help="Validate an event log.")
    validate_parser.add_argument("log")

    project_parser = subparsers.add_parser("project", help="Project an event log to a state snapshot.")
    project_parser.add_argument("log")
    project_parser.add_argument("out")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "demo":
        demo(Path(args.out_dir))
        return 0
    if args.command == "validate-log":
        return cmd_validate_log(args)
    if args.command == "project":
        return cmd_project(args)
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
