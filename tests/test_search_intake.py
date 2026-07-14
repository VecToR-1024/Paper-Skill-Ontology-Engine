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


class SearchFixture:
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

    def paper(self) -> None:
        self.add_event(
            actor="user",
            function="create_object",
            action_type="paper.created",
            object_type="Paper",
            object_id="P-test",
            payload={"paper_id": "P-test", "stage": "positioning", "title": "Search Test"},
        )

    def external_work(self) -> None:
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
            },
        )

    def citation(self) -> None:
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="citation.created",
            object_type="Citation",
            object_id="Cite-shifman",
            payload={"citation_id": "Cite-shifman", "paper_id": "P-test"},
        )

    def link_citation_to_external_work(self) -> None:
        self.add_event(
            actor="router",
            function="create_link",
            action_type="link.created",
            object_type="Link",
            object_id="L-citation-external-work",
            payload={
                "link_type": "citation_represents_external_work",
                "from_object_type": "Citation",
                "from_object_id": "Cite-shifman",
                "to_object_type": "ExternalWork",
                "to_object_id": "EW-shifman-2013",
            },
        )

    def write(self) -> None:
        write_yaml(self.root / "events" / "event_log.yml", {"events": self.events})
        write_yaml(self.root / "state" / "paper.yml", project_state(self.events, self.root / "events"))


class SearchIntakeTests(unittest.TestCase):
    def run_script(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )

    def test_import_search_results_generates_applyable_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = SearchFixture(project)
            fixture.paper()
            fixture.write()
            source = project / "artifacts" / "search-results.yml"
            write_yaml(
                source,
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
                            "snippet": "Foundational meme studies reference.",
                        },
                        {
                            "provider_work_id": "paper-2",
                            "title": "The World Made Meme",
                            "authors": "Milner, Ryan",
                            "year": 2016,
                            "venue": "MIT Press",
                            "uri": "https://mitpress.mit.edu/9780262034999/the-world-made-meme/",
                            "score": 0.91,
                        },
                    ],
                },
            )
            proposals = project / "proposals" / "search-intake.yml"

            result = self.run_script(
                str(SCRIPTS / "import_search_results.py"),
                str(project),
                str(source),
                "--out",
                str(proposals),
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data = read_yaml(proposals)
            action_types = [item["action_type"] for item in data["proposals"]]
            self.assertEqual(action_types.count("search_run.created"), 1)
            self.assertEqual(action_types.count("external_work.upserted"), 2)
            self.assertEqual(action_types.count("search_result.created"), 2)
            first_work = next(item for item in data["proposals"] if item["action_type"] == "external_work.upserted")
            self.assertEqual(first_work["payload"]["title"], "Memes in Digital Culture")
            self.assertEqual(first_work["payload"]["source_provider"], "semantic_scholar")

            apply_result = self.run_script(
                str(SCRIPTS / "apply_action_proposals.py"),
                str(project),
                str(proposals),
                "--actor",
                "system",
            )

            self.assertEqual(apply_result.returncode, 0, apply_result.stderr + apply_result.stdout)
            state = read_yaml(project / "state" / "paper.yml")
            self.assertEqual(len(state["objects"]["SearchRun"]), 1)
            self.assertEqual(len(state["objects"]["ExternalWork"]), 2)
            self.assertEqual(len(state["objects"]["SearchResult"]), 2)

    def test_citation_can_be_traced_to_external_work(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = SearchFixture(project)
            fixture.paper()
            fixture.external_work()
            fixture.citation()
            fixture.link_citation_to_external_work()
            fixture.write()

            report = validate_project(
                project,
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=True,
            )

        self.assertEqual(report["errors"], [])
        self.assertEqual(report["acceptance_status"], "accepted")

    def test_citation_link_to_missing_external_work_fails_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = SearchFixture(project)
            fixture.paper()
            fixture.citation()
            fixture.link_citation_to_external_work()
            fixture.write()

            report = validate_project(
                project,
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=True,
            )

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(any("Citation Cite-shifman links to missing ExternalWork" in error for error in report["errors"]))


if __name__ == "__main__":
    unittest.main()
