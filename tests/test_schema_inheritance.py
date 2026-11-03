"""Contracts introduced by the current Action Data Model's class hierarchy."""

import copy

import pytest

from labprogen.linkml.loader import (
    build_validation_schema,
    class_slot_constraints,
    ensure_six_meta_path_importer_compatibility,
    listed_action_classes,
)


@pytest.fixture(scope="module")
def schema():
    return build_validation_schema()


def test_concrete_actions_include_indirect_descendants(schema):
    actions = listed_action_classes(schema)
    assert {"Add", "NoAction", "ChangeContainer", "Repeat"} <= actions
    assert not {"Action", "OneOffAction", "PersistentAction", "DirectPersistentAction"} & actions


def test_constraints_include_inherited_mixins_and_required_overrides(schema):
    polymer = class_slot_constraints("Copolymer", schema)
    assert {"repeat_units", "copolymer_type", "bigsmiles", "entity_producer"} <= polymer["allowed"]
    assert "name" not in polymer["required"]
    zeolite = class_slot_constraints("Zeolite", schema)
    assert {"frameworks", "si_al_ratio", "n2_adsorption_bet_area"} <= zeolite["allowed"]
    cell = class_slot_constraints("Cell", schema)
    assert {"species_name", "passage_number", "genetic_modifications"} <= cell["allowed"]


@pytest.mark.parametrize(
    ("class_name", "instance", "invalid"),
    [
        (
            "Cell",
            {"type": "Cell", "species_name": "Escherichia coli", "passage_number": 3,
             "genetic_modifications": [{"construct": "pLab"}]},
            {"passage_number": "not an integer"},
        ),
        (
            "Copolymer",
            {"type": "Copolymer", "copolymer_type": "random",
             "repeat_units": [{"formula": "C2H4"}, {"formula": "C3H6"}]},
            {"repeat_units": [{"formula": "C2H4"}]},
        ),
        (
            "Zeolite",
            {"type": "Zeolite", "si_al_ratio": "10", "frameworks": [{"framework_code": "MFI"}],
             "n2_adsorption_bet_area": "400 m2/g"},
            {"frameworks": [{"name": "missing framework code"}]},
        ),
        (
            "Separate",
            {"type": "Separate", "method": {"type": "Filtration", "phase_to_keep": "Solid",
                                               "filter_pore_size": "1 µm"}},
            {"method": {"type": "Filtration", "phase_to_keep": "Organic"}},
        ),
    ],
)
def test_current_model_accepts_valid_instances_and_rejects_invalid_values(
    schema, class_name, instance, invalid
):
    ensure_six_meta_path_importer_compatibility()
    from linkml.validator import validate

    assert not validate(instance, schema=schema, target_class=class_name, strict=True).results
    bad = copy.deepcopy(instance)
    bad.update(invalid)
    assert validate(bad, schema=schema, target_class=class_name, strict=True).results
