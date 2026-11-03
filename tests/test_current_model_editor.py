"""The editor and semantic round trips follow the current schema contract."""
import copy

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLineEdit, QMessageBox, QPushButton, QScrollArea, QToolButton

from labprogen.core.model import concrete_classes, default_params, field_config
from labprogen.core.protocol import Protocol
from labprogen.linkml.adapter import convert_linkml_to_protocol
from labprogen.linkml.exporter import convert_protocol_to_linkml
from labprogen.linkml.loader import class_slot_constraints, load_linkml_schema
from labprogen.linkml.validator import validate_linkml_protocol
from labprogen.ui.block import ChemicalBlock, ElementaryAction
from labprogen.ui.editor import ActionSelectionDialog, Editor, UnifiedChemicalDetailsDialog
from labprogen.ui.schema_fields import SchemaRecordDialog, SchemaValueField


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def protocol(steps):
    return {"protocol_name": "Current model – água", "flows": [{"flow_id": 1, "type": "horizontal", "steps": steps}]}


def steps():
    entity = {"type": "Cell", "species_name": "Escherichia coli", "passage_number": 3,
              "genetic_modifications": [{"construct": "pLab"}]}
    params = {
        "Add": {"duration": "5 s", "add_type": "Normal", "open_flame": "False"},
        "Grind": {"duration": "1 min"},
        "Separate": {"method": {"type": "Sieving", "size_range": "1 - 2 mm", "phase_to_keep": "Oversize"}},
        "NoAction": {"duration": "1 min"},
        "ChangeContainer": {"recipient": "Beaker", "material": "Glass", "volume": "100 mL"},
        "CollectSubProduct": {"phase_to_keep": "Solid"},
        "Repeat": {"amount": "2"},
        "ChangePressure": {"pressure": "100 kPa"},
        "ChangeTemperature": {"process": "Plate-heater", "temperature": "40 °C"},
        "ChangeAgitation": {"agitation_type": "Magnetic", "speed": "100 rpm"},
        "ContinuousAddition": {"chemical": [entity], "continuous_add_type": "Continuous", "flow_rate": "1 mL/min"},
    }
    result = [{"block_id": i, "action": name, "params": value, "chemicals": []}
              for i, (name, value) in enumerate(params.items(), 1)]
    result[0]["chemicals"] = [{"block_id": 50, "chemical": "Substance", "params": {"name": "water", "quantity": "1 g"}}]
    return result


@pytest.mark.parametrize("mode", ["strict", "optimized"])
def test_all_current_actions_roundtrip_without_source_snapshot(mode):
    original = protocol(steps())
    payload = convert_protocol_to_linkml(original, mode=mode)
    payload.pop("source_protocol", None)
    restored = convert_linkml_to_protocol(payload)
    assert [s["action"] for s in restored["flows"][0]["steps"]] == [s["action"] for s in steps()]
    assert restored["flows"][0]["steps"][-1]["params"]["chemical"][0]["passage_number"] == 3
    assert not [m for m in validate_linkml_protocol(restored) if m.level == "error"]
    again = convert_protocol_to_linkml(restored)
    assert again["activities"][0]["laboratory_actions"][2]["slots"]["method"]["phase_to_keep"] == "Oversize"


@pytest.mark.parametrize("method,phase", [("Filtration", "Solid"), ("Centrifugation", "Liquid"),
    ("Sieving", "Undersize"), ("Decantation", "Organic"), ("Evaporation", "Gas")])
