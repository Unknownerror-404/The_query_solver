"""Regression checks for application/module integration contracts."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent.parent


def module_exports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    exports: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            exports.add(node.name)
        elif isinstance(node, ast.Assign):
            exports.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            exports.add(node.target.id)
    return exports


class TestApplicationIntegrationContracts(unittest.TestCase):
    def test_fastapi_imports_only_existing_map_exports(self):
        app_tree = ast.parse((ROOT / "app_fastapi.py").read_text(encoding="utf-8"))
        map_exports = module_exports(ROOT / "map.py")
        missing = []
        for node in ast.walk(app_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "map":
                missing.extend(alias.name for alias in node.names if alias.name not in map_exports)
        self.assertEqual(missing, [])

    def test_storage_exposes_persistent_proposal_vote_function(self):
        exports = module_exports(ROOT / "storage.py")
        self.assertIn("cast_proposal_vote", exports)

    def test_storage_exposes_communication_summary_function(self):
        exports = module_exports(ROOT / "storage.py")
        self.assertIn("load_communication_summary", exports)

    def test_text_artifact_scanner_script_exists(self):
        self.assertTrue((ROOT / "artifact_scan.py").exists())

    def test_case_communication_storage_preserves_visibility(self):
        import storage

        storage._MEM_CASE_EVENTS.clear()
        storage._MEM_CASE_MESSAGES.clear()
        storage.create_case_event(1, "submitted", "citizen@test.example", "community", "Case submitted")
        storage.create_case_message(1, "citizen@test.example", "community", "Public update", visibility="public")
        storage.create_case_message(1, "uni@test.example", "university", "Participant update")

        public_messages = storage.load_case_messages(1)
        participant_messages = storage.load_case_messages(1, include_participants=True)
        participant_events = storage.load_case_events(1, include_participants=True)

        self.assertEqual([item["message"] for item in public_messages], ["Public update"])
        self.assertEqual(
            {item["message"] for item in participant_messages},
            {"Public update", "Participant update"},
        )
        self.assertEqual(storage.load_case_events(1)[0]["event_type"], "submitted")
        self.assertEqual(participant_events[0]["event_type"], "submitted")

    def test_fastapi_case_routes_are_declared(self):
        source = (ROOT / "app_fastapi.py").read_text(encoding="utf-8")
        self.assertIn('@app.get("/api/cases/{issue_id}")', source)
        self.assertIn('@app.post("/api/cases/{issue_id}/messages")', source)

    def test_case_room_is_reachable_from_frontend_issue_views(self):
        template = (ROOT / "templates" / "case_room.html").read_text(encoding="utf-8")
        community_source = (ROOT / "community.py").read_text(encoding="utf-8")
        map_source = (ROOT / "map.py").read_text(encoding="utf-8")
        self.assertIn("Case timeline", template)
        self.assertIn("case-message-form", template)
        self.assertIn('href="/cases/{issue["id"]}"', community_source)
        self.assertIn('href=\"/cases/{issue[\"id\"]}\"', map_source)

    def test_legacy_server_supports_case_room_routes(self):
        source = (ROOT / "map.py").read_text(encoding="utf-8")
        self.assertIn('if path.startswith("/cases/")', source)
        self.assertIn('if path.startswith("/api/cases/") and path.endswith("/messages")', source)

    def test_role_dashboards_link_associated_problems_to_case_room(self):
        source = (ROOT / "map.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(source.count("/cases/{issue_id}"), 3)
        self.assertIn("/cases/{a.get('issue_id')}", source)
        self.assertIn("/cases/{resp['issue_id']}", source)
        self.assertIn("/cases/{issue['id']}", source)

    def test_pending_reports_are_visible_to_institutions_as_read_only_cases(self):
        map_source = (ROOT / "map.py").read_text(encoding="utf-8")
        fastapi_source = (ROOT / "app_fastapi.py").read_text(encoding="utf-8")
        self.assertIn("New community reports awaiting moderation", map_source)
        self.assertIn("Awaiting government moderation", map_source)
        self.assertIn("role in {\"university\", \"industry\"}", fastapi_source)

    def test_case_updates_fan_out_notifications_without_self_notification(self):
        app_source = (ROOT / "app_fastapi.py").read_text(encoding="utf-8")
        legacy_source = (ROOT / "map.py").read_text(encoding="utf-8")
        self.assertIn("case_notification_recipients(issue_id, user)", app_source)
        self.assertIn("case_notification_recipients(issue_id, user)", legacy_source)
        self.assertIn("recipients.discard(str(sender).strip().lower())", app_source)
        self.assertIn("recipients.discard(str(sender).strip().lower())", legacy_source)
        self.assertIn('"case_message"', app_source)


if __name__ == "__main__":
    unittest.main()
