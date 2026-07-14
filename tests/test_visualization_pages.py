from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_project_visualization import render_html  # noqa: E402


class VisualizationPagesTests(unittest.TestCase):
    def test_visualization_is_split_into_route_like_pages(self) -> None:
        html = render_html({"project": {}, "story": {}, "graph": {"nodes": [], "edges": []}})

        self.assertIn('aria-label="Visualization pages"', html)
        for page_id in ("overview", "graph", "timeline", "issues", "evidence-files", "audit"):
            self.assertIn(f'data-page-target="{page_id}"', html)
            self.assertIn(f'data-page="{page_id}"', html)

        self.assertIn("function initPageRouting()", html)
        self.assertIn("hashchange", html)
        self.assertIn("hidden = !isActive", html)


if __name__ == "__main__":
    unittest.main()
