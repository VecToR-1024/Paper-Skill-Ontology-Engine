from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from event_log import make_event, project_state  # noqa: E402
from import_search_results import normalize_work_payload  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class LiteratureEvidencePolicyTests(unittest.TestCase):
    def run_apply(self, project: Path, proposal_file: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "apply_action_proposals.py"),
                str(project),
                str(proposal_file),
                "--actor",
                "positioning_expert",
                "--dry-run",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def seed_project(self, project: Path, *, abstract: str | None = None) -> None:
        external_work = {
            "external_work_id": "EW-policy-test",
            "title": "A Candidate Work",
            "authors": "Example, Ada",
            "year": 2020,
            "source_provider": "crossref",
            "doi": "10.1000/example",
        }
        if abstract is not None:
            external_work["abstract"] = abstract

        events = [
            make_event(
                offset=1,
                actor="user",
                function="create_object",
                action_type="paper.created",
                object_type="Paper",
                object_id="P-policy-test",
                payload={"paper_id": "P-policy-test", "stage": "positioning", "title": "Policy Test"},
            ),
            make_event(
                offset=2,
                actor="positioning_expert",
                function="create_object",
                action_type="claim.created",
                object_type="Claim",
                object_id="C-policy-test",
                payload={
                    "claim_id": "C-policy-test",
                    "paper_id": "P-policy-test",
                    "text": "A claim needing literature support.",
                    "strength": "moderate",
                },
            ),
            make_event(
                offset=3,
                actor="system",
                function="upsert_object",
                action_type="external_work.upserted",
                object_type="ExternalWork",
                object_id="EW-policy-test",
                payload=external_work,
            ),
        ]
        write_yaml(project / "events" / "event_log.yml", {"events": events})
        write_yaml(project / "state" / "paper.yml", project_state(events, project / "events"))

    def citation_proposal(self, status: str) -> dict[str, Any]:
        return {
            "action_type": "citation.created",
            "payload": {
                "citation_id": "Cite-policy-test",
                "paper_id": "P-policy-test",
                "title": "A Candidate Work",
                "role": "support",
                "verification_status": status,
            },
            "references": {"external_work_ids": ["EW-policy-test"]},
        }

    def test_search_intake_marks_title_only_and_abstract_metadata_quality(self) -> None:
        title_only, _ = normalize_work_payload("crossref", {"title": "Title Only"}, 1)
        with_abstract, _ = normalize_work_payload(
            "openalex",
            {"title": "With Abstract", "abstract": "This abstract supports semantic review."},
            1,
        )

        self.assertEqual(title_only["metadata_quality"], "title_only")
        self.assertEqual(with_abstract["metadata_quality"], "abstract")

    def test_verified_citation_requires_abstract_or_full_text_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)
            proposal_file = project / "proposals" / "verified-title-only.yml"
            write_yaml(proposal_file, {"proposals": [self.citation_proposal("verified")]})

            result = self.run_apply(project, proposal_file)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires abstract or full_text metadata", result.stdout + result.stderr)

    def test_tentative_citation_cannot_be_linked_as_claim_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)
            proposal_file = project / "proposals" / "tentative-link.yml"
            write_yaml(
                proposal_file,
                {
                    "proposals": [
                        self.citation_proposal("tentative"),
                        {
                            "action_type": "link.created",
                            "payload": {
                                "link_type": "claim_uses_citation",
                                "from_object_type": "Claim",
                                "from_object_id": "C-policy-test",
                                "to_object_type": "Citation",
                                "to_object_id": "Cite-policy-test",
                            },
                        },
                    ]
                },
            )

            result = self.run_apply(project, proposal_file)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("tentative Citation Cite-policy-test cannot be linked", result.stdout + result.stderr)

    def test_citation_link_rejects_stale_external_work_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project, abstract="Enough metadata to verify this work.")
            proposal_file = project / "proposals" / "stale-external-work-link.yml"
            write_yaml(
                proposal_file,
                {
                    "proposals": [
                        self.citation_proposal("verified"),
                        {
                            "action_type": "link.created",
                            "payload": {
                                "link_type": "citation_represents_external_work",
                                "from_object_type": "Citation",
                                "from_object_id": "Cite-policy-test",
                                "to_object_type": "ExternalWork",
                                "to_object_id": "EW-stale-id",
                            },
                        },
                    ]
                },
            )

            result = self.run_apply(project, proposal_file)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown ExternalWork id EW-stale-id", result.stdout + result.stderr)

    def test_citation_gap_issue_requires_object_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project, abstract="Enough metadata for the unrelated fixture.")
            proposal_file = project / "proposals" / "untargeted-gap.yml"
            write_yaml(
                proposal_file,
                {
                    "proposals": [
                        {
                            "action_type": "issue.created",
                            "payload": {
                                "issue_id": "I-citation-gap",
                                "paper_id": "P-policy-test",
                                "category": "citation_gap",
                                "severity": "P1",
                                "issue_status": "open",
                                "evidence": "No predecessor literature has been selected.",
                            },
                        }
                    ]
                },
            )

            result = self.run_apply(project, proposal_file)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("citation_gap requires target_object_type and target_object_id", result.stdout + result.stderr)

    def test_citation_gap_issue_requires_missing_literature_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project, abstract="Enough metadata for the unrelated fixture.")
            proposal_file = project / "proposals" / "unclassified-gap.yml"
            write_yaml(
                proposal_file,
                {
                    "proposals": [
                        {
                            "action_type": "issue.created",
                            "payload": {
                                "issue_id": "I-citation-gap",
                                "paper_id": "P-policy-test",
                                "category": "citation_gap",
                                "severity": "P1",
                                "issue_status": "open",
                                "evidence": "No predecessor literature has been selected.",
                                "target_object_type": "Claim",
                                "target_object_id": "C-policy-test",
                            },
                        }
                    ]
                },
            )

            result = self.run_apply(project, proposal_file)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("citation_gap requires missing_literature_role", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
