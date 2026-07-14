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
from validate_project_acceptance import validate_project  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class LiteraturePipelineE2ETests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def seed_project(self, project: Path) -> None:
        events = [
            make_event(
                offset=1,
                actor="user",
                function="create_object",
                action_type="paper.created",
                object_type="Paper",
                object_id="P-lit-e2e",
                payload={
                    "paper_id": "P-lit-e2e",
                    "stage": "positioning",
                    "title": "Literature Pipeline E2E",
                },
            ),
            make_event(
                offset=2,
                actor="positioning_expert",
                function="create_object",
                action_type="claim.created",
                object_type="Claim",
                object_id="C-lit-gap",
                payload={
                    "claim_id": "C-lit-gap",
                    "paper_id": "P-lit-e2e",
                    "text": "Ontology-backed writing workflows need related-work positioning against prior meme-culture studies.",
                    "strength": "moderate",
                },
            ),
        ]
        write_yaml(project / "events" / "event_log.yml", {"events": events})
        write_yaml(project / "state" / "paper.yml", project_state(events, project / "events"))

    def test_import_select_apply_and_acceptance_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)
            search_results = project / "artifacts" / "search-results.yml"
            write_yaml(
                search_results,
                {
                    "provider": "semantic_scholar",
                    "query": "meme studies digital culture",
                    "searched_at": "2026-07-09T10:00:00+08:00",
                    "parameters": {"limit": 2},
                    "results": [
                        {
                            "provider_work_id": "paper-1",
                            "title": "Memes in Digital Culture",
                            "authors": "Shifman, Limor",
                            "year": 2013,
                            "venue": "MIT Press",
                            "doi": "10.7551/mitpress/9429.001.0001",
                            "uri": "https://doi.org/10.7551/mitpress/9429.001.0001",
                            "abstract": "A foundational account of internet meme culture.",
                            "score": 0.98,
                        }
                    ],
                },
            )

            intake_proposals = project / "proposals" / "search-intake.yml"
            intake = self.run_script(
                str(SCRIPTS / "import_search_results.py"),
                str(project),
                str(search_results),
                "--out",
                str(intake_proposals),
            )
            self.assertEqual(intake.returncode, 0, intake.stderr + intake.stdout)
            intake_apply = self.run_script(
                str(SCRIPTS / "apply_action_proposals.py"),
                str(project),
                str(intake_proposals),
                "--actor",
                "system",
            )
            self.assertEqual(intake_apply.returncode, 0, intake_apply.stderr + intake_apply.stdout)

            state = read_yaml(project / "state" / "paper.yml")
            external_work_id = next(iter(state["objects"]["ExternalWork"]))
            external_work = state["objects"]["ExternalWork"][external_work_id]
            self.assertEqual(external_work["title"], "Memes in Digital Culture")

            selection_proposals = project / "proposals" / "literature-selection.yml"
            write_yaml(
                selection_proposals,
                {
                    "proposals": [
                        {
                            "action_type": "citation.created",
                            "payload": {
                                "citation_id": "Cite-selected-shifman",
                                "paper_id": "P-lit-e2e",
                                "citation_key": "shifman2013memes",
                                "title": external_work["title"],
                                "authors": external_work["authors"],
                                "year": external_work["year"],
                                "uri": external_work["uri"],
                                "role": "background",
                                "verification_status": "verified",
                                "positioning_role": "predecessor",
                            },
                            "references": {"external_work_ids": [external_work_id]},
                        },
                        {
                            "action_type": "link.created",
                            "payload": {
                                "link_type": "citation_represents_external_work",
                                "from_object_type": "Citation",
                                "from_object_id": "Cite-selected-shifman",
                                "to_object_type": "ExternalWork",
                                "to_object_id": external_work_id,
                            },
                        },
                        {
                            "action_type": "link.created",
                            "payload": {
                                "link_type": "claim_uses_citation",
                                "from_object_type": "Claim",
                                "from_object_id": "C-lit-gap",
                                "to_object_type": "Citation",
                                "to_object_id": "Cite-selected-shifman",
                            },
                        },
                    ]
                },
            )

            selection_apply = self.run_script(
                str(SCRIPTS / "apply_action_proposals.py"),
                str(project),
                str(selection_proposals),
                "--actor",
                "positioning_expert",
            )
            self.assertEqual(selection_apply.returncode, 0, selection_apply.stderr + selection_apply.stdout)

            final_state = read_yaml(project / "state" / "paper.yml")
            self.assertIn("Cite-selected-shifman", final_state["objects"]["Citation"])
            active_link_types = {
                link["link_type"]
                for link in final_state["links"]
                if link.get("status") == "active"
            }
            self.assertIn("citation_represents_external_work", active_link_types)
            self.assertIn("claim_uses_citation", active_link_types)

            report = validate_project(
                project,
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=False,
            )
            self.assertEqual(report["errors"], [])
            self.assertIn(report["acceptance_status"], {"accepted", "accepted_with_warnings"})


if __name__ == "__main__":
    unittest.main()
