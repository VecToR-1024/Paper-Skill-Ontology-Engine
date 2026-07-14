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

from event_log import make_event, project_state  # noqa: E402
from validate_project_acceptance import validate_project  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class AcceptanceFixture:
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

    def artifact(self, artifact_id: str, path: str, artifact_type: str = "source_pdf") -> None:
        self.add_event(
            actor="system",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=artifact_id,
            payload={
                "artifact_id": artifact_id,
                "paper_id": "P-test",
                "artifact_type": artifact_type,
                "path": path,
            },
        )

    def evidence(
        self,
        evidence_id: str,
        *,
        summary: str = "A concrete observed example.",
        source_ref: str | None = "artifacts/source.md#case-1",
        artifact_id: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "evidence_id": evidence_id,
            "paper_id": "P-test",
            "evidence_type": "qualitative_example",
            "summary": summary,
        }
        if source_ref is not None:
            payload["source_ref"] = source_ref
        if artifact_id is not None:
            payload["artifact_id"] = artifact_id
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="evidence.created",
            object_type="Evidence",
            object_id=evidence_id,
            payload=payload,
        )

    def citation(self, citation_id: str, **fields: Any) -> None:
        payload = {"citation_id": citation_id, "paper_id": "P-test", **fields}
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="citation.created",
            object_type="Citation",
            object_id=citation_id,
            payload=payload,
        )

    def evidence_uses_citation(self, evidence_id: str, citation_id: str) -> None:
        self.add_event(
            actor="router",
            function="create_link",
            action_type="link.created",
            object_type="Link",
            object_id=f"L-{evidence_id}-{citation_id}",
            payload={
                "link_type": "evidence_uses_citation",
                "from_object_type": "Evidence",
                "from_object_id": evidence_id,
                "to_object_type": "Citation",
                "to_object_id": citation_id,
            },
        )

    def write(self) -> None:
        write_yaml(self.root / "events" / "event_log.yml", {"events": self.events})
        write_yaml(
            self.root / "state" / "paper.yml",
            project_state(self.events, self.root / "events"),
        )

    def validate(self) -> dict[str, Any]:
        self.write()
        return validate_project(
            self.root,
            max_section_content_chars=1500,
            max_total_section_content_chars=3000,
            allow_no_citations=True,
        )


class ValidateProjectAcceptanceTests(unittest.TestCase):
    def test_rejects_durable_file_without_artifact_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            output = Path(tmp) / "outputs" / "paper-overview.html"
            output.parent.mkdir(parents=True)
            output.write_text("<h1>side output</h1>", encoding="utf-8")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(
            any("durable files are not recorded as Artifact objects" in error for error in report["errors"])
        )

    def test_rejects_placeholder_evidence_and_unstructured_external_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            fixture.evidence(
                "E-placeholder",
                summary="[待补充] find examples later",
                source_ref="百度百科词条 + 抖音话题数据",
            )

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(any("Evidence E-placeholder still contains placeholder text" in error for error in report["errors"]))
        self.assertTrue(any("Evidence E-placeholder" in error and "no artifact_id" in error for error in report["errors"]))

    def test_rejects_evidence_artifact_id_that_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            fixture.evidence("E-missing-artifact", artifact_id="A-missing")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(any("Evidence E-missing-artifact references missing Artifact A-missing" in error for error in report["errors"]))

    def test_rejects_empty_citation_even_when_evidence_links_to_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            fixture.evidence("E-weak-citation", source_ref="External article")
            fixture.citation("Cite-empty")
            fixture.evidence_uses_citation("E-weak-citation", "Cite-empty")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(any("Citation Cite-empty is not traceable" in error for error in report["errors"]))

    def test_rejects_artifact_record_with_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            fixture.artifact("A-missing-file", "artifacts/missing.md", artifact_type="section_md")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(any("Artifact A-missing-file path does not exist" in error for error in report["errors"]))

    def test_accepts_evidence_backed_by_recorded_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "artifacts" / "source.md"
            source.parent.mkdir(parents=True)
            source.write_text("case material", encoding="utf-8")
            fixture = AcceptanceFixture(root)
            fixture.paper()
            fixture.artifact("A-source", "artifacts/source.md", artifact_type="section_md")
            fixture.evidence("E-artifact", artifact_id="A-source")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "accepted")
        self.assertEqual(report["errors"], [])

    def test_accepts_evidence_backed_by_traceable_citation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            fixture.evidence("E-cited", source_ref="Smith 2026")
            fixture.citation(
                "Cite-smith-2026",
                citation_key="smith-2026",
                title="A Traceable Study",
                authors="Smith, Ada",
                year=2026,
            )
            fixture.evidence_uses_citation("E-cited", "Cite-smith-2026")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "accepted")
        self.assertEqual(report["errors"], [])

    def test_rejects_tentative_citation_used_as_evidence_support(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = AcceptanceFixture(Path(tmp))
            fixture.paper()
            fixture.evidence("E-tentative", source_ref="Smith 2026")
            fixture.citation(
                "Cite-tentative",
                citation_key="smith-2026",
                title="A Search Lead",
                authors="Smith, Ada",
                year=2026,
                verification_status="tentative",
            )
            fixture.evidence_uses_citation("E-tentative", "Cite-tentative")

            report = fixture.validate()

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(
            any(
                "tentative Citation Cite-tentative cannot be used as support" in error
                for error in report["errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
