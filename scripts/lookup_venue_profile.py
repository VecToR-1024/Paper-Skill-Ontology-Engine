from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT / "references" / "venue_profiles"


def normalize(value: str) -> str:
    return "".join(ch.lower() for ch in value if ch.isalnum())


def profile_summary(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = next((line[2:].strip() for line in lines if line.startswith("# ")), path.stem)
    venue_type = ""
    field = ""
    for line in lines:
        if line.startswith("- **类型**"):
            venue_type = line.split("：", 1)[-1].strip()
        if line.startswith("- **领域**"):
            field = line.split("：", 1)[-1].strip()
    return {
        "id": path.stem,
        "title": title,
        "type": venue_type,
        "field": field,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
    }


def list_profiles() -> list[dict[str, str]]:
    return [
        profile_summary(path)
        for path in sorted(PROFILE_DIR.glob("*.md"))
        if path.name.lower() != "readme.md"
    ]


def find_profiles(query: str) -> list[dict[str, str]]:
    needle = normalize(query)
    matches = []
    for item in list_profiles():
        haystack = normalize(" ".join([item["id"], item["title"], item["type"], item["field"]]))
        if needle in haystack:
            matches.append(item)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="List or find cached venue profiles.")
    parser.add_argument("query", nargs="?", help="Venue name, acronym, or field keyword.")
    parser.add_argument("--list", action="store_true", help="List all cached profiles.")
    args = parser.parse_args()

    if args.list or not args.query:
        data = list_profiles()
    else:
        data = find_profiles(args.query)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
