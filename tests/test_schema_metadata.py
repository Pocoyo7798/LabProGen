"""Evolution of official models, contextual contracts and lossless UI drafts."""

import copy
import importlib.util
import sys

import pytest
import yaml
from pydantic import ValidationError
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QDialog, QLineEdit, QMessageBox, QPushButton

from labprogen.core import model
from labprogen.core.config import (
    FIELD_CONFIG, UI_FIELD_PREFERENCES, action_requires_attached_chemical,
    is_chemical_entity_field, validate_schema_references,
)
from labprogen.linkml import loader
from labprogen.linkml.adapter import chemical_record_to_instance, convert_linkml_to_protocol
from labprogen.linkml.exporter import convert_protocol_to_linkml
from labprogen.linkml.validator import _python_instance_checks
from labprogen.ui.block import ChemicalBlock, ElementaryAction
from labprogen.ui.schema_fields import RetainedValueField, SchemaRecordDialog
from labprogen.complex.actions import ComplexActionParameter
from labprogen.complex.fields import ParameterValueEditor
from tools.generate_models import generate_source


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope='module')
def evolved(tmp_path_factory):
    """Change only a temporary copy, then use the official generator."""
    schema = copy.deepcopy(loader.load_linkml_schema())
    schema['classes']['Cell']['attributes'] = {
        'review_note': {'range': 'string', 'description': 'Review note from the schema.'},
    }
    schema['classes']['Cell'].setdefault('slot_usage', {})['passage_number'] = {'required': True}
    schema['classes']['ReviewMixin'] = {'mixin': True, 'attributes': {
        'score': {'range': 'integer', 'ifabsent': 'integer(7)', 'minimum_value': 0},
    }}
    schema['classes']['ReviewAction'] = {
        'is_a': 'Action', 'mixins': ['ReviewMixin'], 'slots': ['duration'],
        'attributes': {
            'enabled': {'range': 'boolean'},
            'ratio': {'range': 'float'},
            'tags': {'range': 'string', 'multivalued': True, 'minimum_cardinality': 1, 'maximum_cardinality': 3},
            'sample': {'range': 'Cell', 'inlined': True},
            'local_value': {'range': 'integer', 'required': True, 'minimum_value': 0},
        },
        'slot_usage': {'duration': {'required': False}},
    }
    schema['classes']['ReviewOther'] = {'attributes': {
        'local_value': {'range': 'string', 'multivalued': True},
    }}
    values = schema['enums']['AdditionTypeEnum']['permissible_values']
    values.pop('Normal'); values['Careful'] = {}
    del schema['slots']['solubility']
    schema['classes']['Medium']['slots'].remove('solubility')
    directory = tmp_path_factory.mktemp('evolved-model')
    path = directory / 'action_data_model.yaml'
    path.write_text(yaml.safe_dump(schema, sort_keys=False), encoding='utf-8')
    module_path = directory / 'models.py'
    module_path.write_text(generate_source(path), encoding='utf-8')
    spec = importlib.util.spec_from_file_location('labprogen_evolved_models', module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
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
    # The dialog imports this accessor directly; simulate a fresh process with
    # the temporary schema without touching the official source file.
    monkeypatch.setattr('labprogen.ui.schema_fields.model_schema', lambda: schema)
    monkeypatch.setattr(model, 'model_class', lambda name: getattr(module, name))


def test_new_inline_property_is_generated_and_described(evolved):
    schema, module = evolved
    assert module.Cell(passage_number=1, review_note='água').review_note == 'água'
    spec = model.field_contract('review_note', 'Cell', schema=schema)
    assert spec['declared'] and spec['range'] == 'string'
    assert model.field_config('review_note', 'Cell', schema=schema)['placeholder'] == 'Review note from the schema.'
    assert not model.field_contract('review_note', schema=schema)['declared']


def test_new_class_has_typed_fields_relations_defaults_and_cardinality(evolved, monkeypatch):
    schema, module = evolved
    obj = module.ReviewAction(local_value=0, enabled=True, ratio=1.5, tags=['a'], sample={'type': 'Cell', 'passage_number': 1})
    assert obj.score == 7 and isinstance(obj.sample, module.Cell)
    assert module.ReviewAction.model_fields['local_value'].is_required()
    with pytest.raises(ValidationError):
        module.ReviewAction(local_value=0, tags=[])
    with pytest.raises(ValidationError):
        module.ReviewAction(local_value=0, tags=['a', 'b', 'c', 'd'])
    spec = model.field_contract('tags', 'ReviewAction', schema=schema)
    assert (spec['minimum_cardinality'], spec['maximum_cardinality']) == (1, 3)
    assert 'ReviewAction' in model.concrete_classes('Action', schema=schema)
    assert 'sample' in model.chemical_fields('ReviewAction', schema=schema)
    activate(monkeypatch, evolved)
    assert model.default_params('ReviewAction')['score'] == 7
    assert model.default_params('ReviewAction')['tags'] == []


def test_optional_to_required_matches_metadata_and_generated_validation(evolved):
    schema, module = evolved
    assert not model.field_contract('passage_number', 'Cell')['required']
    assert model.field_contract('passage_number', 'Cell', schema=schema)['required']
    with pytest.raises(ValidationError):
        module.Cell()
    assert module.Cell(passage_number=2).passage_number == 2


def test_enum_addition_and_removal_update_models_and_presentation(evolved):
    schema, module = evolved
    options = model.field_config('add_type', 'Add', schema=schema)['options']
    assert 'Careful' in options and 'Normal' not in options
    data = {'chemical': [{'type': 'Substance', 'name': 'water'}], 'duration': '1 s', 'open_flame': 'False'}
    assert module.Add(**data, add_type='Careful').add_type == 'Careful'
    with pytest.raises(ValidationError):
        module.Add(**data, add_type='Normal')


def test_removed_property_is_not_declared_even_with_old_preferences(evolved):
    schema, module = evolved
    assert 'solubility' in UI_FIELD_PREFERENCES
    assert 'solubility' not in module.Medium.model_fields
    config = model.field_config('solubility', 'Medium', schema=schema)
    assert not config['declared'] and config['type'] == 'retained' and not config['required']
    assert any('solubility' in error for error in validate_schema_references(schema))
    with pytest.raises(ValidationError):
        module.Medium(solubility='old')


def test_class_scoped_slots_never_borrow_another_class_contract(evolved):
    schema, _ = evolved
    integer = model.field_config('local_value', 'ReviewAction', schema=schema)
    strings = model.field_config('local_value', 'ReviewOther', schema=schema)
    assert (integer['range'], integer['required'], integer['multivalued'], integer['minimum']) == ('integer', True, False, 0)
    assert (strings['range'], strings['required'], strings['multivalued']) == ('string', False, True)
    assert not model.field_contract('local_value', 'Cell', schema=schema)['declared']
    assert not model.field_contract('duration', 'UnknownClass', schema=schema)['declared']
    # Existing global slot, but required/list on Add and required/scalar on a constituent.
    assert model.field_config('chemical', 'Add')['type'] == 'list'
    assert model.field_config('chemical', 'MixtureConstituent')['type'] == 'single_chemical'


def test_inheritance_mixins_slot_usage_and_inline_metadata(evolved):
    schema, module = evolved
    assert issubclass(module.ReviewAction, module.ReviewMixin)
    assert model.field_contract('score', 'ReviewAction', schema=schema)['ifabsent'] == 'integer(7)'
    assert not model.field_contract('duration', 'ReviewAction', schema=schema)['required']
    assert model.field_contract('duration', 'Add', schema=schema)['required']
    assert not model.field_contract('name', 'Cell', schema=schema)['required']
    assert 'name' in loader.class_slot_constraints('Cell', schema)['allowed']


def test_presentation_survives_and_cannot_override_changed_types(evolved, monkeypatch):
    schema, _ = evolved
    config = model.field_config('duration', 'Add', schema=schema)
    assert config['label'] == 'Duration' and config['placeholder'] == 'Time'
    assert config['units'] == ['s', 'min', 'h'] and config['defaults'] == ['0', '10', '30']
    monkeypatch.setitem(UI_FIELD_PREFERENCES, 'local_value', {'label': 'Local label', 'range': 'boolean', 'required': False, 'options': ['wrong']})
    config = model.field_config('local_value', 'ReviewAction', schema=schema)
    assert config['label'] == 'Local label' and config['range'] == 'integer' and config['required']
    assert 'options' not in config
    config['required'] = False  # Callers cannot mutate cached contracts.
    assert model.field_contract('local_value', 'ReviewAction', schema=schema)['required']


def test_chemical_relations_and_canvas_rules_are_distinct():
    assert is_chemical_entity_field('supplements', 'Cell')
    assert is_chemical_entity_field('suspension_medium', 'Cell')
    assert not is_chemical_entity_field('chemical', 'NoAction')
    assert 'substance_list' not in FIELD_CONFIG
    assert action_requires_attached_chemical('Add')
    assert not action_requires_attached_chemical('Add', part_of_complex_action=True)
    assert model.field_contract('chemical', 'Add')['required']
    item = chemical_record_to_instance({'chemical_type': 'Cell', 'supplements': [
        {'chemical_type': 'Substance', 'name': 'glucose', 'concentration': '1 g/L'}]})
    assert item['supplements'][0]['type'] == 'MixtureConstituent'
    assert item['supplements'][0]['chemical']['name'] == 'glucose'


def test_removed_structured_value_survives_import_and_actual_editor_save(app, evolved, monkeypatch):
    activate(monkeypatch, evolved)
    historical = {'original': ['água', {'amount': 3}], 'empty': []}
    # Read an old semantic document directly: current strict export must reject
    # it, whereas import/editing must retain its undeclared data for review.
    payload = {'activities': [{'laboratory_actions': [{
        'source_action': 'ContinuousAddition', 'linkml_class': 'ContinuousAddition',
        'slots': {'chemical': [{'type': 'Medium', 'solubility': historical}]},
    }]}]}
    restored = convert_linkml_to_protocol(payload)
    assert restored['flows'][0]['steps'][0]['params']['chemical'][0]['solubility'] == historical
    messages = _python_instance_checks({'solubility': historical}, 'Medium', evolved[0], {})
    assert any(message.code == 'validation.unknown_field' for message in messages)
    block = ChemicalBlock('Medium', {'solubility': historical})
    errors = []
    monkeypatch.setattr(QMessageBox, 'warning', lambda *args: errors.append(args[2]))
    def interact():
        dialog = app.activeModalWidget()
        try:
            field = dialog.findChild(RetainedValueField)
            assert field.get_value() == historical and field.isReadOnly()
            next(button for button in dialog.findChildren(QPushButton) if button.text() == 'Save Changes').click()
        finally:
            if dialog.isVisible():
                dialog.reject()
    QTimer.singleShot(0, interact)
    block.open_editor()
    assert not errors
    assert block.params['solubility'] == historical
    dialog = SchemaRecordDialog('Medium', {'type': 'Medium', 'solubility': historical, 'old_empty': []})
    assert dialog._read()['solubility'] == historical
    assert dialog._read()['old_empty'] == []
    dialog.deleteLater()


def test_complex_and_block_editors_use_context_and_preserve_bad_shapes(app):
    def editor(action, key, value):
        return ParameterValueEditor(ComplexActionParameter(0, action, key, key, value=value))
    scalar = editor('MixtureConstituent', 'chemical', {'chemical_type': 'Substance', 'name': 'water'})
    # Complex parameters use the existing nested editor for single chemical records.
    assert scalar.value() == {'chemical_type': 'Substance', 'name': 'water'}
    bad = editor('ContinuousAddition', 'chemical', {'old': ['a']})
    assert isinstance(bad.widget, RetainedValueField) and bad.value() == {'old': ['a']}
    bad.set_read_only(False)
    record = editor('Separate', 'method', {'type': 'Filtration'})
    record.set_read_only(True); record.set_read_only(False)
    assert record.value() == {'type': 'Filtration'}
    for block in [ElementaryAction('NoAction', {}), ChemicalBlock('Cell', {})]:
        _, tracker = block._get_field_widget('deleted_field', {'raw': [False, 'á']})
        assert tracker.get_value() == {'raw': [False, 'á']}
    assert not validate_schema_references()


def test_existing_editors_accept_new_typed_fields_without_widget_generation(app, evolved, monkeypatch):
    activate(monkeypatch, evolved)
    dialog = SchemaRecordDialog('ReviewAction', {'local_value': 0, 'enabled': False, 'ratio': 1.5, 'tags': ['á']})
    assert dialog.trackers['local_value'].validator().bottom() == 0
    data = dialog._read()
    assert data['enabled'] is False and data['local_value'] == 0
    assert data['ratio'] == 1.5 and data['score'] == 7 and data['tags'] == ['á']
    binding = ComplexActionParameter(0, 'ReviewAction', 'enabled', 'Enabled', value=False)
    assert ParameterValueEditor(binding).value() is False
    block = ElementaryAction('Add', {})
    _, enum = block._get_field_widget('add_type', 'Careful')
    assert enum.currentText() == 'Careful' and enum.findText('Normal') == -1
    dialog.deleteLater()


def test_removed_class_binding_is_reported_without_guessing_a_replacement():
    schema = copy.deepcopy(loader.load_linkml_schema())
    del schema['classes']['Grind']
    assert 'Obsolete class reference: Grind' in validate_schema_references(schema)
