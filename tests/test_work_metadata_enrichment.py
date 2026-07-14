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


class WorkMetadataEnrichmentTests(unittest.TestCase):
    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args],
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
                object_id="P-enrichment",
                payload={"paper_id": "P-enrichment", "stage": "positioning", "title": "Enrichment"},
            ),
            make_event(
                offset=2,
                actor="system",
                function="upsert_object",
                action_type="external_work.upserted",
                object_type="ExternalWork",
                object_id="EW-enrichment",
                payload={
                    "external_work_id": "EW-enrichment",
                    "title": "Mixed Multi-Head Self-Attention for Neural Machine Translation",
                    "source_provider": "crossref",
                    "doi": "10.18653/v1/D19-5622",
                    "metadata_quality": "bibliographic",
                },
            ),
        ]
        write_yaml(project / "events" / "event_log.yml", {"events": events})
        write_yaml(project / "state" / "paper.yml", project_state(events, project / "events"))

    def test_imports_official_abstract_as_artifact_and_external_work_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            self.seed_project(project)
            source = root / "acl-metadata.yml"
            write_yaml(
                source,
                {
                    "metadata_source_uri": "https://aclanthology.org/D19-5622/",
                    "metadata_retrieved_at": "2026-07-13T12:00:00Z",
                    "abstract": "The paper identifies redundancy in standard multi-head self-attention.",
                },
            )
            proposals = project / "proposals" / "metadata-enrichment.yml"

            imported = self.run_script(
                "import_work_metadata.py",
                str(project),
                "EW-enrichment",
                str(source),
                "--out",
                str(proposals),
            )
            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)

            dry_run = self.run_script(
                "apply_action_proposals.py",
                str(project),
                str(proposals),
                "--actor",
                "system",
                "--dry-run",
            )
            self.assertEqual(dry_run.returncode, 0, dry_run.stdout + dry_run.stderr)

            applied = self.run_script(
                "apply_action_proposals.py",
                str(project),
                str(proposals),
                "--actor",
                "system",
            )
            self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)

            state = read_yaml(project / "state" / "paper.yml")
            work = state["objects"]["ExternalWork"]["EW-enrichment"]
            self.assertEqual(work["metadata_quality"], "abstract")
            self.assertEqual(work["metadata_source_uri"], "https://aclanthology.org/D19-5622/")
            self.assertIn("redundancy", work["abstract"])
            artifacts = state["objects"]["Artifact"]
            self.assertEqual(next(iter(artifacts.values()))["artifact_type"], "external_work_metadata")
            self.assertTrue(
                any(link["link_type"] == "artifact_documents_external_work" for link in state["links"])
            )

    def test_accepts_source_uri_as_a_cli_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            self.seed_project(project)
            source = root / "provider-response.json"
            source.write_text(
                '{"abstract": "An auditable provider abstract."}',
                encoding="utf-8",
            )
            proposals = project / "proposals" / "metadata-enrichment.yml"

            imported = self.run_script(
                "import_work_metadata.py",
                str(project),
                "EW-enrichment",
                str(source),
                "--metadata-source-uri",
                "https://api.crossref.org/works/10.18653/v1/D19-5622",
                "--retrieved-at",
                "2026-07-13T12:00:00Z",
                "--out",
                str(proposals),
            )

            self.assertEqual(imported.returncode, 0, imported.stdout + imported.stderr)
            payloads = [item["payload"] for item in read_yaml(proposals)["proposals"]]
            work = next(item for item in payloads if item.get("external_work_id") == "EW-enrichment")
            self.assertEqual(
                work["metadata_source_uri"],
                "https://api.crossref.org/works/10.18653/v1/D19-5622",
            )


if __name__ == "__main__":
    unittest.main()
