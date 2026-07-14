from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from event_log import load_registry, project_state, read_events, write_yaml


REFERENCE_KEY_BY_OBJECT_TYPE = {
    "Paper": "paper_ids",
    "Section": "section_ids",
    "Claim": "claim_ids",
    "Evidence": "evidence_ids",
    "ReasoningStep": "reasoning_step_ids",
    "Method": "method_ids",
    "Dataset": "dataset_ids",
    "Experiment": "experiment_ids",
    "Metric": "metric_ids",
    "Result": "result_ids",
    "Citation": "citation_ids",
    "Review": "review_ids",
    "Issue": "issue_ids",
    "Decision": "decision_ids",
    "Venue": "venue_ids",
    "Extraction": "extraction_ids",
    "Artifact": "artifact_ids",
}

UPDATE_FUNCTIONS = {"update_object", "upsert_object"}
CREATE_FUNCTIONS = {"create_object"}


def find_event(events: list[dict[str, Any]], event_ref: str) -> tuple[int, dict[str, Any]]:
    for index, event in enumerate(events):
        if str(event.get("event_id")) == event_ref or str(event.get("offset")) == event_ref:
            return index, event
    raise ValueError(f"target event not found: {event_ref}")


def object_record(state: dict[str, Any], object_type: str, object_id: str) -> dict[str, Any] | None:
    record = state.get("objects", {}).get(object_type, {}).get(object_id)
    return record if isinstance(record, dict) else None


def changed_payload_fields(
    payload: dict[str, Any],
    before_record: dict[str, Any],
    after_record: dict[str, Any],
    primary_key: str,
) -> list[str]:
    fields = []
    for field in payload:
        if field == primary_key:
            continue
        if before_record.get(field) != after_record.get(field):
            fields.append(field)
    return fields


def later_field_conflicts(
    events: list[dict[str, Any]],
    *,
    object_type: str,
    object_id: str,
    fields: set[str],
) -> list[dict[str, Any]]:
    conflicts = []
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("object_type") != object_type or event.get("object_id") != object_id:
            continue
        if fields.intersection(payload.keys()):
            conflicts.append(event)
    return conflicts


def issue_severity_revert_payload(
    *,
    object_id: str,
    before_record: dict[str, Any],
    after_record: dict[str, Any],
    target_event_id: str,
    reason: str,
) -> tuple[dict[str, Any], list[str]]:
    before_severity = before_record.get("severity")
    after_severity = after_record.get("severity")
    if before_severity == after_severity:
        raise ValueError(f"{target_event_id}: no severity change found to restore")
    if before_severity is None or after_severity is None:
        raise ValueError(f"{target_event_id}: severity missing before or after target event")
    return (
        {
            "issue_id": object_id,
            "previous_severity": after_severity,
            "severity": before_severity,
            "reclassification_reason": f"Revert {target_event_id}: {reason}",
        },
        ["severity"],
    )


def reference_for_object(object_type: str, object_id: str) -> dict[str, Any]:
    reference_key = REFERENCE_KEY_BY_OBJECT_TYPE.get(object_type)
    return {reference_key: [object_id]} if reference_key else {}


