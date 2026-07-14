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


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class LiteratureSelectionFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.events: list[dict[str, Any]] = []

    def add_event(
        self,
        *,
        actor: str,
        function: str,
        action_type: str,
        object_type: str,
        object_id: str,
        payload: dict[str, Any],
    ) -> None:
        self.events.append(
            make_event(
                offset=len(self.events) + 1,
                actor=actor,
                function=function,
                action_type=action_type,
                object_type=object_type,
                object_id=object_id,
                payload=payload,
            )
        )

    def populate(self) -> None:
        self.add_event(
            actor="user",
            function="create_object",
            action_type="paper.created",
            object_type="Paper",
            object_id="P-zero-demo",
            payload={"paper_id": "P-zero-demo", "stage": "positioning", "title": "Literature Demo"},
        )
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="claim.created",
            object_type="Claim",
            object_id="C-related-work-gap",
            payload={
                "claim_id": "C-related-work-gap",
                "paper_id": "P-zero-demo",
                "text": "The paper needs to position ontology-backed writing workflows against prior meme-culture work.",
                "strength": "moderate",
            },
        )
        self.add_event(
            actor="system",
            function="upsert_object",
            action_type="external_work.upserted",
            object_type="ExternalWork",
            object_id="EW-shifman-2013",
            payload={
                "external_work_id": "EW-shifman-2013",
                "title": "Memes in Digital Culture",
                "authors": "Shifman, Limor",
                "year": 2013,
                "source_provider": "manual",
                "doi": "10.7551/mitpress/9429.001.0001",
                "abstract": "A foundational account of internet meme culture.",
                "metadata_quality": "abstract",
            },
        )

    def write(self) -> None:
        write_yaml(self.root / "events" / "event_log.yml", {"events": self.events})
        write_yaml(self.root / "state" / "paper.yml", project_state(self.events, self.root / "events"))


class LiteratureSelectionTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_workflow_template_and_proposal_fixture_are_applicable(self) -> None:
        workflows = read_yaml(ROOT / "dynamic" / "workflows.yml")["workflows"]
        self.assertIn("literature_selection", workflows)
        self.assertIn("citation.created", workflows["literature_selection"]["may_emit_actions"])
        self.assertIn("link.created", workflows["literature_selection"]["may_emit_actions"])
        self.assertTrue((ROOT / "dynamic" / "templates" / "literature_selection.md").exists())

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            route_file = temp_root / "route.yml"
            write_yaml(
                route_file,
                {
                    "route_decision": {
                        "route_id": "RD-literature-selection-test",
                        "suite_triggered": True,
                        "project_required": True,
                        "workflow": "literature_selection",
                        "primary_expert": "positioning_expert",
                        "invocation_mode": "isolated_worker",
                        "allowed_actions": ["citation.created", "issue.created", "link.created"],
                        "state_reads": ["Paper", "Claim", "Evidence", "Citation", "ExternalWork", "Issue"],
                        "artifact_reads": [],
                        "human_gates": [],
                        "rationale": "Select imported literature and connect it to the argument graph.",
                        "next_step": {
                            "type": "prepare_expert_invocation",
                            "task": "Evaluate imported ExternalWork objects for citation use.",
                        },
                    }
                },
            )
            route_check = self.run_script(str(SCRIPTS / "validate_route_decision.py"), str(route_file))
            self.assertEqual(route_check.returncode, 0, route_check.stderr + route_check.stdout)

            project = temp_root / "project"
            fixture = LiteratureSelectionFixture(project)
            fixture.populate()
            fixture.write()
            proposal_file = temp_root / "proposals.yml"
            write_yaml(
                proposal_file,
                {
                    "proposals": [
                        {
                            "action_type": "citation.created",
                            "payload": {
                                "citation_id": "Cite-shifman-2013",
                                "paper_id": "P-zero-demo",
                                "citation_key": "shifman2013memes",
                                "title": "Memes in Digital Culture",
                                "authors": "Shifman, Limor",
                                "year": 2013,
                                "uri": "https://doi.org/10.7551/mitpress/9429.001.0001",
                                "role": "background",
                                "verification_status": "verified",
                                "positioning_role": "predecessor",
                            },
                            "references": {"external_work_ids": ["EW-shifman-2013"]},
                        },
                        {
                            "action_type": "link.created",
                            "payload": {
                                "link_type": "citation_represents_external_work",
                                "from_object_type": "Citation",
                                "from_object_id": "Cite-shifman-2013",
                                "to_object_type": "ExternalWork",
                                "to_object_id": "EW-shifman-2013",
                            },
                        },
                        {
                            "action_type": "link.created",
                            "payload": {
                                "link_type": "claim_uses_citation",
                                "from_object_type": "Claim",
                                "from_object_id": "C-related-work-gap",
                                "to_object_type": "Citation",
                                "to_object_id": "Cite-shifman-2013",
                            },
                        },
                    ]
                },
            )

            dry_run = self.run_script(
                str(SCRIPTS / "apply_action_proposals.py"),
                str(project),
                str(proposal_file),
                "--actor",
                "positioning_expert",
                "--dry-run",
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr + dry_run.stdout)

            applied = self.run_script(
                str(SCRIPTS / "apply_action_proposals.py"),
                str(project),
                str(proposal_file),
                "--actor",
                "positioning_expert",
            )
            self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)

            state = read_yaml(project / "state" / "paper.yml")
            self.assertIn("Cite-shifman-2013", state["objects"]["Citation"])
            active_links = [link for link in state["links"] if link.get("status") == "active"]
            link_types = {link["link_type"] for link in active_links}
            self.assertIn("citation_represents_external_work", link_types)
            self.assertIn("claim_uses_citation", link_types)


if __name__ == "__main__":
    unittest.main()
