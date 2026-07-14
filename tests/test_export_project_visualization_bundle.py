from __future__ import annotations

import json
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

from export_project_visualization import project_state  # noqa: E402


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")


class ExportProjectVisualizationBundleTests(unittest.TestCase):
    def test_cli_exports_complete_visualization_data_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            events = [
                {
                    "offset": 1,
                    "event_id": "EVT-000001",
                    "timestamp": "2026-07-07T00:00:01Z",
                    "actor": "user",
                    "function": "create_object",
                    "action_type": "paper.created",
                    "object_type": "Paper",
                    "object_id": "P-test",
                    "payload": {"paper_id": "P-test", "title": "Visualization Bundle Test", "stage": "idea"},
                }
            ]
            write_yaml(project_dir / "events" / "event_log.yml", {"events": events})
            write_yaml(project_dir / "state" / "paper.yml", project_state(events))

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "export_project_visualization.py"),
                    str(project_dir),
                ],
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("visualization_data:", result.stdout)

            bundle_path = project_dir / "visualization" / "visualization.json"
            self.assertTrue(bundle_path.exists())
            data = json.loads(bundle_path.read_text(encoding="utf-8"))
            self.assertEqual(data["project"]["paper_id"], "P-test")
            self.assertIn("events", data)
            self.assertIn("objects", data)
            self.assertIn("graph", data)
            self.assertIn("story", data)
            self.assertIn("literature", data)
            self.assertIn("provenance", data)
            self.assertIn("expert_executions", data)
            for filename in ("literature.json", "provenance.json", "expert_executions.json"):
                self.assertTrue((project_dir / "visualization" / filename).exists(), filename)


if __name__ == "__main__":
    unittest.main()
