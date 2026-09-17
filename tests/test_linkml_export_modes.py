import copy
import unittest

from src.linkml.adapter import build_material_entity, convert_linkml_to_protocol
from src.linkml.exporter import (
    _expand_optimized_export,
    convert_protocol_to_linkml,
)


def _valid_protocol():
    return {
        "protocol_name": "Minimal ADM test",
        "flows": [
            {
                "flow_id": "flow1",
                "type": "test",
                "steps": [
                    {
                        "block_id": "step1",
                        "action": "Add",
                        "params": {
                            "duration": "5 s",
                            "add_quantity": "1 g",
                            "add_type": "Normal",
                            "open_flame": "False",
                        },
                        "chemicals": [
                            {
                                "block_id": "chem1",
                                "chemical": "Substance",
                                "params": {"name": "water"},
                            }
                        ],
                    }
                ],
            }
        ],
    }


class TestLinkMLExportModes(unittest.TestCase):
    def setUp(self):
        self.protocol = _valid_protocol()

    def test_strict_export_is_default_and_roundtrips_actions(self):
        strict_payload = convert_protocol_to_linkml(self.protocol)
        roundtrip = convert_linkml_to_protocol(strict_payload)

        self.assertNotIn("materials", strict_payload)
        self.assertEqual(roundtrip["protocol_name"], self.protocol["protocol_name"])
        self.assertEqual(roundtrip["flows"][0]["steps"][0]["action"], "Add")
        self.assertEqual(roundtrip["flows"][0]["steps"][0]["params"]["add_type"], "Normal")
        self.assertEqual(roundtrip["flows"][0]["steps"][0]["chemicals"][0]["chemical"], "Substance")
        self.assertEqual(roundtrip["flows"][0]["steps"][0]["chemicals"][0]["params"]["name"], "water")

    def test_optimized_export_is_deterministic(self):
        optimized_1 = convert_protocol_to_linkml(self.protocol, mode="optimized")
        optimized_2 = convert_protocol_to_linkml(self.protocol, mode="optimized")

        self.assertEqual(optimized_1, optimized_2)
        self.assertIn("materials", optimized_1)
        reconstructed = _expand_optimized_export(copy.deepcopy(optimized_1))
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
