from __future__ import annotations

import argparse
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = "skill_manifest.yml"
IGNORED_NAMES = {".git", ".pytest_cache", "__pycache__", ".DS_Store"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_package(root: Path) -> dict[str, Any]:
    manifest_path = root / MANIFEST_NAME
    if not manifest_path.exists():
        raise ValueError(f"package manifest is missing: {manifest_path}")
    manifest = load_yaml(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"package manifest must be a mapping: {manifest_path}")
    required_files = manifest.get("required_files")
    if not isinstance(required_files, list) or not required_files:
        raise ValueError("package manifest must contain a non-empty required_files list")
    missing = [str(item) for item in required_files if not (root / str(item)).is_file()]
    if missing:
        raise ValueError("package is incomplete; missing required files: " + ", ".join(missing))
    return manifest


def ignore_package_noise(_directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in IGNORED_NAMES or name.endswith(".pyc")}
    return ignored


def validate_target_location(source: Path, target: Path) -> None:
    source = source.resolve()
    target = target.resolve()
    if source == target or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError("package source and install target must not overlap")


def install_skill(target: Path, *, replace: bool) -> tuple[dict[str, Any], Path | None]:
    source = ROOT.resolve()
    target = target.resolve()
    validate_target_location(source, target)
    manifest = validate_package(source)

    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not replace:
        raise FileExistsError(
            f"target already exists; refusing to merge into {target}. "
            "Use --replace to create a backup and install a clean copy."
        )

    staging = target.parent / f".{target.name}.installing-{uuid.uuid4().hex[:10]}"
    backup: Path | None = None
    try:
        shutil.copytree(source, staging, ignore=ignore_package_noise)
        validate_package(staging)

        if target.exists():
            suffix = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
            backup = target.parent / f"{target.name}.backup-{suffix}"
            target.rename(backup)
        staging.rename(target)
        validate_package(target)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        if backup is not None and backup.exists() and not target.exists():
            backup.rename(target)
        raise
    return manifest, backup


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Research Paper Suite into an empty target or replace it with a backed-up clean copy."
    )
    parser.add_argument("target_dir")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Rename an existing target to a timestamped backup before installing a clean copy.",
    )
    args = parser.parse_args()

    try:
        manifest, backup = install_skill(Path(args.target_dir), replace=args.replace)
    except (FileExistsError, ValueError, OSError) as exc:
        print(f"install_error: {exc}")
        return 1

    print(f"installed: {Path(args.target_dir).resolve()}")
    print(f"package_version: {manifest.get('package_version')}")
    if backup is not None:
        print(f"backup: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
