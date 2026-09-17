"""Regression checks for application/module integration contracts."""

from __future__ import annotations

import ast
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent


def module_exports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
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
    def test_fastapi_registers_core_workflow_endpoints(self):
        import app_fastapi

        registered = {
            (route.path, method)
            for route in app_fastapi.app.routes
            for method in (route.methods or set())
        }
        required = {
            ("/login", "POST"),
            ("/api/issues", "POST"),
            ("/api/proposals", "POST"),
            ("/api/proposals/{proposal_id}/vote", "POST"),
            ("/api/university/assignment-response", "POST"),
            ("/api/notifications", "GET"),
            ("/api/notifications/{notification_id}/read", "POST"),
            ("/api/notifications/read-all", "POST"),
            ("/api/messages", "GET"),
            ("/api/messages", "POST"),
            ("/api/industry/offers", "POST"),
            ("/api/contractor/assignment-status", "POST"),
        }
        self.assertTrue(required.issubset(registered), sorted(required - registered))

    def test_map_import_does_not_load_embedding_stack(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import map; assert 'sentence_transformers' not in sys.modules",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

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

    def test_government_dashboard_review_button_routes_to_moderation_queue(self):
        template = (ROOT / "templates" / "government.html").read_text(encoding="utf-8")

        self.assertIn('href="/admin"', template)
        self.assertNotIn('href="/government-dashboard">Review Now', template)

    def test_exif_coordinate_parser_handles_pillow_rational_tuples(self):
        from AI_model import _exif_coordinate

        gps = {
            1: "N",
            2: ((23, 1), (11, 1), (30, 1)),
            3: "E",
            4: ((85, 1), (18, 1), (30, 1)),
        }

        self.assertAlmostEqual(_exif_coordinate(gps, 2, 1), 23.1916666667)
        self.assertAlmostEqual(_exif_coordinate(gps, 4, 3), 85.3083333333)

    def test_geotagged_image_keeps_exif_after_reencode(self):
        from io import BytesIO

        from PIL import Image

        from AI_model import inspect_image_proof, sanitize_and_reencode_image

        img = Image.new("RGB", (10, 10), color="red")
        exif = Image.Exif()
        exif[34853] = {
            1: "N",
            2: ((23, 1), (11, 1), (30, 1)),
            3: "E",
            4: ((85, 1), (18, 1), (30, 1)),
        }

        buf = BytesIO()
        img.save(buf, format="JPEG", exif=exif)
        sanitized, _ = sanitize_and_reencode_image(buf.getvalue(), "image/jpeg")

        result = inspect_image_proof(sanitized, 23.1916666667, 85.3083333333)
        self.assertEqual(result["status"], "verified")


if __name__ == "__main__":
    unittest.main()
