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

from apply_action_proposals import load_action_policy, validate_proposal_policy  # noqa: E402
from event_log import make_event, project_state, read_events, load_registry  # noqa: E402
from validate_project_acceptance import validate_project  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SourceSpanFixture:
    def __init__(self, root: Path, *, stage: str = "idea") -> None:
        self.root = root
        self.events: list[dict[str, Any]] = []
        self.stage = stage

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
            payload={"paper_id": "P-test", "stage": self.stage, "title": "Anchor Test"},
        )

    def artifact(self, artifact_id: str = "A-source", path: str = "artifacts/source.md") -> None:
        source = self.root / path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("First source paragraph.\n\nSecond source paragraph.\n", encoding="utf-8")
        self.add_event(
            actor="system",
            function="create_object",
            action_type="artifact.created",
            object_type="Artifact",
            object_id=artifact_id,
            payload={
                "artifact_id": artifact_id,
                "paper_id": "P-test",
                "artifact_type": "extracted_text_md",
                "path": path,
            },
        )

    def source_span(self, span_id: str = "SPAN-A-source-0001") -> None:
        self.add_event(
            actor="system",
            function="create_object",
            action_type="source_span.created",
            object_type="SourceSpan",
            object_id=span_id,
            payload={
                "source_span_id": span_id,
                "paper_id": "P-test",
                "artifact_id": "A-source",
                "locator_type": "paragraph",
                "locator": {"paragraph_index": 1, "start_line": 1, "end_line": 1},
                "text_excerpt": "First source paragraph.",
                "text_hash": "0" * 64,
            },
        )

    def claim(self, *, strength: str = "strong") -> None:
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="claim.created",
            object_type="Claim",
            object_id="C-strong",
            payload={
                "claim_id": "C-strong",
                "paper_id": "P-test",
                "text": "A strong claim should have an auditable support trail.",
                "strength": strength,
            },
        )

    def evidence(self, evidence_id: str, *, source_ref: str | None = None) -> None:
        payload: dict[str, Any] = {
            "evidence_id": evidence_id,
            "paper_id": "P-test",
            "evidence_type": "qualitative_example",
            "summary": "Evidence anchored to a normalized source span.",
        }
        if source_ref is not None:
            payload["source_ref"] = source_ref
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="evidence.created",
            object_type="Evidence",
            object_id=evidence_id,
            payload=payload,
        )

    def link_claim_to_span(self) -> None:
        self.add_event(
            actor="router",
            function="create_link",
            action_type="link.created",
            object_type="Link",
            object_id="L-claim-span",
            payload={
                "link_type": "claim_anchored_to_source_span",
                "from_object_type": "Claim",
                "from_object_id": "C-strong",
                "to_object_type": "SourceSpan",
                "to_object_id": "SPAN-A-source-0001",
            },
        )

    def link_evidence_to_span(
        self,
        evidence_id: str = "E-span-backed",
        span_id: str = "SPAN-A-source-0001",
    ) -> None:
        self.add_event(
            actor="router",
            function="create_link",
            action_type="link.created",
            object_type="Link",
            object_id=f"L-{evidence_id}-{span_id}",
            payload={
                "link_type": "evidence_anchored_to_source_span",
                "from_object_type": "Evidence",
                "from_object_id": evidence_id,
                "to_object_type": "SourceSpan",
                "to_object_id": span_id,
            },
        )

    def write(self) -> None:
        write_yaml(self.root / "events" / "event_log.yml", {"events": self.events})
        write_yaml(self.root / "state" / "paper.yml", project_state(self.events, self.root / "events"))

    def state(self) -> dict[str, Any]:
        self.write()
        return project_state(read_events(self.root / "events" / "event_log.yml"), self.root / "events")


class SourceSpanAnchorTests(unittest.TestCase):
    def test_extract_source_spans_emits_stable_span_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = SourceSpanFixture(project)
            fixture.paper()
            fixture.artifact()
            fixture.write()
            out = project / "proposals" / "source_spans.yml"

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "extract_source_spans.py"),
                    str(project),
                    "A-source",
                    "--out",
                    str(out),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            proposals = read_yaml(out)["proposals"]
            self.assertEqual(len(proposals), 2)
            self.assertEqual(proposals[0]["action_type"], "source_span.created")
            self.assertEqual(proposals[0]["payload"]["locator_type"], "paragraph")
            self.assertEqual(proposals[0]["payload"]["text_excerpt"], "First source paragraph.")
            self.assertEqual(len(proposals[0]["payload"]["text_hash"]), 64)

    def test_claim_creation_requires_source_span_or_unanchored_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SourceSpanFixture(Path(tmp))
            fixture.paper()
            fixture.artifact()
            fixture.source_span()
            state = fixture.state()
            registry = load_registry()
            action_policy = load_action_policy()
            existing_event_ids = {event["event_id"] for event in fixture.events}

            unanchored_claim = {
                "action_type": "claim.created",
                "payload": {
                    "claim_id": "C-new",
                    "paper_id": "P-test",
                    "text": "An unanchored claim.",
                    "strength": "moderate",
                },
            }
            anchored_claim = {
                "action_type": "claim.created",
                "payload": {
                    "claim_id": "C-new",
                    "paper_id": "P-test",
                    "text": "An anchored claim.",
                    "strength": "moderate",
                },
                "references": {"source_span_ids": ["SPAN-A-source-0001"]},
            }
            explicit_unanchored_claim = {
                **unanchored_claim,
                "rationale": {"unanchored_reason": "This is a user-authored thesis statement, not extracted text."},
            }

            self.assertTrue(
                any(
                    "source_span_ids or rationale.unanchored_reason" in error
                    for error in validate_proposal_policy(
                        registry, action_policy, unanchored_claim, state, existing_event_ids
                    )
                )
            )
            self.assertEqual(
                validate_proposal_policy(registry, action_policy, anchored_claim, state, existing_event_ids),
                [],
            )
            self.assertEqual(
                validate_proposal_policy(registry, action_policy, explicit_unanchored_claim, state, existing_event_ids),
                [],
            )

    def test_submission_blocks_strong_claim_without_anchor_or_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SourceSpanFixture(Path(tmp), stage="submission")
            fixture.paper()
            fixture.artifact()
            fixture.claim(strength="strong")
            fixture.write()

            report = validate_project(
                Path(tmp),
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=True,
            )

        self.assertEqual(report["acceptance_status"], "failed")
        self.assertTrue(any("Strong Claim C-strong has no Evidence or SourceSpan support" in error for error in report["errors"]))

    def test_submission_accepts_strong_claim_anchored_to_source_span(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SourceSpanFixture(Path(tmp), stage="submission")
            fixture.paper()
            fixture.artifact()
            fixture.source_span()
            fixture.claim(strength="strong")
            fixture.link_claim_to_span()
            fixture.write()

            report = validate_project(
                Path(tmp),
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=True,
            )

        self.assertEqual(report["errors"], [])
        self.assertEqual(report["acceptance_status"], "accepted")

    def test_acceptance_treats_evidence_source_span_as_auditable_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = SourceSpanFixture(Path(tmp))
            fixture.paper()
            fixture.artifact()
            fixture.source_span()
            fixture.evidence("E-span-backed", source_ref=None)
            fixture.link_evidence_to_span()
            fixture.write()

            report = validate_project(
                Path(tmp),
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=True,
            )

        self.assertEqual(report["errors"], [])
        self.assertEqual(report["acceptance_status"], "accepted")


if __name__ == "__main__":
    unittest.main()
