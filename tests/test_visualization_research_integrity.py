from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_project_visualization import build_project_data, render_html  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class VisualizationResearchIntegrityTests(unittest.TestCase):
    def seed_project(self, project: Path) -> None:
        event = {
            "offset": 1,
            "event_id": "EVT-000001",
            "timestamp": "2026-07-13T08:00:00Z",
            "actor": "user",
            "function": "create_object",
            "action_type": "paper.created",
            "object_type": "Paper",
            "object_id": "P-viz",
            "payload": {"paper_id": "P-viz", "title": "Integrity Visualization", "stage": "positioning"},
        }
        objects: dict[str, dict[str, dict[str, Any]]] = {
            "Paper": {
                "P-viz": {"paper_id": "P-viz", "title": "Integrity Visualization", "stage": "positioning"}
            },
            "Artifact": {
                "A-source": {
                    "artifact_id": "A-source",
                    "paper_id": "P-viz",
                    "artifact_type": "extracted_text_md",
                    "path": "artifacts/extracted_text.md",
                },
                "A-metadata": {
                    "artifact_id": "A-metadata",
                    "paper_id": "P-viz",
                    "artifact_type": "external_work_metadata",
                    "path": "artifacts/external-work-metadata/provider.yml",
                },
            },
            "SourceSpan": {
                "SPAN-001": {
                    "source_span_id": "SPAN-001",
                    "paper_id": "P-viz",
                    "artifact_id": "A-source",
                    "locator_type": "paragraph",
                    "locator": {"paragraph_index": 1},
                    "text_excerpt": "Attention replaces recurrent computation.",
                    "text_hash": "0" * 64,
                }
            },
            "Evidence": {
                "E-001": {
                    "evidence_id": "E-001",
                    "paper_id": "P-viz",
                    "evidence_type": "paper_text",
                    "summary": "The architecture relies on attention rather than recurrence.",
                }
            },
            "ExternalWork": {},
            "Citation": {},
        }
        links: list[dict[str, Any]] = [
            {
                "link_type": "evidence_anchored_to_source_span",
                "from_object_type": "Evidence",
                "from_object_id": "E-001",
                "to_object_type": "SourceSpan",
                "to_object_id": "SPAN-001",
                "status": "active",
            }
        ]
        roles = ("predecessor", "direct_competitor", "later_extension", "limitation")
        for index, role in enumerate(roles, start=1):
            work_id = f"EW-{index}"
            citation_id = f"Cite-{index}"
            objects["ExternalWork"][work_id] = {
                "external_work_id": work_id,
                "title": f"Verified {role}",
                "year": 2010 + index,
                "source_provider": "openalex",
                "metadata_quality": "abstract",
                "abstract": f"Abstract for {role}.",
            }
            objects["Citation"][citation_id] = {
                "citation_id": citation_id,
                "paper_id": "P-viz",
                "title": f"Verified {role}",
                "verification_status": "verified",
                "positioning_role": role,
            }
            links.append(
                {
                    "link_type": "citation_represents_external_work",
                    "from_object_type": "Citation",
                    "from_object_id": citation_id,
                    "to_object_type": "ExternalWork",
                    "to_object_id": work_id,
                    "status": "active",
                }
            )
        objects["ExternalWork"]["EW-hold"] = {
            "external_work_id": "EW-hold",
            "title": "Title-only lead",
            "source_provider": "crossref",
            "metadata_quality": "title_only",
        }
        objects["Citation"]["Cite-hold"] = {
            "citation_id": "Cite-hold",
            "paper_id": "P-viz",
            "title": "Title-only lead",
            "verification_status": "tentative",
            "positioning_role": "background",
        }
        links.extend(
            [
                {
                    "link_type": "citation_represents_external_work",
                    "from_object_type": "Citation",
                    "from_object_id": "Cite-hold",
                    "to_object_type": "ExternalWork",
                    "to_object_id": "EW-hold",
                    "status": "active",
                },
                {
                    "link_type": "artifact_documents_external_work",
                    "from_object_type": "Artifact",
                    "from_object_id": "A-metadata",
                    "to_object_type": "ExternalWork",
                    "to_object_id": "EW-1",
                    "status": "active",
                },
            ]
        )

        write_yaml(project / "events" / "event_log.yml", {"events": [event]})
        write_yaml(project / "state" / "paper.yml", {"objects": objects, "links": links})
        write_yaml(
            project / "expert_invocations" / "EX-positioning" / "runner_manifest.yml",
            {
                "invocation_id": "EX-positioning",
                "expert_name": "positioning_expert",
                "requested_mode": "isolated_worker",
                "execution": {
                    "backend": "current_agent_fallback",
                    "isolation_verified": False,
                    "recorded_at": "2026-07-13T08:30:00Z",
                    "recorded_by": "main-agent",
                    "reason": "The host has no isolated worker runtime.",
                },
            },
        )

    def test_bundle_exposes_literature_provenance_and_execution_integrity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)

            data = build_project_data(project)

        self.assertEqual(data["literature"]["counts"]["verified"], 4)
        self.assertEqual(data["literature"]["counts"]["tentative"], 1)
        self.assertEqual(data["literature"]["coverage"]["coverage_status"], "complete_or_accounted_for")
        self.assertEqual(
            data["literature"]["coverage"]["covered_roles"],
            ["direct_competitor", "later_extension", "limitation", "predecessor"],
        )
        predecessor = next(item for item in data["literature"]["citations"] if item["positioning_role"] == "predecessor")
        self.assertEqual(predecessor["metadata_quality"], "abstract")
        self.assertEqual(predecessor["metadata_artifact_ids"], ["A-metadata"])

        self.assertEqual(data["provenance"]["counts"]["evidence_with_source_spans"], 1)
        chain = data["provenance"]["evidence_source_chains"][0]
        self.assertEqual(chain["evidence_id"], "E-001")
        self.assertEqual(chain["spans"][0]["artifact_path"], "artifacts/extracted_text.md")

        self.assertEqual(data["expert_executions"]["counts"]["current_agent_fallback"], 1)
        self.assertEqual(data["expert_executions"]["counts"]["isolation_verified"], 0)
        self.assertIn("no isolated worker", data["expert_executions"]["executions"][0]["reason"])

    def test_html_contains_integrity_reporting_surfaces(self) -> None:
        html = render_html({"project": {}, "story": {}, "literature": {}, "provenance": {}, "expert_executions": {}})

        for element_id in (
            "research-integrity",
            "literature-overview",
            "provenance-chains",
            "expert-execution",
        ):
            self.assertIn(f'id="{element_id}"', html)
        for function_name in (
            "renderResearchIntegrity",
            "renderLiterature",
            "renderProvenanceChains",
            "renderExpertExecutions",
        ):
            self.assertIn(f"function {function_name}", html)

    def test_unanchored_evidence_is_reported_as_a_provenance_gap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)
            state_path = project / "state" / "paper.yml"
            state = yaml.safe_load(state_path.read_text(encoding="utf-8"))
            state["links"] = []
            write_yaml(state_path, state)

            provenance = build_project_data(project)["provenance"]

        self.assertEqual(provenance["counts"]["evidence_without_source_spans"], 1)
        self.assertEqual(provenance["counts"]["broken_links"], 1)
        self.assertEqual(provenance["evidence_source_chains"][0]["evidence_id"], "E-001")
        self.assertFalse(provenance["evidence_source_chains"][0]["complete"])
        self.assertEqual(provenance["broken_links"][0]["problem"], "no SourceSpan anchor")


if __name__ == "__main__":
    unittest.main()
