"""Restore explicitly persisted groups, independent of the local dictionary."""
import copy
import json

import pytest
import yaml
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from labprogen.complex import actions
from labprogen.complex.actions import ComplexActionDefinition, ComplexActionRegistry, build_parameter_bindings, copy_instance_parameters
from labprogen.complex.protocol import materialize_complex_action, next_group_id
from labprogen.core.protocol import Protocol
from labprogen.linkml.adapter import convert_linkml_to_protocol, flatten_exported_instance
from labprogen.linkml.exporter import convert_protocol_to_linkml
from labprogen.linkml.validator import validate_linkml_protocol
from labprogen.ui.editor import Editor


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def registry(monkeypatch):
    registry = ComplexActionRegistry()
    monkeypatch.setattr(actions, '_GLOBAL_REGISTRY', registry)
    return registry


def make_group(registry, repeated=False):
    steps = [{'action': 'Grind', 'params': {'duration': '5 min'}},
             {'action': 'Grind', 'params': {'duration': '2 min'}} if repeated else
             {'action': 'Separate', 'params': {'method': {'type': 'Centrifugation', 'phase_to_keep': 'Liquid', 'speed': '4000 rpm'}}},
             {'action': 'Repeat', 'params': {'amount': '2'}}]
    parameters = build_parameter_bindings(steps)
    parameters[0].display_name = 'Grinding time – preparação'
    parameters[0].editable = False
    definition = ComplexActionDefinition('Grind, separate and repeat', steps, parameters)
    registry.register(definition)
    editor = Editor()
    group = materialize_complex_action(editor, definition.name, copy_instance_parameters(definition))
    group.member_blocks[0].is_first = True
    return editor, group


def assert_group(editor, repeated):
    assert not editor.import_warnings
    assert len(editor.complex_action_groups) == 1
    group = next(iter(editor.complex_action_groups.values()))
    assert [b.action for b in group.member_blocks] == ['Grind', 'Grind' if repeated else 'Separate', 'Repeat']
    assert group.parameters[0].display_name == 'Grinding time – preparação'
    assert not group.parameters[0].editable
    assert group.definition_name == 'Grind, separate and repeat'
    assert group.member_blocks[-1].params['amount'] == '2'
    assert group.member_blocks[0].is_first
    for collapsed in [True, False, True, False]:
        editor._toggle_complex_visibility(collapsed)
        assert group.surrogate_block.isVisible() == collapsed
        assert all(block.isVisible() != collapsed for block in group.member_blocks)
    return group


@pytest.mark.parametrize('kind', ['native', 'strict', 'optimized'])
@pytest.mark.parametrize('repeated', [False, True])
@pytest.mark.parametrize('format', ['json', 'yaml'])
def test_save_import_edit_save_preserves_group_and_bindings(app, registry, kind, repeated, format, tmp_path, monkeypatch):
    original, group = make_group(registry, repeated)
    original._toggle_complex_visibility(True)
    native = original.generate_protocol_output(False)
    assert not [m for m in validate_linkml_protocol(native) if m.level == 'error']
    payload = native if kind == 'native' else convert_protocol_to_linkml(native, mode=kind)
    path = tmp_path / ('protocol.' + format)
    path.write_text(json.dumps(payload, ensure_ascii=False) if format == 'json' else yaml.safe_dump(payload), encoding='utf-8')
    loaded = json.loads(path.read_text()) if format == 'json' else yaml.safe_load(path.read_text())
    # A different installation need not have the same dictionary or template.
    monkeypatch.setattr(actions, '_GLOBAL_REGISTRY', ComplexActionRegistry())
    restored = Editor(); restored.load_protocol_data(loaded)
    assert restored.show_complex_actions_collapsed
    group = assert_group(restored, repeated)
    if repeated:
        group.member_blocks[1].params['duration'] = '12 min'
    else:
        group.member_blocks[1].params['method']['speed'] = '5200 rpm'
    second = restored.generate_protocol_output(False)
    again = Editor(); again.load_protocol_data(json.loads(json.dumps(second)))
    assert_group(again, repeated)
    member = next(iter(again.complex_action_groups.values())).member_blocks[1]
    assert member.params['duration'] == '12 min' if repeated else member.params['method']['speed'] == '5200 rpm'
    # Editing the collapsed instance uses its imported snapshot, not a registry lookup.
    def edit(definition, **kwargs):
        assert definition.name == group.definition_name
        values = copy.deepcopy(kwargs['initial_parameters'])
        next(p for p in values if p.step_index == 2 and p.param_key == 'amount').value = '3'
        return values
    monkeypatch.setattr('labprogen.complex.ui.prompt_complex_action_use', edit)
    next(iter(again.complex_action_groups.values())).surrogate_block.open_editor()
    assert next(iter(again.complex_action_groups.values())).member_blocks[2].params['amount'] == '3'
    assert next_group_id(again) not in again.complex_action_groups
    for editor in [original, restored, again]: editor.container.close()


