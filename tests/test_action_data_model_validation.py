import copy
import unittest

from src.core.chemicals import (
    embedded_chemical_type_choices,
    selectable_chemical_entity_types,
)
from src.core.config import FIELD_CONFIG, KEY_SUBSTANCE_LIST, migrate_action_params
from src.linkml.adapter import chemical_record_to_instance
from src.linkml.exporter import convert_protocol_to_linkml
from src.linkml.loader import listed_action_classes, listed_chemical_classes, load_linkml_schema
from src.linkml.validator import validate_linkml_protocol


PDF_ACTIONS = {
    "Add",
    "Grind",
    "Separate",
    "Sieve",
    "NoModification",
    "ChangePressure",
    "ChangeTemperature",
    "ChangeAgitation",
    "ChangeRecipient",
    "CollectSubProduct",
    "Repeat",
    "ContinuousAddition",
}

PDF_CHEMICALS = {
    "ChemicalEntity",
    "Substance",
    "MixtureSubstance",
    "Mixture",
    "BioProducts",
    "Molecules",
    "Polymers",
    "Medium",
    "Dispersion",
    "HeterogeneousCatalysts",
}


def _valid_protocol():
    return {
        "protocol_name": "ADM valid procedure",
        "flows": [
            {
                "flow_id": "flow1",
                "type": "horizontal",
                "steps": [
                    {
                        "block_id": "add1",
                        "action": "Add",
                        "params": {
                            "duration": "10 s",
                            "add_quantity": "5 g",
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
                    },
                    {
                        "block_id": "wait1",
                        "action": "NoModification",
                        "params": {"duration": "10 min"},
                        "chemicals": [],
                    },
                    {
                        "block_id": "heat1",
                        "action": "ChangeTemperature",
                        "params": {
                            "temperature": "80 °C",
                            "process": "Electrical",
                        },
                        "chemicals": [],
                    },
                    {
                        "block_id": "repeat1",
                        "action": "Repeat",
                        "params": {"amount": "2"},
                        "chemicals": [],
                    },
                ],
            }
        ],
    }


def _error_codes(messages):
    return {msg.code for msg in messages if msg.level == "error"}


def _mixture_item():
    return {"chemical_type": "Substance", "name": "NaCl", "concentration": "1 M"}


def _minimal_chemical_entity(type_name: str) -> dict:
    nested_substance = {"chemical_type": "Substance", "name": "water"}
    samples = {
        "Substance": {"chemical_type": "Substance", "name": "water"},
        "Mixture": {
            "chemical_type": "Mixture",
            "name": "brine",
            "chemical_list": [_mixture_item()],
        },
        "Molecules": {
            "chemical_type": "Molecules",
            "name": "ethanol",
            "formula": "C2H6O",
            "smile": "CCO",
        },
        "Polymers": {
            "chemical_type": "Polymers",
            "name": "PEG",
            "formula": "(C2H4O)n",
            "bigsmiles": "[*]OCC[*]",
        },
        "Medium": {
            "chemical_type": "Medium",
            "name": "LB",
            "quantity": "1 L",
            "chemical_list": [_mixture_item()],
        },
        "Dispersion": {
            "chemical_type": "Dispersion",
            "name": "sol",
            "chemical_list": [_mixture_item()],
            "solvent": nested_substance,
        },
        "BioProducts": {
            "chemical_type": "BioProducts",
            "name": "enzyme",
            "toxicity_to_producer": "neutral",
        },
        "HeterogeneousCatalysts": {
            "chemical_type": "HeterogeneousCatalysts",
            "formula": "TiO2",
        },
    }
    return samples[type_name]


def _continuous_addition_protocol(substance_list):
    return {
        "protocol_name": "Continuous addition",
        "flows": [
            {
                "flow_id": "flow1",
                "type": "horizontal",
                "steps": [
                    {
                        "block_id": "ca1",
                        "action": "ContinuousAddition",
                        "params": {
                            "substance_list": substance_list,
                            "continuous_add_type": "Continuous",
                            "amount": "1",
                            "flow_rate": "1 mL/min",
                        },
                        "chemicals": [],
                    }
                ],
            }
        ],
    }


class TestActionDataModelValidation(unittest.TestCase):
    def test_schema_contains_pdf_actions_and_chemicals_only(self):
        schema = load_linkml_schema()
        self.assertEqual(schema.get("name"), "action-data-model")
        self.assertEqual(listed_action_classes(), PDF_ACTIONS)
        self.assertTrue(PDF_CHEMICALS.issubset(listed_chemical_classes()))
        self.assertNotIn("WashingStep", schema.get("classes", {}))
        self.assertNotIn("SolutionPreparationStep", schema.get("classes", {}))
        self.assertNotIn("Material", schema.get("classes", {}))
        self.assertNotIn("PerfectSingleCrystalMaterial", schema.get("classes", {}))

    def test_valid_procedure_passes(self):
        messages = validate_linkml_protocol(_valid_protocol())
        errors = [msg for msg in messages if msg.level == "error"]
        self.assertEqual(errors, [])
        payload = convert_protocol_to_linkml(_valid_protocol(), mode="strict")
        self.assertEqual(payload["class"], "LabProcedure")
        self.assertEqual(payload["summary"]["step_count"], 4)

    def test_unknown_action_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][1]["action"] = "Teleport"
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("mapping.unknown_action", codes)
        with self.assertRaises(ValueError):
            convert_protocol_to_linkml(protocol, mode="strict")

    def test_unknown_field_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][0]["params"]["secret_bypass"] = "yes"
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.unknown_field", codes)

    def test_missing_required_field_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][0]["params"].pop("add_type")
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.required_field_missing", codes)

    def test_wrong_type_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][1]["params"]["duration"] = {"not": "a string"}
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.wrong_type", codes)

    def test_invalid_enum_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][0]["params"]["add_type"] = "Sprinkle"
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.invalid_enum", codes)

    def test_unknown_chemical_entity_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][0]["chemicals"][0]["chemical"] = "Unobtainium"
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("mapping.unknown_chemical", codes)

    def test_unknown_chemical_field_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][0]["chemicals"][0]["params"]["hidden_slot"] = "x"
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.unknown_field", codes)

    def test_missing_chemical_required_field_is_rejected(self):
        protocol = _valid_protocol()
        protocol["flows"][0]["steps"][0]["chemicals"][0]["params"].pop("name")
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.required_field_missing", codes)

    def test_undeclared_fields_are_not_stripped_before_validation(self):
        protocol = copy.deepcopy(_valid_protocol())
        protocol["flows"][0]["steps"][0]["params"]["not_in_schema"] = "1"
        payload, _, _, _, unmapped = __import__(
            "src.linkml.exporter", fromlist=["_build_protocol_export"]
        )._build_protocol_export(protocol)
        step = payload["activities"][0]["has_synthesis_step"][0]
        self.assertIn("not_in_schema", step.get("slots", {}))
        self.assertGreaterEqual(unmapped, 1)

    def test_continuous_addition_substance_list_objects_pass(self):
        protocol = {
            "protocol_name": "Continuous addition",
            "flows": [
                {
                    "flow_id": "flow1",
                    "type": "horizontal",
                    "steps": [
                        {
                            "block_id": "ca1",
                            "action": "ContinuousAddition",
                            "params": {
                                "substance_list": [
                                    {"chemical_type": "Substance", "name": "water"},
                                    {
                                        "chemical": "Molecules",
                                        "params": {
                                            "name": "ethanol",
                                            "formula": "C2H6O",
                                            "smile": "CCO",
                                        },
                                    },
                                ],
                                "continuous_add_type": "Continuous",
                                "amount": "3",
                                "flow_rate": "1 mL/min",
                            },
                            "chemicals": [],
                        }
                    ],
                }
            ],
        }
        errors = [msg for msg in validate_linkml_protocol(protocol) if msg.level == "error"]
        self.assertEqual(errors, [])
        payload = convert_protocol_to_linkml(protocol, mode="strict")
        slots = payload["activities"][0]["has_synthesis_step"][0]["slots"]
        substances = slots["substance_list"]
        self.assertEqual(len(substances), 2)
        self.assertEqual(substances[0]["type"], "Substance")
        self.assertEqual(substances[0]["name"], "water")
        self.assertEqual(substances[1]["type"], "Molecules")
        self.assertEqual(substances[1]["smile"], "CCO")

    def test_continuous_addition_plain_text_substance_list_is_rejected(self):
        protocol = {
            "protocol_name": "Continuous addition text",
            "flows": [
                {
                    "flow_id": "flow1",
                    "type": "horizontal",
                    "steps": [
                        {
                            "block_id": "ca1",
                            "action": "ContinuousAddition",
                            "params": {
                                "substance_list": "water, ethanol",
                                "continuous_add_type": "Continuous",
                                "amount": "1",
                                "flow_rate": "1 mL/min",
                            },
                            "chemicals": [],
                        }
                    ],
                }
            ],
        }
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.wrong_type", codes)

    def test_substance_list_field_config_is_chemical_object_list(self):
        config = FIELD_CONFIG[KEY_SUBSTANCE_LIST]
        self.assertEqual(config["type"], "list")
        self.assertFalse(config.get("include_concentration"))

    def test_migrate_empty_substance_list_string_to_list(self):
        migrated = migrate_action_params("ContinuousAddition", {KEY_SUBSTANCE_LIST: ""})
        self.assertEqual(migrated[KEY_SUBSTANCE_LIST], [])
        kept = migrate_action_params("ContinuousAddition", {KEY_SUBSTANCE_LIST: "water"})
        self.assertEqual(kept[KEY_SUBSTANCE_LIST], "water")

    def test_substance_list_picker_offers_all_chemical_entity_types(self):
        selectable = selectable_chemical_entity_types()
        self.assertEqual(
            set(selectable),
            {
                "Substance",
                "Mixture",
                "Molecules",
                "Polymers",
                "Medium",
                "Dispersion",
                "BioProducts",
                "HeterogeneousCatalysts",
            },
        )
        self.assertNotIn("MixtureSubstance", selectable)
        self.assertNotIn("ChemicalEntity", selectable)
        self.assertEqual(
            embedded_chemical_type_choices(for_solvent=False, include_concentration=False),
            selectable,
        )
        mixture_choices = embedded_chemical_type_choices(
            for_solvent=False, include_concentration=True
        )
        self.assertNotEqual(set(mixture_choices), set(selectable))

    def test_all_chemical_entity_types_are_valid_in_substance_list(self):
        for type_name in selectable_chemical_entity_types():
            protocol = _continuous_addition_protocol([_minimal_chemical_entity(type_name)])
            errors = [msg for msg in validate_linkml_protocol(protocol) if msg.level == "error"]
            self.assertEqual(errors, [], msg=f"{type_name} was rejected: {errors}")
            payload = convert_protocol_to_linkml(protocol, mode="strict")
            exported = payload["activities"][0]["has_synthesis_step"][0]["slots"]["substance_list"]
            self.assertEqual(exported[0]["type"], type_name)

    def test_medium_with_empty_concentration_key_stays_medium(self):
        medium = {
            "chemical_type": "Medium",
            "name": "LB",
            "quantity": "1 L",
            "concentration": "",
            "chemical_list": [
                {
                    "chemical_type": "Polymers",
                    "name": "PEG",
                    "formula": "(C2H4O)n",
                    "bigsmiles": "[*]OCC[*]",
                    "concentration": "1 g/L",
                }
            ],
        }
        instance = chemical_record_to_instance(medium)
        self.assertEqual(instance["type"], "Medium")
        self.assertNotIn("concentration", instance)
        nested = instance["chemical_list"][0]
        self.assertEqual(nested["type"], "MixtureSubstance")
        self.assertEqual(nested["concentration"], "1 g/L")
        self.assertEqual(nested["chemical"]["type"], "Polymers")

    def test_substance_list_medium_preserves_nested_polymer_concentration(self):
        polymer_concentration = "12 g/L"
        protocol = _continuous_addition_protocol(
            [
                {
                    "chemical_type": "Medium",
                    "name": "LB",
                    "quantity": "1 L",
                    "concentration": "",
                    "chemical_list": [
                        {
                            "chemical_type": "Polymers",
                            "name": "PEG",
                            "formula": "(C2H4O)n",
                            "bigsmiles": "[*]OCC[*]",
                            "concentration": polymer_concentration,
                        }
                    ],
                }
            ]
        )
        errors = [msg for msg in validate_linkml_protocol(protocol) if msg.level == "error"]
        self.assertEqual(errors, [])
        payload = convert_protocol_to_linkml(protocol, mode="strict")
        medium = payload["activities"][0]["has_synthesis_step"][0]["slots"]["substance_list"][0]
        self.assertEqual(medium["type"], "Medium")
        item = medium["chemical_list"][0]
        self.assertEqual(item["type"], "MixtureSubstance")
        self.assertEqual(item["concentration"], polymer_concentration)
        self.assertEqual(item["chemical"]["type"], "Polymers")
        self.assertEqual(item["chemical"]["bigsmiles"], "[*]OCC[*]")

    def test_nested_mixture_dispersion_preserves_structured_fields(self):
        protocol = _continuous_addition_protocol(
            [
                {
                    "chemical_type": "Mixture",
                    "name": "feed",
                    "chemical_list": [
                        {
                            "chemical_type": "Dispersion",
                            "name": "sol",
                            "concentration": "10 vol/vol",
                            "chemical_list": [
                                {
                                    "chemical_type": "Molecules",
                                    "name": "solute",
                                    "formula": "NaCl",
                                    "smile": "[Na+].[Cl-]",
                                    "concentration": "1 M",
                                }
                            ],
                            "solvent": {"chemical_type": "Substance", "name": "water"},
                        }
                    ],
                }
            ]
        )
        errors = [msg for msg in validate_linkml_protocol(protocol) if msg.level == "error"]
        self.assertEqual(errors, [])
        payload = convert_protocol_to_linkml(protocol, mode="strict")
        mixture = payload["activities"][0]["has_synthesis_step"][0]["slots"]["substance_list"][0]
        self.assertEqual(mixture["type"], "Mixture")
        wrapper = mixture["chemical_list"][0]
        self.assertEqual(wrapper["type"], "MixtureSubstance")
        self.assertEqual(wrapper["concentration"], "10 vol/vol")
        dispersion = wrapper["chemical"]
        self.assertEqual(dispersion["type"], "Dispersion")
        self.assertEqual(dispersion["solvent"]["type"], "Substance")
        self.assertEqual(dispersion["solvent"]["name"], "water")
        inner = dispersion["chemical_list"][0]
        self.assertEqual(inner["type"], "MixtureSubstance")
        self.assertEqual(inner["concentration"], "1 M")
        self.assertEqual(inner["chemical"]["type"], "Molecules")

    def test_nested_mixture_substance_missing_concentration_still_fails(self):
        protocol = _continuous_addition_protocol(
            [
                {
                    "chemical_type": "Medium",
                    "name": "LB",
                    "quantity": "1 L",
                    "chemical_list": [
                        {
                            "chemical_type": "Polymers",
                            "name": "PEG",
                            "formula": "(C2H4O)n",
                            "bigsmiles": "[*]OCC[*]",
                        }
                    ],
                }
            ]
        )
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.required_field_missing", codes)
        messages = [
            msg.message
            for msg in validate_linkml_protocol(protocol)
            if msg.level == "error" and msg.code == "validation.required_field_missing"
        ]
        self.assertTrue(any("concentration" in text and "MixtureSubstance" in text for text in messages))

    def test_standalone_add_without_chemical_is_rejected(self):
        protocol = {
            "protocol_name": "Missing chemical",
            "flows": [
                {
                    "flow_id": "flow1",
                    "type": "horizontal",
                    "steps": [
                        {
                            "block_id": "add1",
                            "action": "Add",
                            "params": {
                                "duration": "10 s",
                                "add_quantity": "5 g",
                                "add_type": "Normal",
                                "open_flame": "False",
                            },
                            "chemicals": [],
                        }
                    ],
                }
            ],
        }
        codes = _error_codes(validate_linkml_protocol(protocol))
        self.assertIn("validation.required_field_missing", codes)

    def test_complex_member_add_without_chemical_is_accepted(self):
        protocol = {
            "protocol_name": "Complex Add",
            "flows": [
                {
                    "flow_id": "flow1",
                    "type": "horizontal",
                    "steps": [
                        {
                            "block_id": "add1",
                            "action": "Add",
                            "part_of_complex_action": True,
                            "complex_action_name": "Prep",
                            "params": {
                                "duration": "10 s",
                                "add_quantity": "5 g",
                                "add_type": "Normal",
                                "open_flame": "False",
                            },
                            "chemicals": [],
                        },
                        {
                            "block_id": "sp1",
                            "action": "CollectSubProduct",
                            "part_of_complex_action": True,
                            "params": {"substance": ""},
                            "chemicals": [],
                        },
                        {
                            "block_id": "ca1",
                            "action": "ContinuousAddition",
                            "part_of_complex_action": True,
                            "params": {
                                "substance_list": [],
                                "continuous_add_type": "Continuous",
                                "amount": "1",
                                "flow_rate": "1 mL/min",
                            },
                            "chemicals": [],
                        },
                    ],
                }
            ],
        }
        errors = [msg for msg in validate_linkml_protocol(protocol) if msg.level == "error"]
        self.assertEqual(errors, [])
        payload = convert_protocol_to_linkml(protocol, mode="strict")
        steps = payload["activities"][0]["has_synthesis_step"]
        self.assertEqual(steps[0]["source_action"], "Add")
        self.assertTrue(steps[0].get("part_of_complex_action"))
        self.assertNotIn("chemical", steps[0].get("slots", {}))


if __name__ == "__main__":
    unittest.main()
