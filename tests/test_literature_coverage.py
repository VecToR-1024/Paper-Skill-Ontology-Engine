from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "validate_literature_coverage.py"


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class LiteratureCoverageTests(unittest.TestCase):
    def run_validator(self, project: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(project)],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def write_state(
        self,
        project: Path,
        *,
        citations: dict[str, dict[str, Any]],
        issues: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        write_yaml(
            project / "state" / "paper.yml",
            {
                "schema_version": "0.1.0",
                "objects": {
                    "Paper": {
                        "P-coverage": {
                            "paper_id": "P-coverage",
                            "title": "Coverage Test",
                            "stage": "positioning",
                        }
                    },
                    "Citation": citations,
                    "Issue": issues or {},
                },
                "links": [],
            },
        )

    def test_missing_roles_without_targeted_issues_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.write_state(
                project,
                citations={
                    "Cite-extension": {
                        "citation_id": "Cite-extension",
                        "paper_id": "P-coverage",
                        "verification_status": "verified",
                        "positioning_role": "later_extension",
                    }
                },
            )

            result = self.run_validator(project)

            self.assertNotEqual(result.returncode, 0)
            output = result.stdout + result.stderr
            self.assertIn("predecessor", output)
            self.assertIn("direct_competitor", output)
            self.assertIn("limitation", output)

    def test_targeted_gap_issues_satisfy_missing_role_accountability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.write_state(
                project,
                citations={
                    "Cite-predecessor": {
                        "citation_id": "Cite-predecessor",
                        "paper_id": "P-coverage",
                        "verification_status": "verified",
                        "positioning_role": "predecessor",
                    },
                    "Cite-extension": {
                        "citation_id": "Cite-extension",
                        "paper_id": "P-coverage",
                        "verification_status": "verified",
                        "positioning_role": "later_extension",
                    },
                },
                issues={
                    "I-competitor-gap": {
                        "issue_id": "I-competitor-gap",
                        "paper_id": "P-coverage",
                        "category": "citation_gap",
                        "severity": "P1",
                        "issue_status": "open",
                        "target_object_type": "Paper",
                        "target_object_id": "P-coverage",
                        "missing_literature_role": "direct_competitor",
                        "evidence": "No direct competitor was verified in the current search runs.",
                    },
                    "I-limitation-gap": {
                        "issue_id": "I-limitation-gap",
                        "paper_id": "P-coverage",
                        "category": "citation_gap",
                        "severity": "P1",
                        "issue_status": "open",
                        "target_object_type": "Paper",
                        "target_object_id": "P-coverage",
                        "missing_literature_role": "limitation",
                        "evidence": "No limitation evidence was verified in the current search runs.",
                    },
                },
            )

            result = self.run_validator(project)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("coverage_status: complete_or_accounted_for", result.stdout)

    def test_tentative_citation_does_not_count_as_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.write_state(
                project,
                citations={
                    "Cite-tentative-predecessor": {
                        "citation_id": "Cite-tentative-predecessor",
                        "paper_id": "P-coverage",
                        "verification_status": "tentative",
                        "positioning_role": "predecessor",
                    }
                },
            )

            result = self.run_validator(project)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("predecessor", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
