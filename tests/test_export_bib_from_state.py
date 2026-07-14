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

from event_log import make_event, project_state, read_events, validate_event_log, load_registry  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class BibExportFixture:
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
            payload={"paper_id": "P-test", "stage": "idea", "title": "Test Paper"},
        )

    def citation(self) -> None:
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="citation.created",
            object_type="Citation",
            object_id="Cite-smith-2026",
            payload={
                "citation_id": "Cite-smith-2026",
                "paper_id": "P-test",
                "citation_key": "smith2026",
                "title": "A Study of AI Writing",
                "authors": "Smith, Ada and Chen, Bo",
                "year": 2026,
                "uri": "https://example.com/paper",
                "role": "background",
            },
        )

    def write(self) -> None:
        write_yaml(self.root / "events" / "event_log.yml", {"events": self.events})
        write_yaml(self.root / "state" / "paper.yml", project_state(self.events, self.root / "events"))


class ExportBibFromStateTests(unittest.TestCase):
    def test_exports_citations_to_bibtex_and_records_artifact_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = BibExportFixture(root)
            fixture.paper()
            fixture.citation()
            fixture.write()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "export_bib_from_state.py"),
                    str(root),
                    "--out",
                    "artifacts/references.bib",
                    "--append-event",
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            bib_path = root / "artifacts" / "references.bib"
            self.assertTrue(bib_path.exists())
            bib = bib_path.read_text(encoding="utf-8")
            self.assertIn("@misc{smith2026,", bib)
            self.assertIn("author = {Smith, Ada and Chen, Bo}", bib)
            self.assertIn("title = {A Study of AI Writing}", bib)
            self.assertIn("year = {2026}", bib)
            self.assertIn("url = {https://example.com/paper}", bib)

            events = read_events(root / "events" / "event_log.yml")
            self.assertEqual(len(events), 3)
            artifact_event = events[-1]
            self.assertEqual(artifact_event["function"], "export_bib_from_state")
            self.assertEqual(artifact_event["action_type"], "artifact.created")
            self.assertEqual(artifact_event["payload"]["artifact_type"], "bibliography_bib")
            self.assertEqual(artifact_event["payload"]["path"], "artifacts/references.bib")
            self.assertEqual(validate_event_log(events, load_registry()), [])

            state = yaml.safe_load((root / "state" / "paper.yml").read_text(encoding="utf-8"))
            artifact = state["objects"]["Artifact"][artifact_event["object_id"]]
            self.assertEqual(artifact["artifact_type"], "bibliography_bib")

    def test_refuses_to_write_empty_bibliography_when_no_citations_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = BibExportFixture(root)
            fixture.paper()
            fixture.write()

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "export_bib_from_state.py"),
                    str(root),
                    "--out",
                    "artifacts/references.bib",
                ],
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("no Citation objects", result.stderr + result.stdout)
            self.assertFalse((root / "artifacts" / "references.bib").exists())


if __name__ == "__main__":
    unittest.main()
