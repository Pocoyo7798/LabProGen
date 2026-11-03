"""Direct canvas relationships follow induced LinkML slots, not action name lists."""
import copy
import importlib.util
import json
import sys
from dataclasses import FrozenInstanceError

import pytest
import yaml
from pydantic import ValidationError
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QPushButton

from labprogen.core import model
from labprogen.core.actions import Add, Grind, ContinuousAddition
from labprogen.core.chemicals import Substance
from labprogen.core.capabilities import can_attach_chemical_blocks, get_action_capabilities, requires_canvas_chemical
from labprogen.core.config import action_requires_attached_chemical
from labprogen.core.protocol import Protocol
from labprogen.linkml import loader, models, exporter
from labprogen.linkml.adapter import chemical_slot_for_action, convert_linkml_to_protocol, project_canvas_chemicals, flatten_exported_instance
from labprogen.linkml.exporter import convert_protocol_to_linkml
from labprogen.linkml.validator import validate_linkml_protocol
from labprogen.ui.block import ChemicalBlock, ElementaryAction, SupportAction, ComplexActionBlock
from labprogen.ui.editor import Editor
from tools.generate_models import generate_source, DEFAULT_SCHEMA


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope='module')
def evolved(tmp_path_factory):
    """A single generated snapshot exercises added/inherited/mixin/inline fields."""
    schema = copy.deepcopy(loader.load_linkml_schema())
    schema['classes']['Grind']['slots'].append('chemical')
    schema['classes']['Grind'].setdefault('slot_usage', {})['chemical'] = {'required': False}
    schema['classes']['InheritedGrind'] = {'is_a': 'Grind'}
    schema['classes']['ChemicalMixin'] = {'mixin': True, 'attributes': {
        'chemical': {'range': 'Substance', 'multivalued': False, 'inlined': True}}}
    schema['classes']['MixedAction'] = {'is_a': 'Action', 'mixins': ['ChemicalMixin']}
    schema['classes']['InlineAction'] = {'is_a': 'Action', 'attributes': {
        'chemical': {'range': 'ChemicalEntity', 'multivalued': True, 'required': True, 'inlined_as_list': True}}}
    schema['classes']['AbstractCarrier'] = {'abstract': True, 'is_a': 'Action', 'slots': ['chemical']}
    schema['classes']['ConcreteCarrier'] = {'is_a': 'AbstractCarrier'}
    schema['classes']['NestedAction'] = {'is_a': 'Action', 'attributes': {
        'container': {'range': 'MixtureConstituent', 'inlined': True}}}
    schema['classes']['OtherFieldAction'] = {'is_a': 'Action', 'attributes': {
        'reagent': {'range': 'ChemicalEntity', 'multivalued': True}}}
    schema['classes']['WrongRangeAction'] = {'is_a': 'Action', 'slots': ['chemical'],
        'slot_usage': {'chemical': {'range': 'string'}}}
    schema['classes']['FakeAction'] = {'slots': ['chemical']}
    path = tmp_path_factory.mktemp('action-capabilities') / 'action_data_model.yaml'
    path.write_text(yaml.safe_dump(schema, sort_keys=False), encoding='utf-8')
    output = path.parent / 'generated.py'; output.write_text(generate_source(path), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('evolved_action_capabilities', output)
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        yield schema, module
    finally:
        sys.modules.pop(spec.name, None)


def activate(monkeypatch, evolved):
    schema, module = evolved
    view = loader.schema_view(schema)
    monkeypatch.setattr(loader, '_default_schema_view', lambda: view)
    monkeypatch.setattr(model, 'model_schema', lambda: schema)
    monkeypatch.setattr(models, 'action_data_model', module)
    monkeypatch.setattr(loader, 'build_validation_schema', lambda *args: loader._strip_unsupported_metamodel_keys(schema))
    monkeypatch.setattr('labprogen.linkml.validator.build_validation_schema', loader.build_validation_schema)
    monkeypatch.setattr(exporter, 'load_linkml_schema', lambda *args: schema)


@pytest.mark.parametrize('name,allowed', [('Add', True), ('ContinuousAddition', True), ('Grind', False),
    ('MixtureConstituent', False), ('ChemicalEntity', False), ('Action', False), ('OneOffAction', False),
    ('MissingClass', False), ('MaterialAdditionStep', False), ('Sieve', False), ('', False), (None, False), (42, False)])
def test_current_capability_is_explicit_and_fail_closed(name, allowed):
    assert can_attach_chemical_blocks(name) is allowed
    assert get_action_capabilities(name).allows_chemical_blocks is allowed


def test_permission_is_independent_of_requiredness_and_canvas_context(evolved):
    schema, generated = evolved
    assert can_attach_chemical_blocks('Grind', schema=schema)
    assert not requires_canvas_chemical('Grind', schema=schema)
    assert can_attach_chemical_blocks('InlineAction', schema=schema)
    assert requires_canvas_chemical('InlineAction', schema=schema)
    assert not requires_canvas_chemical('InlineAction', schema=schema, part_of_complex_action=True)
    assert not requires_canvas_chemical('InlineAction', schema=schema, params={'chemical': [{'type': 'Substance', 'name': 'water'}]})
    with pytest.raises(ValidationError): generated.InlineAction()
    required = copy.deepcopy(schema)
    required['classes']['Grind']['slot_usage']['chemical']['required'] = True
    assert can_attach_chemical_blocks('Grind', schema=required)
    assert requires_canvas_chemical('Grind', schema=required)
    assert get_action_capabilities('ContinuousAddition').requires_chemical_relation
    assert not action_requires_attached_chemical('ContinuousAddition', params={'chemical': [{'type': 'Substance', 'name': 'water'}]})
    with pytest.raises(FrozenInstanceError): get_action_capabilities('Add').allows_chemical_blocks = False


@pytest.mark.parametrize('name,allowed', [('InheritedGrind', True), ('MixedAction', True), ('InlineAction', True),
    ('AbstractCarrier', False), ('ConcreteCarrier', True), ('ChemicalMixin', False), ('NestedAction', False),
    ('OtherFieldAction', False), ('WrongRangeAction', False), ('FakeAction', False)])
def test_inherited_mixin_inline_and_effective_ranges(evolved, name, allowed):
    assert can_attach_chemical_blocks(name, schema=evolved[0]) is allowed


def test_removing_overriding_or_breaking_the_direct_field_revokes_permission(evolved):
    schema = copy.deepcopy(evolved[0])
    schema['classes']['Add']['slots'].remove('chemical')
    schema['classes']['Add']['slot_usage'].pop('chemical')
    assert not can_attach_chemical_blocks('Add', schema=schema)
    schema['classes']['InheritedGrind']['slot_usage'] = {'chemical': {'range': 'string'}}
    assert not can_attach_chemical_blocks('InheritedGrind', schema=schema)
    schema['classes']['WrongRangeAction']['slot_usage']['chemical']['range'] = 'MissingChemicalClass'
    assert not can_attach_chemical_blocks('WrongRangeAction', schema=schema)
    assert not can_attach_chemical_blocks('Grind')  # Custom snapshots did not pollute the application's view.


def test_only_the_direct_chemical_slot_has_the_canvas_role(evolved, monkeypatch):
    activate(monkeypatch, evolved)
    assert chemical_slot_for_action('Grind') == 'chemical'
    assert chemical_slot_for_action('NestedAction') is None
    assert chemical_slot_for_action('OtherFieldAction') is None
    assert chemical_slot_for_action('MixtureConstituent') is None
    slots = {}
    project_canvas_chemicals('MixedAction', slots, [{'chemical': 'Substance', 'params': {'name': 'water'}}])
    assert slots['chemical']['name'] == 'water'  # Effective scalar slot from a mixin.
    semantic = flatten_exported_instance({'source_action': 'MixedAction', 'linkml_class': 'MixedAction',
        'slots': {}, 'attached_chemicals': [{'source_chemical': 'Substance', 'linkml_class': 'Substance', 'slots': {'name': 'water'}}]})
    assert semantic['chemical']['name'] == 'water'
    with pytest.raises(ValueError, match='single entity'):
        project_canvas_chemicals('MixedAction', {}, [{'type': 'Substance', 'name': 'a'}, {'type': 'Substance', 'name': 'b'}])


def test_domain_creation_is_guarded_but_historical_import_is_lossless():
    chemical = Substance(name='água')
    with pytest.raises(ValueError, match='Grind'):
        Grind(duration='1 min').add_chemical(chemical)
    original = {'flows': [{'steps': [{'action': 'Grind', 'params': {'duration': '1 min'},
        'chemicals': [{'chemical': 'Substance', 'params': {'name': 'água', 'historical': {'raw': [1, 'β']}}}]}]}]}
    domain = Protocol.from_dict(original)
    assert domain.to_dict()[0]['chemicals'][0]['params']['historical'] == {'raw': [1, 'β']}
    messages = validate_linkml_protocol(original)
    assert any(m.code == 'validation.chemical_attachment_not_allowed' for m in messages)
    with pytest.raises(ValueError, match='chemical relation'):
        convert_protocol_to_linkml(original)
    assert original['flows'][0]['steps'][0]['chemicals'][0]['params']['name'] == 'água'


def test_continuous_addition_canvas_projection_and_conflicts_are_not_silent():
    action = ContinuousAddition(flow_rate='1 mL/min', continuous_add_type='Continuous')
    action.add_chemical(Substance(name='water'))
    assert action.to_model().chemical[0].name == 'water'
    action.params['chemical'] = [{'type': 'Substance', 'name': 'ethanol'}]
    with pytest.raises(ValueError, match='Conflicting'):
        action.to_linkml_dict()


def add_block(editor, cls, name, params=None):
    block = cls(name, params or {}, editor=editor)
    editor.scene.addItem(block); editor.blocks.append(block)
    return block


@pytest.mark.parametrize('name', ['Add', 'ContinuousAddition'])
def test_canvas_attach_detach_edit_save_import(app, name, monkeypatch):
    params = {'duration': '1 s', 'add_type': 'Normal', 'open_flame': 'False'} if name == 'Add' else {
        'chemical': [], 'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous'}
    editor = Editor(); action = editor._create_block_by_name(name, params); action.is_first = True
    chemical = add_block(editor, ChemicalBlock, 'Substance', {'name': 'water'})
    assert editor._link_chemical_to_parent(chemical, action)
    assert action.chem_below is chemical and chemical.above_block is action
    errors = []; monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[2]))
    def save():
        dialog = app.activeModalWidget()
        try:
            assert dialog.findChild(QLineEdit, 'chemical') is None
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Save Changes').click()
        finally:
            if dialog.isVisible(): dialog.reject()
    QTimer.singleShot(0, save); action.open_editor(); assert not errors
    native = editor.generate_protocol_output(False)
    for mode in ['strict', 'optimized']:
        semantic = convert_protocol_to_linkml(native, mode)
        restored = Editor(); restored.load_protocol_data(semantic)
        host = next(b for b in restored.blocks if b.action == name)
        assert host.chem_below.params['name'] == 'water'
        assert not host.params.get('chemical')  # No duplicate inline copy for an explicit canvas relation.
        assert not restored.import_warnings
        assert not [m for m in validate_linkml_protocol(restored.generate_protocol_output(False)) if m.level == 'error']
        restored.container.close()
    editor._pluck_vertical(chemical)
    assert action.chem_below is None
    assert editor._link_chemical_to_parent(chemical, action)
    editor.container.close()


