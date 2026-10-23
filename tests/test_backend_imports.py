"""Keep API startup independent of packages available only in worker images."""

from pathlib import Path
import subprocess
import sys
import unittest


class BackendImportTests(unittest.TestCase):
    def test_uvicorn_can_load_api_without_worker_packages(self):
        script = """
import importlib.abc
import sys

class BlockWorkerPackages(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'offers_bot', 'pydantic_ai', 'playwright'}:
            raise ModuleNotFoundError(f'Worker-only package imported: {fullname}')

sys.meta_path.insert(0, BlockWorkerPackages())
from uvicorn.importer import import_from_string
app = import_from_string('backend.app.main:app')
assert any(route.path == '/health' for route in app.routes)
assert not any(name.startswith('offers_bot') for name in sys.modules)
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