def test_typed_separation_dialog_and_export(app, method, phase, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    value = {"type": method, "phase_to_keep": phase}
    if method == "Sieving":
        value["size_range"] = "1 mm"
    dialog = SchemaRecordDialog("SeparationMethod", value)
    assert dialog.selector.currentText() == method
    assert phase in [dialog.trackers["phase_to_keep"].itemText(i) for i in range(dialog.trackers["phase_to_keep"].count())]
    dialog._accept_value()
    assert dialog.value == value
    assert not warnings
    output = convert_protocol_to_linkml(protocol([{"action": "Separate", "params": {"method": dialog.value}}]))
    assert output["activities"][0]["laboratory_actions"][0]["slots"]["method"] == value
    dialog.deleteLater()


def test_separation_type_switch_keeps_drafts_and_rejects_wrong_phase(app, monkeypatch):
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog = SchemaRecordDialog("SeparationMethod", {"type": "Filtration", "phase_to_keep": "Organic"})
    dialog._accept_value()
    assert warnings and dialog.value is None
    dialog.selector.setCurrentText("Sieving")
    assert "size_range" in dialog.trackers
    dialog.selector.setCurrentText("Filtration")
    assert dialog.trackers["phase_to_keep"].currentText() == "Organic"
    dialog.reject()


@pytest.mark.parametrize("class_name,key,value", [
    ("Cell", "genetic_modifications", [{"construct": "pLab"}]),
    ("Copolymer", "repeat_units", [{"formula": "C2H4"}, {"formula": "C3H6"}]),
    ("Zeolite", "frameworks", [{"framework_code": "MFI"}]),
])
def test_nested_fields_remain_editable_and_roundtrip(app, class_name, key, value):
    dialog = SchemaRecordDialog(class_name, {"type": class_name, key: value})
    assert isinstance(dialog.trackers[key], SchemaValueField)
    assert dialog.trackers[key].get_value() == value
    dialog._accept_value()
    assert dialog.value[key] == value
    item = steps()[-1]
    item["params"]["chemical"] = [dialog.value]
    output = convert_protocol_to_linkml(protocol([item]))
    output.pop("source_protocol", None)
    restored = convert_linkml_to_protocol(output)
    assert restored["flows"][0]["steps"][0]["params"]["chemical"][0][key] == value
    dialog.deleteLater()


def test_picker_and_defaults_use_only_current_contract(app):
    dialog = ActionSelectionDialog()
    assert "Sieve" not in dialog.btn_elementary
    assert "ChangeContainer" in dialog.btn_elementary
    assert "ChangeContainer" not in dialog.btn_support
    for name in concrete_classes("Action") + concrete_classes("ChemicalEntity"):
        assert set(default_params(name)) <= class_slot_constraints(name)["allowed"]
    assert "concentration" not in default_params("Medium")
    assert "formula" not in default_params("Polymer")
    assert "substance" not in default_params("CollectSubProduct")
    assert "add_quantity" not in default_params("Add")
    assert "chemical" in default_params("ContinuousAddition")
    details = UnifiedChemicalDetailsDialog(chemical_type="Mixture")
    assert details.purity_edit.isHidden()
    details._accept()
    assert "entity_purity" not in details.first_level_fields
    details.deleteLater(); dialog.deleteLater()


def test_cell_block_scrolls_and_saves_integer_and_nested_values(app, monkeypatch):
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: errors.append(args[2]))
    block = ChemicalBlock("Cell", default_params("Cell"))
    observed = {}
    def interact():
        try:
            dialog = app.activeModalWidget()
            assert dialog.findChild(QScrollArea) is not None
            for toggle in dialog.findChildren(QToolButton):
                if toggle.text() == "Advanced parameters":
                    toggle.click()
            field = dialog.findChild(QLineEdit, "passage_number")
            field.setText("3")
            assert dialog.height() < 900
            next(b for b in dialog.findChildren(QPushButton) if b.text() == "Save Changes").click()
            observed["ok"] = True
        except Exception as exc:
            observed["error"] = repr(exc)
            QDialog.reject(app.activeModalWidget())
    QTimer.singleShot(0, interact)
    block.open_editor()
    assert observed == {"ok": True}
    assert not errors
    assert block.params["passage_number"] == 3


def test_editor_reconstructs_current_actions_and_exports(app):
    editor = Editor()
    original = protocol(steps())
    editor.load_protocol_data(original)
    assert isinstance(next(b for b in editor.blocks if b.action == "ChangeContainer"), ElementaryAction)
    regenerated = editor.generate_protocol_output(show_feedback=False)
    assert regenerated is not None
    assert not [m for m in validate_linkml_protocol(regenerated) if m.level == "error"]
    assert len(convert_protocol_to_linkml(regenerated)["activities"][0]["laboratory_actions"]) == 11
    editor.container.close()