def test_legacy_member_markers_restore_group_without_new_metadata(app, registry):
    original, _ = make_group(registry)
    native = original.generate_protocol_output(False)
    native.pop('complex_action_groups')
    # Old LinkML files did not carry member indices.
    for step in native['flows'][0]['steps']: step.pop('complex_step_index', None)
    restored = Editor(); restored.load_protocol_data(native)
    assert len(restored.complex_action_groups) == 1
    assert [b.action for b in next(iter(restored.complex_action_groups.values())).member_blocks] == ['Grind', 'Separate', 'Repeat']
    original.container.close(); restored.container.close()


def test_flat_sequences_without_markers_never_group_or_merge_repeated_actions(app, registry):
    original, _ = make_group(registry, True)
    native = original.generate_protocol_output(False)
    native.pop('complex_action_groups')
    for step in native['flows'][0]['steps']:
        for key in ['part_of_complex_action', 'complex_group_id', 'complex_step_index', 'complex_action_name', 'block_id']:
            step.pop(key, None)
    for data in [native, native['flows'][0]['steps']]:
        restored = Editor(); restored.load_protocol_data(copy.deepcopy(data))
        assert not restored.complex_action_groups
        assert [b.action for b in restored.blocks] == ['Grind', 'Grind', 'Repeat']
        assert len(restored.generate_protocol_output(False)['flows'][0]['steps']) == 3
        restored.container.close()
    original.container.close()


def test_linkml_envelope_metadata_does_not_become_schema_slots(app, registry):
    editor, _ = make_group(registry)
    payload = convert_protocol_to_linkml(editor.generate_protocol_output(False))
    assert 'source_protocol' not in payload
    assert payload['complex_action_groups']['version'] == 1
    for step in payload['activities'][0]['laboratory_actions']:
        semantic = flatten_exported_instance(step)
        assert not any(k.startswith('complex_') for k in semantic)
        assert 'part_of_complex_action' not in semantic
    flat = copy.deepcopy(payload); flat.pop('complex_action_groups')
    for step in flat['activities'][0]['laboratory_actions']:
        for key in ['part_of_complex_action', 'complex_group_id', 'complex_step_index', 'complex_action_name']:
            step.pop(key, None)
    restored = Editor(); restored.load_protocol_data(flat)
    assert not restored.complex_action_groups and len(restored.blocks) == 3
    malformed = copy.deepcopy(payload)
    malformed['activities'][0]['laboratory_actions'][0]['slots']['complex_group_id'] = 'not-a-slot'
    with pytest.raises(ValueError):
        convert_protocol_to_linkml(convert_linkml_to_protocol(malformed))
    editor.container.close(); restored.container.close()


def test_inconsistent_group_metadata_warns_and_retains_all_actions_and_markers(app, registry):
    original, _ = make_group(registry)
    native = original.generate_protocol_output(False)
    native['flows'][0]['steps'][1]['complex_step_index'] = 40
    restored = Editor(); restored.load_protocol_data(native)
    assert restored.import_warnings and not restored.complex_action_groups
    saved = restored.generate_protocol_output(False)
    assert len(saved['flows'][0]['steps']) == 3
    assert saved['flows'][0]['steps'][1]['complex_step_index'] == 40
    assert saved['complex_action_groups']['groups'] == native['complex_action_groups']['groups']
    unsupported = copy.deepcopy(native); unsupported['complex_action_groups']['version'] = 999
    with pytest.raises(ValueError, match='Unsupported'):
        restored.load_protocol_data(unsupported)
    assert len(restored.blocks) == 3
    original.container.close(); restored.container.close()


def test_domain_protocol_serialization_retains_member_identity_and_properties(app, registry):
    original, _ = make_group(registry)
    native = original.generate_protocol_output(False)
    model = Protocol.from_dict(native)
    restored = json.loads(model.to_json())
    assert restored['complex_action_groups'] == native['complex_action_groups']
    assert [s['complex_step_index'] for s in restored['flows'][0]['steps']] == [0, 1, 2]
    semantic = model.to_linkml_dict()
    assert semantic['complex_action_groups'] == native['complex_action_groups']
    original.container.close()


@pytest.mark.parametrize('kind', ['protocol', 'linkml'])
def test_actual_export_and_import_file_dialog_paths_keep_groups(app, registry, monkeypatch, tmp_path, kind):
    original, _ = make_group(registry)
    filename = tmp_path / 'saved.json'
    class ExportChoice:
        export_kind = kind
        export_format = 'json'
        def __init__(self, *args): pass
        def exec(self): return QDialog.DialogCode.Accepted
    monkeypatch.setattr('labprogen.ui.editor.ExportProtocolDialog', ExportChoice)
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', lambda *args: (str(filename), ''))
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(filename), ''))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    original.export_protocol()
    assert filename.is_file()
    restored = Editor(); restored.import_protocol()
    assert_group(restored, False)
    original.container.close(); restored.container.close()


