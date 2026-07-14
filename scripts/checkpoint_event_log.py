from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path
from typing import Any

from event_log import (
    ROOT,
    append_event,
    load_registry,
    make_event,
    project_state,
    read_events,
    validate_event_log,
    write_events,
    write_yaml,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def workspace_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved)


def project_paths(project_dir: Path) -> dict[str, Path]:
    project_dir = project_dir.resolve()
    return {
        "project": project_dir,
        "active_log": project_dir / "events" / "event_log.yml",
        "state": project_dir / "state" / "paper.yml",
        "checkpoints": project_dir / "state" / "checkpoints",
        "archive": project_dir / "events" / "archive",
    }


def next_epoch(checkpoint_dir: Path) -> int:
    epochs = []
    for path in checkpoint_dir.glob("checkpoint_*.yml"):
        stem = path.stem.replace("checkpoint_", "")
        if stem.isdigit():
            epochs.append(int(stem))
    return max(epochs, default=0) + 1


def paper_id_from_state(state: dict[str, Any]) -> str:
    papers = state.get("objects", {}).get("Paper", {})
    if not papers:
        raise ValueError("cannot infer paper_id: state contains no Paper object")
    return sorted(papers)[0]


def checkpoint_event(
    *,
    epoch: int,
    paper_id: str,
    checkpoint_path: Path,
    archive_path: Path,
    source_log_path: Path,
    source_log_hash: str,
    source_event_count: int,
    approved_by: str,
    summary: str,
) -> dict[str, Any]:
    checkpoint_id = f"checkpoint_{epoch:04d}"
    artifact_id = f"A-{checkpoint_id}"
    return make_event(
        offset=1,
        actor="user",
        function="create_checkpoint",
        action_type="checkpoint.created",
        object_type="Artifact",
        object_id=artifact_id,
        payload={
            "artifact_id": artifact_id,
            "paper_id": paper_id,
            "artifact_type": "state_snapshot",
            "path": workspace_path(checkpoint_path),
            "checkpoint_id": checkpoint_id,
            "source_event_log": workspace_path(source_log_path),
            "source_event_log_sha256": source_log_hash,
            "source_event_count": source_event_count,
            "archived_event_log": workspace_path(archive_path),
            "checkpoint_epoch": epoch,
            "approved_by": approved_by,
            "summary": summary,
            "produced_by": "checkpoint_event_log.py",
        },
        approval={
            "required": True,
            "approved_by": approved_by,
            "summary": summary,
        },
    )


def write_checkpoint_metadata(path: Path, event: dict[str, Any]) -> None:
    metadata_path = path.with_suffix(".meta.yml")
    write_yaml(
        metadata_path,
        {
            "checkpoint_id": event["payload"]["checkpoint_id"],
            "checkpoint_event_id": event["event_id"],
            "checkpoint_event_payload": event["payload"],
            "approval": event.get("approval", {}),
        },
    )


def create_checkpoint(args: argparse.Namespace) -> int:
    paths = project_paths(Path(args.project_dir))
    active_log = paths["active_log"]
    if not active_log.exists():
        raise ValueError(f"active event log not found: {active_log}")

    registry = load_registry()
    events = read_events(active_log)
    errors = validate_event_log(events, registry)
    if errors:
        raise ValueError("active event log validation failed:\n" + "\n".join(errors))

    state = project_state(events, active_log.parent)
    paper_id = args.paper_id or paper_id_from_state(state)
    epoch = args.epoch or next_epoch(paths["checkpoints"])
    checkpoint_path = paths["checkpoints"] / f"checkpoint_{epoch:04d}.yml"
    archive_path = paths["archive"] / f"event_log_{epoch:04d}.yml"

    if checkpoint_path.exists() or archive_path.exists():
        raise ValueError(f"checkpoint/archive epoch already exists: {epoch:04d}")

    source_log_hash = sha256_file(active_log)
    paths["checkpoints"].mkdir(parents=True, exist_ok=True)
    paths["archive"].mkdir(parents=True, exist_ok=True)
    write_yaml(checkpoint_path, state)
    shutil.copy2(active_log, archive_path)

    event = checkpoint_event(
        epoch=epoch,
        paper_id=paper_id,
        checkpoint_path=checkpoint_path,
        archive_path=archive_path,
        source_log_path=active_log,
        source_log_hash=source_log_hash,
        source_event_count=len(events),
        approved_by=args.approved_by,
        summary=args.summary,
    )
    write_checkpoint_metadata(checkpoint_path, event)
    write_events(active_log, [])
    append_event(active_log, event, registry)
    new_events = read_events(active_log)
    write_yaml(paths["state"], project_state(new_events, active_log.parent))

    print(f"checkpoint: {checkpoint_path}")
    print(f"archived event log: {archive_path}")
    print(f"new active event log: {active_log}")
    print("active events: 1")
    return 0


