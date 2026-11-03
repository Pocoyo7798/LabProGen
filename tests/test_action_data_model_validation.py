import copy
import unittest

from labprogen.core.chemicals import (
    embedded_chemical_type_choices,
    selectable_chemical_entity_types,
)
from labprogen.core.config import FIELD_CONFIG, LEGACY_FIELD_PREFERENCES, KEY_SUBSTANCE_LIST, migrate_action_params
from labprogen.core.model import field_config
from labprogen.linkml.adapter import chemical_record_to_instance
from labprogen.linkml.exporter import convert_protocol_to_linkml
from labprogen.linkml.loader import ACTION_DATA_MODEL_SCHEMA, listed_action_classes, listed_chemical_classes, load_linkml_schema
from labprogen.linkml.validator import validate_linkml_protocol


PDF_ACTIONS = {
    "Add",
    "Grind",
    "Separate",
    "NoAction",
    "ChangePressure",
    "ChangeTemperature",
    "ChangeAgitation",
    "ChangeContainer",
    "CollectSubProduct",
    "Repeat",
    "ContinuousAddition",
}

PDF_CHEMICALS = {
    "ChemicalEntity",
    "Substance",
    "MixtureConstituent",
    "Mixture",
    "BioProducts",
    "Molecule",
    "Polymer",
    "Medium",
    "PorousMaterial",
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
                        "action": "NoAction",
                        "params": {"duration": "10 min"},
                        "chemicals": [],
                    },
                    {
                        "block_id": "heat1",
                        "action": "ChangeTemperature",
                        "params": {
                            "temperature": "80 °C",
                            "process": "Plate-heater",
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
        "Molecule": {
            "chemical_type": "Molecule",
            "name": "ethanol",
            "formula": "C2H6O",
            "smile": "CCO",
        },
        "Polymer": {
            "chemical_type": "Polymer",
            "name": "PEG",
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
        "PorousMaterial": {
            "chemical_type": "PorousMaterial",
            "formula": "TiO2",
        },
    }
    for name in ("Copolymer", "PolymerMixture", "CopolymerMixture", "BioProductsMixture",
                 "PorousMaterialMixture", "Zeolite", "ZeoliteMixture", "Cell"):
        samples.setdefault(name, {"chemical_type": name})
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
    def test_current_schema_actions_and_chemicals(self):
        schema = load_linkml_schema(ACTION_DATA_MODEL_SCHEMA)
        self.assertEqual(schema.get("name"), "action-data-model")
        self.assertEqual(listed_action_classes(schema), PDF_ACTIONS)
        self.assertTrue(PDF_CHEMICALS.issubset(listed_chemical_classes(schema)))
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
            "labprogen.linkml.exporter", fromlist=["_build_protocol_export"]
        )._build_protocol_export(protocol)
        step = payload["activities"][0]["laboratory_actions"][0]
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
                                        "chemical": "Molecule",
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
        slots = payload["activities"][0]["laboratory_actions"][0]["slots"]
        substances = slots["chemical"]
        self.assertEqual(len(substances), 2)
        self.assertEqual(substances[0]["type"], "Substance")
        self.assertEqual(substances[0]["name"], "water")
        self.assertEqual(substances[1]["type"], "Molecule")
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
        self.assertNotIn(KEY_SUBSTANCE_LIST, FIELD_CONFIG)
        self.assertFalse(field_config(KEY_SUBSTANCE_LIST, "ContinuousAddition")["declared"])
        config = LEGACY_FIELD_PREFERENCES[KEY_SUBSTANCE_LIST]
        self.assertEqual(config["type"], "list")
        self.assertFalse(config.get("include_concentration"))

    def test_migrate_empty_substance_list_string_to_list(self):
        migrated = migrate_action_params("ContinuousAddition", {KEY_SUBSTANCE_LIST: ""})
        self.assertEqual(migrated["chemical"], [])
        kept = migrate_action_params("ContinuousAddition", {KEY_SUBSTANCE_LIST: "water"})
        self.assertEqual(kept["chemical"], "water")

    def test_substance_list_picker_offers_all_chemical_entity_types(self):
        selectable = selectable_chemical_entity_types()
        self.assertEqual(len(selectable), 15)
        self.assertIn("Cell", selectable)
        self.assertIn("Copolymer", selectable)
        self.assertNotIn("Dispersion", selectable)
        self.assertNotIn("MixtureConstituent", selectable)
        self.assertNotIn("ChemicalEntity", selectable)
        self.assertEqual(
            embedded_chemical_type_choices(for_solvent=False, include_concentration=False),
            selectable,
        )
        mixture_choices = embedded_chemical_type_choices(
            for_solvent=False, include_concentration=True
        )
        self.assertEqual(set(mixture_choices), set(selectable))

    def test_all_chemical_entity_types_are_valid_in_substance_list(self):
        for type_name in selectable_chemical_entity_types():
            protocol = _continuous_addition_protocol([_minimal_chemical_entity(type_name)])
            errors = [msg for msg in validate_linkml_protocol(protocol) if msg.level == "error"]
            self.assertEqual(errors, [], msg=f"{type_name} was rejected: {errors}")
            payload = convert_protocol_to_linkml(protocol, mode="strict")
            exported = payload["activities"][0]["laboratory_actions"][0]["slots"]["chemical"]
            self.assertEqual(exported[0]["type"], type_name)

    def test_medium_with_empty_concentration_key_stays_medium(self):
        medium = {
            "chemical_type": "Medium",
            "name": "LB",
            "quantity": "1 L",
            "concentration": "",
            "chemical_list": [
                {
                    "chemical_type": "Polymer",
                    "name": "PEG",
                                        "bigsmiles": "[*]OCC[*]",
                    "concentration": "1 g/L",
                }
            ],
        }
        instance = chemical_record_to_instance(medium)
        self.assertEqual(instance["type"], "Medium")
        self.assertNotIn("concentration", instance)
        nested = instance["chemical_list"][0]
        self.assertEqual(nested["type"], "MixtureConstituent")
        self.assertEqual(nested["concentration"], "1 g/L")
        self.assertEqual(nested["chemical"]["type"], "Polymer")

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
                            "chemical_type": "Polymer",
                            "name": "PEG",
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
        medium = payload["activities"][0]["laboratory_actions"][0]["slots"]["chemical"][0]
        self.assertEqual(medium["type"], "Medium")
        item = medium["chemical_list"][0]
        self.assertEqual(item["type"], "MixtureConstituent")
        self.assertEqual(item["concentration"], polymer_concentration)
        self.assertEqual(item["chemical"]["type"], "Polymer")
        self.assertEqual(item["chemical"]["bigsmiles"], "[*]OCC[*]")

    def test_legacy_dispersion_is_preserved_but_rejected(self):
        entity = _minimal_chemical_entity("Dispersion")
        original = copy.deepcopy(entity)
        protocol = _continuous_addition_protocol([entity])
        self.assertTrue(_error_codes(validate_linkml_protocol(protocol)))
        with self.assertRaises(ValueError):
            convert_protocol_to_linkml(protocol)
        self.assertEqual(entity, original)

    def test_nested_mixture_substance_missing_concentration_still_fails(self):
        protocol = _continuous_addition_protocol(
            [
                {
                    "chemical_type": "Medium",
                    "name": "LB",
                    "quantity": "1 L",
                    "chemical_list": [
                        {
                            "chemical_type": "Polymer",
                            "name": "PEG",
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
        self.assertTrue(any("concentration" in text and "MixtureConstituent" in text for text in messages))

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

    def test_complex_members_still_require_current_model_fields(self):
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
        self.assertTrue(errors)
        self.assertIn("validation.required_field_missing", {m.code for m in errors})
        with self.assertRaises(ValueError):
            convert_protocol_to_linkml(protocol, mode="strict")


if __name__ == "__main__":
    unittest.main()
