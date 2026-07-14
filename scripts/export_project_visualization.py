from __future__ import annotations

import argparse
import ast
import copy
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal runtimes.
    yaml = None

from path_utils import portable_path


ROOT = Path(__file__).resolve().parents[1]


REF_TARGETS = {
    "paper_id": "Paper",
    "section_id": "Section",
    "claim_id": "Claim",
    "reasoning_step_id": "ReasoningStep",
    "evidence_id": "Evidence",
    "citation_id": "Citation",
    "method_id": "Method",
    "dataset_id": "Dataset",
    "experiment_id": "Experiment",
    "metric_id": "Metric",
    "result_id": "Result",
    "review_id": "Review",
    "issue_id": "Issue",
    "decision_id": "Decision",
    "venue_id": "Venue",
    "target_venue_id": "Venue",
    "artifact_id": "Artifact",
    "source_artifact_id": "Artifact",
    "output_artifact_ids": "Artifact",
}

WORKFLOW_RULES = [
    (
        "intake",
        "Create or ingest the project state",
        {"paper.created", "section.upserted", "citation.created"},
        {"user", "writing_expert"},
    ),
    (
        "positioning",
        "Clarify claims, evidence, contribution, and venue fit",
        {"claim.created", "claim.updated", "evidence.created", "reasoning_step.created", "venue.created", "paper.target_venue_set"},
        {"positioning_expert", "venue_expert"},
    ),
    (
        "writing",
        "Draft or revise paper objects and manuscript artifacts",
        {"section.upserted", "reasoning_step.created", "method.created", "dataset.created", "experiment.created", "metric.created", "result.created"},
        {"writing_expert"},
    ),
    (
        "style_check",
        "Run style and structure diagnostics",
        {"review.created", "issue.created", "artifact.created"},
        {"style_expert"},
    ),
    (
        "mock_review",
        "Aggregate independent review signals into actionable issues",
        {"review.created", "issue.created", "decision.proposed"},
        {"review_expert", "domain_expert", "general_reviewer", "methodologist"},
    ),
    (
        "assembly",
        "Export, assemble, checkpoint, or finalize artifacts",
        {"artifact.created", "checkpoint.created", "submission.finalized"},
        {"assembly_expert"},
    ),
]

HISTORY_ISSUE_STATUSES = {"resolved", "wont_fix", "rejected"}
HANDOFF_MANIFEST_NAMES = ("handoff_manifest.yml", "accepted_manifest.yml")
ACCEPTED_HANDOFF_STATUSES = {"accepted", "accepted_with_warnings"}
REQUIRED_LITERATURE_ROLES = ("predecessor", "direct_competitor", "later_extension", "limitation")
ACTIVE_GAP_STATUSES = {"open", "proposed", "accepted"}
METADATA_QUALITY_RANK = {"title_only": 0, "bibliographic": 1, "abstract": 2, "full_text": 3}


def load_yaml(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text) if yaml is not None else parse_simple_yaml(text)
    return default if data is None else data


def read_events(log_path: Path) -> list[dict[str, Any]]:
    data = load_yaml(log_path, {"events": []})
    if not isinstance(data, dict) or not isinstance(data.get("events"), list):
        raise ValueError(f"{log_path} must contain an 'events' list")
    return data["events"]


def parse_simple_yaml(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))
    if not lines:
        return None
    data, index = parse_yaml_block(lines, 0, lines[0][0])
    if index != len(lines):
        raise ValueError("YAML fallback parser stopped before EOF")
    return data