def test_legacy_aliases_and_quantity_migrate_losslessly():
    old = {"action": "Add", "params": {"duration": "1 s", "add_type": "Normal", "open_flame": "False", "add_quantity": "3 g"},
           "chemicals": [{"chemical": "Molecules", "params": {"name": "water", "formula": "H2O", "smile": "O"}}]}
    original = copy.deepcopy(old)
    payload = convert_protocol_to_linkml(protocol([old]))
    entity = payload["activities"][0]["laboratory_actions"][0]["slots"]["chemical"][0]
    assert entity["type"] == "Molecule" and entity["quantity"] == "3 g"
    assert old == original
    old["chemicals"][0]["params"]["quantity"] = "4 g"
    with pytest.raises(ValueError, match="Conflicting"):
        convert_protocol_to_linkml(protocol([old]))


def test_legacy_incompatible_records_preserved_for_review():
    legacy = protocol([{"action": "Sieve", "params": {"size_range": "1 mm"},
                        "chemicals": [{"chemical": "Dispersion", "params": {"solvent": {"name": "water"}}}]}])
    restored = Protocol.from_dict(legacy).to_dict()[0]
    assert restored["action"] == "Separate"
    assert restored["params"]["method"] == {"type": "Sieving", "size_range": "1 mm"}
    assert restored["chemicals"][0]["chemical"] == "Dispersion"
    assert restored["chemicals"][0]["params"]["solvent"] == {"name": "water"}
    assert [m for m in validate_linkml_protocol(legacy) if m.level == "error"]


def test_unknown_nested_fields_are_not_discarded():
    item = steps()[2]
    item["params"]["method"]["unrecognized"] = "keep for review"
    before = copy.deepcopy(item)
    with pytest.raises(ValueError):
        convert_protocol_to_linkml(protocol([item]))
    assert item == before


def test_preparation_procedure_has_schema_string_representation_and_roundtrip():
    item = steps()[0]
    prep = protocol([steps()[3]])
    item["chemicals"][0]["params"]["preparation_procedure"] = prep
    output = convert_protocol_to_linkml(protocol([item]))
    assert isinstance(output["activities"][0]["laboratory_actions"][0]["slots"]["chemical"][0]["preparation_procedure"], str)
    output.pop("source_protocol", None)
    restored = convert_linkml_to_protocol(output)
    assert restored["flows"][0]["steps"][0]["chemicals"][0]["params"]["preparation_procedure"] == prep


def test_subproduct_branch_is_validated_and_roundtrips():
    item = steps()[2]
    item["subproduct_branch"] = {"action": "CollectSubProduct", "params": {"phase_to_keep": "Solid"}}
    output = convert_protocol_to_linkml(protocol([item]))
    restored = convert_linkml_to_protocol(output)
    assert restored["flows"][0]["steps"][0]["subproduct_branch"]["params"]["phase_to_keep"] == "Solid"
    item["subproduct_branch"]["params"] = {}
    with pytest.raises(ValueError, match="phase_to_keep"):
        convert_protocol_to_linkml(protocol([item]))


def test_conflicting_inline_and_attached_chemicals_are_not_dropped():
    item = steps()[-1]
    item["chemicals"] = [{"chemical": "Substance", "params": {"name": "water"}}]
    with pytest.raises(ValueError, match="Conflicting"):
        convert_protocol_to_linkml(protocol([item]))


def test_domain_type_argument_alias_maps_to_current_slot():
    from labprogen.core.actions import Add
    action = Add(type="Normal", duration="1 s", open_flame="False")
    assert action.params["add_type"] == "Normal"
    assert "type" not in action.params


def test_unstructured_legacy_field_is_not_silently_replaced(app):
    block = ElementaryAction("ContinuousAddition", {})
    widget, tracker = block._get_field_widget("chemical", "water, ethanol")
    assert isinstance(widget, QLineEdit) and tracker.text() == "water, ethanol"
    nested = SchemaValueField(field_config("repeat_units", "Copolymer"), "old draft")
    assert nested.get_value() == "old draft"
    nested._clear_legacy()
    assert nested.get_value() == []