def test_gui_filters_preview_drop_and_actual_link_including_stack_bypasses(app):
    editor = Editor(); blocked = add_block(editor, ElementaryAction, 'Grind', {'duration': '1 min'})
    chemical = add_block(editor, ChemicalBlock, 'Substance', {'name': 'water'})
    blocked.setPos(100, 100); chemical.setPos(100, 100)
    assert not editor._can_attach_chemical_to(blocked)
    assert editor.is_incompatible_vertical_link(blocked, chemical)
    editor.preview_link(chemical); assert getattr(editor, "preview_pair", None) is None
    assert editor._get_target_and_zone(chemical) == (None, None)
    assert editor._find_vertical_target(chemical) == (None, None)
    assert not editor._link_chemical_to_parent(chemical, blocked)
    assert blocked.chem_below is None and chemical.above_block is None
    # An imported invalid stack must not permit a new association through its tail.
    old = add_block(editor, ChemicalBlock, 'Substance', {'name': 'legacy'})
    blocked.chem_below = old; old.above_block = blocked
    assert not editor._can_attach_chemical_to(old)
    assert not editor._link_chemical_to_parent(chemical, old)
    assert old.below_block is None
    # Free stacks remain usable before the user chooses an eligible action.
    old.above_block = None; blocked.chem_below = None
    assert editor._can_attach_chemical_to(old)
    assert editor._link_chemical_to_parent(chemical, old)
    surrogate = ComplexActionBlock('Custom template', {}, editor=editor)
    assert not editor._can_attach_chemical_to(surrogate)
    editor.container.close()