def parse_yaml_block(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent, content = lines[index]
    if current_indent < indent:
        return {}, index
    if content.startswith("- "):
        return parse_yaml_list(lines, index, current_indent)
    return parse_yaml_mapping(lines, index, current_indent)


def parse_yaml_mapping(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[dict[str, Any], int]:
    mapping: dict[str, Any] = {}
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent < indent or content.startswith("- "):
            break
        if current_indent > indent:
            break
        key, value_text = split_yaml_key_value(content)
        index += 1
        if value_text == "":
            if index < len(lines) and lines[index][1].startswith("- ") and lines[index][0] == current_indent:
                value, index = parse_yaml_block(lines, index, lines[index][0])
            elif index < len(lines) and lines[index][0] > current_indent:
                value, index = parse_yaml_block(lines, index, lines[index][0])
            else:
                value = {}
        else:
            value_lines = [value_text]
            while index < len(lines) and lines[index][0] > current_indent:
                continuation_indent, continuation = lines[index]
                if looks_like_structural_yaml(continuation):
                    break
                value_lines.append(continuation)
                index += 1
            value = parse_yaml_scalar(" ".join(value_lines))
        mapping[key] = value
    return mapping, index


def parse_yaml_list(lines: list[tuple[int, str]], index: int, indent: int) -> tuple[list[Any], int]:
    items: list[Any] = []
    while index < len(lines):
        current_indent, content = lines[index]
        if current_indent != indent or not content.startswith("- "):
            break
        rest = content[2:].strip()
        index += 1
        if rest == "":
            if index < len(lines) and lines[index][0] > current_indent:
                value, index = parse_yaml_block(lines, index, lines[index][0])
            else:
                value = None
            items.append(value)
            continue
        if looks_like_key_value(rest):
            key, value_text = split_yaml_key_value(rest)
            item: dict[str, Any] = {key: parse_yaml_scalar(value_text) if value_text else {}}
            if index < len(lines) and lines[index][0] > current_indent:
                child, index = parse_yaml_mapping(lines, index, lines[index][0])
                item.update(child)
            items.append(item)
        else:
            items.append(parse_yaml_scalar(rest))
    return items, index


def looks_like_structural_yaml(content: str) -> bool:
    return content.startswith("- ") or looks_like_key_value(content)


def looks_like_key_value(content: str) -> bool:
    if ":" not in content:
        return False
    key, _sep, _value = content.partition(":")
    return bool(key) and all(ch.isalnum() or ch in "_-" for ch in key)


def split_yaml_key_value(content: str) -> tuple[str, str]:
    if not looks_like_key_value(content):
        raise ValueError(f"Expected YAML key/value line, got: {content}")
    key, _sep, value = content.partition(":")
    return key.strip(), value.strip()


def parse_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if value == "":
        return ""
    lowered = value.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value[0:1] in {"'", '"'} and value[-1:] == value[0]:
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value[1:-1]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_project_dir(project_dir: str) -> Path:
    path = Path(project_dir)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def project_rel(project_dir: Path, path: Path) -> str:
    return portable_path(path, project_dir, ROOT)


def load_state(project_dir: Path, events: list[dict[str, Any]]) -> dict[str, Any]:
    state_path = project_dir / "state" / "paper.yml"
    state = load_yaml(state_path)
    if isinstance(state, dict):
        state.setdefault("objects", {})
        state.setdefault("links", [])
        return state
    return project_state(events)


def project_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    state: dict[str, Any] = {"objects": {}, "links": []}
    for event in events:
        state = apply_event(state, event)
    return state


def apply_event(state: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
    state.setdefault("objects", {})
    state.setdefault("links", [])
    action_type = event.get("action_type")
    object_type = event.get("object_type")
    object_id = event.get("object_id")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    actor = event.get("actor")
    timestamp = event.get("timestamp")

    if object_type == "Link":
        link_record = {
            "link_type": payload.get("link_type"),
            "from_object_type": payload.get("from_object_type"),
            "from_object_id": payload.get("from_object_id"),
            "to_object_type": payload.get("to_object_type"),
            "to_object_id": payload.get("to_object_id"),
            "status": "active",
            "created_at": timestamp,
            "created_by": actor,
        }
        if action_type == "link.created":
            state["links"].append(link_record)
        elif action_type == "link.removed":
            for existing in state["links"]:
                if all(
                    existing.get(key) == link_record[key]
                    for key in ("link_type", "from_object_type", "from_object_id", "to_object_type", "to_object_id")
                ):
                    existing["status"] = "removed"
                    existing["updated_at"] = timestamp
        return state

    if not object_type or not object_id:
        return state

    bucket = state["objects"].setdefault(object_type, {})
    record = copy.deepcopy(bucket.get(object_id)) if isinstance(bucket.get(object_id), dict) else None
    if record is None:
        record = {
            "id": object_id,
            "created_at": timestamp,
            "created_by": actor,
            "status": "active",
        }
    else:
        record["updated_at"] = timestamp
    record.update(payload)
    bucket[object_id] = record
    return state


def first_object(state: dict[str, Any], object_type: str) -> dict[str, Any] | None:
    bucket = state.get("objects", {}).get(object_type, {})
    if not isinstance(bucket, dict) or not bucket:
        return None
    first_key = next(iter(bucket))
    value = bucket[first_key]
    return value if isinstance(value, dict) else None


def object_label(object_type: str, object_id: str, record: dict[str, Any]) -> str:
    if object_type == "Extraction":
        method = record.get("method") or "document"
        status = record.get("extraction_status")
        return f"{method} extraction" + (f" ({status})" if status else "")
    for key in ("title", "name", "citation_key", "review_type", "category", "artifact_type", "section_type"):
        value = record.get(key)
        if value:
            return str(value)
    text = record.get("text") or record.get("summary") or record.get("evidence")
    if text:
        value = " ".join(str(text).split())
        return value[:72] + ("..." if len(value) > 72 else "")
    return object_id


def object_summary(record: dict[str, Any]) -> str:
    for key in ("summary", "description", "evidence", "suggested_action", "text", "path"):
        value = record.get(key)
        if value:
            compact = " ".join(str(value).split())
            return compact[:180] + ("..." if len(compact) > 180 else "")
    if record.get("page_count") or record.get("character_count"):
        parts = []
        if record.get("page_count"):
            parts.append(f"{record.get('page_count')} pages")
        if record.get("character_count"):
            parts.append(f"{record.get('character_count')} characters")
        return ", ".join(parts)
    return ""


def build_events_data(events: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts = Counter(event.get("action_type", "unknown") for event in events)
    actor_counts = Counter(event.get("actor", "unknown") for event in events)
    object_counts = Counter(event.get("object_type", "unknown") for event in events)
    timeline = []
    for event in events:
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        timeline.append(
            {
                "offset": event.get("offset"),
                "event_id": event.get("event_id"),
                "timestamp": event.get("timestamp"),
                "actor": event.get("actor"),
                "function": event.get("function"),
                "action_type": event.get("action_type"),
                "object_type": event.get("object_type"),
                "object_id": event.get("object_id"),
                "headline": f"{event.get('action_type')} -> {event.get('object_id')}",
                "payload_preview": preview_payload(payload),
            }
        )
    return {
        "timeline": timeline,
        "counts": {
            "events": len(events),
            "actions": dict(action_counts),
            "actors": dict(actor_counts),
            "object_types": dict(object_counts),
        },
    }


def build_object_event_history(events: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    history: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        object_type = event.get("object_type")
        object_id = event.get("object_id")
        if not object_type or object_type == "Link" or not object_id:
            continue
        approval = event.get("approval") if isinstance(event.get("approval"), dict) else {}
        history[str(object_id)].append(
            {
                "offset": event.get("offset"),
                "event_id": event.get("event_id"),
                "timestamp": event.get("timestamp"),
                "actor": event.get("actor"),
                "function": event.get("function"),
                "action_type": event.get("action_type"),
                "approval_status": approval.get("status"),
            }
        )
    return {object_id: entries for object_id, entries in history.items()}


def build_action_inventory(events: list[dict[str, Any]]) -> dict[str, Any]:
    actions_doc = load_yaml(ROOT / "kinetic" / "actions.yml", {})
    functions_doc = load_yaml(ROOT / "kinetic" / "functions.yml", {})
    action_specs = actions_doc.get("action_types", {}) if isinstance(actions_doc, dict) else {}
    function_specs = functions_doc.get("functions", {}) if isinstance(functions_doc, dict) else {}
    inventory: dict[str, dict[str, Any]] = {}

    for event in events:
        action_type = str(event.get("action_type") or "unknown")
        spec = action_specs.get(action_type, {}) if isinstance(action_specs, dict) else {}
        default_function = spec.get("default_function") or spec.get("function") or "unknown"
        actual_function = event.get("function") or default_function
        object_type = event.get("object_type") or spec.get("object_type") or action_type.split(".")[0].title()
        entry = inventory.setdefault(
            action_type,
            {
                "action_type": action_type,
                "object_type": object_type,
                "description": spec.get("description", ""),
                "default_function": default_function,
                "allowed_functions": list(spec.get("allowed_functions") or ([default_function] if default_function != "unknown" else [])),
                "approval_required": bool(spec.get("approval_required", False)),
                "event_count": 0,
                "actual_function_counts": Counter(),
                "events": [],
            },
        )
        entry["event_count"] += 1
        entry["actual_function_counts"][actual_function] += 1
        entry["events"].append(
            {
                "offset": event.get("offset"),
                "event_id": event.get("event_id"),
                "object_type": event.get("object_type"),
                "object_id": event.get("object_id"),
                "actor": event.get("actor"),
                "function": actual_function,
            }
        )

    function_counts: Counter[str] = Counter()
    actions = []
    for entry in inventory.values():
        actual_functions = []
        for function, count in sorted(entry["actual_function_counts"].items()):
            function_counts[function] += count
            function_spec = function_specs.get(function, {}) if isinstance(function_specs, dict) else {}
            actual_functions.append(
                {
                    "function": function,
                    "count": count,
                    "description": function_spec.get("description", ""),
                }
            )
        default_function_spec = function_specs.get(entry["default_function"], {}) if isinstance(function_specs, dict) else {}
        actions.append(
            {
                "action_type": entry["action_type"],
                "object_type": entry["object_type"],
                "description": entry["description"],
                "default_function": entry["default_function"],
                "default_function_description": default_function_spec.get("description", ""),
                "allowed_functions": entry["allowed_functions"],
                "actual_functions": actual_functions,
                "approval_required": entry["approval_required"],
                "event_count": entry["event_count"],
                "events": sorted(entry["events"], key=lambda item: item.get("offset") or 0),
            }
        )

    object_order = [
        "Paper",
        "Section",
        "Claim",
        "Evidence",
        "ReasoningStep",
        "Method",
        "Dataset",
        "Experiment",
        "Metric",
        "Result",
        "Citation",
        "Review",
        "Issue",
        "Decision",
        "Venue",
        "Artifact",
        "Extraction",
        "Link",
    ]
    object_rank = {name: index for index, name in enumerate(object_order)}
    groups = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for action in actions:
        grouped[str(action.get("object_type") or "Unknown")].append(action)
    for object_type, group_actions in sorted(grouped.items(), key=lambda item: (object_rank.get(item[0], 999), item[0])):
        sorted_actions = sorted(group_actions, key=lambda action: (action["action_type"], action["default_function"]))
        groups.append(
            {
                "object_type": object_type,
                "event_count": sum(action["event_count"] for action in sorted_actions),
                "action_type_count": len(sorted_actions),
                "actions": sorted_actions,
            }
        )

    return {
        "groups": groups,
        "counts": {
            "events": len(events),
            "action_types": len(actions),
            "functions": len(function_counts),
            "by_function": dict(sorted(function_counts.items())),
        },
    }


def preview_payload(payload: dict[str, Any]) -> dict[str, Any]:
    preferred = [
        "title",
        "stage",
        "section_type",
        "artifact_type",
        "path",
        "review_type",
        "severity",
        "issue_status",
        "category",
        "decision_type",
        "decision_status",
        "link_type",
    ]
    preview: dict[str, Any] = {}
    for key in preferred:
        if key in payload:
            preview[key] = payload[key]
    if "text" in payload:
        preview["text"] = truncate(payload["text"])
    if "summary" in payload:
        preview["summary"] = truncate(payload["summary"])
    if "evidence" in payload:
        preview["evidence"] = truncate(payload["evidence"])
    return preview


def truncate(value: Any, limit: int = 120) -> str:
    compact = " ".join(str(value).split())
    return compact[:limit] + ("..." if len(compact) > limit else "")


def build_objects_data(state: dict[str, Any]) -> dict[str, Any]:
    objects: dict[str, dict[str, Any]] = {}
    object_counts: dict[str, int] = {}
    for object_type, bucket in state.get("objects", {}).items():
        if not isinstance(bucket, dict):
            continue
        object_counts[object_type] = len(bucket)
        for object_id, record in bucket.items():
            if not isinstance(record, dict):
                continue
            objects[object_id] = {
                "id": object_id,
                "type": object_type,
                "label": object_label(object_type, object_id, record),
                "summary": object_summary(record),
                "status": record.get("status"),
                "created_by": record.get("created_by"),
                "created_at": record.get("created_at"),
                "record": record,
            }
    return {"objects": objects, "counts": object_counts, "links": state.get("links", [])}


def build_graph_data(state: dict[str, Any], events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    objects_data = build_objects_data(state)["objects"]
    event_history = build_object_event_history(events or [])
    nodes = []
    for object_id, node in objects_data.items():
        node_with_history = dict(node)
        node_with_history["event_history"] = event_history.get(str(object_id), [])
        nodes.append(node_with_history)
    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for link in state.get("links", []):
        if not isinstance(link, dict) or link.get("status") == "removed":
            continue
        source = link.get("from_object_id")
        target = link.get("to_object_id")
        label = link.get("link_type", "link")
        add_edge(edges, seen, source, target, label, "explicit")

    for object_type, bucket in state.get("objects", {}).items():
        if not isinstance(bucket, dict):
            continue
        for object_id, record in bucket.items():
            if not isinstance(record, dict):
                continue
            for field, target_type in REF_TARGETS.items():
                raw_target_ids = record.get(field)
                if raw_target_ids is None:
                    continue
                target_ids = raw_target_ids if isinstance(raw_target_ids, list) else [raw_target_ids]
                for target_id in target_ids:
                    if not target_id or target_id == object_id:
                        continue
                    if target_id not in objects_data:
                        continue
                    label = inferred_link_label(object_type, field, target_type)
                    if field == "paper_id":
                        add_edge(edges, seen, target_id, object_id, label, "inferred")
                    else:
                        add_edge(edges, seen, object_id, target_id, label, "inferred")

            if object_type == "Issue":
                target_type = record.get("target_object_type")
                target_id = record.get("target_object_id")
                target_id_str = str(target_id) if target_id is not None else ""
                if target_type and target_id_str and target_id_str in objects_data:
                    add_edge(edges, seen, object_id, target_id_str, "issue_targets_object", "inferred")

    return {"nodes": nodes, "edges": edges}


def add_edge(
    edges: list[dict[str, Any]],
    seen: set[tuple[str, str, str]],
    source: Any,
    target: Any,
    label: Any,
    source_kind: str,
) -> None:
    if not source or not target:
        return
    key = (str(source), str(target), str(label))
    if key in seen:
        return
    seen.add(key)
    edges.append({"source": str(source), "target": str(target), "label": str(label), "source_kind": source_kind})


def inferred_link_label(object_type: str, field: str, target_type: str) -> str:
    if field == "paper_id":
        return f"paper_has_{object_type.lower()}"
    if field == "target_venue_id":
        return "paper_targets_venue"
    return f"{object_type.lower()}_refs_{target_type.lower()}"


def build_issue_data(state: dict[str, Any]) -> dict[str, Any]:
    issues = []
    for issue_id, record in state.get("objects", {}).get("Issue", {}).items():
        if not isinstance(record, dict):
            continue
        issues.append(
            {
                "id": issue_id,
                "severity": record.get("severity", "unknown"),
                "previous_severity": record.get("previous_severity"),
                "reclassification_reason": truncate(record.get("reclassification_reason", ""), 220),
                "status": record.get("issue_status", "unknown"),
                "category": record.get("category", "unknown"),
                "created_by": record.get("created_by", "unknown"),
                "target_object_type": record.get("target_object_type"),
                "target_object_id": record.get("target_object_id"),
                "section_id": record.get("section_id"),
                "claim_id": record.get("claim_id"),
                "review_id": record.get("review_id"),
                "evidence": truncate(record.get("evidence", ""), 260),
                "suggested_action": truncate(record.get("suggested_action", ""), 220),
            }
        )
    severity_order = {"P0": 0, "P1": 1, "P2": 2}
    issues.sort(key=lambda item: (severity_order.get(item["severity"], 9), item["status"], item["id"]))
    active_issues = [issue for issue in issues if issue["status"] not in HISTORY_ISSUE_STATUSES]
    history_issues = [issue for issue in issues if issue["status"] in HISTORY_ISSUE_STATUSES]
    return {
        "issues": issues,
        "active_issues": active_issues,
        "history_issues": history_issues,
        "counts": {
            "active": len(active_issues),
            "history": len(history_issues),
            "total": len(issues),
            "by_severity": dict(Counter(item["severity"] for item in active_issues)),
            "by_all_severity": dict(Counter(item["severity"] for item in issues)),
            "by_status": dict(Counter(item["status"] for item in issues)),
            "by_source": dict(Counter(item["created_by"] for item in issues)),
        },
    }


def build_artifact_data(state: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    producer_by_artifact = {}
    for event in events:
        if event.get("action_type") != "artifact.created" and event.get("action_type") != "checkpoint.created":
            continue
        producer_by_artifact[event.get("object_id")] = {
            "offset": event.get("offset"),
            "actor": event.get("actor"),
            "function": event.get("function"),
            "action_type": event.get("action_type"),
        }

    artifacts = []
    for artifact_id, record in state.get("objects", {}).get("Artifact", {}).items():
        if not isinstance(record, dict):
            continue
        artifacts.append(
            {
                "id": artifact_id,
                "type": record.get("artifact_type", "unknown"),
                "path": record.get("path"),
                "description": record.get("description", ""),
                "produced_by": record.get("produced_by") or record.get("created_by"),
                "event": producer_by_artifact.get(artifact_id, {}),
            }
        )
    artifacts.sort(key=lambda item: (item["event"].get("offset", 999999), item["id"]))
    return {
        "artifacts": artifacts,
        "counts": dict(Counter(item["type"] for item in artifacts)),
    }


def active_links(state: dict[str, Any], link_type: str | None = None) -> list[dict[str, Any]]:
    return [
        link
        for link in state.get("links", [])
        if isinstance(link, dict)
        and link.get("status") != "removed"
        and (link_type is None or link.get("link_type") == link_type)
    ]


def build_literature_data(state: dict[str, Any]) -> dict[str, Any]:
    objects = state.get("objects", {})
    citations = objects.get("Citation", {}) or {}
    external_works = objects.get("ExternalWork", {}) or {}
    artifacts = objects.get("Artifact", {}) or {}
    issues = objects.get("Issue", {}) or {}

    citation_to_work: dict[str, list[str]] = defaultdict(list)
    work_to_metadata_artifacts: dict[str, list[str]] = defaultdict(list)
    citation_targets: dict[str, list[dict[str, str]]] = defaultdict(list)
    for link in active_links(state):
        link_type = link.get("link_type")
        if link_type == "citation_represents_external_work":
            citation_to_work[str(link.get("from_object_id"))].append(str(link.get("to_object_id")))
        elif link_type == "artifact_documents_external_work":
            work_to_metadata_artifacts[str(link.get("to_object_id"))].append(str(link.get("from_object_id")))
        elif link_type in {"claim_uses_citation", "evidence_uses_citation"}:
            citation_targets[str(link.get("to_object_id"))].append(
                {
                    "object_type": str(link.get("from_object_type")),
                    "object_id": str(link.get("from_object_id")),
                    "link_type": str(link_type),
                }
            )

    rows = []
    for citation_id, citation in citations.items():
        work_ids = sorted(set(citation_to_work.get(str(citation_id), [])))
        works = [external_works[work_id] for work_id in work_ids if work_id in external_works]
        qualities = [str(work.get("metadata_quality") or "unknown") for work in works]
        metadata_quality = max(qualities, key=lambda item: METADATA_QUALITY_RANK.get(item, -1), default="unknown")
        metadata_artifact_ids = sorted(
            {
                artifact_id
                for work_id in work_ids
                for artifact_id in work_to_metadata_artifacts.get(work_id, [])
                if artifact_id in artifacts
            }
        )
        primary_work = works[0] if works else {}
        rows.append(
            {
                "citation_id": str(citation_id),
                "title": citation.get("title") or primary_work.get("title") or str(citation_id),
                "year": citation.get("year") or primary_work.get("year"),
                "verification_status": citation.get("verification_status") or "unverified",
                "positioning_role": citation.get("positioning_role") or "unknown",
                "citation_role": citation.get("role") or "unknown",
                "metadata_quality": metadata_quality,
                "source_provider": primary_work.get("source_provider") or "unknown",
                "external_work_ids": work_ids,
                "metadata_artifact_ids": metadata_artifact_ids,
                "targets": sorted(citation_targets.get(str(citation_id), []), key=lambda item: (item["object_type"], item["object_id"])),
            }
        )
    role_order = {role: index for index, role in enumerate(REQUIRED_LITERATURE_ROLES)}
    rows.sort(
        key=lambda item: (
            role_order.get(str(item["positioning_role"]), len(role_order)),
            str(item["verification_status"]),
            str(item["title"]),
        )
    )

    covered_roles = {
        str(item["positioning_role"])
        for item in rows
        if item["verification_status"] == "verified" and item["positioning_role"] in REQUIRED_LITERATURE_ROLES
    }
    missing_roles = set(REQUIRED_LITERATURE_ROLES) - covered_roles
    documented_gap_roles = {
        str(issue.get("missing_literature_role"))
        for issue in issues.values()
        if isinstance(issue, dict)
        and issue.get("category") == "citation_gap"
        and issue.get("issue_status") in ACTIVE_GAP_STATUSES
        and issue.get("missing_literature_role") in missing_roles
        and issue.get("target_object_type")
        and issue.get("target_object_id")
    }
    unaccounted_roles = missing_roles - documented_gap_roles
    coverage = {
        "coverage_status": "complete_or_accounted_for" if not unaccounted_roles else "incomplete",
        "required_roles": list(REQUIRED_LITERATURE_ROLES),
        "covered_roles": sorted(covered_roles),
        "documented_gap_roles": sorted(documented_gap_roles),
        "missing_roles": sorted(missing_roles),
        "unaccounted_roles": sorted(unaccounted_roles),
    }
    verification_counts = Counter(str(item["verification_status"]) for item in rows)
    metadata_quality_counts = Counter(
        str(work.get("metadata_quality") or "unknown")
        for work in external_works.values()
        if isinstance(work, dict)
    )
    return {
        "citations": rows,
        "coverage": coverage,
        "counts": {
            "citations": len(rows),
            "verified": verification_counts.get("verified", 0),
            "tentative": verification_counts.get("tentative", 0),
            "unverified": verification_counts.get("unverified", 0),
            "external_works": len(external_works),
            "metadata_artifacts": len({artifact_id for ids in work_to_metadata_artifacts.values() for artifact_id in ids}),
        },
        "metadata_quality_counts": dict(sorted(metadata_quality_counts.items())),
    }


def build_provenance_data(state: dict[str, Any]) -> dict[str, Any]:
    objects = state.get("objects", {})
    evidence = objects.get("Evidence", {}) or {}
    source_spans = objects.get("SourceSpan", {}) or {}
    artifacts = objects.get("Artifact", {}) or {}
    evidence_to_spans: dict[str, list[str]] = defaultdict(list)
    for link in active_links(state, "evidence_anchored_to_source_span"):
        evidence_to_spans[str(link.get("from_object_id"))].append(str(link.get("to_object_id")))

    chains = []
    broken_links = []
    for evidence_id, evidence_record in sorted(evidence.items()):
        if not isinstance(evidence_record, dict):
            continue
        span_ids = evidence_to_spans.get(str(evidence_id), [])
        if not span_ids:
            broken_links.append(
                {"evidence_id": str(evidence_id), "source_span_id": None, "problem": "no SourceSpan anchor"}
            )
        span_rows = []
        for span_id in sorted(set(span_ids)):
            span = source_spans.get(span_id)
            if not isinstance(span, dict):
                broken_links.append({"evidence_id": evidence_id, "source_span_id": span_id, "problem": "missing SourceSpan"})
                continue
            artifact_id = span.get("artifact_id")
            artifact = artifacts.get(artifact_id, {}) if artifact_id else {}
            if not isinstance(artifact, dict):
                artifact = {}
            if not artifact:
                broken_links.append(
                    {"evidence_id": str(evidence_id), "source_span_id": span_id, "problem": "missing Artifact"}
                )
            span_rows.append(
                {
                    "source_span_id": span_id,
                    "text_excerpt": truncate(span.get("text_excerpt") or "No excerpt recorded.", 220),
                    "locator_type": span.get("locator_type") or "unknown",
                    "locator": span.get("locator") if isinstance(span.get("locator"), dict) else {},
                    "text_hash": span.get("text_hash"),
                    "artifact_id": artifact_id,
                    "artifact_type": artifact.get("artifact_type") or "unknown",
                    "artifact_path": artifact.get("path"),
                    "complete": bool(artifact),
                }
            )
        chains.append(
            {
                "evidence_id": str(evidence_id),
                "summary": truncate(evidence_record.get("summary") or str(evidence_id), 220),
                "spans": span_rows,
                "complete": bool(span_rows) and all(span["complete"] for span in span_rows),
            }
        )
    for evidence_id in sorted(set(evidence_to_spans) - {str(item) for item in evidence}):
        broken_links.append({"evidence_id": evidence_id, "source_span_id": None, "problem": "missing Evidence"})
    return {
        "evidence_source_chains": chains,
        "broken_links": broken_links,
        "counts": {
            "evidence_with_source_spans": sum(1 for chain in chains if chain["spans"]),
            "evidence_without_source_spans": sum(1 for chain in chains if not chain["spans"]),
            "source_span_links": sum(len(span_ids) for span_ids in evidence_to_spans.values()),
            "source_spans": len(source_spans),
            "artifacts": len(artifacts),
            "complete_chains": sum(1 for chain in chains if chain["complete"]),
            "broken_links": len(broken_links),
        },
    }


def build_expert_execution_data(project_dir: Path) -> dict[str, Any]:
    executions = []
    invocation_root = project_dir / "expert_invocations"
    if invocation_root.exists():
        for manifest_path in sorted(invocation_root.glob("*/runner_manifest.yml")):
            manifest = load_yaml(manifest_path, {})
            if not isinstance(manifest, dict):
                continue
            execution = manifest.get("execution") if isinstance(manifest.get("execution"), dict) else {}
            output_dir = manifest_path.parent / "outputs"
            executions.append(
                {
                    "invocation_id": manifest.get("invocation_id") or manifest_path.parent.name,
                    "expert_name": manifest.get("expert_name") or "unknown",
                    "requested_mode": manifest.get("requested_mode") or manifest.get("mode") or "unknown",
                    "backend": execution.get("backend") or "legacy_unrecorded",
                    "isolation_verified": bool(execution.get("isolation_verified")),
                    "recorded_at": execution.get("recorded_at"),
                    "recorded_by": execution.get("recorded_by"),
                    "reason": execution.get("reason"),
                    "report_exists": (output_dir / "report.md").exists(),
                    "proposals_exist": (output_dir / "proposals.yml").exists(),
                }
            )
    backend_counts = Counter(str(item["backend"]) for item in executions)
    return {
        "executions": executions,
        "counts": {
            "total": len(executions),
            "isolation_verified": sum(1 for item in executions if item["isolation_verified"]),
            "isolation_unverified": sum(1 for item in executions if not item["isolation_verified"]),
            **dict(sorted(backend_counts.items())),
        },
    }


def classify_workflow_event(event: dict[str, Any]) -> str:
    action_type = event.get("action_type")
    actor = event.get("actor")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    if action_type == "review.created" and payload.get("review_type") == "style_check":
        return "style_check"
    if action_type == "review.created":
        return "mock_review"
    if action_type == "checkpoint.created":
        return "assembly"
    for name, _description, actions, actors in WORKFLOW_RULES:
        if actor in actors and action_type in actions:
            return name
    for name, _description, actions, _actors in WORKFLOW_RULES:
        if action_type in actions:
            return name
    return "other"


def build_workflow_data(events: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[classify_workflow_event(event)].append(
            {
                "offset": event.get("offset"),
                "action_type": event.get("action_type"),
                "actor": event.get("actor"),
                "object_id": event.get("object_id"),
            }
        )
    catalog = {name: description for name, description, _actions, _actors in WORKFLOW_RULES}
    catalog["other"] = "Events that do not match the coarse v0.1 workflow heuristics"
    return {
        "stages": [
            {"name": name, "description": catalog.get(name, ""), "events": grouped.get(name, [])}
            for name in [rule[0] for rule in WORKFLOW_RULES] + ["other"]
            if grouped.get(name)
        ]
    }


def build_story_data(state: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    paper = first_object(state, "Paper") or {}
    objects = build_objects_data(state)["objects"]
    issue_data = build_issue_data(state)
    issues = issue_data["active_issues"]
    artifacts = build_artifact_data(state, events)["artifacts"]
    graph = build_graph_data(state)
    return {
        "headline": story_headline(paper, events, issues, artifacts),
        "thesis": (
            "This page shows the current paper state, the accepted events that created it, "
            "the review issues still open, and the files attached to the project."
        ),
        "mechanism": [
            {
                "title": "Experts propose changes",
                "body": "Writing, review, style, venue, and assembly experts can propose focused changes without directly editing the projected state.",
                "proof": "The event log keeps the actor for each accepted step.",
            },
            {
                "title": "Accepted events are saved",
                "body": "When a proposal is accepted, it becomes a numbered event that can be replayed and inspected later.",
                "proof": f"This project contains {len(events)} recorded steps.",
            },
            {
                "title": "Objects stay separate",
                "body": "Sections, claims, evidence, reviews, issues, decisions, and artifacts remain addressable objects rather than one mutable document blob.",
                "proof": f"The current projection tracks {count_phrase(len(objects), 'object')} and {count_phrase(len(graph['edges']), 'link')}.",
            },
            {
                "title": "Review trails stay visible",
                "body": "Claims, issues, decisions, and artifacts remain connected so a reviewer can see why a concern exists.",
                "proof": f"This view shows {count_phrase(len(issues), 'open issue')} and {count_phrase(issue_data['counts']['history'], 'resolved/history issue')} separately, plus {count_phrase(len(artifacts), 'file artifact')}.",
            },
        ],
        "lifecycle": [humanize_event(event, objects) for event in events],
        "issue_cards": build_story_issue_cards(state),
        "evidence_trails": build_evidence_trails(state),
        "artifact_cards": build_story_artifact_cards(state, events),
        "debug_note": "The exported JSON files remain available for inspecting the raw event timeline, projected objects, graph links, and generated narration.",
        "text_source": {
            "title": "Data provenance",
            "body": (
                "This page is generated by a deterministic script. It does not call an LLM while exporting. "
                "Long paper-specific sentences come from event_log.yml and paper.yml fields such as claim text, "
                "issue evidence, suggested actions, review summaries, artifact descriptions, and file paths. "
                "The short explanatory phrases are fixed templates in the exporter."
            ),
            "future_option": (
                "A later version could add an optional LLM summarizer, but it should write its summaries back as "
                "reviewed artifacts or events so the page remains auditable."
            ),
        },
    }


def story_headline(
    paper: dict[str, Any],
    events: list[dict[str, Any]],
    issues: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> str:
    title = paper.get("title") or "A paper project"
    return (
        f"{title} has {count_phrase(len(events), 'recorded step')}, "
        f"{count_phrase(len(issues), 'open issue')}, and {count_phrase(len(artifacts), 'file artifact')}."
    )


def count_phrase(count: int, singular: str, plural: str | None = None) -> str:
    noun = singular if count == 1 else plural or f"{singular}s"
    return f"{count} {noun}"


def humanize_event(event: dict[str, Any], objects: dict[str, dict[str, Any]]) -> dict[str, Any]:
    action_type = event.get("action_type", "unknown")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    object_id = str(event.get("object_id", ""))
    object_record = objects.get(object_id, {})
    object_name = object_record.get("label") or object_id

    title = readable_action_title(action_type)
    body = f"{actor_phrase(event.get('actor'))} recorded a change to {object_name}."
    why = "The event can be replayed into paper.yml and inspected later."

    if action_type == "paper.created":
        title = "Paper project initialized"
        body = f"The suite started tracking \"{payload.get('title', object_name)}\" as a typed paper project."
        why = "This creates the root object that later sections, claims, reviews, issues, and artifacts attach to."
    elif action_type == "section.upserted":
        title = "Manuscript section recorded"
        body = f"{actor_phrase(event.get('actor'))} added or updated the {payload.get('section_type', 'section')} section."
        why = "Sections stop being loose text only; they become addressable objects that reviewers and claims can point to."
    elif action_type == "claim.created":
        title = "Research claim recorded"
        body = truncate(payload.get("text", object_name), 180)
        why = "Explicit claims can be challenged, supported, revised, and linked to evidence."
    elif action_type == "claim.updated":
        title = "Research claim updated"
        body = truncate(payload.get("text", object_name), 180)
        why = "Claim changes are high-value edits because they alter what the paper is promising."
    elif action_type == "evidence.created":
        title = "Evidence was recorded"
        body = truncate(payload.get("summary", object_name), 180)
        why = "Evidence gives claims a visible support trail instead of relying on chat memory."
    elif action_type == "reasoning_step.created":
        title = "Reasoning step recorded"
        body = truncate(payload.get("summary", object_name), 180)
        why = "Proof steps and argument links become addressable objects that can be supported, challenged, or revised."
    elif action_type in {"method.created", "dataset.created", "experiment.created", "metric.created", "result.created"}:
        noun = action_type.split(".")[0].replace("_", " ")
        title = f"{noun.title()} object recorded"
        body = truncate(payload.get("name") or payload.get("summary") or object_name, 180)
        why = "Evaluation structure becomes queryable and linkable instead of being buried in prose."
    elif action_type == "review.created":
        title = "Review pass recorded"
        body = truncate(payload.get("summary") or f"{payload.get('review_type', 'review')} review completed.", 180)
        why = "Reviews become durable records that can produce issues and artifacts."
    elif action_type == "issue.created":
        title = f"{payload.get('severity', 'Issue')} issue found"
        body = truncate(payload.get("evidence", object_name), 220)
        why = "The system turns critique into a tracked work item with severity, status, evidence, and next action."
    elif action_type == "issue.status_changed":
        title = "Issue status changed"
        body = f"The issue moved to {payload.get('issue_status', 'a new status')}."
        why = "Resolution state is part of the project history, not an informal chat note."
    elif action_type == "issue.severity_changed":
        title = "Issue severity reclassified"
        body = f"The issue moved from {payload.get('previous_severity', 'a prior severity')} to {payload.get('severity', 'a new severity')}."
        why = truncate(payload.get("reclassification_reason") or "The current risk level changed while the old risk remains visible in the event log.", 220)
    elif action_type == "decision.proposed":
        title = "Decision point proposed"
        body = truncate(payload.get("reason_summary", object_name), 200)
        why = "The workflow separates proposed decisions from human-approved decisions."
    elif action_type == "decision.recorded":
        title = "A decision was recorded"
        body = truncate(payload.get("reason_summary", object_name), 200)
        why = "Human judgment becomes a visible project fact."
    elif action_type == "artifact.created":
        title = "File artifact recorded"
        body = f"{artifact_type_label(payload.get('artifact_type'))} at {payload.get('path', object_name)}"
        why = "Reports, drafts, manuscripts, source files, and figures stay connected to the event that recorded them."
    elif action_type == "extraction.created":
        title = "Document extraction recorded"
        status = payload.get("extraction_status", "recorded")
        method = payload.get("method", "the configured extractor")
        page_count = payload.get("page_count")
        body = f"{method} extraction {status}"
        if page_count:
            body += f" across {page_count} pages"
        body += "."
        why = "Extraction metadata keeps source files, extracted text, and reports connected for downstream review."
    elif action_type == "checkpoint.created":
        title = "A human-approved checkpoint was created"
        body = truncate(payload.get("summary") or payload.get("path", object_name), 200)
        why = "Checkpointing keeps long projects recoverable without replaying every old event."
    elif action_type == "link.created":
        title = "Object link recorded"
        body = (
            f"{payload.get('from_object_id')} now points to {payload.get('to_object_id')} "
            f"as {payload.get('link_type', 'a relation')}."
        )
        why = "Links turn isolated records into an evidence and accountability graph."

    return {
        "offset": event.get("offset"),
        "title": title,
        "body": body,
        "why": why,
        "actor": actor_phrase(event.get("actor")),
        "raw": {
            "event_id": event.get("event_id"),
            "action_type": action_type,
            "object_type": event.get("object_type"),
            "object_id": object_id,
            "function": event.get("function"),
            "payload_preview": preview_payload(payload),
        },
    }


def readable_action_title(action_type: Any) -> str:
    words = str(action_type or "event.recorded").replace(".", " ").replace("_", " ")
    return " ".join(word.capitalize() for word in words.split())


def actor_phrase(actor: Any) -> str:
    labels = {
        "user": "The user",
        "router": "The router",
        "writing_expert": "The writing expert",
        "positioning_expert": "The positioning expert",
        "style_expert": "The style expert",
        "review_expert": "The review expert",
        "venue_expert": "The venue expert",
        "assembly_expert": "The assembly expert",
        "domain_expert": "A domain reviewer",
        "general_reviewer": "A general reviewer",
        "methodologist": "A methodologist",
    }
    return labels.get(str(actor), str(actor or "An actor"))


def build_story_issue_cards(state: dict[str, Any]) -> list[dict[str, Any]]:
    cards = []
    sections = state.get("objects", {}).get("Section", {})
    claims = state.get("objects", {}).get("Claim", {})
    reviews = state.get("objects", {}).get("Review", {})
    all_objects = state.get("objects", {})
    for issue in build_issue_data(state)["issues"]:
        claim = claims.get(issue.get("claim_id"), {}) if issue.get("claim_id") else {}
        section = sections.get(issue.get("section_id"), {}) if issue.get("section_id") else {}
        review = reviews.get(issue.get("review_id"), {}) if issue.get("review_id") else {}
        target_type = issue.get("target_object_type")
        target_id = issue.get("target_object_id")
        target = {}
        if target_type and target_id:
            target_bucket = all_objects.get(target_type, {})
            if isinstance(target_bucket, dict):
                target = target_bucket.get(target_id, {}) or {}
        cards.append(
            {
                "id": issue["id"],
                "problem": issue_problem_title(issue),
                "severity": issue["severity"],
                "previous_severity": issue.get("previous_severity"),
                "status": issue["status"],
                "is_history": issue["status"] in HISTORY_ISSUE_STATUSES,
                "history_note": issue_history_note(issue),
                "why_it_matters": issue_why_it_matters(issue),
                "evidence": issue["evidence"],
                "next_step": issue.get("suggested_action") or "Decide whether to revise, gather evidence, or explicitly accept the risk.",
                "affected": affected_phrase(section, claim, review, target_type, target_id, target),
                "debug": {
                    "category": issue["category"],
                    "previous_severity": issue.get("previous_severity"),
                    "reclassification_reason": issue.get("reclassification_reason"),
                    "target_object_type": target_type,
                    "target_object_id": target_id,
                    "section_id": issue.get("section_id"),
                    "claim_id": issue.get("claim_id"),
                    "review_id": issue.get("review_id"),
                    "created_by": issue.get("created_by"),
                },
            }
        )
    return cards


def issue_problem_title(issue: dict[str, Any]) -> str:
    category = str(issue.get("category", "issue")).replace("_", " ")
    if issue.get("status") in HISTORY_ISSUE_STATUSES:
        previous = issue.get("previous_severity")
        if previous and previous != issue.get("severity"):
            return f"Resolved former {previous}: {category}"
        return f"Resolved issue: {category}"
    if issue.get("severity") == "P0":
        return f"Blocking risk: {category}"
    if issue.get("severity") == "P1":
        return f"Major revision risk: {category}"
    if issue.get("severity") == "P2":
        return f"Minor improvement: {category}"
    return category.title()


def issue_history_note(issue: dict[str, Any]) -> str:
    if issue.get("status") not in HISTORY_ISSUE_STATUSES:
        return ""
    previous = issue.get("previous_severity")
    current = issue.get("severity")
    reason = issue.get("reclassification_reason")
    if previous and previous != current:
        return f"Previously {previous}; currently {current}. {reason}".strip()
    return "Resolved or closed issue kept here for audit history."


def issue_why_it_matters(issue: dict[str, Any]) -> str:
    category = issue.get("category")
    if category == "missing_evidence":
        return "The paper is making a claim before the support trail is strong enough."
    if category == "overclaim":
        return "Readers may reject the paper if the stated contribution outruns the evidence."
    if category == "style_violation":
        return "Surface-level writing problems can hide or weaken the scientific argument."
    if category == "missing_evaluation":
        return "Without an evaluation protocol, the project cannot yet prove its central promise."
    return "The issue is tracked because it affects reviewability, credibility, or submission readiness."


def affected_phrase(
    section: dict[str, Any],
    claim: dict[str, Any],
    review: dict[str, Any],
    target_type: str | None = None,
    target_id: str | None = None,
    target: dict[str, Any] | None = None,
) -> str:
    parts = []
    if target_type and target_id:
        if target:
            parts.append(f"{target_type}: {object_label(target_type, target_id, target)}")
        else:
            parts.append(f"{target_type}: {target_id}")
    elif section:
        parts.append(f"section: {section.get('title') or section.get('section_type') or section.get('id')}")
    if not target_type and claim:
        parts.append(f"claim: {truncate(claim.get('text') or claim.get('id'), 96)}")
    if review:
        parts.append(f"source review: {review.get('review_type') or review.get('id')}")
    return " / ".join(parts) if parts else "paper-level issue"


def build_evidence_trails(state: dict[str, Any]) -> list[dict[str, Any]]:
    claims = state.get("objects", {}).get("Claim", {})
    issues = state.get("objects", {}).get("Issue", {})
    decisions = state.get("objects", {}).get("Decision", {})
    artifacts = state.get("objects", {}).get("Artifact", {})
    trails = []

    for claim_id, claim in claims.items():
        related_issues = [
            (issue_id, issue)
            for issue_id, issue in issues.items()
            if isinstance(issue, dict)
            and (
                issue.get("claim_id") == claim_id
                or (issue.get("target_object_type") == "Claim" and issue.get("target_object_id") == claim_id)
            )
        ]
        if not related_issues:
            continue
        for issue_id, issue in related_issues:
            related_decisions = [
                decision
                for decision in decisions.values()
                if isinstance(decision, dict) and decision.get("issue_id") == issue_id
            ]
            trails.append(
                {
                    "title": "Claim under review",
                    "nodes": [
                        {"label": "Claim", "text": truncate(claim.get("text") or claim_id, 180)},
                        {"label": "Issue", "text": truncate(issue.get("evidence") or issue_id, 180)},
                        {
                            "label": "Decision",
                            "text": truncate(related_decisions[0].get("reason_summary"), 180)
                            if related_decisions
                            else "No decision recorded yet.",
                        },
                    ],
                }
            )

    if trails:
        return trails

    if issues:
        for issue_id, issue in list(issues.items())[:3]:
            trails.append(
                {
                    "title": "Review finding needs action",
                    "nodes": [
                        {"label": "Issue", "text": truncate(issue.get("evidence") or issue_id, 180)},
                        {"label": "Next step", "text": truncate(issue.get("suggested_action") or "Decide how to handle the issue.", 180)},
                        {"label": "Artifact", "text": first_artifact_text(artifacts)},
                    ],
                }
            )
    return trails


def first_artifact_text(artifacts: dict[str, Any]) -> str:
    for artifact in artifacts.values():
        if isinstance(artifact, dict):
            return truncate(artifact.get("path") or artifact.get("description") or artifact.get("artifact_id"), 180)
    return "No artifact linked yet."


def build_story_artifact_cards(state: dict[str, Any], events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    event_by_artifact = {
        event.get("object_id"): event
        for event in events
        if event.get("action_type") in {"artifact.created", "checkpoint.created"}
    }
    cards = []
    for artifact in build_artifact_data(state, events)["artifacts"]:
        event = event_by_artifact.get(artifact["id"], {})
        cards.append(
            {
                "title": artifact_title(artifact.get("type")),
                "path": artifact.get("path"),
                "body": artifact.get("description") or "A project file recorded as a first-class artifact.",
                "provenance": artifact_provenance(artifact, event),
                "debug": {"artifact_id": artifact["id"], "artifact_type": artifact.get("type")},
            }
        )
    return cards


def artifact_provenance(artifact: dict[str, Any], event: dict[str, Any]) -> str:
    recorder = artifact.get("produced_by") or event.get("actor", "unknown")
    offset = event.get("offset", artifact.get("event", {}).get("offset", "unknown"))
    return f"Recorded by {recorder} at event {offset}."


def artifact_title(artifact_type: Any) -> str:
    labels = {
        "manuscript_tex": "Editable manuscript export",
        "manuscript_md": "Markdown manuscript source",
        "bibliography_bib": "Bibliography artifact",
        "quick_scan_report": "Mechanical style report",
        "review_report": "Review report",
        "style_report": "Style report",
        "positioning_card": "Positioning card",
        "venue_card": "Venue fit card",
        "state_snapshot": "Recoverable state snapshot",
        "section_tex": "Section source artifact",
        "figure_image": "Figure artifact",
        "table_tex": "Table source artifact",
        "table_md": "Table artifact",
        "source_pdf": "Source PDF",
        "extracted_text_md": "Extracted text",
        "extraction_report": "Extraction report",
    }
    return labels.get(str(artifact_type), artifact_type_label(artifact_type).capitalize())


def artifact_type_label(artifact_type: Any) -> str:
    labels = {
        "manuscript_tex": "LaTeX manuscript",
        "manuscript_md": "Markdown manuscript",
        "bibliography_bib": "BibTeX bibliography",
        "quick_scan_report": "mechanical style report",
        "section_tex": "LaTeX section source",
        "source_pdf": "source PDF",
        "extracted_text_md": "extracted Markdown text",
        "extraction_report": "extraction report",
    }
    return labels.get(str(artifact_type), str(artifact_type or "artifact").replace("_", " "))


def acceptance_label(status: Any) -> str:
    labels = {
        "accepted": "Accepted",
        "accepted_with_warnings": "Accepted with warnings",
        "failed": "Failed",
        "not_checked": "Not checked",
    }
    return labels.get(str(status), "Unknown")


def build_acceptance_data(project_dir: Path) -> dict[str, Any]:
    for manifest_name in HANDOFF_MANIFEST_NAMES:
        manifest_path = project_dir / manifest_name
        manifest = load_yaml(manifest_path, {})
        if isinstance(manifest, dict) and manifest:
            status = manifest.get("acceptance_status", "unknown")
            validation = manifest.get("validation", {}) if isinstance(manifest.get("validation"), dict) else {}
            return {
                "status": status,
                "label": acceptance_label(status),
                "manifest_path": project_rel(project_dir, manifest_path),
                "generated_at": manifest.get("generated_at"),
                "error_count": validation.get("error_count"),
                "warning_count": validation.get("warning_count"),
            }
    return {
        "status": "not_checked",
        "label": acceptance_label("not_checked"),
        "manifest_path": None,
        "generated_at": None,
        "error_count": None,
        "warning_count": None,
    }


def build_project_data(project_dir: Path) -> dict[str, Any]:
    log_path = project_dir / "events" / "event_log.yml"
    if not log_path.exists():
        raise FileNotFoundError(f"Missing event log: {log_path}")
    events = read_events(log_path)
    state = load_state(project_dir, events)
    paper = first_object(state, "Paper") or {}
    return {
        "project": {
            "project_dir": portable_path(project_dir, ROOT),
            "paper_id": paper.get("paper_id") or paper.get("id"),
            "title": paper.get("title", "Untitled paper"),
            "field": paper.get("field", ""),
            "stage": paper.get("stage", ""),
        },
        "events": build_events_data(events),
        "objects": build_objects_data(state),
        "graph": build_graph_data(state, events),
        "issues": build_issue_data(state),
        "artifacts": build_artifact_data(state, events),
        "workflow": build_workflow_data(events),
        "story": build_story_data(state, events),
        "literature": build_literature_data(state),
        "provenance": build_provenance_data(state),
        "expert_executions": build_expert_execution_data(project_dir),
        "action_inventory": build_action_inventory(events),
        "acceptance": build_acceptance_data(project_dir),
    }


def render_html(data: dict[str, Any]) -> str:
    data_json = json.dumps(data, ensure_ascii=False)
    return STORY_HTML_TEMPLATE.replace("__VIS_DATA__", data_json)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Paper Suite Visualization</title>
  <style>
    :root {
      --bg: #f8faf7;
      --ink: #1d2522;
      --muted: #66736d;
      --line: #d8dfd9;
      --paper: #ffffff;
      --green: #25705a;
      --teal: #0f766e;
      --amber: #b7791f;
      --red: #b42318;
      --violet: #6d5bd0;
      --gray: #eef2ee;
      --shadow: 0 10px 24px rgba(29, 37, 34, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    header {
      background: #fbfcfa;
      border-bottom: 1px solid var(--line);
    }
    .wrap {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
    }
    .hero {
      min-height: 76vh;
      display: grid;
      align-content: center;
      gap: 28px;
      padding: 56px 0 40px;
    }
    .eyebrow {
      color: var(--green);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      max-width: 880px;
      font-size: clamp(42px, 7vw, 88px);
      line-height: 0.98;
      letter-spacing: 0;
    }
    .lede {
      max-width: 760px;
      color: #43504a;
      font-size: 19px;
    }
    .intro-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 16px;
    }
    .intro-card, .panel, .metric, .event, .issue, .artifact, .stage {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .intro-card {
      padding: 18px;
      min-height: 190px;
    }
    .intro-card h2, .panel h2 {
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .intro-card p, .panel p {
      margin: 0;
      color: var(--muted);
    }
    main { padding: 20px 0 64px; }
    section.band {
      padding: 32px 0;
      border-bottom: 1px solid var(--line);
    }
    .section-head {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 18px;
      margin-bottom: 18px;
    }
    .section-head h2 {
      margin: 0;
      font-size: 28px;
      letter-spacing: 0;
    }
    .section-head p {
      margin: 6px 0 0;
      max-width: 700px;
      color: var(--muted);
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }
    .metric {
      padding: 16px;
    }
    .metric strong {
      display: block;
      font-size: 28px;
      line-height: 1;
    }
    .metric span {
      display: block;
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .timeline {
      display: grid;
      gap: 10px;
    }
    .event {
      display: grid;
      grid-template-columns: 82px minmax(0, 1fr) 180px;
      gap: 14px;
      padding: 14px;
      align-items: start;
    }
    .offset {
      display: inline-grid;
      place-items: center;
      width: 48px;
      height: 48px;
      border-radius: 8px;
      background: #e8f3ee;
      color: var(--green);
      font-weight: 800;
    }
    .event h3, .issue h3, .artifact h3, .stage h3 {
      margin: 0 0 6px;
      font-size: 16px;
      letter-spacing: 0;
    }
    .event-meta, .tiny {
      color: var(--muted);
      font-size: 12px;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--gray);
      color: #46524c;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }
    .chip.p0 { background: #fee4e2; color: var(--red); }
    .chip.p1 { background: #fef3c7; color: #8a570e; }
    .chip.p2 { background: #e8f3ee; color: var(--green); }
    .chip.open { background: #fff1e6; color: #9a3412; }
    .chip.resolved { background: #dcfce7; color: #166534; }
    .two-col {
      display: grid;
      grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
      gap: 18px;
    }
    .panel {
      padding: 18px;
      min-width: 0;
    }
    .graph-wrap {
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
    }
    svg.graph {
      width: 100%;
      min-width: 880px;
      height: 620px;
      display: block;
    }
    .node rect {
      fill: white;
      stroke: #cfd8d1;
      rx: 8;
    }
    .node.core rect { stroke: var(--green); stroke-width: 2; }
    .node.review rect { stroke: var(--red); stroke-width: 2; }
    .node.artifact rect { stroke: var(--violet); stroke-width: 2; }
    .node text {
      font-size: 12px;
      fill: var(--ink);
    }
    .edge {
      stroke: #a7b0aa;
      stroke-width: 1.4;
      fill: none;
    }
    .edge.explicit {
      stroke: var(--green);
      stroke-width: 2;
    }
    .edge-label {
      font-size: 10px;
      fill: #66736d;
    }
    .object-list {
      display: grid;
      gap: 8px;
      max-height: 620px;
      overflow: auto;
      padding-right: 4px;
    }
    .object-row {
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
    }
    .object-row strong {
      display: block;
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .object-row span {
      display: block;
      margin-top: 3px;
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .issue-board {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .issue-col {
      display: grid;
      align-content: start;
      gap: 10px;
      min-width: 0;
    }
    .issue-col h3 {
      margin: 0 0 4px;
      font-size: 18px;
    }
    .issue, .artifact, .stage {
      padding: 14px;
      min-width: 0;
    }
    .issue p, .artifact p, .stage p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .artifact-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .workflow {
      display: grid;
      grid-template-columns: repeat(6, minmax(0, 1fr));
      gap: 12px;
    }
    .stage {
      min-height: 170px;
    }
    .stage ol {
      margin: 10px 0 0;
      padding-left: 20px;
      color: var(--muted);
      font-size: 12px;
    }
    footer {
      padding: 28px 0 44px;
      color: var(--muted);
      font-size: 13px;
    }
    @media (max-width: 920px) {
      .intro-grid, .metrics, .two-col, .issue-board, .artifact-grid, .workflow {
        grid-template-columns: 1fr;
      }
      .event {
        grid-template-columns: 58px minmax(0, 1fr);
      }
      .event .chips {
        grid-column: 2;
      }
      .hero {
        min-height: auto;
      }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div>
        <div class="eyebrow">Research Paper Suite</div>
        <h1 id="project-title">Ontology-backed paper workflow</h1>
        <p class="lede" id="project-subtitle"></p>
      </div>
      <div class="intro-grid">
        <article class="intro-card">
          <h2>Ontology Structure</h2>
          <p>The suite separates paper work into a semantic layer of typed objects, a kinetic layer of append-only events and deterministic functions, and a dynamic layer of routers, experts, workflows, and approval gates.</p>
        </article>
        <article class="intro-card">
          <h2>Inspiration</h2>
          <p>The design borrows the useful idea of an ontology from AIP-style systems, but keeps it small: YAML schemas, proposal validation, replayable state, and isolated expert packets instead of a heavy platform.</p>
        </article>
        <article class="intro-card">
          <h2>Metacognition</h2>
          <p>The goal is not to store hidden reasoning. The project records evidence, actions, issues, artifacts, and decisions so a paper can be audited, reviewed, recovered, and improved over time.</p>
        </article>
      </div>
    </div>
  </header>

  <main>
    <section class="band">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Project Snapshot</h2>
            <p>One glance at the current projected state: event count, object surface, issue load, and artifact output.</p>
          </div>
        </div>
        <div class="metrics" id="metrics"></div>
      </div>
    </section>

    <section class="band">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Event Timeline</h2>
            <p>The event log is the source of truth. Each entry records who proposed or executed an action, which function handled it, and which object changed.</p>
          </div>
        </div>
        <div class="timeline" id="timeline"></div>
      </div>
    </section>

    <section class="band">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Object Graph</h2>
            <p>The projected paper state becomes a typed graph: paper objects, argument objects, review objects, and artifacts connected by explicit links or schema references.</p>
          </div>
        </div>
        <div class="two-col">
          <div class="panel">
            <div class="graph-wrap"><svg class="graph" id="graph" role="img" aria-label="Object graph"></svg></div>
          </div>
          <aside class="panel">
            <h2>Objects</h2>
            <div class="object-list" id="objects"></div>
          </aside>
        </div>
      </div>
    </section>

    <section class="band">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Issue Board</h2>
            <p>Review and style checks become structured work items. Severity, status, source, and affected paper objects stay machine-readable.</p>
          </div>
        </div>
        <div class="issue-board" id="issues"></div>
      </div>
    </section>

    <section class="band">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Artifact Map</h2>
            <p>Generated and user-provided files are first-class artifacts, tied back to events, functions, and paper objects.</p>
          </div>
        </div>
        <div class="artifact-grid" id="artifacts"></div>
      </div>
    </section>

    <section class="band">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Workflow Summary</h2>
            <p>v0.1 infers coarse workflow stages from action types and actors. This is intentionally simple until workflow-run events exist.</p>
          </div>
        </div>
        <div class="workflow" id="workflow"></div>
      </div>
    </section>
  </main>

  <footer>
    <div class="wrap">Generated by scripts/export_project_visualization.py</div>
  </footer>

  <script id="viz-data" type="application/json">__VIS_DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById("viz-data").textContent);
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    const chip = (value, cls = "") => `<span class="chip ${cls}">${esc(value)}</span>`;

    function renderHeader() {
      const project = data.project;
      document.title = `${project.title || "Research Paper Suite"} Visualization`;
      document.getElementById("project-title").textContent = project.title || "Ontology-backed paper workflow";
      const bits = [project.paper_id, project.field, project.stage].filter(Boolean).join(" / ");
      document.getElementById("project-subtitle").textContent = bits || project.project_dir;
    }

    function renderMetrics() {
      const objectTotal = Object.values(data.objects.counts).reduce((a, b) => a + b, 0);
      const items = [
        ["Events", data.events.counts.events],
        ["Objects", objectTotal],
        ["Issues", data.issues.issues.length],
        ["Artifacts", data.artifacts.artifacts.length],
      ];
      document.getElementById("metrics").innerHTML = items.map(([label, value]) => `
        <article class="metric"><strong>${esc(value)}</strong><span>${esc(label)}</span></article>
      `).join("");
    }

    function renderTimeline() {
      document.getElementById("timeline").innerHTML = data.events.timeline.map((event) => {
        const payload = Object.entries(event.payload_preview || {}).map(([key, value]) => chip(`${key}: ${value}`)).join("");
        return `
          <article class="event">
            <div><span class="offset">${esc(event.offset)}</span></div>
            <div>
              <h3>${esc(event.headline)}</h3>
              <div class="event-meta">${esc(event.event_id)} / ${esc(event.actor)} / ${esc(event.function)}</div>
            </div>
            <div class="chips">${chip(event.action_type)}${chip(event.object_type)}${payload}</div>
          </article>
        `;
      }).join("");
    }

    function typeClass(type) {
      if (["Paper", "Section", "Claim", "Evidence", "Method", "Dataset", "Experiment", "Metric", "Result", "Citation"].includes(type)) return "core";
      if (["Review", "Issue", "Decision"].includes(type)) return "review";
      if (type === "Artifact") return "artifact";
      return "";
    }

    function renderGraph() {
      const svg = document.getElementById("graph");
      const nodes = data.graph.nodes;
      const edges = data.graph.edges;
      const width = 1180;
      const height = Math.max(620, Math.ceil(nodes.length / 4) * 150 + 160);
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      svg.innerHTML = "";

      const lanes = ["Paper", "Section", "Claim", "Evidence", "ReasoningStep", "Method", "Dataset", "Experiment", "Metric", "Result", "Citation", "Review", "Issue", "Decision", "Venue", "Artifact"];
      const laneIndex = new Map(lanes.map((name, index) => [name, index]));
      const buckets = new Map();
      nodes.forEach((node) => {
        const index = laneIndex.has(node.type) ? laneIndex.get(node.type) : lanes.length;
        if (!buckets.has(index)) buckets.set(index, []);
        buckets.get(index).push(node);
      });
      const positions = new Map();
      let row = 0;
      [...buckets.keys()].sort((a, b) => a - b).forEach((bucketKey) => {
        const bucket = buckets.get(bucketKey);
        bucket.forEach((node, col) => {
          positions.set(node.id, {
            x: 30 + (col % 4) * 278,
            y: 30 + row * 132 + Math.floor(col / 4) * 132,
          });
        });
        row += Math.ceil(bucket.length / 4);
      });

      const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
      defs.innerHTML = `<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z" fill="#8b9690"></path></marker>`;
      svg.appendChild(defs);

      edges.forEach((edge) => {
        const from = positions.get(edge.source);
        const to = positions.get(edge.target);
        if (!from || !to) return;
        const x1 = from.x + 220;
        const y1 = from.y + 31;
        const x2 = to.x;
        const y2 = to.y + 31;
        const mid = Math.max(24, Math.abs(x2 - x1) / 2);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("class", `edge ${edge.source_kind}`);
        path.setAttribute("d", `M ${x1} ${y1} C ${x1 + mid} ${y1}, ${x2 - mid} ${y2}, ${x2} ${y2}`);
        path.setAttribute("marker-end", "url(#arrow)");
        svg.appendChild(path);

        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("class", "edge-label");
        label.setAttribute("x", String((x1 + x2) / 2));
        label.setAttribute("y", String((y1 + y2) / 2 - 6));
        label.textContent = edge.label;
        svg.appendChild(label);
      });

      nodes.forEach((node) => {
        const pos = positions.get(node.id);
        const group = document.createElementNS("http://www.w3.org/2000/svg", "g");
        group.setAttribute("class", `node ${typeClass(node.type)}`);
        group.setAttribute("transform", `translate(${pos.x}, ${pos.y})`);
        group.innerHTML = `
          <rect width="220" height="72"></rect>
          <text x="12" y="22" font-weight="700">${esc(node.type)}</text>
          <text x="12" y="42">${esc(node.id).slice(0, 28)}</text>
          <text x="12" y="60">${esc(node.label).slice(0, 30)}</text>
        `;
        svg.appendChild(group);
      });
    }

    function renderObjects() {
      const objects = Object.values(data.objects.objects);
      document.getElementById("objects").innerHTML = objects.map((object) => `
        <div class="object-row">
          <strong>${esc(object.type)} / ${esc(object.id)}</strong>
          <span>${esc(object.label)}</span>
          ${object.summary ? `<span>${esc(object.summary)}</span>` : ""}
        </div>
      `).join("");
    }

    function severityClass(severity) {
      return String(severity || "").toLowerCase();
    }

    function renderIssues() {
      const severities = ["P0", "P1", "P2"];
      const bySeverity = new Map(severities.map((severity) => [severity, []]));
      data.issues.issues.forEach((issue) => {
        if (!bySeverity.has(issue.severity)) bySeverity.set(issue.severity, []);
        bySeverity.get(issue.severity).push(issue);
      });
      document.getElementById("issues").innerHTML = [...bySeverity.entries()].map(([severity, issues]) => `
        <div class="issue-col">
          <h3>${esc(severity)} <span class="tiny">${issues.length} issue${issues.length === 1 ? "" : "s"}</span></h3>
          ${issues.map((issue) => `
            <article class="issue">
              <div class="chips">${chip(issue.severity, severityClass(issue.severity))}${chip(issue.status, issue.status)}${chip(issue.category)}</div>
              <h3>${esc(issue.id)}</h3>
              <p>${esc(issue.evidence)}</p>
              ${issue.suggested_action ? `<p><strong>Suggested:</strong> ${esc(issue.suggested_action)}</p>` : ""}
              <p class="tiny">${esc(issue.created_by)} ${issue.target_object_id ? `/ ${esc(issue.target_object_type)} ${esc(issue.target_object_id)}` : issue.claim_id ? `/ ${esc(issue.claim_id)}` : ""} ${issue.review_id ? `/ ${esc(issue.review_id)}` : ""}</p>
            </article>
          `).join("") || `<article class="issue"><p>No ${esc(severity)} issues.</p></article>`}
        </div>
      `).join("");
    }

    function renderArtifacts() {
      document.getElementById("artifacts").innerHTML = data.artifacts.artifacts.map((artifact) => `
        <article class="artifact">
          <div class="chips">${chip(artifact.type)}${artifact.event.offset ? chip(`event ${artifact.event.offset}`) : ""}</div>
          <h3>${esc(artifact.id)}</h3>
          <p>${esc(artifact.path)}</p>
          ${artifact.description ? `<p>${esc(artifact.description)}</p>` : ""}
          <p class="tiny">${esc(artifact.produced_by || artifact.event.actor || "")}</p>
        </article>
      `).join("") || `<article class="artifact"><p>No artifacts recorded.</p></article>`;
    }

    function renderWorkflow() {
      document.getElementById("workflow").innerHTML = data.workflow.stages.map((stage) => `
        <article class="stage">
          <h3>${esc(stage.name)}</h3>
          <p>${esc(stage.description)}</p>
          <ol>
            ${stage.events.slice(0, 7).map((event) => `<li>${esc(event.offset)} ${esc(event.action_type)}</li>`).join("")}
          </ol>
          ${stage.events.length > 7 ? `<p class="tiny">+ ${stage.events.length - 7} more events</p>` : ""}
        </article>
      `).join("");
    }

    renderHeader();
    renderMetrics();
    renderTimeline();
    renderGraph();
    renderObjects();
    renderIssues();
    renderArtifacts();
    renderWorkflow();
  </script>
</body>
</html>
"""


STORY_HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Research Paper Suite Visualization</title>
  <style>
    :root {
      --bg: #f7f8f5;
      --ink: #202722;
      --muted: #626d66;
      --line: #d9dfd8;
      --paper: #ffffff;
      --soft: #eef3ef;
      --green: #206b55;
      --blue: #245f9f;
      --amber: #a86617;
      --red: #ad2f24;
      --violet: #6552b8;
      --shadow: 0 12px 28px rgba(29, 37, 34, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }
    .wrap { width: min(1180px, calc(100% - 32px)); margin: 0 auto; }
    header {
      min-height: 88vh;
      display: grid;
      align-items: center;
      border-bottom: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(255,255,255,0.78), rgba(247,248,245,0.92)),
        url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='1200' height='760' viewBox='0 0 1200 760'%3E%3Crect width='1200' height='760' fill='%23edf3ee'/%3E%3Cg fill='none' stroke='%23b8c8bd' stroke-width='2' opacity='0.65'%3E%3Cpath d='M125 170h210v86H125zM525 118h240v96H525zM840 292h230v94H840zM186 438h250v94H186zM596 482h255v104H596z'/%3E%3Cpath d='M335 213c80 0 110-48 190-48M765 166c86 0 86 174 75 174M436 485c88-4 90 42 160 42M306 256c30 72-84 114-5 182M735 214c-34 132-164 116-139 268'/%3E%3C/g%3E%3Cg fill='%23206b55' opacity='0.16'%3E%3Ccircle cx='125' cy='170' r='10'/%3E%3Ccircle cx='525' cy='118' r='10'/%3E%3Ccircle cx='840' cy='292' r='10'/%3E%3Ccircle cx='186' cy='438' r='10'/%3E%3Ccircle cx='596' cy='482' r='10'/%3E%3C/g%3E%3C/svg%3E");
      background-size: cover;
      background-position: center;
    }
    .hero { padding: 54px 0 42px; }
    .eyebrow {
      color: var(--green);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }
    h1 {
      max-width: 940px;
      margin: 10px 0 18px;
      font-size: clamp(42px, 7vw, 88px);
      line-height: 0.98;
      letter-spacing: 0;
    }
    .lede {
      max-width: 760px;
      margin: 0;
      color: #3f4b45;
      font-size: 20px;
    }
    .hero-strip {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-top: 30px;
      max-width: 980px;
    }
    .metric, .card, .step, .issue, .trail, .artifact, .debug-panel {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .metric { padding: 16px; min-height: 92px; }
    .metric strong { display: block; font-size: 30px; line-height: 1; }
    .metric.is-text strong { font-size: 20px; line-height: 1.12; overflow-wrap: anywhere; }
    .metric span { display: block; margin-top: 8px; color: var(--muted); font-size: 13px; }
    .page-nav {
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 1px solid var(--line);
      background: rgba(247, 248, 245, 0.96);
      backdrop-filter: blur(10px);
    }
    .page-nav-inner {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 10px 0;
      scrollbar-width: thin;
    }
    .page-tab {
      flex: 0 0 auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 800;
      padding: 8px 11px;
    }
    .page-tab:hover,
    .page-tab:focus-visible {
      border-color: var(--green);
      outline: 2px solid #cfe6db;
      outline-offset: 1px;
    }
    .page-tab.is-active {
      background: var(--ink);
      border-color: var(--ink);
      color: #ffffff;
    }
    main { padding: 16px 0 64px; }
    section { padding: 34px 0; border-bottom: 1px solid var(--line); }
    .page-section[hidden] { display: none; }
    .page-section {
      min-height: calc(100vh - 180px);
    }
    .page-subsection {
      margin-top: 34px;
      padding-top: 34px;
      border-top: 1px solid var(--line);
    }
    .section-head {
      display: grid;
      grid-template-columns: minmax(0, 0.72fr) minmax(300px, 0.28fr);
      gap: 24px;
      align-items: end;
      margin-bottom: 18px;
    }
    .section-head h2 { margin: 0; font-size: 30px; letter-spacing: 0; }
    .section-head p, .muted { color: var(--muted); margin: 6px 0 0; }
    .mechanism {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
    }
    .visual-board {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(300px, 0.8fr);
      gap: 14px;
      align-items: stretch;
      margin-top: 18px;
    }
    .integrity-panel {
      margin-top: 18px;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      background: #fbfcfa;
      padding: 16px 0;
    }
    .integrity-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 12px;
    }
    .integrity-head h3 { margin: 0; font-size: 18px; letter-spacing: 0; }
    .integrity-head p { margin: 0; color: var(--muted); font-size: 13px; }
    .integrity-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: var(--paper);
    }
    .integrity-stat {
      min-height: 112px;
      padding: 14px;
      border-right: 1px solid var(--line);
    }
    .integrity-stat:last-child { border-right: 0; }
    .integrity-stat strong { display: block; font-size: 22px; line-height: 1.1; overflow-wrap: anywhere; }
    .integrity-stat span { display: block; margin-top: 6px; color: var(--muted); font-size: 12px; }
    .integrity-stat .state { color: var(--green); font-weight: 800; }
    .integrity-stat .state.warn { color: var(--amber); }
    .integrity-stat .state.fail { color: var(--red); }
    .viz-card {
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 16px;
      min-width: 0;
    }
    .viz-card h3 {
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .viz-card p {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 13px;
    }
    .flow-svg, .dot-svg {
      width: 100%;
      min-height: 220px;
      display: block;
      border-radius: 8px;
      background: #fbfcfa;
      border: 1px solid var(--line);
    }
    .bar-list {
      display: grid;
      gap: 10px;
      margin-top: 12px;
    }
    .bar-row {
      display: grid;
      grid-template-columns: 118px minmax(0, 1fr) 38px;
      gap: 8px;
      align-items: center;
      font-size: 13px;
      color: #3f4b45;
    }
    .bar-track {
      height: 12px;
      border-radius: 999px;
      background: #edf1ee;
      overflow: hidden;
    }
    .bar-fill {
      height: 100%;
      border-radius: 999px;
      background: var(--green);
    }
    .bar-fill.p0 { background: var(--red); }
    .bar-fill.p1 { background: var(--amber); }
    .bar-fill.p2 { background: var(--green); }
    .source-note {
      margin-top: 18px;
      padding: 16px;
      background: #fbfcfa;
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .source-note summary {
      color: var(--ink);
      font-size: 15px;
      font-weight: 800;
    }
    .source-note p {
      margin: 7px 0 0;
      color: var(--muted);
      font-size: 14px;
    }
    .card { padding: 18px; min-height: 220px; }
    .card .num {
      display: grid;
      place-items: center;
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background: #e5f2ec;
      color: var(--green);
      font-weight: 800;
      margin-bottom: 14px;
    }
    .card h3, .step h3, .issue h3, .trail h3, .artifact h3, .debug-panel h3 {
      margin: 0 0 8px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .card p, .step p, .issue p, .trail p, .artifact p, .debug-panel p {
      margin: 7px 0 0;
      color: var(--muted);
      font-size: 14px;
      overflow-wrap: anywhere;
    }
    .flow {
      display: grid;
      grid-template-columns: 1fr;
      gap: 18px;
      align-items: start;
    }
    .steps { display: grid; gap: 12px; }
    .step {
      display: grid;
      grid-template-columns: 64px minmax(0, 1fr);
      gap: 14px;
      padding: 16px;
    }
    .offset {
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      border-radius: 8px;
      background: #e9f1ec;
      color: var(--green);
      font-weight: 800;
    }
    details {
      margin-top: 10px;
      border-top: 1px solid var(--line);
      padding-top: 10px;
    }
    summary {
      cursor: pointer;
      color: var(--blue);
      font-size: 13px;
      font-weight: 700;
    }
    pre {
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 10px 0 0;
      padding: 10px;
      border-radius: 8px;
      background: #f1f4f2;
      color: #39443f;
      font-size: 12px;
    }
    .chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
    .chip {
      display: inline-flex;
      min-height: 24px;
      align-items: center;
      padding: 3px 8px;
      border-radius: 999px;
      background: var(--soft);
      color: #46524c;
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .chip.p0 { background: #fee4e2; color: var(--red); }
    .chip.p1 { background: #fef1cb; color: #83500e; }
    .chip.p2 { background: #e5f2ec; color: var(--green); }
    .chip.open { background: #fff1e6; color: #9a3412; }
    .chip.resolved { background: #dcfce7; color: #166534; }
    .chip.history { background: #edf2f7; color: #475569; }
    .debug-panel { padding: 18px; position: sticky; top: 16px; }
    .debug-panel ul { margin: 12px 0 0; padding-left: 18px; color: var(--muted); font-size: 13px; }
    .audit-details {
      margin-top: 0;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 0;
      overflow: hidden;
    }
    .audit-details > summary {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px;
      color: var(--ink);
      font-size: 14px;
      list-style: none;
    }
    .audit-details > summary::-webkit-details-marker { display: none; }
    .audit-details[open] > summary { border-bottom: 1px solid var(--line); }
    .audit-grid {
      display: grid;
      grid-template-columns: minmax(0, 0.36fr) minmax(0, 0.64fr);
      gap: 14px;
      padding: 16px;
    }
    .audit-grid .debug-panel { position: static; box-shadow: none; }
    .execution-panel {
      padding: 16px;
      border-bottom: 1px solid var(--line);
      background: #fbfcfa;
    }
    .execution-panel h3 { margin: 0; font-size: 18px; letter-spacing: 0; }
    .execution-panel > p { margin: 5px 0 12px; color: var(--muted); font-size: 13px; }
    .execution-list { display: grid; gap: 8px; }
    .execution-row {
      display: grid;
      grid-template-columns: minmax(150px, 0.9fr) minmax(150px, 0.9fr) minmax(180px, 1.1fr) minmax(0, 1.6fr);
      gap: 10px;
      align-items: start;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }
    .execution-row strong { display: block; font-size: 13px; overflow-wrap: anywhere; }
    .execution-row span { display: block; margin-top: 3px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .execution-row .state.good { color: var(--green); }
    .execution-row .state.warn { color: var(--amber); }
    .action-inventory {
      margin-top: 14px;
    }
    .action-inventory-list {
      display: grid;
      gap: 10px;
      max-height: 420px;
      overflow-y: auto;
      padding-right: 4px;
      scrollbar-gutter: stable;
      scrollbar-width: thin;
      scrollbar-color: #b8c8bd #eef3ef;
    }
    .action-inventory-list::-webkit-scrollbar { width: 10px; }
    .action-inventory-list::-webkit-scrollbar-thumb {
      background: #b8c8bd;
      border: 2px solid #ffffff;
      border-radius: 999px;
    }
    .action-inventory-list::-webkit-scrollbar-track {
      background: #eef3ef;
      border-radius: 999px;
    }
    .action-group {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 0;
      background: #ffffff;
    }
    .action-group > summary {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 10px;
      color: var(--ink);
      list-style: none;
    }
    .action-group > summary::-webkit-details-marker { display: none; }
    .action-group[open] > summary { border-bottom: 1px solid var(--line); }
    .action-group-title { font-weight: 800; }
    .action-group-meta { color: var(--muted); font-size: 12px; font-weight: 600; }
    .action-row {
      padding: 10px;
      border-bottom: 1px solid var(--line);
    }
    .action-row:last-child { border-bottom: 0; }
    .action-title {
      display: flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
    }
    .action-title code, .function-line code, .action-event code {
      padding: 2px 5px;
      border-radius: 6px;
      background: #f1f4f2;
      color: #39443f;
      font-size: 12px;
    }
    .function-line {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .action-events {
      display: grid;
      gap: 6px;
      max-height: 150px;
      overflow-y: auto;
      margin-top: 8px;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
    }
    .action-event {
      color: var(--muted);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .issue-board { display: grid; gap: 22px; }
    .issue-section-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 14px;
      margin-bottom: 10px;
    }
    .issue-section-head h3 { margin: 0; font-size: 18px; letter-spacing: 0; }
    .issue-section-head p { margin: 0; color: var(--muted); font-size: 13px; }
    .issue-grid, .trail-grid, .artifact-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }
    .issue, .trail, .artifact { padding: 16px; min-width: 0; }
    .issue h3 { color: #26302b; }
    .issue.is-history {
      border-style: dashed;
      box-shadow: none;
      background: #fbfcfa;
    }
    .label {
      display: block;
      margin-top: 12px;
      color: var(--ink);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .trail-node {
      border-left: 3px solid var(--green);
      padding: 0 0 13px 12px;
      margin-top: 12px;
    }
    .trail-node:last-child { padding-bottom: 0; }
    .trail-node strong { display: block; font-size: 13px; color: var(--ink); }
    .literature-summary {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }
    .coverage-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #ffffff;
      margin-bottom: 14px;
    }
    .coverage-role { min-height: 88px; padding: 12px; border-right: 1px solid var(--line); }
    .coverage-role:last-child { border-right: 0; }
    .coverage-role strong { display: block; font-size: 13px; overflow-wrap: anywhere; }
    .coverage-role span { display: block; margin-top: 6px; color: var(--muted); font-size: 12px; }
    .coverage-role.covered { border-top: 4px solid var(--green); }
    .coverage-role.documented { border-top: 4px solid var(--amber); }
    .coverage-role.missing { border-top: 4px solid var(--red); }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }
    .literature-table { width: 100%; min-width: 920px; border-collapse: collapse; }
    .literature-table th,
    .literature-table td {
      padding: 10px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 12px;
    }
    .literature-table th { color: var(--ink); background: #f1f4f2; font-weight: 800; }
    .literature-table td { color: #46524c; }
    .literature-table tr:last-child td { border-bottom: 0; }
    .literature-table .work-title { color: var(--ink); font-size: 13px; font-weight: 800; }
    .literature-table .subline { display: block; margin-top: 3px; color: var(--muted); overflow-wrap: anywhere; }
    .provenance-list { display: grid; gap: 12px; }
    .provenance-chain {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
      padding: 14px;
    }
    .provenance-chain h3 { margin: 0; font-size: 16px; letter-spacing: 0; }
    .provenance-chain > p { margin: 5px 0 0; color: var(--muted); font-size: 13px; }
    .chain-path {
      display: grid;
      grid-template-columns: minmax(160px, 1fr) 28px minmax(160px, 1fr) 28px minmax(180px, 1.2fr);
      gap: 8px;
      align-items: stretch;
      margin-top: 12px;
    }
    .chain-node {
      min-width: 0;
      padding: 10px;
      border-left: 4px solid var(--green);
      background: #f7faf8;
    }
    .chain-node.is-span { border-left-color: var(--blue); }
    .chain-node.is-artifact { border-left-color: var(--amber); }
    .chain-node strong { display: block; font-size: 12px; }
    .chain-node span { display: block; margin-top: 4px; color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }
    .chain-arrow { display: grid; place-items: center; color: #7c8881; font-weight: 800; }
    .artifact .path {
      font-family: ui-monospace, SFMono-Regular, Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      color: #46524c;
      background: #f1f4f2;
      border-radius: 8px;
      padding: 8px;
    }
    .mini-graph {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 12px;
    }
    .mini-node {
      min-height: 98px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
    }
    .mini-node strong { display: block; color: var(--green); font-size: 13px; }
    .mini-node span { display: block; margin-top: 6px; color: var(--muted); font-size: 12px; }
    .graph-details {
      margin-top: 18px;
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }
    .graph-details > summary {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 16px;
      color: var(--ink);
      font-size: 14px;
      list-style: none;
    }
    .graph-details > summary::-webkit-details-marker { display: none; }
    .graph-details[open] > summary { border-bottom: 1px solid var(--line); }
    .summary-title {
      display: block;
      font-size: 18px;
      font-weight: 800;
    }
    .summary-meta {
      display: block;
      color: var(--muted);
      font-size: 13px;
      font-weight: 500;
    }
    .graph-layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 0.32fr);
      gap: 14px;
      padding: 16px;
    }
    .graph-toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }
    .graph-actions { display: flex; flex-wrap: wrap; gap: 8px; }
    .graph-button, .neighbor-button {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      font-size: 13px;
      font-weight: 700;
    }
    .graph-button { padding: 7px 10px; }
    .neighbor-button {
      width: 100%;
      padding: 8px;
      text-align: left;
    }
    .graph-button:hover, .neighbor-button:hover,
    .graph-button:focus-visible, .neighbor-button:focus-visible {
      border-color: var(--green);
      outline: 2px solid #cfe6db;
      outline-offset: 1px;
    }
    .graph-canvas {
      min-height: 360px;
      max-height: 640px;
      overflow: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
    }
    .object-link-svg {
      display: block;
      min-width: 860px;
      width: 100%;
      height: auto;
    }
    .graph-edge {
      fill: none;
      stroke: #a5afa8;
      stroke-width: 1.5;
    }
    .graph-edge.explicit {
      stroke: var(--green);
      stroke-width: 2.2;
    }
    .graph-edge-label {
      fill: #56615b;
      font-size: 10px;
      paint-order: stroke;
      stroke: #fbfcfa;
      stroke-width: 4px;
      stroke-linejoin: round;
    }
    .graph-node { cursor: pointer; }
    .graph-node rect {
      fill: #ffffff;
      stroke: #cfd8d1;
      stroke-width: 1.5;
    }
    .graph-node.is-seed rect { stroke: var(--blue); }
    .graph-node.is-expanded rect { stroke: var(--green); stroke-width: 2.5; }
    .graph-node.is-selected rect { stroke: var(--amber); stroke-width: 3; }
    .graph-node text { pointer-events: none; }
    .graph-node-type {
      fill: var(--green);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .graph-node-label {
      fill: var(--ink);
      font-size: 13px;
      font-weight: 800;
    }
    .graph-node-id {
      fill: var(--muted);
      font-size: 10px;
    }
    .graph-side {
      display: grid;
      gap: 12px;
      align-content: start;
    }
    .graph-detail, .visible-links {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfa;
      padding: 12px;
      min-width: 0;
    }
    .graph-detail h3, .visible-links h3 {
      margin: 0 0 8px;
      font-size: 16px;
    }
    .graph-detail p, .visible-links p {
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }
    .event-history-list,
    .neighbor-list {
      display: grid;
      gap: 6px;
      margin-top: 10px;
      max-height: 190px;
      overflow-y: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
      scrollbar-width: thin;
      scrollbar-color: #b8c8bd #eef3ef;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }
    .event-history-list {
      max-height: 150px;
      margin-bottom: 12px;
    }
    .link-list {
      display: grid;
      gap: 8px;
      margin-top: 8px;
      max-height: 260px;
      overflow-y: auto;
      overscroll-behavior: contain;
      scrollbar-gutter: stable;
      scrollbar-width: thin;
      scrollbar-color: #b8c8bd #eef3ef;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #ffffff;
    }
    .event-history-list::-webkit-scrollbar,
    .neighbor-list::-webkit-scrollbar,
    .link-list::-webkit-scrollbar {
      width: 10px;
    }
    .event-history-list::-webkit-scrollbar-thumb,
    .neighbor-list::-webkit-scrollbar-thumb,
    .link-list::-webkit-scrollbar-thumb {
      background: #b8c8bd;
      border: 2px solid #ffffff;
      border-radius: 999px;
    }
    .event-history-list::-webkit-scrollbar-track,
    .neighbor-list::-webkit-scrollbar-track,
    .link-list::-webkit-scrollbar-track {
      background: #eef3ef;
      border-radius: 999px;
    }
    .event-history-row {
      display: grid;
      grid-template-columns: 58px minmax(0, 1fr);
      gap: 8px;
      align-items: start;
      border-left: 3px solid #d8dfd9;
      padding: 4px 0 4px 8px;
    }
    .event-history-row code {
      color: var(--green);
      font-size: 11px;
      font-weight: 800;
    }
    .event-history-row strong {
      display: block;
      color: var(--ink);
      font-size: 12px;
      overflow-wrap: anywhere;
    }
    .event-history-row span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-top: 2px;
      overflow-wrap: anywhere;
    }
    .link-row {
      border-left: 3px solid #cfd8d1;
      padding-left: 8px;
    }
    .link-row.explicit { border-left-color: var(--green); }
    footer { padding: 28px 0 44px; color: var(--muted); font-size: 13px; }
    @media (max-width: 980px) {
      header { min-height: auto; }
      .hero-strip, .mechanism, .visual-board, .flow, .issue-grid, .trail-grid, .artifact-grid, .section-head, .mini-graph, .graph-layout {
        grid-template-columns: 1fr;
      }
      .step { grid-template-columns: 54px minmax(0, 1fr); }
      .debug-panel { position: static; }
      .audit-grid { grid-template-columns: 1fr; }
      .integrity-grid, .coverage-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .integrity-stat:nth-child(2), .coverage-role:nth-child(2) { border-right: 0; }
      .integrity-stat:nth-child(-n+2), .coverage-role:nth-child(-n+2) { border-bottom: 1px solid var(--line); }
      .execution-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .chain-path { grid-template-columns: 1fr; }
      .chain-arrow { min-height: 24px; transform: rotate(90deg); }
      .graph-details > summary { align-items: flex-start; flex-direction: column; }
    }
    @media (max-width: 560px) {
      .integrity-grid, .coverage-grid, .execution-row { grid-template-columns: 1fr; }
      .integrity-stat, .coverage-role { border-right: 0; border-bottom: 1px solid var(--line); }
      .integrity-stat:last-child, .coverage-role:last-child { border-bottom: 0; }
    }
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <div class="eyebrow">Research Paper Suite / Guided View</div>
      <h1 id="project-title">A paper project you can trace</h1>
      <p class="lede" id="story-headline"></p>
      <div class="hero-strip" id="metrics"></div>
    </div>
  </header>

  <nav class="page-nav" aria-label="Visualization pages">
    <div class="wrap page-nav-inner">
      <button class="page-tab is-active" type="button" data-page-target="overview" aria-current="page">Overview</button>
      <button class="page-tab" type="button" data-page-target="graph">Graph</button>
      <button class="page-tab" type="button" data-page-target="timeline">Timeline</button>
      <button class="page-tab" type="button" data-page-target="issues">Issues</button>
      <button class="page-tab" type="button" data-page-target="evidence-files">Evidence & Files</button>
      <button class="page-tab" type="button" data-page-target="audit">Audit</button>
    </div>
  </nav>

  <main>
    <section class="page-section is-active" data-page="overview">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Project Tracking Model</h2>
            <p id="story-thesis"></p>
          </div>
          <div class="mini-graph">
            <div class="mini-node"><strong>Experts</strong><span>Propose focused writing, review, style, venue, or assembly changes.</span></div>
            <div class="mini-node"><strong>Event log</strong><span>Stores accepted changes as numbered, replayable events.</span></div>
            <div class="mini-node"><strong>Objects</strong><span>Keeps sections, claims, issues, reviews, decisions, and artifacts addressable.</span></div>
            <div class="mini-node"><strong>Links</strong><span>Connects claims, evidence, review findings, decisions, and files.</span></div>
          </div>
        </div>
        <div class="mechanism" id="mechanism"></div>
        <div class="integrity-panel" id="research-integrity"></div>
        <div class="visual-board">
          <article class="viz-card">
            <h3>Workflow Overview</h3>
            <svg class="flow-svg" id="flow-diagram" role="img" aria-label="Workflow overview diagram"></svg>
            <p>Accepted paper work moves from expert proposals, to event log entries, to projected objects and visible review trails.</p>
          </article>
          <article class="viz-card">
            <h3>Current Project Snapshot</h3>
            <div id="run-bars"></div>
          </article>
        </div>
        <div class="visual-board">
          <article class="viz-card">
            <h3>Event Timeline</h3>
            <svg class="dot-svg" id="event-dots" role="img" aria-label="Event timeline diagram"></svg>
            <p>Each dot is one recorded step. Color shows the rough kind of work being done.</p>
          </article>
          <article class="viz-card">
            <details class="source-note">
              <summary id="source-title">Data provenance</summary>
              <p id="source-body"></p>
              <p id="source-future"></p>
            </details>
          </article>
        </div>
      </div>
    </section>

    <section class="page-section" data-page="graph" hidden>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Object Link Graph</h2>
            <p>Key paper objects appear first, and the full relationship graph remains available without overwhelming the page.</p>
          </div>
        </div>
        <details class="graph-details" open>
          <summary>
            <span>
              <span class="summary-title">Expandable Object Graph</span>
              <span class="summary-meta" id="graph-summary"></span>
            </span>
            <span class="chip" id="graph-visible-count"></span>
          </summary>
          <div class="graph-layout">
            <div>
              <div class="graph-toolbar">
                <p class="muted" id="graph-note"></p>
                <div class="graph-actions">
                  <button class="graph-button" type="button" id="graph-expand-all">Expand all</button>
                  <button class="graph-button" type="button" id="graph-reset">Reset</button>
                </div>
              </div>
              <div class="graph-canvas">
                <svg class="object-link-svg" id="object-link-graph" role="img" aria-label="Expandable object link graph"></svg>
              </div>
            </div>
            <aside class="graph-side">
              <div class="graph-detail" id="object-graph-detail"></div>
              <div class="visible-links" id="visible-links"></div>
            </aside>
          </div>
        </details>
      </div>
    </section>

    <section class="page-section" data-page="timeline" hidden>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Change Timeline</h2>
            <p>Each recorded step is translated into a plain-language note: what happened, who did it, and why it matters.</p>
          </div>
        </div>
        <div class="flow">
          <div class="steps" id="lifecycle"></div>
        </div>
      </div>
    </section>

    <section class="page-section" data-page="issues" hidden>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Open Review Issues</h2>
            <p>Unresolved findings stay in the active work queue. Resolved findings move to history so old P0 risks do not look like current blockers.</p>
          </div>
        </div>
        <div class="issue-board" id="issues"></div>
      </div>
    </section>

    <section class="page-section" data-page="evidence-files" hidden>
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Literature Verification & Positioning</h2>
            <p>Selected citations show their metadata depth, verification state, positioning role, and exact paper target.</p>
          </div>
        </div>
        <div id="literature-overview"></div>
      </div>
      <div class="wrap page-subsection">
        <div class="section-head">
          <div>
            <h2>Source Provenance Chains</h2>
            <p>Evidence remains traceable through normalized SourceSpan anchors to the exact recorded Artifact.</p>
          </div>
        </div>
        <div class="provenance-list" id="provenance-chains"></div>
      </div>
      <div class="wrap page-subsection">
        <div class="section-head">
          <div>
            <h2>Evidence Trail</h2>
            <p>Claims, review findings, decisions, and files are connected so you can see the reason behind each concern.</p>
          </div>
        </div>
        <div class="trail-grid" id="trails"></div>
      </div>
      <div class="wrap page-subsection">
        <div class="section-head">
          <div>
            <h2>Project Files & Artifacts</h2>
            <p>Reports, manuscripts, source files, and generated outputs are shown with where they entered the project.</p>
          </div>
        </div>
        <div class="artifact-grid" id="artifacts"></div>
      </div>
    </section>

    <section id="audit-debug" class="page-section" data-page="audit" hidden>
      <div class="wrap">
        <div class="execution-panel">
          <h3>Expert Execution</h3>
          <p>Requested invocation mode is shown separately from the backend that actually ran.</p>
          <div id="expert-execution"></div>
        </div>
        <details class="audit-details">
          <summary>
            <span>
              <span class="summary-title">Audit / Debug Details</span>
              <span class="summary-meta">Technical provenance for maintainers, reviewers, and workflow debugging.</span>
            </span>
            <span class="summary-meta">Collapsed by default</span>
          </summary>
          <div class="audit-grid">
            <aside class="debug-panel">
              <h3>Data Files</h3>
              <p id="debug-note"></p>
              <ul>
                <li><code>events.json</code> keeps the timeline data.</li>
                <li><code>objects.json</code> keeps projected state objects.</li>
                <li><code>graph.json</code> keeps graph nodes and edges.</li>
                <li><code>story.json</code> keeps this explain-mode narration.</li>
                <li><code>literature.json</code> keeps citation verification and positioning coverage.</li>
                <li><code>provenance.json</code> keeps Evidence to SourceSpan to Artifact chains.</li>
                <li><code>expert_executions.json</code> keeps actual worker backend and isolation records.</li>
                <li><code>visualization.json</code> keeps the complete render data bundle.</li>
              </ul>
            </aside>
            <aside class="debug-panel">
              <h3>Action Runtime</h3>
              <details class="action-inventory">
                <summary>Action Type / Function Inventory</summary>
                <p id="action-inventory-summary"></p>
                <div class="action-inventory-list" id="action-inventory"></div>
              </details>
            </aside>
          </div>
        </details>
      </div>
    </section>
  </main>

  <footer><div class="wrap">Generated by scripts/export_project_visualization.py</div></footer>

  <script id="viz-data" type="application/json">__VIS_DATA__</script>
  <script>
    const data = JSON.parse(document.getElementById("viz-data").textContent);
    const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
    const chip = (value, cls = "") => `<span class="chip ${cls}">${esc(value)}</span>`;
    const severityClass = (severity) => String(severity || "").toLowerCase();
    const shorten = (value, limit = 42) => {
      const compact = String(value ?? "").replace(/\s+/g, " ").trim();
      return compact.length > limit ? `${compact.slice(0, Math.max(0, limit - 3))}...` : compact;
    };
    const pageIds = ["overview", "graph", "timeline", "issues", "evidence-files", "audit"];

    function pageFromHash() {
      const page = window.location.hash.replace(/^#/, "");
      return pageIds.includes(page) ? page : "overview";
    }

    function setActivePage(pageId) {
      const activePage = pageIds.includes(pageId) ? pageId : "overview";
      document.querySelectorAll("[data-page]").forEach((section) => {
        const isActive = section.dataset.page === activePage;
        section.hidden = !isActive;
        section.classList.toggle("is-active", isActive);
      });
      document.querySelectorAll("[data-page-target]").forEach((button) => {
        const isActive = button.dataset.pageTarget === activePage;
        button.classList.toggle("is-active", isActive);
        if (isActive) {
          button.setAttribute("aria-current", "page");
        } else {
          button.removeAttribute("aria-current");
        }
      });
    }

    function initPageRouting() {
      document.querySelectorAll("[data-page-target]").forEach((button) => {
        button.addEventListener("click", () => {
          const target = button.dataset.pageTarget;
          if (!target) return;
          if (window.location.hash !== `#${target}`) {
            window.location.hash = target;
          } else {
            setActivePage(target);
          }
        });
      });
      window.addEventListener("hashchange", () => setActivePage(pageFromHash()));
      setActivePage(pageFromHash());
    }

    function formatAcceptanceStatus(status) {
      const labels = {
        accepted: "Accepted",
        accepted_with_warnings: "Accepted with warnings",
        failed: "Failed",
        not_checked: "Not checked",
      };
      return labels[status] || "Unknown";
    }

    function renderHeader() {
      const project = data.project;
      const acceptance = data.acceptance || { status: "not_checked" };
      document.title = `${project.title || "Research Paper Suite"} / Guided View`;
      document.getElementById("project-title").textContent = project.title || "A paper project you can trace";
      document.getElementById("story-headline").textContent = data.story.headline;
      const objectTotal = Object.values(data.objects.counts).reduce((a, b) => a + b, 0);
      const metrics = [
        ["Recorded steps", data.events.counts.events, false],
        ["Tracked objects", objectTotal, false],
        ["Open issues", data.issues.counts.active || 0, false],
        ["File artifacts", data.artifacts.artifacts.length, false],
        ["Handoff", acceptance.label || formatAcceptanceStatus(acceptance.status), true],
      ];
      document.getElementById("metrics").innerHTML = metrics.map(([label, value, isText]) => `<div class="metric ${isText ? "is-text" : ""}"><strong>${esc(value)}</strong><span>${esc(label)}</span></div>`).join("");
      document.getElementById("story-thesis").textContent = data.story.thesis;
      document.getElementById("debug-note").textContent = data.story.debug_note;
    }

    function renderMechanism() {
      document.getElementById("mechanism").innerHTML = data.story.mechanism.map((item, index) => `
        <article class="card">
          <div class="num">${index + 1}</div>
          <h3>${esc(item.title)}</h3>
          <p>${esc(item.body)}</p>
          <span class="label">Visible proof</span>
          <p>${esc(item.proof)}</p>
        </article>
      `).join("");
    }

    function renderVisuals() {
      renderFlowDiagram();
      renderRunBars();
      renderEventDots();
      document.getElementById("source-title").textContent = data.story.text_source.title;
      document.getElementById("source-body").textContent = data.story.text_source.body;
      document.getElementById("source-future").textContent = data.story.text_source.future_option;
    }

    function renderFlowDiagram() {
      const svg = document.getElementById("flow-diagram");
      svg.setAttribute("viewBox", "0 0 760 240");
      const nodes = [
        ["Experts", "proposals", 34, 74, "#206b55"],
        ["Event log", `${data.events.counts.events} steps`, 214, 74, "#245f9f"],
        ["Objects", `${Object.values(data.objects.counts).reduce((a, b) => a + b, 0)} tracked`, 414, 74, "#6552b8"],
        ["Review trails", `${data.issues.counts.active || 0} open / ${data.artifacts.artifacts.length} files`, 604, 74, "#a86617"],
      ];
      const arrows = [
        [174, 120, 214, 120],
        [374, 120, 414, 120],
        [564, 120, 604, 120],
      ];
      svg.innerHTML = `
        <defs>
          <marker id="story-arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto">
            <path d="M0,0 L9,4.5 L0,9 Z" fill="#8b9690"></path>
          </marker>
        </defs>
        ${arrows.map(([x1,y1,x2,y2]) => `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#9aa59e" stroke-width="2" marker-end="url(#story-arrow)"></line>`).join("")}
        ${nodes.map(([title, subtitle, x, y, color]) => `
          <g transform="translate(${x}, ${y})">
            <rect width="140" height="92" rx="8" fill="#ffffff" stroke="${color}" stroke-width="2"></rect>
            <circle cx="20" cy="22" r="7" fill="${color}"></circle>
            <text x="36" y="27" font-size="15" font-weight="800" fill="#202722">${esc(title)}</text>
            <text x="14" y="58" font-size="13" fill="#626d66">${esc(subtitle)}</text>
          </g>
        `).join("")}
      `;
    }

    function renderRunBars() {
      const severityCounts = data.issues.counts.by_severity || {};
      const artifactCounts = data.artifacts.counts || {};
      const severityItems = ["P0", "P1", "P2"].map((name) => [name, severityCounts[name] || 0]);
      const artifactItems = Object.entries(artifactCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
      const bars = [
        `<span class="label">Open issues by severity</span>`,
        renderBars(severityItems, "p"),
        `<span class="label">Artifacts by type</span>`,
        renderBars(artifactItems.length ? artifactItems : [["no files", 0]], "artifact"),
      ];
      document.getElementById("run-bars").innerHTML = bars.join("");
    }

    function renderBars(items, kind) {
      const maxValue = Math.max(1, ...items.map(([, value]) => Number(value) || 0));
      return `<div class="bar-list">${items.map(([name, value]) => {
        const width = Math.max(2, Math.round(((Number(value) || 0) / maxValue) * 100));
        const cls = kind === "p" ? String(name).toLowerCase() : "";
        return `
          <div class="bar-row">
            <span>${esc(name)}</span>
            <div class="bar-track"><div class="bar-fill ${cls}" style="width:${width}%"></div></div>
            <strong>${esc(value)}</strong>
          </div>
        `;
      }).join("")}</div>`;
    }

    function eventColor(step) {
      const action = step.raw?.action_type || "";
      if (action.includes("issue") || action.includes("review")) return "#ad2f24";
      if (action.includes("artifact") || action.includes("checkpoint")) return "#a86617";
      if (action.includes("claim") || action.includes("evidence") || action.includes("decision")) return "#6552b8";
      if (action.includes("section") || action.includes("paper")) return "#206b55";
      return "#245f9f";
    }

    function renderEventDots() {
      const svg = document.getElementById("event-dots");
      const steps = data.story.lifecycle;
      const width = 860;
      const height = 240;
      svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
      const pad = 44;
      const usable = width - pad * 2;
      svg.innerHTML = `
        <line x1="${pad}" y1="104" x2="${width - pad}" y2="104" stroke="#c7d0ca" stroke-width="3"></line>
        ${steps.map((step, index) => {
          const x = steps.length === 1 ? width / 2 : pad + (index / (steps.length - 1)) * usable;
          const y = 104 + (index % 2 === 0 ? -26 : 26);
          return `
            <line x1="${x}" y1="104" x2="${x}" y2="${y}" stroke="#c7d0ca" stroke-width="1.5"></line>
            <circle cx="${x}" cy="${y}" r="9" fill="${eventColor(step)}"></circle>
            <text x="${x}" y="${y + (index % 2 === 0 ? -16 : 26)}" text-anchor="middle" font-size="11" fill="#3f4b45">${esc(step.offset)}</text>
          `;
        }).join("")}
        <text x="44" y="190" font-size="12" fill="#626d66">green: setup/drafting</text>
        <text x="210" y="190" font-size="12" fill="#626d66">violet: claim/reason</text>
        <text x="382" y="190" font-size="12" fill="#626d66">red: review/issue</text>
        <text x="540" y="190" font-size="12" fill="#626d66">amber: files/checkpoints</text>
        <text x="44" y="216" font-size="12" fill="#626d66">blue: other actions</text>
      `;
    }

    const objectGraphState = {
      nodes: [],
      edges: [],
      nodeById: new Map(),
      adjacency: new Map(),
      seedIds: [],
      expandedIds: new Set(),
      selectedId: null,
    };

    function initObjectGraph() {
      const graph = data.graph || {};
      objectGraphState.nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
      objectGraphState.edges = Array.isArray(graph.edges) ? graph.edges : [];
      objectGraphState.nodeById = new Map(objectGraphState.nodes.map((node) => [node.id, node]));
      objectGraphState.adjacency = new Map(objectGraphState.nodes.map((node) => [node.id, []]));
      objectGraphState.edges.forEach((edge) => {
        if (!objectGraphState.nodeById.has(edge.source) || !objectGraphState.nodeById.has(edge.target)) return;
        objectGraphState.adjacency.get(edge.source)?.push({ edge, neighborId: edge.target, direction: "out" });
        objectGraphState.adjacency.get(edge.target)?.push({ edge, neighborId: edge.source, direction: "in" });
      });
      objectGraphState.seedIds = chooseInitialGraphNodes();
      objectGraphState.selectedId = objectGraphState.seedIds[0] || objectGraphState.nodes[0]?.id || null;

      document.getElementById("graph-expand-all")?.addEventListener("click", () => {
        objectGraphState.expandedIds = new Set(objectGraphState.nodes.map((node) => node.id));
        renderObjectGraph();
      });
      document.getElementById("graph-reset")?.addEventListener("click", () => {
        objectGraphState.expandedIds = new Set();
        objectGraphState.selectedId = objectGraphState.seedIds[0] || objectGraphState.nodes[0]?.id || null;
        renderObjectGraph();
      });

      renderObjectGraph();
    }

    function chooseInitialGraphNodes() {
      const nodes = objectGraphState.nodes;
      const byType = (type) => nodes.filter((node) => node.type === type);
      const severityRank = { P0: 0, P1: 1, P2: 2 };
      const openIssues = byType("Issue")
        .filter((node) => (node.record?.issue_status || node.status) !== "resolved")
        .sort((a, b) => (severityRank[a.record?.severity] ?? 9) - (severityRank[b.record?.severity] ?? 9))
        .slice(0, 3)
        .map((node) => node.id);
      const issueTargets = openIssues.flatMap((issueId) =>
        (objectGraphState.adjacency.get(issueId) || [])
          .map((entry) => objectGraphState.nodeById.get(entry.neighborId))
          .filter((node) => ["Claim", "Evidence", "ReasoningStep", "Method", "Dataset", "Experiment", "Metric", "Result", "Citation", "Section"].includes(node?.type))
          .map((node) => node.id)
      );
      const preferred = [
        ...openIssues,
        ...issueTargets,
        ...byType("Decision").slice(0, 1).map((node) => node.id),
        ...byType("Review").slice(0, 1).map((node) => node.id),
        ...byType("Artifact").slice(0, 2).map((node) => node.id),
        ...byType("Section").slice(0, 1).map((node) => node.id),
        ...byType("Extraction").slice(0, 1).map((node) => node.id),
      ];
      const seedIds = enrichInitialGraphNodes(uniqueIds(preferred), 7);
      if (seedIds.length >= 4) return seedIds.slice(0, 7);
      const fallback = [
        ...nodes.filter((node) => node.type !== "Paper").map((node) => node.id),
        ...byType("Paper").map((node) => node.id),
      ];
      return enrichInitialGraphNodes(uniqueIds([...seedIds, ...fallback]), Math.min(7, nodes.length));
    }

    function enrichInitialGraphNodes(seedIds, limit) {
      const enriched = uniqueIds(seedIds).slice(0, limit);
      const addNeighbor = (neighborId) => {
        if (!neighborId || enriched.includes(neighborId) || enriched.length >= limit) return;
        enriched.push(neighborId);
      };
      seedIds.forEach((nodeId) => {
        if (enriched.length >= limit) return;
        sortedGraphNeighbors(nodeId)
          .filter((entry) => objectGraphState.nodeById.get(entry.neighborId)?.type !== "Paper")
          .slice(0, 2)
          .forEach((entry) => addNeighbor(entry.neighborId));
      });
      if (countVisibleEdges(enriched) === 0) {
        for (const nodeId of enriched.slice()) {
          const neighbors = sortedGraphNeighbors(nodeId).map((entry) => entry.neighborId);
          const neighbor =
            neighbors.find((neighborId) => objectGraphState.nodeById.get(neighborId)?.type !== "Paper") ||
            neighbors.find((neighborId) => objectGraphState.nodeById.has(neighborId));
          if (neighbor && !enriched.includes(neighbor)) {
            if (enriched.length >= limit) enriched.pop();
            enriched.push(neighbor);
            break;
          }
        }
      }
      return enriched.slice(0, limit);
    }

    function sortedGraphNeighbors(nodeId) {
      const rank = { Claim: 0, Evidence: 1, ReasoningStep: 2, Result: 3, Method: 4, Experiment: 5, Dataset: 6, Metric: 7, Citation: 8, Review: 9, Issue: 10, Decision: 11, Section: 12, Artifact: 13, Extraction: 14, Paper: 20 };
      return (objectGraphState.adjacency.get(nodeId) || [])
        .slice()
        .sort((a, b) => {
          const aNode = objectGraphState.nodeById.get(a.neighborId) || {};
          const bNode = objectGraphState.nodeById.get(b.neighborId) || {};
          return (rank[aNode.type] ?? 8) - (rank[bNode.type] ?? 8) || String(aNode.label).localeCompare(String(bNode.label));
        });
    }

    function countVisibleEdges(nodeIds) {
      const visible = new Set(nodeIds);
      return objectGraphState.edges.filter((edge) => visible.has(edge.source) && visible.has(edge.target)).length;
    }

    function uniqueIds(ids) {
      const seen = new Set();
      return ids.filter((id) => {
        if (!id || seen.has(id)) return false;
        seen.add(id);
        return true;
      });
    }

    function currentVisibleNodeIds() {
      const visible = new Set(objectGraphState.seedIds);
      objectGraphState.expandedIds.forEach((id) => {
        visible.add(id);
        expansionGraphNeighbors(id).forEach((entry) => visible.add(entry.neighborId));
      });
      if (objectGraphState.selectedId) visible.add(objectGraphState.selectedId);
      return visible;
    }

    function expansionGraphNeighbors(nodeId) {
      const node = objectGraphState.nodeById.get(nodeId);
      const neighbors = sortedGraphNeighbors(nodeId);
      if (!node || neighbors.length <= 12) return neighbors;
      const limit = node.type === "Paper" ? 10 : 18;
      return neighbors.slice(0, limit);
    }

    function toggleGraphNode(nodeId) {
      objectGraphState.selectedId = nodeId;
      if (objectGraphState.expandedIds.has(nodeId)) {
        objectGraphState.expandedIds.delete(nodeId);
      } else {
        objectGraphState.expandedIds.add(nodeId);
      }
      renderObjectGraph();
    }

    function focusGraphNode(nodeId) {
      const previousSelected = objectGraphState.selectedId;
      if (previousSelected) objectGraphState.expandedIds.add(previousSelected);
      objectGraphState.selectedId = nodeId;
      renderObjectGraph();
    }

    function renderObjectGraph() {
      const svg = document.getElementById("object-link-graph");
      if (!svg) return;
      if (!objectGraphState.nodes.length) {
        svg.setAttribute("viewBox", "0 0 760 220");
        svg.innerHTML = `<text x="24" y="44" font-size="15" fill="#626d66">No objects recorded yet.</text>`;
        return;
      }

      const visibleIds = currentVisibleNodeIds();
      const visibleNodes = objectGraphState.nodes.filter((node) => visibleIds.has(node.id));
      const visibleEdges = objectGraphState.edges.filter((edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target));
      const layout = graphLayout(visibleNodes);
      svg.setAttribute("viewBox", `0 0 ${layout.width} ${layout.height}`);
      document.getElementById("graph-summary").textContent =
        `${objectGraphState.nodes.length} objects and ${objectGraphState.edges.length} links available`;
      document.getElementById("graph-visible-count").textContent =
        `${visibleNodes.length}/${objectGraphState.nodes.length} objects visible`;
      document.getElementById("graph-note").textContent =
        "Seed set: paper, highest-priority issues, linked claims, decisions, and file artifacts.";

      const edgeMarkup = visibleEdges.map((edge) => renderGraphEdge(edge, layout.positions)).join("");
      const nodeMarkup = visibleNodes.map((node) => renderGraphNode(node, layout.positions.get(node.id))).join("");
      svg.innerHTML = `
        <defs>
          <marker id="object-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L8,4 L0,8 Z" fill="#8b9690"></path>
          </marker>
        </defs>
        ${edgeMarkup}
        ${nodeMarkup}
      `;

      svg.querySelectorAll(".graph-node").forEach((nodeEl) => {
        nodeEl.addEventListener("click", () => toggleGraphNode(nodeEl.dataset.nodeId));
        nodeEl.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleGraphNode(nodeEl.dataset.nodeId);
          }
        });
      });

      renderGraphDetail(visibleEdges);
    }

    function graphLayout(visibleNodes) {
      const typeOrder = ["Paper", "Section", "Claim", "Evidence", "ReasoningStep", "Method", "Dataset", "Experiment", "Metric", "Result", "Citation", "Review", "Issue", "Decision", "Venue", "Artifact", "Extraction"];
      const typeRank = (type) => {
        const index = typeOrder.indexOf(type);
        return index === -1 ? typeOrder.length : index;
      };
      const groups = new Map();
      visibleNodes
        .slice()
        .sort((a, b) => typeRank(a.type) - typeRank(b.type) || String(a.label).localeCompare(String(b.label)))
        .forEach((node) => {
          const type = typeOrder.includes(node.type) ? node.type : "Other";
          if (!groups.has(type)) groups.set(type, []);
          groups.get(type).push(node);
        });
      const columns = Array.from(groups.keys()).sort((a, b) => typeRank(a) - typeRank(b));
      const margin = 28;
      const columnWidth = 190;
      const rowHeight = 118;
      const nodeWidth = 160;
      const nodeHeight = 82;
      const maxRows = Math.max(1, ...columns.map((type) => groups.get(type).length));
      const width = Math.max(900, margin * 2 + columns.length * columnWidth);
      const height = Math.max(330, margin * 2 + maxRows * rowHeight);
      const positions = new Map();
      columns.forEach((type, columnIndex) => {
        groups.get(type).forEach((node, rowIndex) => {
          positions.set(node.id, {
            x: margin + columnIndex * columnWidth,
            y: margin + rowIndex * rowHeight,
            width: nodeWidth,
            height: nodeHeight,
          });
        });
      });
      return { width, height, positions };
    }

    function renderGraphEdge(edge, positions) {
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return "";
      const sx = source.x + source.width;
      const sy = source.y + source.height / 2;
      const tx = target.x;
      const ty = target.y + target.height / 2;
      const direction = tx >= sx ? 1 : -1;
      const curve = Math.max(50, Math.abs(tx - sx) * 0.45);
      const path = `M${sx},${sy} C${sx + curve * direction},${sy} ${tx - curve * direction},${ty} ${tx},${ty}`;
      const labelX = (sx + tx) / 2;
      const labelY = (sy + ty) / 2 - 6;
      const cls = edge.source_kind === "explicit" ? "explicit" : "inferred";
      return `
        <path class="graph-edge ${cls}" d="${path}" marker-end="url(#object-arrow)"></path>
        <text class="graph-edge-label" x="${labelX}" y="${labelY}" text-anchor="middle">${esc(shorten(String(edge.label).replace(/_/g, " "), 24))}</text>
      `;
    }

    function renderGraphNode(node, position) {
      const isSeed = objectGraphState.seedIds.includes(node.id);
      const isExpanded = objectGraphState.expandedIds.has(node.id);
      const isSelected = objectGraphState.selectedId === node.id;
      const classes = ["graph-node", isSeed ? "is-seed" : "", isExpanded ? "is-expanded" : "", isSelected ? "is-selected" : ""]
        .filter(Boolean)
        .join(" ");
      const neighborCount = (objectGraphState.adjacency.get(node.id) || []).length;
      return `
        <g class="${classes}" data-node-id="${esc(node.id)}" tabindex="0" role="button"
          aria-label="${esc(`${node.type} ${node.label || node.id}, ${neighborCount} links`)}"
          transform="translate(${position.x}, ${position.y})">
          <rect width="${position.width}" height="${position.height}" rx="8"></rect>
          <text class="graph-node-type" x="12" y="20">${esc(node.type || "Object")}</text>
          <text class="graph-node-label" x="12" y="43">${esc(shorten(node.label || node.id, 22))}</text>
          <text class="graph-node-id" x="12" y="64">${esc(shorten(node.id, 26))}</text>
        </g>
      `;
    }

    function renderGraphDetail(visibleEdges) {
      const selected = objectGraphState.nodeById.get(objectGraphState.selectedId) || objectGraphState.nodes[0];
      const detail = document.getElementById("object-graph-detail");
      const links = document.getElementById("visible-links");
      if (!selected || !detail || !links) return;
      const neighbors = (objectGraphState.adjacency.get(selected.id) || [])
        .map((entry) => ({ ...entry, node: objectGraphState.nodeById.get(entry.neighborId) }))
        .filter((entry) => entry.node);
      const history = Array.isArray(selected.event_history) ? selected.event_history : [];
      detail.innerHTML = `
        <div class="chip-row">${chip(selected.type || "Object")}${chip(selected.status || selected.record?.status || "active")}</div>
        <h3>${esc(selected.label || selected.id)}</h3>
        <p>${esc(selected.summary || selected.id)}</p>
        <span class="label">Object ID</span>
        <p>${esc(selected.id)}</p>
        <span class="label">Event history</span>
        <div class="event-history-list">
          ${history.map((event) => `
            <div class="event-history-row">
              <code>${esc(event.offset ? `#${event.offset}` : event.event_id || "event")}</code>
              <div>
                <strong>${esc(event.action_type || "event.recorded")}</strong>
                <span>${esc([event.function, event.actor, event.approval_status].filter(Boolean).join(" / ") || "recorded")}</span>
              </div>
            </div>
          `).join("") || `<p>No direct events recorded for this object.</p>`}
        </div>
        <span class="label">Connected objects</span>
        <div class="neighbor-list">
          ${neighbors.map((entry) => `
            <button class="neighbor-button" type="button" data-neighbor-id="${esc(entry.node.id)}">
              ${esc(entry.direction === "out" ? "to" : "from")} ${esc(entry.node.type)}: ${esc(shorten(entry.node.label || entry.node.id, 34))}
            </button>
          `).join("") || `<p>No object links recorded for this node.</p>`}
        </div>
      `;
      detail.querySelectorAll(".neighbor-button").forEach((button) => {
        button.addEventListener("click", () => focusGraphNode(button.dataset.neighborId));
      });
      links.innerHTML = `
        <h3>Visible Links</h3>
        <div class="link-list">
          ${visibleEdges.map((edge) => `
            <div class="link-row ${edge.source_kind === "explicit" ? "explicit" : ""}">
              <p><strong>${esc(shorten(edge.source, 24))}</strong> -> <strong>${esc(shorten(edge.target, 24))}</strong></p>
              <p>${esc(String(edge.label).replace(/_/g, " "))} (${esc(edge.source_kind)})</p>
            </div>
          `).join("") || `<p>No links are visible in the current graph view.</p>`}
        </div>
      `;
    }

    function renderLifecycle() {
      document.getElementById("lifecycle").innerHTML = data.story.lifecycle.map((step) => `
        <article class="step">
          <div><span class="offset">${esc(step.offset)}</span></div>
          <div>
            <h3>${esc(step.title)}</h3>
            <p>${esc(step.body)}</p>
            <span class="label">Why it matters</span>
            <p>${esc(step.why)}</p>
            <div class="chip-row">${chip(step.actor)}</div>
            <details>
              <summary>Show technical details</summary>
              <pre>${esc(JSON.stringify(step.raw, null, 2))}</pre>
            </details>
          </div>
        </article>
      `).join("");
    }

    function renderActionInventory() {
      const inventory = data.action_inventory || {};
      const groups = Array.isArray(inventory.groups) ? inventory.groups : [];
      const counts = inventory.counts || {};
      const summary = document.getElementById("action-inventory-summary");
      const host = document.getElementById("action-inventory");
      if (!summary || !host) return;
      summary.textContent =
        `${counts.action_types || 0} action types, ${counts.functions || 0} functions, ${counts.events || 0} events.`;
      if (!groups.length) {
        host.innerHTML = `<p>No action types recorded yet.</p>`;
        return;
      }
      host.innerHTML = groups.map((group) => `
        <details class="action-group">
          <summary>
            <span class="action-group-title">${esc(group.object_type)}</span>
            <span class="action-group-meta">${esc(group.action_type_count)} action types / ${esc(group.event_count)} events</span>
          </summary>
          ${group.actions.map((action) => {
            const functionChips = (action.actual_functions || [])
              .map((fn) => chip(`${fn.function} x${fn.count}`))
              .join("");
            const allowed = (action.allowed_functions || []).join(", ") || "not declared";
            return `
              <article class="action-row">
                <div class="action-title">
                  <code>${esc(action.action_type)}</code>
                  ${chip(action.approval_required ? "approval required" : "no approval")}
                  ${chip(`${action.event_count} events`)}
                </div>
                ${action.description ? `<p>${esc(action.description)}</p>` : ""}
                <p class="function-line"><strong>Default function</strong> <code>${esc(action.default_function)}</code>${action.default_function_description ? `: ${esc(action.default_function_description)}` : ""}</p>
                <p class="function-line"><strong>Allowed functions</strong> ${esc(allowed)}</p>
                <div class="chip-row">${functionChips || chip("no function recorded")}</div>
                <details>
                  <summary>Show event offsets</summary>
                  <div class="action-events">
                    ${(action.events || []).map((event) => `
                      <div class="action-event">
                        <code>${esc(event.event_id || ("offset " + event.offset))}</code>
                        offset ${esc(event.offset)} / ${esc(event.object_id || event.object_type || "unknown object")} / ${esc(event.actor || "unknown actor")} / ${esc(event.function || "unknown function")}
                      </div>
                    `).join("") || `<div class="action-event">No events recorded for this action type.</div>`}
                  </div>
                </details>
              </article>
            `;
          }).join("")}
        </details>
      `).join("");
    }

    function renderIssues() {
      const active = data.story.issue_cards.filter((issue) => !issue.is_history);
      const history = data.story.issue_cards.filter((issue) => issue.is_history);
      const renderIssueCard = (issue, extraClass = "") => `
        <article class="issue ${extraClass}">
          <div class="chip-row">
            ${chip(issue.severity, severityClass(issue.severity))}
            ${issue.previous_severity && issue.previous_severity !== issue.severity ? chip(`former ${issue.previous_severity}`, "history") : ""}
            ${chip(issue.status, issue.status)}
          </div>
          <h3>${esc(issue.problem)}</h3>
          ${issue.history_note ? `<span class="label">History note</span><p>${esc(issue.history_note)}</p>` : ""}
          <span class="label">Why it matters</span>
          <p>${esc(issue.why_it_matters)}</p>
          <span class="label">Evidence</span>
          <p>${esc(issue.evidence)}</p>
          <span class="label">Suggested next step</span>
          <p>${esc(issue.next_step)}</p>
          <span class="label">Affected object</span>
          <p>${esc(issue.affected)}</p>
          <details>
            <summary>Show technical details</summary>
            <pre>${esc(JSON.stringify(issue.debug, null, 2))}</pre>
          </details>
        </article>
      `;
      document.getElementById("issues").innerHTML = `
        <div>
          <div class="issue-section-head">
            <h3>Needs Attention</h3>
            <p>${active.length} current issue${active.length === 1 ? "" : "s"}</p>
          </div>
          <div class="issue-grid">
            ${active.map((issue) => renderIssueCard(issue)).join("") || `<article class="issue"><h3>Nothing needs attention right now</h3><p>Resolved issues are kept below as project history.</p></article>`}
          </div>
        </div>
        <details class="history-details">
          <summary>Resolved / History (${history.length})</summary>
          <div class="issue-grid">
            ${history.map((issue) => renderIssueCard(issue, "is-history")).join("") || `<article class="issue is-history"><h3>No resolved issues yet</h3><p>Closed issues will appear here after they are resolved.</p></article>`}
          </div>
        </details>
      `;
    }

    function renderResearchIntegrity() {
      const host = document.getElementById("research-integrity");
      if (!host) return;
      const literature = data.literature || {};
      const literatureCounts = literature.counts || {};
      const coverage = literature.coverage || {};
      const requiredRoles = coverage.required_roles || [];
      const coveredRoles = coverage.covered_roles || [];
      const documentedRoles = coverage.documented_gap_roles || [];
      const provenanceCounts = (data.provenance || {}).counts || {};
      const executionCounts = (data.expert_executions || {}).counts || {};
      const coveredOrAccounted = new Set([...coveredRoles, ...documentedRoles]).size;
      const executionTotal = executionCounts.total || 0;
      const verifiedExecutions = executionCounts.isolation_verified || 0;
      const integrityItems = [
        {
          label: "Verified literature",
          value: literatureCounts.verified || 0,
          detail: `${literatureCounts.tentative || 0} tentative / ${literatureCounts.external_works || 0} external works`,
          status: literatureCounts.verified ? "good" : "warn",
        },
        {
          label: "Positioning coverage",
          value: `${coveredOrAccounted}/${requiredRoles.length || 4}`,
          detail: coverage.coverage_status === "complete_or_accounted_for" ? "Complete or gaps documented" : "Unaccounted roles remain",
          status: coverage.coverage_status === "complete_or_accounted_for" ? "good" : "fail",
        },
        {
          label: "Auditable evidence",
          value: provenanceCounts.complete_chains || 0,
          detail: `${provenanceCounts.source_span_links || 0} SourceSpan links / ${provenanceCounts.broken_links || 0} broken`,
          status: provenanceCounts.broken_links ? "fail" : (provenanceCounts.complete_chains ? "good" : "warn"),
        },
        {
          label: "Verified isolation",
          value: `${verifiedExecutions}/${executionTotal}`,
          detail: executionTotal ? `${executionCounts.isolation_unverified || 0} fallback or unverified` : "No execution manifests recorded",
          status: executionTotal && verifiedExecutions === executionTotal ? "good" : "warn",
        },
      ];
      host.innerHTML = `
        <div class="integrity-head">
          <div>
            <span class="eyebrow">Research Integrity</span>
            <h3>What the workflow can prove</h3>
          </div>
          ${chip(coverage.coverage_status === "complete_or_accounted_for" ? "coverage accounted for" : "coverage incomplete", coverage.coverage_status === "complete_or_accounted_for" ? "good" : "fail")}
        </div>
        <div class="integrity-grid">
          ${integrityItems.map((item) => `
            <div class="integrity-stat ${item.status}">
              <span>${esc(item.label)}</span>
              <strong class="state ${item.status}">${esc(item.value)}</strong>
              <p>${esc(item.detail)}</p>
            </div>
          `).join("")}
        </div>
      `;
    }

    function renderLiterature() {
      const host = document.getElementById("literature-overview");
      if (!host) return;
      const literature = data.literature || {};
      const citations = literature.citations || [];
      const counts = literature.counts || {};
      const coverage = literature.coverage || {};
      const requiredRoles = coverage.required_roles || [];
      const coveredRoles = new Set(coverage.covered_roles || []);
      const documentedRoles = new Set(coverage.documented_gap_roles || []);
      const roleLabel = (role) => String(role || "unknown").replace(/_/g, " ");
      const qualityCounts = literature.metadata_quality_counts || {};
      const qualitySummary = Object.entries(qualityCounts)
        .map(([quality, count]) => chip(`${quality}: ${count}`))
        .join("");
      host.innerHTML = `
        <div class="literature-summary">
          <div class="chip-row">
            ${chip(`${counts.verified || 0} verified`, counts.verified ? "good" : "warn")}
            ${chip(`${counts.tentative || 0} tentative`, counts.tentative ? "warn" : "")}
            ${chip(`${counts.metadata_artifacts || 0} metadata artifacts`)}
          </div>
          <div class="chip-row">${qualitySummary || chip("metadata quality not recorded", "warn")}</div>
        </div>
        <div class="coverage-grid">
          ${requiredRoles.map((role) => {
            const isCovered = coveredRoles.has(role);
            const isDocumented = documentedRoles.has(role);
            const stateClass = isCovered ? "covered" : (isDocumented ? "documented" : "missing");
            const stateLabel = isCovered ? "Verified coverage" : (isDocumented ? "Gap documented" : "Missing");
            const matches = citations.filter((citation) => citation.positioning_role === role && citation.verification_status === "verified");
            return `
              <article class="coverage-role ${stateClass}">
                <span>${esc(roleLabel(role))}</span>
                <strong>${esc(stateLabel)}</strong>
                <p>${matches.length ? esc(matches.map((citation) => citation.title).join("; ")) : "No verified citation assigned."}</p>
              </article>
            `;
          }).join("") || `<p>No required positioning roles are configured.</p>`}
        </div>
        <div class="table-wrap">
          <table class="literature-table">
            <thead>
              <tr><th>Work</th><th>Position</th><th>Verification</th><th>Metadata</th><th>Used by</th></tr>
            </thead>
            <tbody>
              ${citations.map((citation) => `
                <tr>
                  <td><strong class="work-title">${esc(citation.title)}</strong><span class="subline">${esc([citation.year, citation.citation_id].filter(Boolean).join(" / "))}</span></td>
                  <td>${chip(roleLabel(citation.positioning_role))}</td>
                  <td>${chip(citation.verification_status, citation.verification_status === "verified" ? "good" : "warn")}</td>
                  <td><strong>${esc(citation.metadata_quality)}</strong><span class="subline">${esc(citation.source_provider)} / ${esc((citation.metadata_artifact_ids || []).length)} artifacts</span></td>
                  <td>${(citation.targets || []).map((target) => `<code>${esc(target.object_type)}:${esc(target.object_id)}</code>`).join("<br>") || "Not linked to a claim or evidence"}</td>
                </tr>
              `).join("") || `<tr><td colspan="5">No citations recorded yet.</td></tr>`}
            </tbody>
          </table>
        </div>
      `;
    }

    function renderProvenanceChains() {
      const host = document.getElementById("provenance-chains");
      if (!host) return;
      const provenance = data.provenance || {};
      const chains = provenance.evidence_source_chains || [];
      const broken = provenance.broken_links || [];
      host.innerHTML = `
        <div class="provenance-list">
          ${chains.map((chain) => `
            <article class="provenance-chain ${chain.complete ? "complete" : "broken"}">
              <div class="chip-row">${chip(chain.complete ? "auditable" : "incomplete", chain.complete ? "good" : "fail")}</div>
              <h3>${esc(chain.summary)}</h3>
              <p><code>${esc(chain.evidence_id)}</code></p>
              ${(chain.spans || []).map((span) => `
                <div class="chain-path">
                  <div class="chain-node"><strong>Evidence</strong><span>${esc(chain.evidence_id)}</span></div>
                  <div class="chain-arrow" aria-hidden="true">&#8594;</div>
                  <div class="chain-node is-span"><strong>SourceSpan</strong><span>${esc(span.source_span_id)} / ${esc(span.text_excerpt)}</span></div>
                  <div class="chain-arrow" aria-hidden="true">&#8594;</div>
                  <div class="chain-node is-artifact"><strong>${esc(span.artifact_type || "Artifact")}</strong><span>${esc(span.artifact_id || "missing artifact")} / ${esc(span.artifact_path || "No artifact path recorded")}</span></div>
                </div>
              `).join("") || `<p>No SourceSpan links recorded for this evidence.</p>`}
            </article>
          `).join("") || `<article class="provenance-chain"><h3>No source chains recorded yet</h3><p>Evidence anchored through SourceSpan objects will appear here.</p></article>`}
        </div>
        ${broken.length ? `<details><summary>${esc(broken.length)} broken provenance link${broken.length === 1 ? "" : "s"}</summary><pre>${esc(JSON.stringify(broken, null, 2))}</pre></details>` : ""}
      `;
    }

    function renderExpertExecutions() {
      const host = document.getElementById("expert-execution");
      if (!host) return;
      const expertData = data.expert_executions || {};
      const executions = expertData.executions || [];
      const counts = expertData.counts || {};
      host.innerHTML = `
        <div class="execution-head">
          <div>
            <span class="eyebrow">Execution Truth</span>
            <h3>Requested mode versus actual backend</h3>
          </div>
          <div class="chip-row">${chip(`${counts.isolation_verified || 0}/${counts.total || 0} isolation verified`, counts.total && counts.isolation_verified === counts.total ? "good" : "warn")}</div>
        </div>
        <div class="execution-list">
          ${executions.map((execution) => `
            <article class="execution-row">
              <div><strong>${esc(execution.expert_name)}</strong><span>${esc(execution.invocation_id)}</span></div>
              <div><strong>${esc(execution.requested_mode)}</strong><span>Requested mode</span></div>
              <div><strong class="state ${execution.isolation_verified ? "good" : "warn"}">${esc(execution.backend)}</strong><span>${execution.isolation_verified ? "Isolation verified" : "Isolation not verified"}</span></div>
              <div><strong>Execution record</strong><span>${esc(execution.reason || "No execution reason recorded.")}</span><span>${execution.report_exists ? "report.md present" : "report.md missing"} / ${execution.proposals_exist ? "proposals.yml present" : "proposals.yml missing"}</span></div>
            </article>
          `).join("") || `<article class="execution-row empty"><p>No expert runner manifests recorded yet.</p></article>`}
        </div>
      `;
    }

    function renderTrails() {
      document.getElementById("trails").innerHTML = data.story.evidence_trails.map((trail) => `
        <article class="trail">
          <h3>${esc(trail.title)}</h3>
          ${trail.nodes.map((node) => `
            <div class="trail-node">
              <strong>${esc(node.label)}</strong>
              <p>${esc(node.text)}</p>
            </div>
          `).join("")}
        </article>
      `).join("") || `<article class="trail"><h3>No reason trail yet</h3><p>Add claims, review findings, or decisions to make the explanation visible.</p></article>`;
    }

    function renderArtifacts() {
      document.getElementById("artifacts").innerHTML = data.story.artifact_cards.map((artifact) => `
        <article class="artifact">
          <h3>${esc(artifact.title)}</h3>
          <p>${esc(artifact.body)}</p>
          <p class="path">${esc(artifact.path)}</p>
          <span class="label">Provenance</span>
          <p>${esc(artifact.provenance)}</p>
          <details>
            <summary>Show technical details</summary>
            <pre>${esc(JSON.stringify(artifact.debug, null, 2))}</pre>
          </details>
        </article>
      `).join("") || `<article class="artifact"><h3>No files recorded yet</h3><p>This project has no generated or user-provided files yet.</p></article>`;
    }

    renderHeader();
    renderMechanism();
    renderVisuals();
    initObjectGraph();
    renderLifecycle();
    renderActionInventory();
    renderIssues();
    renderResearchIntegrity();
    renderLiterature();
    renderProvenanceChains();
    renderExpertExecutions();
    renderTrails();
    renderArtifacts();
    initPageRouting();
  </script>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a static visualization for a research-paper-suite project.")
    parser.add_argument("project_dir", help="Project directory containing events/event_log.yml and state/paper.yml.")
    parser.add_argument(
        "--out-dir",
        help="Output directory. Defaults to <project_dir>/visualization.",
    )
    parser.add_argument(
        "--require-accepted",
        action="store_true",
        help="Refuse to export unless handoff_manifest.yml says the project is accepted or accepted_with_warnings.",
    )
    args = parser.parse_args()

    project_dir = normalize_project_dir(args.project_dir)
    acceptance = build_acceptance_data(project_dir)
    if args.require_accepted and acceptance.get("status") not in ACCEPTED_HANDOFF_STATUSES:
        print(
            "Project visualization export blocked: "
            f"handoff status is {acceptance.get('status')}. "
            "Run scripts/handoff_project.py first and fix acceptance errors before formal export."
        )
        return 2
    out_dir = Path(args.out_dir) if args.out_dir else project_dir / "visualization"
    if not out_dir.is_absolute():
        out_dir = (Path.cwd() / out_dir).resolve()

    data = build_project_data(project_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "events.json", data["events"])
    write_json(out_dir / "objects.json", data["objects"])
    write_json(out_dir / "graph.json", data["graph"])
    write_json(out_dir / "story.json", data["story"])
    write_json(out_dir / "literature.json", data["literature"])
    write_json(out_dir / "provenance.json", data["provenance"])
    write_json(out_dir / "expert_executions.json", data["expert_executions"])
    write_json(out_dir / "visualization.json", data)
    (out_dir / "index.html").write_text(render_html(data), encoding="utf-8")

    print(f"visualization: {out_dir / 'index.html'}")
    print(f"events: {out_dir / 'events.json'}")
    print(f"objects: {out_dir / 'objects.json'}")
    print(f"graph: {out_dir / 'graph.json'}")
    print(f"story: {out_dir / 'story.json'}")
    print(f"literature: {out_dir / 'literature.json'}")
    print(f"provenance: {out_dir / 'provenance.json'}")
    print(f"expert_executions: {out_dir / 'expert_executions.json'}")
    print(f"visualization_data: {out_dir / 'visualization.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