def build_revert_proposal(
    registry: dict[str, Any],
    events: list[dict[str, Any]],
    target_index: int,
    *,
    base_dir: Path | None,
    reason: str,
    actor: str,
    allow_conflicts: bool,
) -> dict[str, Any]:
    target = events[target_index]
    action_type = str(target.get("action_type"))
    action_spec = registry["actions"]["action_types"].get(action_type)
    if not action_spec:
        raise ValueError(f"{action_type}: action type is not registered")

    function = target.get("function") or action_spec.get("default_function")
    if function not in UPDATE_FUNCTIONS:
        if function in CREATE_FUNCTIONS:
            raise ValueError(
                f"{target.get('event_id')}: target object did not exist before the event; creation reverts are not supported yet"
            )
        raise ValueError(
            f"{target.get('event_id')}: only update/upsert object events are supported in this first revert slice"
        )

    object_type = str(target.get("object_type"))
    if object_type == "Link":
        raise ValueError("link revert is not supported yet; use link.created/link.removed explicitly")
    object_id = str(target.get("object_id"))
    payload = target.get("payload") if isinstance(target.get("payload"), dict) else {}
    object_schema = registry["objects"]["objects"].get(object_type)
    if not object_schema:
        raise ValueError(f"{object_type}: object type is not registered")
    primary_key = object_schema["primary_key"]

    before_state = project_state(events[:target_index], base_dir)
    after_state = project_state(events[: target_index + 1], base_dir)
    before_record = object_record(before_state, object_type, object_id)
    after_record = object_record(after_state, object_type, object_id)
    if before_record is None:
        raise ValueError(
            f"{target.get('event_id')}: target object did not exist before the event; creation reverts are not supported yet"
        )
    if after_record is None:
        raise ValueError(f"{target.get('event_id')}: target object missing after event")

    if action_type == "issue.severity_changed":
        revert_payload, changed_fields = issue_severity_revert_payload(
            object_id=object_id,
            before_record=before_record,
            after_record=after_record,
            target_event_id=str(target.get("event_id")),
            reason=reason,
        )
    else:
        changed_fields = changed_payload_fields(payload, before_record, after_record, primary_key)
        if not changed_fields:
            raise ValueError(f"{target.get('event_id')}: no changed payload fields found to restore")
        missing_before = [field for field in changed_fields if field not in before_record]
        if missing_before:
            raise ValueError(
                f"{target.get('event_id')}: cannot revert fields that were introduced by the event yet: {missing_before}"
            )

    conflicts = later_field_conflicts(
        events[target_index + 1 :],
        object_type=object_type,
        object_id=object_id,
        fields=set(changed_fields),
    )
    if conflicts and not allow_conflicts:
        ids = ", ".join(str(event.get("event_id")) for event in conflicts)
        raise ValueError(
            f"{target.get('event_id')}: later events also changed these fields; refusing lossy revert: {ids}"
        )

    if action_type != "issue.severity_changed":
        revert_payload = {primary_key: object_id}
        for field in action_spec.get("required_payload", []):
            if field == primary_key:
                continue
            if field not in before_record:
                raise ValueError(
                    f"{target.get('event_id')}: cannot build revert payload; required field {field} was missing before target event"
                )
            revert_payload[field] = before_record[field]
        for field in changed_fields:
            revert_payload[field] = before_record[field]

    references = {"event_ids": [target["event_id"]], **reference_for_object(object_type, object_id)}
    restored = ", ".join(changed_fields)
    return {
        "action_type": action_type,
        "actor": actor,
        "object_type": object_type,
        "object_id": object_id,
        "payload": revert_payload,
        "references": references,
        "rationale": {
            "problem_addressed": f"Undo committed event {target['event_id']} without editing history.",
            "why_this_action": (
                f"Append a compensating {action_type} event that restores {object_type} "
                f"{object_id} fields from the state before {target['event_id']}."
            ),
            "expected_state_delta": f"Restore {object_type} {object_id} fields: {restored}.",
            "alternatives_considered": "Deleting or editing the original event was rejected because the event log must remain append-only.",
            "risks": (
                "This only reverts fields changed by the target payload. Later dependent semantic changes may still need review."
            ),
            "confidence": "medium",
            "revert_reason": reason,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a compensating proposal to revert one committed event.")
    parser.add_argument("project_dir")
    parser.add_argument("event_ref", help="Target event_id or offset to revert.")
    parser.add_argument(
        "--out",
        help="Proposal output path. Defaults to <project_dir>/proposals/revert-<event_id>.yml.",
    )
    parser.add_argument("--actor", default="user")
    parser.add_argument("--reason", default="User requested semantic undo.")
    parser.add_argument(
        "--allow-conflicts",
        action="store_true",
        help="Allow revert proposal even if later events touched the same object fields.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    log_path = project_dir / "events" / "event_log.yml"
    try:
        events = read_events(log_path)
        registry = load_registry()
        target_index, target = find_event(events, str(args.event_ref))
        proposal = build_revert_proposal(
            registry,
            events,
            target_index,
            base_dir=log_path.parent,
            reason=args.reason,
            actor=args.actor,
            allow_conflicts=args.allow_conflicts,
        )
    except ValueError as error:
        print(f"revert proposal failed: {error}")
        return 1
    out_path = Path(args.out) if args.out else project_dir / "proposals" / f"revert-{target['event_id']}.yml"
    if not out_path.is_absolute():
        out_path = (project_dir / out_path).resolve()
    write_yaml(out_path, {"proposals": [proposal]})
    print(f"revert proposal: {out_path}")
    print(f"target event: {target['event_id']}")
    print(f"action_type: {proposal['action_type']}")
    print(f"object: {proposal['object_type']} {proposal['object_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
