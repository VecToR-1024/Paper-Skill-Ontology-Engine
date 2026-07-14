from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_project_visualization import build_graph_data, project_state, render_html  # noqa: E402


def event(
    offset: int,
    *,
    action_type: str,
    object_type: str,
    object_id: str,
    function: str,
    payload: dict[str, Any],
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "offset": offset,
        "event_id": f"EVT-{offset:06d}",
        "timestamp": f"2026-07-07T00:00:{offset:02d}Z",
        "actor": "positioning_expert",
        "function": function,
        "action_type": action_type,
        "object_type": object_type,
        "object_id": object_id,
        "payload": payload,
    }
    if approval is not None:
        data["approval"] = approval
    return data


class VisualizationObjectHistoryTests(unittest.TestCase):
    def test_graph_nodes_include_direct_object_event_history(self) -> None:
        events = [
            event(
                1,
                action_type="paper.created",
                object_type="Paper",
                object_id="P-test",
                function="create_object",
                payload={"paper_id": "P-test", "title": "Object History Test"},
            ),
            event(
                2,
                action_type="claim.created",
                object_type="Claim",
                object_id="C-main",
                function="create_object",
                payload={"claim_id": "C-main", "paper_id": "P-test", "text": "Original claim."},
            ),
            event(
                3,
                action_type="claim.updated",
                object_type="Claim",
                object_id="C-main",
                function="update_object",
                payload={"claim_id": "C-main", "text": "Scoped claim.", "strength": "weak"},
                approval={"status": "approved", "approved_by": "tester"},
            ),
        ]

        graph = build_graph_data(project_state(events), events)
        nodes = {node["id"]: node for node in graph["nodes"]}

        self.assertIn("C-main", nodes)
        history = nodes["C-main"]["event_history"]
        self.assertEqual([entry["action_type"] for entry in history], ["claim.created", "claim.updated"])
        self.assertEqual(history[1]["function"], "update_object")
        self.assertEqual(history[1]["approval_status"], "approved")

    def test_html_has_object_event_history_panel(self) -> None:
        html = render_html({"project": {}, "story": {}, "graph": {"nodes": [], "edges": []}})

        self.assertIn("Event history", html)
        self.assertIn("event-history-list", html)
        self.assertIn("event-history-row", html)


if __name__ == "__main__":
    unittest.main()
