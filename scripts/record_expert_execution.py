from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


EXECUTION_BACKENDS = {"isolated_worker", "current_agent_fallback", "manual_packet"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)


def record_execution(
    invocation_dir: Path,
    *,
    backend: str,
    recorded_by: str,
    reason: str | None,
) -> dict[str, Any]:
    if backend not in EXECUTION_BACKENDS:
        raise ValueError(f"unknown execution backend: {backend}")
    if backend != "isolated_worker" and not (reason or "").strip():
        raise ValueError(f"reason is required for execution backend {backend}")

    manifest_path = invocation_dir / "runner_manifest.yml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"missing runner manifest: {manifest_path}")
    manifest = load_yaml(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("runner_manifest.yml must contain a mapping")

    isolation_verified = backend == "isolated_worker"
    execution = {
        "backend": backend,
        "isolation_verified": isolation_verified,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "recorded_by": recorded_by,
        "reason": (reason or "").strip() or None,
    }
    manifest["execution"] = execution
    manifest["isolation"] = "verified" if isolation_verified else "not_verified"
    manifest.setdefault("requested_mode", manifest.get("mode", "isolated_worker"))
    write_yaml(manifest_path, manifest)
    return execution


def main() -> int:
    parser = argparse.ArgumentParser(description="Record the backend that actually executed an expert packet.")
    parser.add_argument("invocation_dir")
    parser.add_argument("--backend", required=True, choices=sorted(EXECUTION_BACKENDS))
    parser.add_argument("--recorded-by", required=True)
    parser.add_argument("--reason")
    args = parser.parse_args()

    try:
        execution = record_execution(
            Path(args.invocation_dir).resolve(),
            backend=args.backend,
            recorded_by=args.recorded_by,
            reason=args.reason,
        )
    except (FileNotFoundError, ValueError, OSError) as exc:
        print(f"execution_record_error: {exc}")
        return 1

    print(f"execution_backend: {execution['backend']}")
    print(f"isolation_verified: {str(execution['isolation_verified']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