def list_checkpoints(args: argparse.Namespace) -> int:
    paths = project_paths(Path(args.project_dir))
    metadata_files = sorted(paths["checkpoints"].glob("checkpoint_*.meta.yml"))
    if not metadata_files:
        print("No checkpoints found.")
        return 0
    for path in metadata_files:
        from event_log import load_yaml

        metadata = load_yaml(path, {})
        payload = metadata.get("checkpoint_event_payload", {})
        print(
            f"{metadata.get('checkpoint_id')} "
            f"events={payload.get('source_event_count')} "
            f"archive={payload.get('archived_event_log')} "
            f"approved_by={payload.get('approved_by')}"
        )
    return 0


def restore_checkpoint(args: argparse.Namespace) -> int:
    paths = project_paths(Path(args.project_dir))
    registry = load_registry()
    checkpoint_id = args.checkpoint_id
    if checkpoint_id.startswith("checkpoint_"):
        epoch_text = checkpoint_id.replace("checkpoint_", "")
    else:
        epoch_text = checkpoint_id
        checkpoint_id = f"checkpoint_{int(epoch_text):04d}"
    epoch = int(epoch_text)
    checkpoint_path = paths["checkpoints"] / f"checkpoint_{epoch:04d}.yml"
    metadata_path = checkpoint_path.with_suffix(".meta.yml")
    if not checkpoint_path.exists() or not metadata_path.exists():
        raise ValueError(f"checkpoint not found: {checkpoint_id}")

    from event_log import load_yaml

    metadata = load_yaml(metadata_path, {})
    payload = dict(metadata.get("checkpoint_event_payload", {}))
    paper_id = payload.get("paper_id")
    event = make_event(
        offset=1,
        actor="user",
        function="create_checkpoint",
        action_type="checkpoint.created",
        object_type="Artifact",
        object_id=payload.get("artifact_id", f"A-{checkpoint_id}-restore"),
        payload={
            **payload,
            "summary": args.summary or f"Restored active log from {checkpoint_id}.",
            "approved_by": args.approved_by,
            "produced_by": "checkpoint_event_log.py restore",
        },
        approval={
            "required": True,
            "approved_by": args.approved_by,
            "summary": args.summary or f"Restored active log from {checkpoint_id}.",
        },
    )
    if paper_id is None:
        state = load_yaml(checkpoint_path, {"objects": {}, "links": []})
        event["payload"]["paper_id"] = paper_id_from_state(state)

    active_log = paths["active_log"]
    if active_log.exists() and read_events(active_log) and not args.force:
        raise ValueError("active event log is not empty; pass --force to replace it")
    write_events(active_log, [])
    append_event(active_log, event, registry)
    write_yaml(paths["state"], project_state(read_events(active_log), active_log.parent))
    print(f"restored checkpoint: {checkpoint_id}")
    print(f"active event log: {active_log}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Checkpoint, compact, list, and restore project event logs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a checkpoint and rotate the active event log.")
    create.add_argument("project_dir")
    create.add_argument("--approved-by", required=True)
    create.add_argument("--summary", required=True)
    create.add_argument("--paper-id")
    create.add_argument("--epoch", type=int)

    list_cmd = subparsers.add_parser("list", help="List project checkpoints.")
    list_cmd.add_argument("project_dir")

    restore = subparsers.add_parser("restore", help="Restore active event log from a checkpoint.")
    restore.add_argument("project_dir")
    restore.add_argument("checkpoint_id")
    restore.add_argument("--approved-by", required=True)
    restore.add_argument("--summary")
    restore.add_argument("--force", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "create":
        return create_checkpoint(args)
    if args.command == "list":
        return list_checkpoints(args)
    if args.command == "restore":
        return restore_checkpoint(args)
    raise ValueError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
