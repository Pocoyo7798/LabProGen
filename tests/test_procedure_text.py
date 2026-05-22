from src.config import KEY_CONCENTRATION, KEY_NAME, KEY_RECIPIENT, KEY_MATERIAL, KEY_VOLUME
from src.procedure_text import (
    build_procedure_text,
    chemical_display_name,
    format_gas_entry_label,
    main_flow_steps_from_protocol,
    sentence_for_step,
)


def test_add_lists_all_chemical_names():
    step = {
        "action": "Add",
        "params": {"add_quantity": "10 g", "add_type": "Normal", "duration": "5 min"},
        "chemicals": [
            {"chemical": "Molecules", "params": {KEY_NAME: "ethanol"}},
            {"chemical": "Substance", "params": {KEY_NAME: "water"}},
        ],
    }
    text = sentence_for_step(step)
    assert "ethanol" in text
    assert "water" in text
    assert "and" in text
    assert "10 g" in text


def test_subproduct_creation_lists_chemicals():
    step = {
        "action": "SubProductCreation",
        "params": {
            "substance": [
                {"chemical": "Substance", "params": {KEY_NAME: "precipitate A"}},
            ]
        },
    }
    assert "precipitate A" in sentence_for_step(step)


def test_excludes_imported_chemical_flows():
    protocol = {
        "flows": [
            {
                "flow_id": 1,
                "steps": [{"action": "Wait", "params": {"duration": "1 min"}}],
            },
            {
                "flow_id": 2,
                "chemical_block_id": 99,
                "steps": [{"action": "Grind", "params": {}}],
            },
        ]
    }
    steps = main_flow_steps_from_protocol(protocol)
    assert len(steps) == 1
    assert steps[0]["action"] == "Wait"


def test_new_recipient_sentence():
    step = {
        "action": "NewRecipient",
        "params": {KEY_RECIPIENT: "Beaker", KEY_MATERIAL: "Glass", KEY_VOLUME: "250 mL"},
    }
    text = sentence_for_step(step)
    assert "Beaker" in text
    assert "Glass" in text


def test_build_procedure_text_empty():
    assert build_procedure_text([]) == "No procedure steps yet."


def test_repeat_uses_singular_time_for_one():
    assert sentence_for_step({"action": "Repeat", "params": {"amount": "1"}}) == (
        "Repeat the previous steps 1 time."
    )
    assert sentence_for_step({"action": "Repeat", "params": {"amount": "3"}}) == (
        "Repeat the previous steps 3 times."
    )


def test_build_procedure_text_numbers_steps():
    text = build_procedure_text(
        [
            {"action": "Wait", "params": {"duration": "1 min"}},
            {"action": "Grind", "params": {}},
        ]
    )
    assert text.startswith("1. Wait for 1 min.")
    assert "2. Grind the material." in text


def test_gas_entry_label_with_concentration():
    label = format_gas_entry_label(
        {"chemical": "Molecules", "params": {KEY_NAME: "nitrogen", KEY_CONCENTRATION: "80 vol/vol"}}
    )
    assert label == "nitrogen (80 vol/vol)"


def test_chemical_display_name_fallback():
    assert chemical_display_name({"chemical": "Material", "params": {}}) == "Material"
