import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.core.paths import (
    config_read_candidates,
    get_app_dir,
    get_bundle_dir,
    get_config_dir,
    resolve_config_read_path,
    seed_writable_config_from_bundle,
    writable_config_path,
)


class TestAppPaths(unittest.TestCase):
    def test_source_runtime_uses_project_root(self):
        root = Path(__file__).resolve().parent.parent
        self.assertEqual(get_app_dir(), root)
        self.assertEqual(get_config_dir(), root / "config")

    def test_frozen_runtime_uses_executable_directory(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            exe_path = tmp_path / "LabProGen.exe"
            exe_path.write_text("", encoding="utf-8")
            bundle_path = tmp_path / "bundle"
            bundle_path.mkdir()

            with patch.object(sys, "frozen", True, create=True), patch.object(
                sys, "executable", str(exe_path), create=True
            ), patch.object(sys, "_MEIPASS", str(bundle_path), create=True):
                self.assertEqual(get_app_dir(), exe_path.parent)
                self.assertEqual(get_config_dir(), exe_path.parent / "config")
                self.assertEqual(get_bundle_dir(), bundle_path)

    def test_config_read_candidates_prefers_writable_config_dir(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            writable = tmp_path / "config" / "complex_actions.json"
            bundled = tmp_path / "bundle" / "config" / "complex_actions.json"
            writable.parent.mkdir(parents=True)
            bundled.parent.mkdir(parents=True)
            writable.write_text('{"version": 1, "complex_actions": []}', encoding="utf-8")
            bundled.write_text('{"version": 1, "complex_actions": [{"name": "Bundled"}]}', encoding="utf-8")

            with patch("src.core.paths.get_config_dir", return_value=tmp_path / "config"), patch(
                "src.core.paths.get_bundle_dir", return_value=tmp_path / "bundle"
            ):
                candidates = config_read_candidates("complex_actions.json")
                self.assertEqual(candidates[0], writable)
                self.assertEqual(candidates[1], bundled)
                self.assertEqual(resolve_config_read_path("complex_actions.json"), writable)

    def test_seed_writable_config_from_bundle_creates_user_copy(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            source = tmp_path / "bundle" / "config" / "complex_actions.json"
            target = tmp_path / "config" / "complex_actions.json"
            source.parent.mkdir(parents=True)
            source.write_text('{"version": 1, "complex_actions": []}', encoding="utf-8")

            with patch("src.core.paths.get_bundle_dir", return_value=tmp_path / "bundle"), patch(
                "src.core.paths.writable_config_path", return_value=target
            ):
                seeded = seed_writable_config_from_bundle("complex_actions.json")

            self.assertEqual(seeded, target)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
