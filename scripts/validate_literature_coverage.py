from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


REQUIRED_POSITIONING_ROLES = (
    "predecessor",
    "direct_competitor",
    "later_extension",
    "limitation",
)
ACTIVE_GAP_STATUSES = {"open", "proposed", "accepted"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def validate_literature_coverage_state(
    state: dict[str, Any],
    required_roles: tuple[str, ...] = REQUIRED_POSITIONING_ROLES,
) -> dict[str, Any]:
    objects = state.get("objects", {}) if isinstance(state, dict) else {}
    citations = objects.get("Citation", {}) or {}
    issues = objects.get("Issue", {}) or {}

    covered_roles = {
        str(citation.get("positioning_role"))
        for citation in citations.values()
        if citation.get("verification_status") == "verified"
        and citation.get("positioning_role") in required_roles
    }
    missing_roles = set(required_roles) - covered_roles

    accounted_roles: set[str] = set()
    for issue in issues.values():
        role = issue.get("missing_literature_role")
        has_target = bool(issue.get("target_object_type") and issue.get("target_object_id"))
        if (
            issue.get("category") == "citation_gap"
            and issue.get("issue_status") in ACTIVE_GAP_STATUSES
            and role in missing_roles
            and has_target
        ):
            accounted_roles.add(str(role))

    unaccounted_roles = missing_roles - accounted_roles
    status = "complete_or_accounted_for" if not unaccounted_roles else "incomplete"
    return {
        "coverage_status": status,
        "required_roles": list(required_roles),
        "covered_roles": sorted(covered_roles),
        "documented_gap_roles": sorted(accounted_roles),
        "missing_roles": sorted(missing_roles),
        "unaccounted_roles": sorted(unaccounted_roles),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate literature positioning coverage or targeted gap accountability."
    )
    parser.add_argument("project_dir")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    state_path = project_dir / "state" / "paper.yml"
    if not state_path.exists():
        raise FileNotFoundError(f"missing projected state: {state_path}")
    state = load_yaml(state_path) or {"objects": {}, "links": []}
    report = validate_literature_coverage_state(state)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"coverage_status: {report['coverage_status']}")
        print(f"covered_roles: {', '.join(report['covered_roles']) or 'none'}")
        print(f"documented_gap_roles: {', '.join(report['documented_gap_roles']) or 'none'}")
        if report["unaccounted_roles"]:
            print("unaccounted_roles: " + ", ".join(report["unaccounted_roles"]))
            print("Create a targeted open citation_gap Issue for each missing role before finishing selection.")
    return 1 if report["unaccounted_roles"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
