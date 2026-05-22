import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.schema_loader import get_schema_directory


class TestSchemaDirectoryResolution(unittest.TestCase):
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
