from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from event_log import append_event, load_registry, make_event, project_state, read_events, validate_event_log, write_yaml


def slugify(value: str, fallback: str = "paper") -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value or fallback


def build_paper_payload(args: argparse.Namespace) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "paper_id": args.paper_id,
        "stage": args.stage,
    }
    if args.title:
        payload["title"] = args.title
    if args.field:
        payload["field"] = args.field
    if args.main_claim:
        payload["main_claim"] = args.main_claim
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an empty paper project backed by event_log.yml and paper.yml.")
    parser.add_argument("project_dir")
    parser.add_argument("--paper-id")
    parser.add_argument("--title", default="Untitled Paper")
    parser.add_argument("--field")
    parser.add_argument("--main-claim")
    parser.add_argument(
        "--stage",
        default="idea",
        choices=["idea", "positioning", "drafting", "checking", "reviewing", "rebuttal", "assembly", "submission"],
    )
    parser.add_argument("--reset", action="store_true", help="Replace an existing event_log.yml.")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    (project_dir / "proposals").mkdir(parents=True, exist_ok=True)
    log_path = project_dir / "events" / "event_log.yml"
    state_path = project_dir / "state" / "paper.yml"

    if args.paper_id is None:
        args.paper_id = f"P-{slugify(args.title or project_dir.name)}"

    if log_path.exists():
        if not args.reset:
            raise ValueError(f"{log_path} already exists; pass --reset to replace it")
        log_path.unlink()

    registry = load_registry()
    event = make_event(
        offset=1,
        actor="user",
        function="create_object",
        action_type="paper.created",
        object_type="Paper",
        object_id=args.paper_id,
        payload=build_paper_payload(args),
    )
    append_event(log_path, event, registry)
    events = read_events(log_path)
    errors = validate_event_log(events, registry)
    if errors:
        raise ValueError("event log validation failed:\n" + "\n".join(errors))
    write_yaml(state_path, project_state(events, log_path.parent))

    print(f"project: {project_dir}")
    print(f"paper_id: {args.paper_id}")
    print(f"event log: {log_path}")
    print(f"state: {state_path}")
    print("events: 1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