def test_nested_template_bindings_survive_as_materialized_instance_properties(app, registry, monkeypatch):
    inner_steps = [{'action': 'Grind', 'params': {'duration': '2 min'}}, {'action': 'Repeat', 'params': {'amount': '2'}}]
    inner = ComplexActionDefinition('Inner', inner_steps, build_parameter_bindings(inner_steps)); registry.register(inner)
    inner.parameters[0].display_name = 'Nested grinding time'
    inner.parameters[0].editable = False
    nested = {'action': 'ComplexAction', 'params': actions.parameters_to_block_params('Inner', inner.parameters)}
    outer_steps = [{'action': 'NoAction', 'params': {'duration': '1 min'}}, nested]
    outer = ComplexActionDefinition('Outer', outer_steps, build_parameter_bindings(outer_steps)); registry.register(outer)
    original = Editor()
    group = materialize_complex_action(original, outer.name, actions.build_instance_parameters(outer))
    group.member_blocks[0].is_first = True
    group.member_blocks[1].params['duration'] = '9 min'
    native = original.generate_protocol_output(False)
    monkeypatch.setattr(actions, '_GLOBAL_REGISTRY', ComplexActionRegistry())
    restored = Editor(); restored.load_protocol_data(native)
    group = next(iter(restored.complex_action_groups.values()))
    assert [b.action for b in group.member_blocks] == ['NoAction', 'Grind', 'Repeat']
    binding = next(p for p in group.parameters if p.step_index == 1 and p.param_key == 'duration')
    assert binding.display_name == 'Nested grinding time' and not binding.editable and binding.value == '9 min'
    assert group.expanded_steps()[1]['params']['duration'] == '9 min'
    original.container.close(); restored.container.close()


def test_split_add_members_and_two_explicit_groups_roundtrip(app, registry):
    steps = [{'action': 'Add', 'params': {'duration': '1 s', 'add_type': 'Normal', 'open_flame': 'False'}},
             {'action': 'Repeat', 'params': {'amount': '2'}}]
    definition = ComplexActionDefinition('Add twice', steps, build_parameter_bindings(steps)); registry.register(definition)
    original = Editor()
    first = materialize_complex_action(original, definition.name, copy_instance_parameters(definition))
    second = materialize_complex_action(original, definition.name, copy_instance_parameters(definition))
    original._reconstruct_chemicals(first.member_blocks[0], [
        {'chemical': 'Substance', 'params': {'name': 'water'}}, {'chemical': 'Molecule', 'params': {'name': 'ethanol', 'smile': 'CCO', 'formula': 'C2H6O'}}])
    original._reconstruct_chemicals(second.member_blocks[0], [{'chemical': 'Substance', 'params': {'name': 'salt'}}])
    first.member_blocks[-1].next_block = second.member_blocks[0]
    second.member_blocks[0].prev_block = first.member_blocks[-1]
    first.member_blocks[0].is_first = True
    original._toggle_complex_visibility(True)
    native = original.generate_protocol_output(False)
    assert len(native['flows'][0]['steps']) == 5  # The first Add has two exported entries.
    for payload in [native, convert_protocol_to_linkml(native)]:
        restored = Editor(); restored.load_protocol_data(payload)
        assert not restored.import_warnings and len(restored.complex_action_groups) == 2
        groups = list(restored.complex_action_groups.values())
        assert all(len(group.member_blocks) == 2 for group in groups)
        chemical = groups[0].member_blocks[0].chem_below
        assert chemical.params['name'] == 'water' and chemical.below_block.params['name'] == 'ethanol'
        restored._toggle_complex_visibility(False)
        assert groups[0].member_blocks[-1].next_block is groups[1].member_blocks[0]
        restored.container.close()
    original.container.close()


def test_dictionary_is_not_a_protocol_and_does_not_clear_the_open_scene(app, registry):
    original, _ = make_group(registry)
    before = list(original.blocks)
    dictionary = registry.get('Grind, separate and repeat').to_dict()
    with pytest.raises(ValueError, match='complex-action dictionary'):
        original.load_protocol_data(dictionary)
    assert original.blocks == before and len(original.complex_action_groups) == 1
    original.container.close()


def test_dictionary_import_never_guesses_existing_group_membership(app, registry, monkeypatch, tmp_path):
    from labprogen.complex.protocol import import_complex_action_dictionary
    original, _ = make_group(registry)
    native = original.generate_protocol_output(False); native.pop('complex_action_groups')
    for step in native['flows'][0]['steps']:
        for key in ['part_of_complex_action', 'complex_group_id', 'complex_action_name', 'complex_step_index']:
            step.pop(key, None)
    flat = Editor(); flat.load_protocol_data(native)
    dictionary = tmp_path / 'dictionary.json'
    dictionary.write_text(registry.get('Grind, separate and repeat').to_json(), encoding='utf-8')
    registered = []
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *args: (str(dictionary), ''))
    monkeypatch.setattr(QMessageBox, 'information', lambda *args: None)
    monkeypatch.setattr('labprogen.complex.protocol.register_complex_action_definitions', lambda definitions: registered.extend(definitions))
    assert import_complex_action_dictionary(flat)
    assert len(registered) == 1 and not flat.complex_action_groups
    assert len(flat.blocks) == 3
    original.container.close(); flat.container.close()
