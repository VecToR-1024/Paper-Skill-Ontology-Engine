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

from event_log import make_event, project_state, read_events  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class RevertFixture:
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
        approval: dict[str, Any] | None = None,
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
                approval=approval,
            )
        )

    def approved(self) -> dict[str, Any]:
        return {"status": "approved", "approved_by": "tester"}

    def paper(self) -> None:
        self.add_event(
            actor="user",
            function="create_object",
            action_type="paper.created",
            object_type="Paper",
            object_id="P-test",
            payload={"paper_id": "P-test", "stage": "idea", "title": "Undo Test"},
        )

    def section(self, *, content: str = "Original abstract.", title: str = "Abstract") -> None:
        self.add_event(
            actor="writing_expert",
            function="upsert_object",
            action_type="section.upserted",
            object_type="Section",
            object_id="S-abstract",
            payload={
                "section_id": "S-abstract",
                "paper_id": "P-test",
                "section_type": "abstract",
                "title": title,
                "content": content,
                "order_index": 1,
            },
        )

    def claim(self, *, text: str = "Original claim.", strength: str = "moderate") -> None:
        self.add_event(
            actor="positioning_expert",
            function="create_object",
            action_type="claim.created",
            object_type="Claim",
            object_id="C-main",
            payload={
                "claim_id": "C-main",
                "paper_id": "P-test",
                "section_id": "S-abstract",
                "text": text,
                "strength": strength,
            },
        )

    def claim_update(self, *, text: str, strength: str = "weak") -> str:
        self.add_event(
            actor="positioning_expert",
            function="update_object",
            action_type="claim.updated",
            object_type="Claim",
            object_id="C-main",
            payload={"claim_id": "C-main", "text": text, "strength": strength},
            approval=self.approved(),
        )
        return self.events[-1]["event_id"]

    def issue(self, *, severity: str = "P0", status: str = "open") -> None:
        self.add_event(
            actor="review_expert",
            function="create_object",
            action_type="issue.created",
            object_type="Issue",
            object_id="I-main",
            payload={
                "issue_id": "I-main",
                "paper_id": "P-test",
                "category": "missing_evidence",
                "severity": severity,
                "issue_status": status,
                "evidence": "The claim is not backed by evidence.",
                "target_object_type": "Claim",
                "target_object_id": "C-main",
                "claim_id": "C-main",
            },
        )

    def issue_status_change(self, status: str) -> str:
        self.add_event(
            actor="review_expert",
            function="update_object",
            action_type="issue.status_changed",
            object_type="Issue",
            object_id="I-main",
            payload={"issue_id": "I-main", "issue_status": status},
            approval=self.approved(),
        )
        return self.events[-1]["event_id"]

    def issue_severity_change(self, *, previous: str, severity: str, reason: str) -> str:
        self.add_event(
            actor="review_expert",
            function="update_object",
            action_type="issue.severity_changed",
            object_type="Issue",
            object_id="I-main",
            payload={
                "issue_id": "I-main",
                "previous_severity": previous,
                "severity": severity,
                "reclassification_reason": reason,
            },
            approval=self.approved(),
        )
        return self.events[-1]["event_id"]

    def section_update(self, *, content: str, title: str = "Abstract") -> str:
        self.add_event(
            actor="writing_expert",
            function="upsert_object",
            action_type="section.upserted",
            object_type="Section",
            object_id="S-abstract",
            payload={
                "section_id": "S-abstract",
                "paper_id": "P-test",
                "section_type": "abstract",
                "title": title,
                "content": content,
                "order_index": 1,
            },
        )
        return self.events[-1]["event_id"]

    def write(self) -> None:
        write_yaml(self.root / "events" / "event_log.yml", {"events": self.events})
        write_yaml(self.root / "state" / "paper.yml", project_state(self.events, self.root / "events"))


