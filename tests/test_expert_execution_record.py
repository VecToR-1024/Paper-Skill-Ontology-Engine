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


class ExpertExecutionRecordTests(unittest.TestCase):
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
                object_id="P-execution-test",
                payload={
                    "paper_id": "P-execution-test",
                    "stage": "positioning",
                    "title": "Execution Test",
                },
            )
        ]
        write_yaml(project / "events" / "event_log.yml", {"events": events})
        write_yaml(project / "state" / "paper.yml", project_state(events, project / "events"))

    def prepare(self, project: Path) -> Path:
        result = self.run_script(
            "prepare_expert_invocation.py",
            str(project),
            "positioning_expert",
            "--invocation-id",
            "EX-execution-test",
            "--task",
            "Assess the paper position.",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return project / "expert_invocations" / "EX-execution-test"

    def test_prepared_packet_does_not_claim_verified_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)
            invocation = self.prepare(project)

            manifest = read_yaml(invocation / "runner_manifest.yml")

            self.assertEqual(manifest["requested_mode"], "isolated_worker")
            self.assertEqual(manifest["execution"]["backend"], "unassigned")
            self.assertFalse(manifest["execution"]["isolation_verified"])

    def test_fallback_requires_reason_and_is_visible_to_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.seed_project(project)
            invocation = self.prepare(project)

            missing_reason = self.run_script(
                "record_expert_execution.py",
                str(invocation),
                "--backend",
                "current_agent_fallback",
                "--recorded-by",
                "main-agent",
            )
            self.assertNotEqual(missing_reason.returncode, 0)
            self.assertIn("reason is required", missing_reason.stdout + missing_reason.stderr)

            recorded = self.run_script(
                "record_expert_execution.py",
                str(invocation),
                "--backend",
                "current_agent_fallback",
                "--recorded-by",
                "main-agent",
                "--reason",
                "The host platform has no isolated worker runtime.",
            )
            self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)

            manifest = read_yaml(invocation / "runner_manifest.yml")
            self.assertEqual(manifest["execution"]["backend"], "current_agent_fallback")
            self.assertFalse(manifest["execution"]["isolation_verified"])

            report = validate_project(
                project,
                max_section_content_chars=1500,
                max_total_section_content_chars=3000,
                allow_no_citations=True,
            )
            self.assertIn("current_agent_fallback", "\n".join(report["warnings"]))
            self.assertEqual(
                report["expert_executions"][0]["backend"],
                "current_agent_fallback",
            )


if __name__ == "__main__":
    unittest.main()
