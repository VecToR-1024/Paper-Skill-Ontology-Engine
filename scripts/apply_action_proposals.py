from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from event_log import (
    action_default_function,
    append_event,
    load_registry,
    make_event,
    next_offset,
    project_state,
    read_events,
    validate_event,
    validate_event_log,
    validate_required_approval,
    write_yaml,
)

ROOT = Path(__file__).resolve().parents[1]
DYNAMIC = ROOT / "dynamic"


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def proposal_items(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        items = data.get("proposals") or data.get("actions")
        if isinstance(items, list):
            return items
    raise ValueError("proposal file must contain a list or a mapping with 'proposals:'")


def paper_id_from_state(state_path: Path) -> str:
    data = load_yaml(state_path)
    papers = data.get("objects", {}).get("Paper", {}) if isinstance(data, dict) else {}
    if not papers:
        raise ValueError(f"cannot infer paper_id: {state_path} contains no Paper object")
    return next(iter(papers))


def rewrite_project_paper_id(proposals: list[dict[str, Any]], paper_id: str) -> None:
    for proposal in proposals:
        payload = proposal.get("payload")
        if isinstance(payload, dict) and "paper_id" in payload:
            payload["paper_id"] = paper_id


def action_spec(registry: dict[str, Any], action_type: str) -> dict[str, Any]:
    actions = registry["actions"]["action_types"]
    if action_type not in actions:
        raise ValueError(f"unknown action_type: {action_type}")
    return actions[action_type]


def load_action_policy() -> dict[str, Any]:
    return load_yaml(DYNAMIC / "action_policy.yml")


def action_policy_for(action_policy: dict[str, Any], action_type: str) -> dict[str, Any]:
    defaults = action_policy.get("defaults", {})
    policy = action_policy.get("action_policies", {}).get(action_type, {})
    merged = dict(defaults)
    merged.update(policy)
    return merged


def is_non_empty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return True


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


REFERENCE_OBJECT_TYPES = {
    "paper_ids": "Paper",
    "section_ids": "Section",
    "claim_ids": "Claim",
    "evidence_ids": "Evidence",
    "reasoning_step_ids": "ReasoningStep",
    "method_ids": "Method",
    "dataset_ids": "Dataset",
    "experiment_ids": "Experiment",
    "metric_ids": "Metric",
    "result_ids": "Result",
    "citation_ids": "Citation",
    "review_ids": "Review",
    "issue_ids": "Issue",
    "decision_ids": "Decision",
    "venue_ids": "Venue",
    "search_run_ids": "SearchRun",
    "external_work_ids": "ExternalWork",
    "search_result_ids": "SearchResult",
    "source_span_ids": "SourceSpan",
    "extraction_ids": "Extraction",
    "artifact_ids": "Artifact",
}


def state_has_object(state: dict[str, Any], object_type: str, object_id: Any) -> bool:
    return str(object_id) in state.get("objects", {}).get(object_type, {})


def validate_references_exist(
    references: Any,
    state: dict[str, Any],
    existing_event_ids: set[str],
) -> list[str]:
    if references is None:
        return []
    if not isinstance(references, dict):
        return ["references must be a mapping"]

    errors: list[str] = []
    for key, object_type in REFERENCE_OBJECT_TYPES.items():
        if key not in references:
            continue
        for object_id in as_list(references.get(key)):
            if not state_has_object(state, object_type, object_id):
                errors.append(f"references.{key}: unknown {object_type} id {object_id}")
    if "event_ids" in references:
        for event_id in as_list(references.get("event_ids")):
            if str(event_id) not in existing_event_ids:
                errors.append(f"references.event_ids: unknown event id {event_id}")
    return errors


def validate_proposal_policy(
    registry: dict[str, Any],
    action_policy: dict[str, Any],
    proposal: dict[str, Any],
    state: dict[str, Any],
    existing_event_ids: set[str],
) -> list[str]:
    if not isinstance(proposal, dict):
        return ["proposal must be a mapping"]
    action_type = proposal.get("action_type")
    if not action_type:
        return ["proposal missing action_type"]
    if action_type not in registry["actions"]["action_types"]:
        return [f"unknown action_type: {action_type}"]
    spec = action_spec(registry, action_type)
    policy = action_policy_for(action_policy, action_type)
    references = proposal.get("references")
    rationale = proposal.get("rationale")
    errors = validate_references_exist(references, state, existing_event_ids)

    if policy.get("requires_human_gate") and not spec.get("approval_required"):
        errors.append(f"{action_type}: action policy requires a human gate but action approval_required is false")

    if policy.get("requires_anchor_or_unanchored_reason"):
        anchor_keys = policy.get("anchor_reference_keys") or ["source_span_ids"]
        has_anchor = isinstance(references, dict) and any(is_non_empty(references.get(key)) for key in anchor_keys)
        has_unanchored_reason = isinstance(rationale, dict) and is_non_empty(rationale.get("unanchored_reason"))
        if not has_anchor and not has_unanchored_reason:
            errors.append(
                f"{action_type}: references.source_span_ids or rationale.unanchored_reason is required"
            )

    if policy.get("requires_rationale"):
        if not isinstance(rationale, dict):
            errors.append(f"{action_type}: rationale mapping is required by action policy")
        else:
            for field_name in policy.get("required_rationale", []):
                if not is_non_empty(rationale.get(field_name)):
                    errors.append(f"{action_type}: rationale.{field_name} is required by action policy")

        required_any = policy.get("required_references_any", [])
        if required_any:
            if not isinstance(references, dict):
                errors.append(f"{action_type}: references must include one of {required_any}")
            elif not any(is_non_empty(references.get(key)) for key in required_any):
                errors.append(f"{action_type}: references must include one of {required_any}")

    elif rationale is not None and not isinstance(rationale, dict):
        errors.append(f"{action_type}: rationale must be a mapping when provided")

    payload = proposal.get("payload")
    if action_type == "citation.created" and isinstance(payload, dict):
        verification_status = payload.get("verification_status")
        if verification_status not in {"tentative", "verified"}:
            errors.append(
                "citation.created: payload.verification_status must be tentative or verified"
            )
        if verification_status == "verified" and isinstance(references, dict):
            for external_work_id in as_list(references.get("external_work_ids")):
                external_work = (
                    state.get("objects", {}).get("ExternalWork", {}).get(str(external_work_id), {})
                )
                quality = external_work.get("metadata_quality")
                if quality is None and is_non_empty(external_work.get("abstract")):
                    quality = "abstract"
                if quality not in {"abstract", "full_text"}:
                    errors.append(
                        f"citation.created: verified Citation for ExternalWork {external_work_id} "
                        "requires abstract or full_text metadata"
                    )

    if action_type == "issue.created" and isinstance(payload, dict):
        if payload.get("category") == "citation_gap":
            if not is_non_empty(payload.get("target_object_type")) or not is_non_empty(
                payload.get("target_object_id")
            ):
                errors.append(
                    "issue.created: citation_gap requires target_object_type and target_object_id"
                )
            if not is_non_empty(payload.get("missing_literature_role")):
                errors.append(
                    "issue.created: citation_gap requires missing_literature_role"
                )

    return errors


def validate_proposal_batch_policy(
    registry: dict[str, Any],
    proposals: list[dict[str, Any]],
    state: dict[str, Any],
) -> list[str]:
    citation_statuses = {
        str(citation_id): citation.get("verification_status")
        for citation_id, citation in state.get("objects", {}).get("Citation", {}).items()
    }
    for proposal in proposals:
        if proposal.get("action_type") != "citation.created":
            continue
        payload = proposal.get("payload")
        if isinstance(payload, dict) and is_non_empty(payload.get("citation_id")):
            citation_statuses[str(payload["citation_id"])] = payload.get("verification_status")

    available_object_ids = {
        object_type: {str(object_id) for object_id in objects}
        for object_type, objects in state.get("objects", {}).items()
    }
    errors: list[str] = []
    strong_citation_links = {"claim_uses_citation", "evidence_uses_citation"}
    for index, proposal in enumerate(proposals, start=1):
        action_type = proposal.get("action_type")
        payload = proposal.get("payload")
        if action_type != "link.created":
            spec = registry["actions"]["action_types"].get(action_type, {})
            object_type = proposal.get("object_type") or spec.get("object_type")
            object_schema = registry["objects"]["objects"].get(object_type, {})
            primary_key = object_schema.get("primary_key")
            object_id = proposal.get("object_id")
            if object_id is None and isinstance(payload, dict) and primary_key:
                object_id = payload.get(primary_key)
            if object_type != "Link" and is_non_empty(object_type) and is_non_empty(object_id):
                available_object_ids.setdefault(str(object_type), set()).add(str(object_id))
            continue
        if not isinstance(payload, dict):
            continue

        for endpoint in ("from", "to"):
            object_type = payload.get(f"{endpoint}_object_type")
            object_id = payload.get(f"{endpoint}_object_id")
            if not is_non_empty(object_type) or not is_non_empty(object_id):
                continue
            if str(object_id) not in available_object_ids.get(str(object_type), set()):
                errors.append(
                    f"proposal {index}: link.created {endpoint} endpoint references "
                    f"unknown {object_type} id {object_id}"
                )

        if payload.get("link_type") not in strong_citation_links:
            continue
        citation_id = payload.get("to_object_id")
        if payload.get("to_object_type") != "Citation" or not is_non_empty(citation_id):
            continue
        status = citation_statuses.get(str(citation_id))
        if status != "verified":
            label = "tentative" if status == "tentative" else "unverified"
            errors.append(
                f"proposal {index}: {label} Citation {citation_id} cannot be linked "
                f"with {payload.get('link_type')}"
            )
    return errors


def infer_object_id(registry: dict[str, Any], object_type: str, payload: dict[str, Any], offset: int) -> str:
    if object_type == "Link":
        return payload.get("link_id") or f"L-{offset:06d}"
    object_schema = registry["objects"]["objects"][object_type]
    primary_key = object_schema["primary_key"]
    if primary_key not in payload:
        raise ValueError(f"{object_type} proposal is missing primary key payload field: {primary_key}")
    return payload[primary_key]


def build_event_from_proposal(
    registry: dict[str, Any],
    proposal: dict[str, Any],
    *,
    offset: int,
    default_actor: str,
    approved_by: str | None = None,
    approval_summary: str | None = None,
) -> dict[str, Any]:
    if not isinstance(proposal, dict):
        raise ValueError("each proposal must be a mapping")
    action_type = proposal.get("action_type")
    if not action_type:
        raise ValueError("proposal missing action_type")
    spec = action_spec(registry, action_type)
    payload = proposal.get("payload", {})
    if not isinstance(payload, dict):
        raise ValueError(f"{action_type}: payload must be a mapping")
    object_type = proposal.get("object_type") or spec["object_type"]
    function = proposal.get("function") or action_default_function(spec)
    if function is None:
        raise ValueError(f"{action_type}: no default_function configured")
    object_id = proposal.get("object_id") or infer_object_id(registry, object_type, payload, offset)
    approval = proposal.get("approval")
    if spec.get("approval_required") and approved_by:
        approval = dict(approval or {})
        approval["status"] = "approved"
        approval["approved_by"] = approved_by
        if approval_summary:
            approval["summary"] = approval_summary
    return make_event(
        offset=offset,
        actor=proposal.get("actor") or default_actor,
        function=function,
        action_type=action_type,
        object_type=object_type,
        object_id=object_id,
        payload=payload,
        references=proposal.get("references"),
        rationale=proposal.get("rationale"),
        approval=approval,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and append manual/LLM action proposals to a project event log.")
    parser.add_argument("project_dir")
    parser.add_argument("proposal_file")
    parser.add_argument("--actor", default="writing_expert")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--approved-by",
        help="Mark approval-required proposals as human-approved by this user for this apply.",
    )
    parser.add_argument(
        "--approval-summary",
        help="Optional summary recorded with --approved-by approvals.",
    )
    parser.add_argument(
        "--use-project-paper-id",
        action="store_true",
        help="Rewrite payload.paper_id fields to the Paper id found in project_dir/state/paper.yml.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    proposal_file = Path(args.proposal_file).resolve()
    log_path = project_dir / "events" / "event_log.yml"
    state_path = project_dir / "state" / "paper.yml"
    registry = load_registry()
    action_policy = load_action_policy()
    proposals = proposal_items(load_yaml(proposal_file))
    if args.use_project_paper_id:
        rewrite_project_paper_id(proposals, paper_id_from_state(state_path))
    existing_events = read_events(log_path)
    current_state = project_state(existing_events, log_path.parent)
    existing_event_ids = {str(event.get("event_id")) for event in existing_events}

    proposal_policy_errors: list[str] = []
    for index, proposal in enumerate(proposals, start=1):
        for error in validate_proposal_policy(registry, action_policy, proposal, current_state, existing_event_ids):
            proposal_policy_errors.append(f"proposal {index}: {error}")
    proposal_policy_errors.extend(validate_proposal_batch_policy(registry, proposals, current_state))
    if proposal_policy_errors:
        print("Proposal policy validation failed:")
        for error in proposal_policy_errors:
            print(f"- {error}")
        return 1

    offset = next_offset(log_path)
    events = [
        build_event_from_proposal(
            registry,
            proposal,
            offset=offset + index,
            default_actor=args.actor,
            approved_by=args.approved_by,
            approval_summary=args.approval_summary,
        )
        for index, proposal in enumerate(proposals)
    ]

    validation_errors: list[str] = []
    for event in events:
        validation_errors.extend(f"{event['event_id']}: {error}" for error in validate_event(event, registry))
    if validation_errors:
        print("Proposal validation failed:")
        for error in validation_errors:
            print(f"- {error}")
        return 1

    if args.dry_run:
        print(f"dry_run: {len(events)} events validated")
        for event in events:
            approval_note = " approval_required" if validate_required_approval(event, registry) else ""
            print(f"{event['offset']} {event['action_type']} {event['object_type']} {event['object_id']}{approval_note}")
        return 0

    approval_errors: list[str] = []
    for event in events:
        approval_errors.extend(f"{event['event_id']}: {error}" for error in validate_required_approval(event, registry))
    if approval_errors:
        print("Human approval required; no events were appended:")
        for error in approval_errors:
            print(f"- {error}")
        print("To apply after explicit human approval, rerun with --approved-by <name>.")
        return 2

    for event in events:
        append_event(log_path, event, registry)
    all_events = read_events(log_path)
    log_errors = validate_event_log(all_events, registry)
    if log_errors:
        print("Event log validation failed:")
        for error in log_errors:
            print(f"- {error}")
        return 1
    write_yaml(state_path, project_state(all_events, log_path.parent))
    print(f"proposal file: {proposal_file}")
    print(f"events appended: {len(events)}")
    print(f"event log: {log_path}")
    print(f"state: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
