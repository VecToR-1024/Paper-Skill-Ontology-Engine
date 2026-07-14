from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_project_visualization import render_html  # noqa: E402


class VisualizationAuditSeparationTests(unittest.TestCase):
    def test_action_function_inventory_lives_in_audit_debug_section(self) -> None:
        html = render_html({"project": {}, "story": {}, "action_inventory": {}})

        self.assertIn('id="audit-debug"', html)
        self.assertIn("Audit / Debug Details", html)

        change_start = html.index("<h2>Change Timeline</h2>")
        issues_start = html.index("<h2>Open Review Issues</h2>")
        change_section = html[change_start:issues_start]
        self.assertNotIn("Action Type / Function Inventory", change_section)
        self.assertNotIn('id="action-inventory"', change_section)

        audit_start = html.index('id="audit-debug"')
        audit_section = html[audit_start:]
        self.assertIn("Action Type / Function Inventory", audit_section)
        self.assertIn('id="action-inventory"', audit_section)


if __name__ == "__main__":
    unittest.main()