def test_import_keeps_unsupported_links_and_reports_them(app):
    data = {'flows': [{'is_explicit_first': True, 'steps': [{'action': 'Grind', 'params': {'duration': '1 min'},
        'chemicals': [{'chemical': 'Substance', 'params': {'name': 'water'}}]}]}]}
    editor = Editor(); editor.load_protocol_data(copy.deepcopy(data))
    assert any('retained for review' in warning for warning in editor.import_warnings)
    action = next(block for block in editor.blocks if block.action == 'Grind')
    assert action.chem_below.params['name'] == 'water'
    assert not editor._link_chemical_to_parent(ChemicalBlock('Substance', {'name': 'new'}), action)
    retained = editor.generate_protocol_output(False)
    assert retained['flows'][0]['steps'][0]['chemicals'][0]['params']['name'] == 'water'
    assert any(m.code == 'validation.chemical_attachment_not_allowed' for m in validate_linkml_protocol(retained))
    action.chem_below.delete_block(); assert action.chem_below is None
    assert not [m for m in validate_linkml_protocol(editor.generate_protocol_output(False)) if m.level == 'error']
    editor.container.close()


def test_schema_evolution_changes_real_canvas_permissions_and_strict_roundtrip(app, evolved, monkeypatch):
    original = DEFAULT_SCHEMA.read_bytes()
    activate(monkeypatch, evolved)
    editor = Editor(); action = editor._create_block_by_name('Grind', {'duration': '1 min'}); action.is_first = True
    chemical = add_block(editor, ChemicalBlock, 'Substance', {'name': 'water'})
    assert editor._can_attach_chemical_to(action) and editor._link_chemical_to_parent(chemical, action)
    native = editor.generate_protocol_output(False)
    semantic = convert_protocol_to_linkml(native)
    restored = Editor(); restored.load_protocol_data(semantic)
    assert next(b for b in restored.blocks if b.action == 'Grind').chem_below.params['name'] == 'water'
    assert not [m for m in validate_linkml_protocol(restored.generate_protocol_output(False)) if m.level == 'error']
    # Removing the relation revokes new connections, while import retains old data.
    removed = copy.deepcopy(evolved[0]); removed['classes']['Grind']['slots'].remove('chemical')
    removed['classes']['Grind']['slot_usage'].pop('chemical')
    monkeypatch.setattr(loader, '_default_schema_view', lambda: loader.schema_view(removed))
    assert not editor._can_attach_chemical_to(action)
    assert not editor._link_chemical_to_parent(ChemicalBlock('Substance', {'name': 'new'}), action)
    assert action.chem_below is chemical
    assert DEFAULT_SCHEMA.read_bytes() == original
    editor.container.close(); restored.container.close()


