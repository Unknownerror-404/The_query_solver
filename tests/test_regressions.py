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


if __name__ == "__main__":
    unittest.main()