class ProposeEventRevertTests(unittest.TestCase):
    def run_script(self, *args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *args],
            cwd=cwd,
            text=True,
            capture_output=True,
        )

    def propose_revert(self, project: Path, event_id: str) -> Path:
        proposal = project / "proposals" / f"revert-{event_id}.yml"
        result = self.run_script(
            str(SCRIPTS / "propose_event_revert.py"),
            str(project),
            event_id,
            "--out",
            str(proposal),
            "--reason",
            "Regression test undo.",
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(proposal.exists())
        return proposal

    def apply_proposal(self, project: Path, proposal: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_script(str(SCRIPTS / "apply_action_proposals.py"), str(project), str(proposal), *extra)

    def state(self, project: Path) -> dict[str, Any]:
        return read_yaml(project / "state" / "paper.yml")

    def test_claim_update_revert_preserves_human_gate_and_restores_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = RevertFixture(project)
            fixture.paper()
            fixture.section()
            fixture.claim(text="Original claim.", strength="moderate")
            target_event = fixture.claim_update(text="Hedged claim.", strength="weak")
            fixture.write()

            proposal = self.propose_revert(project, target_event)
            dry_run = self.apply_proposal(project, proposal, "--dry-run")
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr + dry_run.stdout)
            self.assertIn("approval_required", dry_run.stdout)

            blocked = self.apply_proposal(project, proposal)
            self.assertEqual(blocked.returncode, 2, blocked.stderr + blocked.stdout)
            self.assertEqual(len(read_events(project / "events" / "event_log.yml")), 4)

            applied = self.apply_proposal(project, proposal, "--approved-by", "tester")
            self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
            claim = self.state(project)["objects"]["Claim"]["C-main"]
            self.assertEqual(claim["text"], "Original claim.")
            self.assertEqual(claim["strength"], "moderate")

    def test_issue_status_revert_restores_open_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = RevertFixture(project)
            fixture.paper()
            fixture.section()
            fixture.claim()
            fixture.issue(status="open")
            target_event = fixture.issue_status_change("resolved")
            fixture.write()

            proposal = self.propose_revert(project, target_event)
            blocked = self.apply_proposal(project, proposal)
            self.assertEqual(blocked.returncode, 2, blocked.stderr + blocked.stdout)
            applied = self.apply_proposal(project, proposal, "--approved-by", "tester")
            self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
            issue = self.state(project)["objects"]["Issue"]["I-main"]
            self.assertEqual(issue["issue_status"], "open")

    def test_issue_severity_revert_restores_current_severity_after_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = RevertFixture(project)
            fixture.paper()
            fixture.section()
            fixture.claim()
            fixture.issue(severity="P0")
            target_event = fixture.issue_severity_change(
                previous="P0",
                severity="P2",
                reason="Scope narrowed during positioning.",
            )
            fixture.write()

            proposal = self.propose_revert(project, target_event)
            data = read_yaml(proposal)
            payload = data["proposals"][0]["payload"]
            self.assertEqual(payload["previous_severity"], "P2")
            self.assertEqual(payload["severity"], "P0")
            self.assertIn("reclassification_reason", payload)

            blocked = self.apply_proposal(project, proposal)
            self.assertEqual(blocked.returncode, 2, blocked.stderr + blocked.stdout)
            applied = self.apply_proposal(project, proposal, "--approved-by", "tester")
            self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
            issue = self.state(project)["objects"]["Issue"]["I-main"]
            self.assertEqual(issue["severity"], "P0")

    def test_section_upsert_revert_restores_content_without_human_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = RevertFixture(project)
            fixture.paper()
            fixture.section(content="Original abstract.", title="Abstract")
            target_event = fixture.section_update(content="Rewritten abstract.", title="New Abstract")
            fixture.write()

            proposal = self.propose_revert(project, target_event)
            dry_run = self.apply_proposal(project, proposal, "--dry-run")
            self.assertEqual(dry_run.returncode, 0, dry_run.stderr + dry_run.stdout)
            self.assertNotIn("approval_required", dry_run.stdout)

            applied = self.apply_proposal(project, proposal)
            self.assertEqual(applied.returncode, 0, applied.stderr + applied.stdout)
            section = self.state(project)["objects"]["Section"]["S-abstract"]
            self.assertEqual(section["content"], "Original abstract.")
            self.assertEqual(section["title"], "Abstract")

    def test_later_same_field_conflict_blocks_lossy_revert(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = RevertFixture(project)
            fixture.paper()
            fixture.section()
            fixture.claim(text="Original claim.", strength="moderate")
            first_update = fixture.claim_update(text="First revision.", strength="weak")
            fixture.claim_update(text="Second revision.", strength="weak")
            fixture.write()

            result = self.run_script(str(SCRIPTS / "propose_event_revert.py"), str(project), first_update)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("later events also changed", result.stdout + result.stderr)

    def test_creation_event_revert_is_rejected_for_now(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            fixture = RevertFixture(project)
            fixture.paper()
            fixture.section()
            fixture.claim()
            fixture.write()

            result = self.run_script(str(SCRIPTS / "propose_event_revert.py"), str(project), "EVT-000003")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("creation reverts are not supported", result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
