from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def portable_path(path: Path | str, *anchors: Path | None) -> str:
    raw_path = Path(path)
    resolved = raw_path if raw_path.is_absolute() else (Path.cwd() / raw_path)
    resolved = resolved.resolve()

    for anchor in anchors:
        if anchor is None:
            continue
        try:
            return resolved.relative_to(anchor.resolve()).as_posix()
        except ValueError:
            continue

    if raw_path.is_absolute():
        return resolved.name
    return raw_path.as_posix()