def test_complex_members_use_the_same_permission_and_roundtrip(app, monkeypatch):
    from labprogen.complex import actions
    from labprogen.complex.protocol import materialize_complex_action
    registry = actions.ComplexActionRegistry(); monkeypatch.setattr(actions, '_GLOBAL_REGISTRY', registry)
    steps = [
        {'action': 'Add', 'params': {'duration': '1 s', 'add_type': 'Normal', 'open_flame': 'False'}},
        {'action': 'ContinuousAddition', 'params': {'chemical': [], 'flow_rate': '1 mL/min', 'continuous_add_type': 'Continuous'}},
        {'action': 'Grind', 'params': {'duration': '1 min'}},
        {'action': 'Repeat', 'params': {'amount': '2'}},
    ]
    definition = actions.ComplexActionDefinition('Chemical capabilities', steps, actions.build_parameter_bindings(steps))
    registry.register(definition)
    editor = Editor(); group = materialize_complex_action(editor, definition.name, actions.copy_instance_parameters(definition))
    group.member_blocks[0].is_first = True
    for member in group.member_blocks[:2]:
        assert editor._can_attach_chemical_to(member)
        assert not requires_canvas_chemical(member.action, part_of_complex_action=True)
        chemical = add_block(editor, ChemicalBlock, 'Substance', {'name': member.action + ' reagent'})
        chemical.setPos(member.pos())
        assert editor._get_target_and_zone(chemical)[0] is member
        assert editor._link_chemical_to_parent(chemical, member)
    assert not editor._can_attach_chemical_to(group.member_blocks[2])
    assert not editor._can_attach_chemical_to(group.surrogate_block)
    editor._toggle_complex_visibility(True)
    probe = add_block(editor, ChemicalBlock, 'Substance', {'name': 'probe'})
    probe.setPos(group.surrogate_block.pos())
    assert editor._get_target_and_zone(probe) == (None, None)
    assert editor._find_vertical_target(probe) == (None, None)
    editor.preview_link(probe); assert getattr(editor, 'preview_pair', None) is None
    editor.scene.removeItem(probe); editor.blocks.remove(probe)
    semantic = convert_protocol_to_linkml(editor.generate_protocol_output(False))
    restored = Editor(); restored.load_protocol_data(semantic)
    assert not restored.import_warnings and len(restored.complex_action_groups) == 1
    members = next(iter(restored.complex_action_groups.values())).member_blocks
    assert members[0].chem_below.params['name'] == 'Add reagent'
    assert members[1].chem_below.params['name'] == 'ContinuousAddition reagent'
    assert members[2].chem_below is None
    assert not [m for m in validate_linkml_protocol(restored.generate_protocol_output(False)) if m.level == 'error']
    editor.container.close(); restored.container.close()


def test_incompatible_scalar_canvas_history_can_still_be_imported(app, evolved, monkeypatch):
    activate(monkeypatch, evolved)
    payload = {'activities': [{'laboratory_actions': [{'source_action': 'MixedAction', 'linkml_class': 'MixedAction',
        'slots': {'chemical': {'type': 'Substance', 'name': 'inline retained'}},
        'attached_chemicals': [
            {'source_chemical': 'Substance', 'slots': {'name': 'a'}},
            {'source_chemical': 'Substance', 'slots': {'name': 'b'}}]}]}]}
    original = copy.deepcopy(payload)
    native = convert_linkml_to_protocol(payload)
    editor = Editor(); editor.load_protocol_data(native)
    action = next(b for b in editor.blocks if b.action == 'MixedAction')
    assert action.params['chemical']['name'] == 'inline retained'
    assert action.chem_below.params['name'] == 'a'
    assert action.chem_below.below_block.params['name'] == 'b'
    with pytest.raises(ValueError, match='single entity'):
        convert_protocol_to_linkml(native)
    assert payload == original
    editor.container.close()
