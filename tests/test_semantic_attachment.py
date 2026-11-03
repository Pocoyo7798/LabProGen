"""Semantic attachment roles across renamed fields and protocol representations."""
import copy
import importlib.util
import json
import sys

import pytest
import yaml
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QLineEdit, QPushButton

from labprogen.core import model
from labprogen.core.actions import Add
from labprogen.core.chemicals import Substance
from labprogen.core.capabilities import (
    CHEMICAL_ATTACHMENT_ANNOTATION as ROLE, ChemicalAttachmentRoleError,
    chemical_attachment_slot, get_action_capabilities, requires_canvas_chemical,
)
from labprogen.core.config import validate_schema_references
from labprogen.linkml import loader, models, exporter, validator
from labprogen.linkml.adapter import chemical_record_to_instance, convert_linkml_to_protocol
from labprogen.linkml.exporter import convert_protocol_to_linkml
from labprogen.text.procedure_text import chemical_names_from_step, sentence_for_step
from labprogen.ui.block import ChemicalBlock
from labprogen.ui.editor import Editor
from tools.generate_models import generate_source, DEFAULT_SCHEMA


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope='module')
def renamed(tmp_path_factory):
    original = DEFAULT_SCHEMA.read_bytes()
    schema = copy.deepcopy(loader.load_linkml_schema())
    schema['slots']['chemical_entity'] = schema['slots'].pop('chemical')
    schema['slots']['chemical_entity']['annotations'] = {ROLE: True}
    for definition in schema['classes'].values():
        if 'slots' in definition:
            definition['slots'] = ['chemical_entity' if name == 'chemical' else name for name in definition['slots']]
        for section in ['attributes', 'slot_usage']:
            values = definition.get(section, {})
            if 'chemical' in values:
                values['chemical_entity'] = values.pop('chemical')
    path = tmp_path_factory.mktemp('semantic-attachment') / 'action_data_model.yaml'
    path.write_text(yaml.safe_dump(schema, sort_keys=False), encoding='utf-8')
    target = path.parent / 'models.py'
    target.write_text(generate_source(path), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('renamed_chemical_models', target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield schema, module
        assert DEFAULT_SCHEMA.read_bytes() == original
    finally:
        sys.modules.pop(spec.name, None)


def activate(monkeypatch, renamed):
    schema, generated = renamed
    view = loader.schema_view(schema)
    monkeypatch.setattr(loader, '_default_schema_view', lambda: view)
    monkeypatch.setattr(model, 'model_schema', lambda: schema)
    monkeypatch.setattr(models, 'action_data_model', generated)
    monkeypatch.setattr('labprogen.ui.schema_fields.model_schema', lambda: schema)
    monkeypatch.setattr(exporter, 'load_linkml_schema', lambda *args: schema)
    monkeypatch.setattr(validator, 'build_validation_schema', lambda *args: loader._strip_unsupported_metamodel_keys(schema))


def test_global_rename_resolves_action_and_composition_roles(renamed, monkeypatch):
    schema, _ = renamed
    activate(monkeypatch, renamed)
    for name in ['Add', 'ContinuousAddition']:
        capability = get_action_capabilities(name)
        assert capability.allows_chemical_blocks and capability.chemical_slot == 'chemical_entity'
        assert requires_canvas_chemical(name)
        assert not requires_canvas_chemical(name, params={'chemical_entity': [{'type': 'Substance', 'name': 'water'}]})
        assert model.field_config('chemical_entity', name)['label'] == 'Chemical'
    assert chemical_attachment_slot('MixtureConstituent') == 'chemical_entity'
    assert not get_action_capabilities('MixtureConstituent').allows_chemical_blocks
    assert not validate_schema_references(schema)
    action = Add(duration='1 s', add_type='Normal', open_flame='False')
    action.add_chemical(Substance(name='water'))
    assert action.to_model().chemical_entity[0].name == 'water'


@pytest.mark.parametrize('name', ['Add', 'ContinuousAddition'])
@pytest.mark.parametrize('mode', ['strict', 'optimized'])
def test_renamed_role_canvas_edit_export_import_and_nested_composition(app, renamed, monkeypatch, name, mode):
    activate(monkeypatch, renamed)
    params = {'duration': '1 s', 'add_type': 'Normal', 'open_flame': 'False'} if name == 'Add' else {
        'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous', 'chemical_entity': []}
    editor = Editor()
    action = editor._create_block_by_name(name, params)
    action.is_first = True
    chemical = ChemicalBlock('Mixture', {'name': 'mixture', 'chemical_list': [
        {'chemical_type': 'Substance', 'name': 'water', 'concentration': '1 g/L'}]}, editor=editor)
    editor.scene.addItem(chemical)
    editor.blocks.append(chemical)
    assert editor._link_chemical_to_parent(chemical, action)
    seen = []
    def save():
        dialog = app.activeModalWidget()
        try:
            assert dialog.findChild(QLineEdit, 'chemical_entity') is None
            seen.append(True)
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Save Changes').click()
        finally:
            if dialog.isVisible():
                dialog.reject()
    QTimer.singleShot(0, save)
    action.open_editor()
    assert seen == [True]
    native = editor.generate_protocol_output(False)
    payload = convert_protocol_to_linkml(native, mode)
    instance = payload['activities'][0]['laboratory_actions'][0]['slots']
    assert 'chemical' not in instance and instance['chemical_entity'][0]['chemical_list'][0]['chemical_entity']['name'] == 'water'
    restored = Editor()
    restored.load_protocol_data(json.loads(json.dumps(payload)))
    assert not restored.import_warnings
    restored_action = next(b for b in restored.blocks if b.action == name)
    assert restored_action.chem_below.action == 'Mixture'
    row = restored_action.chem_below.params['chemical_list'][0]
    assert row['chemical_entity']['name'] == 'water'
    assert not [m for m in validator.validate_linkml_protocol(restored.generate_protocol_output(False)) if m.level == 'error']
    editor.container.close()
    restored.container.close()


def test_renamed_inline_field_and_guide_use_the_same_role(renamed, monkeypatch):
    activate(monkeypatch, renamed)
    step = {'action': 'ContinuousAddition', 'params': {'chemical_entity': [
        {'type': 'Substance', 'name': 'water'}], 'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous'}}
    assert chemical_names_from_step(step) == ['water']
    assert 'water' in sentence_for_step(step)
    payload = convert_protocol_to_linkml({'flows': [{'steps': [step]}]})
    restored = convert_linkml_to_protocol(payload)
    assert restored['flows'][0]['steps'][0]['params']['chemical_entity'][0]['name'] == 'water'


def test_complex_bindings_follow_the_renamed_field(app, renamed, monkeypatch):
    activate(monkeypatch, renamed)
    from labprogen.complex import actions
    from labprogen.complex.protocol import materialize_complex_action
    registry = actions.ComplexActionRegistry()
    monkeypatch.setattr(actions, '_GLOBAL_REGISTRY', registry)
    steps = [{'action': 'ContinuousAddition', 'params': {'chemical_entity': [],
        'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous'}}, {'action': 'Repeat', 'params': {'amount': '2'}}]
    definition = actions.ComplexActionDefinition('Renamed role', steps, actions.build_parameter_bindings(steps))
    registry.register(definition)
    editor = Editor()
    group = materialize_complex_action(editor, definition.name, actions.copy_instance_parameters(definition))
    action = group.member_blocks[0]
    action.is_first = True
    chemical = ChemicalBlock('Substance', {'name': 'water'}, editor=editor)
    editor.scene.addItem(chemical)
    editor.blocks.append(chemical)
    assert editor._link_chemical_to_parent(chemical, action)
    payload = convert_protocol_to_linkml(editor.generate_protocol_output(False))
    restored = Editor()
    restored.load_protocol_data(payload)
    assert not restored.import_warnings and len(restored.complex_action_groups) == 1
    binding = next(p for p in next(iter(restored.complex_action_groups.values())).parameters if p.param_key == 'chemical_entity')
    assert binding.value == []
    editor.container.close()
    restored.container.close()


def test_inherited_inline_roles_and_slot_usage_overrides():
    schema = copy.deepcopy(loader.load_linkml_schema())
    schema['classes']['RoleMixin'] = {'mixin': True, 'attributes': {
        'primary': {'range': 'Substance', 'inlined': True, 'annotations': {ROLE: True}}}}
    schema['classes']['ParentRole'] = {'is_a': 'Action', 'mixins': ['RoleMixin']}
    schema['classes']['ChildRole'] = {'is_a': 'ParentRole', 'slot_usage': {'primary': {'required': True}}}
    assert chemical_attachment_slot('ChildRole', schema=schema) == 'primary'
    assert get_action_capabilities('ChildRole', schema=schema).requires_chemical_relation
    schema['classes']['ChildRole']['slot_usage']['primary']['required'] = False
    assert get_action_capabilities('ChildRole', schema=schema).allows_chemical_blocks
    assert not get_action_capabilities('ChildRole', schema=schema).requires_chemical_relation
    schema['classes']['ChildRole']['slot_usage']['primary']['annotations'] = {ROLE: False}
    assert not get_action_capabilities('ChildRole', schema=schema).allows_chemical_blocks


def test_multiple_relations_choose_only_the_marked_role_and_report_ambiguity():
    schema = copy.deepcopy(loader.load_linkml_schema())
    schema['classes']['Add']['attributes'] = {'reagent': {'range': 'ChemicalEntity', 'annotations': {ROLE: True}}}
    assert get_action_capabilities('Add', schema=schema).chemical_slot == 'reagent'
    schema['slots']['chemical']['annotations'] = {ROLE: True}
    with pytest.raises(ChemicalAttachmentRoleError, match='multiple chemical attachment fields'):
        get_action_capabilities('Add', schema=schema)
    assert any('multiple chemical attachment fields' in error for error in validate_schema_references(schema))
    schema['classes']['Add']['attributes']['reagent']['annotations'] = {ROLE: False}
    assert chemical_attachment_slot('Add', schema=schema) == 'chemical'


@pytest.mark.parametrize('value', ['perhaps', 1, {'value': 'perhaps'}])
def test_invalid_role_values_are_explicit_errors(value):
    schema = copy.deepcopy(loader.load_linkml_schema())
    schema['slots']['chemical']['annotations'] = {ROLE: value}
    with pytest.raises((ChemicalAttachmentRoleError, ValueError), match='boolean|value|Value'):
        get_action_capabilities('Add', schema=schema)


def test_incompatible_role_and_removed_field_do_not_grant_permission(renamed):
    schema = copy.deepcopy(renamed[0])
    schema['classes']['Add']['slot_usage']['chemical_entity']['range'] = 'string'
    with pytest.raises(ChemicalAttachmentRoleError, match='range'):
        get_action_capabilities('Add', schema=schema)
    schema['classes']['Add']['slots'].remove('chemical_entity')
    schema['classes']['Add']['slot_usage'].pop('chemical_entity')
    assert not get_action_capabilities('Add', schema=schema).allows_chemical_blocks


def test_old_semantic_fields_require_explicit_migration(renamed, monkeypatch):
    activate(monkeypatch, renamed)
    old = {'flows': [{'steps': [{'action': 'ContinuousAddition', 'params': {'chemical': [
        {'type': 'Substance', 'name': 'water'}], 'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous'}}]}]}
    before = copy.deepcopy(old)
    with pytest.raises(ValueError):
        convert_protocol_to_linkml(old)
    assert old == before
    composition = {'type': 'MixtureConstituent', 'chemical': {'type': 'Substance', 'name': 'water'}, 'concentration': '1 g/L'}
    projected = chemical_record_to_instance(composition)
    assert projected['chemical']['name'] == 'water' and 'chemical_entity' not in projected


def test_unmarked_rename_is_not_inferred_from_range(renamed):
    schema = copy.deepcopy(renamed[0])
    schema['slots']['chemical_entity'].pop('annotations')
    assert not get_action_capabilities('Add', schema=schema).allows_chemical_blocks


def test_native_composition_wrapper_keeps_its_nested_entity():
    record = {'chemical': 'MixtureConstituent', 'params': {
        'chemical': {'type': 'Substance', 'name': 'water'}, 'concentration': '1 g/L'}}
    projected = chemical_record_to_instance(record)
    assert projected == {'type': 'MixtureConstituent',
                         'chemical': {'type': 'Substance', 'name': 'water'}, 'concentration': '1 g/L'}


def test_old_and_current_composition_fields_remain_available(renamed, monkeypatch):
    activate(monkeypatch, renamed)
    row = {'type': 'MixtureConstituent',
           'chemical': {'type': 'Substance', 'name': 'old'},
           'chemical_entity': {'type': 'Substance', 'name': 'current'},
           'concentration': '1 g/L'}
    assert chemical_record_to_instance(row) == row
    old_entity = {'type': 'Substance', 'name': 'historical', 'chemical': row['chemical']}
    assert chemical_record_to_instance(old_entity) == old_entity


@pytest.mark.parametrize('value', [None, [], 'historical value'])
def test_incompatible_historical_composition_values_are_retained(renamed, monkeypatch, value):
    activate(monkeypatch, renamed)
    row = {'type': 'MixtureConstituent', 'chemical': value, 'concentration': '1 g/L'}
    assert chemical_record_to_instance(row) == row


def test_renamed_inline_relation_remains_editable(app, renamed, monkeypatch):
    from PySide6.QtWidgets import QWidget

    activate(monkeypatch, renamed)
    editor = Editor()
    block = editor._create_block_by_name('ContinuousAddition', {
        'chemical_entity': [{'type': 'Substance', 'name': 'water'}],
        'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous'})
    block.is_first = True
    errors = []

    def save():
        dialog = app.activeModalWidget()
        try:
            widget = dialog.findChild(QWidget, 'chemical_entity')
            field = widget._chemical_list_field
            assert field.param_key == 'chemical_entity'
            field.list_value[0]['name'] = 'ethanol'
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Save Changes').click()
        except Exception as exc:
            errors.append(exc)
            dialog.accept()

    QTimer.singleShot(0, save)
    block.open_editor()
    assert not errors
    assert block.params['chemical_entity'][0]['name'] == 'ethanol'
    convert_protocol_to_linkml(editor.generate_protocol_output(False))
    editor.container.close()


def test_renamed_composition_picker_edits_the_nested_entity(app, renamed, monkeypatch):
    from labprogen.ui.editor import (
        MixtureChemicalDialog, UnifiedChemicalDetailsDialog, pick_embedded_chemical,
    )

    activate(monkeypatch, renamed)
    row = {'type': 'MixtureConstituent',
           'chemical_entity': {'type': 'Substance', 'name': 'water'}, 'concentration': '1 g/L'}
    before = copy.deepcopy(row)
    stages = []
    errors = []

    def advance():
        dialog = app.activeModalWidget()
        try:
            if isinstance(dialog, MixtureChemicalDialog):
                assert dialog.type_combo.currentData() == 'Substance'
                stages.append('type')
                dialog._accept()
                QTimer.singleShot(0, advance)
            elif isinstance(dialog, UnifiedChemicalDetailsDialog):
                stages.append('identity')
                dialog._accept()
                QTimer.singleShot(0, advance)
            else:
                name = dialog.findChild(QLineEdit, 'name')
                assert name.text() == 'water'
                name.setText('ethanol')
                stages.append('parameters')
                next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Save Changes').click()
        except Exception as exc:
            errors.append(exc)
            dialog.accept()

    QTimer.singleShot(0, advance)
    edited = pick_embedded_chemical(None, row)
    assert not errors and stages == ['type', 'identity', 'parameters']
    assert row == before
    projected = chemical_record_to_instance(edited, mixture_item=True)
    assert projected['chemical_entity']['name'] == 'ethanol'
    assert projected['concentration'] == '1 g/L' and 'chemical' not in projected


def test_historical_composition_requires_migration_before_editing(app, renamed, monkeypatch):
    from labprogen.ui.editor import QMessageBox, pick_embedded_chemical

    activate(monkeypatch, renamed)
    warnings = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: warnings.append(args[2]))
    row = {'type': 'MixtureConstituent', 'chemical': {'type': 'Substance', 'name': 'water'},
           'chemical_entity': {'type': 'Substance', 'name': 'ethanol'}, 'concentration': '1 g/L'}
    before = copy.deepcopy(row)
    assert pick_embedded_chemical(None, row) is None
    assert warnings and row == before
