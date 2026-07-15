import copy
import unittest

from src.linkml.adapter import build_material_entity, convert_linkml_to_protocol
from src.linkml.exporter import (
    _expand_optimized_export,
    convert_protocol_to_linkml,
)


class TestLinkMLExportModes(unittest.TestCase):
    def setUp(self):
        self.protocol = {
            "protocol_name": "Minimal test",
            "flows": [
                {
                    "flow_id": "flow1",
                    "type": "test",
                    "steps": [
                        {
                            "block_id": "step1",
                            "action": "Add",
                            "params": {"chemical": "water"},
                            "chemicals": [],
                        }
                    ],
                }
            ],
        }

    def test_strict_export_is_default_and_lossless(self):
        strict_payload = convert_protocol_to_linkml(self.protocol)
        roundtrip = convert_linkml_to_protocol(strict_payload)

        self.assertNotIn("materials", strict_payload)
        self.assertEqual(roundtrip, self.protocol)

    def test_optimized_export_is_deterministic(self):
        optimized_1 = convert_protocol_to_linkml(self.protocol, mode="optimized")
        optimized_2 = convert_protocol_to_linkml(self.protocol, mode="optimized")

        self.assertEqual(optimized_1, optimized_2)
        self.assertIn("materials", optimized_1)
        self.assertEqual(optimized_1["summary"]["unique_materials"], 1)
        self.assertEqual(optimized_1["summary"]["reference_count"], 1)

    def test_optimized_roundtrip_reconstructs_strict_shape(self):
        strict_payload = convert_protocol_to_linkml(self.protocol)
        optimized_payload = convert_protocol_to_linkml(self.protocol, mode="optimized")
        reconstructed = _expand_optimized_export(copy.deepcopy(optimized_payload))

        self.assertEqual(reconstructed["activities"], strict_payload["activities"])
        # Both sides should either include or omit source snapshots; current
        # behavior omits the internal `source_protocol` to avoid duplication.
        self.assertEqual(reconstructed.get("source_protocol"), strict_payload.get("source_protocol"))
        self.assertNotIn("materials", reconstructed)

    def test_material_entity_ids_are_stable(self):
        first = build_material_entity("water")
        second = build_material_entity("water")
        different_case = build_material_entity("Water")

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["entity_id"], second["entity_id"])
        self.assertNotEqual(first["id"], different_case["id"])


if __name__ == "__main__":
    unittest.main()
