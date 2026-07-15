import unittest
from unittest.mock import patch

from src.linkml.validator import validate_linkml_protocol
from src.linkml.loader import ensure_six_meta_path_importer_compatibility


class _SixMetaPathImporter:
    pass


class TestSchemaValidator(unittest.TestCase):
    def test_six_meta_path_importer_gets_path(self):
        dummy_importer = _SixMetaPathImporter()
        import sys

        sys.meta_path.append(dummy_importer)
        try:
            ensure_six_meta_path_importer_compatibility()
            self.assertTrue(hasattr(dummy_importer, "_path"))
        finally:
            sys.meta_path.remove(dummy_importer)

    def test_linkml_unavailable_is_reported_as_warning(self):
        with patch.dict("sys.modules", {"linkml": None, "linkml.validator": None}):
            messages = validate_linkml_protocol({"activities": []})

        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].level, "warning")
        self.assertEqual(messages[0].code, "linkml.unavailable")


if __name__ == "__main__":
    unittest.main()