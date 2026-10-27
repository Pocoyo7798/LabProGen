import sys
import tempfile
import unittest
from pathlib import Path
import os
from unittest.mock import patch

from labprogen.linkml.loader import get_schema_directory


class TestSchemaDirectoryResolution(unittest.TestCase):
    def test_installed_runtime_ignores_schema_in_working_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            decoy = root / "schema"
            decoy.mkdir()
            bundled = root / "assets" / "schema"
            bundled.mkdir(parents=True)
            previous = Path.cwd()
            try:
                os.chdir(root)
                with patch("labprogen.linkml.loader.get_bundle_dir", return_value=root / "assets"):
                    self.assertEqual(get_schema_directory(), bundled)
            finally:
                os.chdir(previous)

    def test_source_runtime_schema_directory_exists(self):
        schema_dir = get_schema_directory()
        self.assertTrue(schema_dir.exists())
        self.assertEqual(schema_dir.name, "schema")

    def test_frozen_runtime_prefers_meipass_schema(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            schema_path = tmp_path / "schema"
            schema_path.mkdir(parents=True, exist_ok=True)

            with patch.object(sys, "frozen", True, create=True), patch.object(sys, "_MEIPASS", str(tmp_path), create=True):
                resolved = get_schema_directory()

            self.assertEqual(resolved, schema_path)


if __name__ == "__main__":
    unittest.main()
