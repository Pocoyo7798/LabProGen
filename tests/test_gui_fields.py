"""List controls and string-valued quantities in every existing form context."""
import copy

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt, QTimer
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QLabel, QLineEdit, QPushButton, QToolButton

from labprogen.app import STYLESHEET
from labprogen.core.model import field_config
from labprogen.complex.actions import ComplexActionParameter
from labprogen.complex.fields import ParameterValueEditor
from labprogen.ui.block import ChemicalBlock, ElementaryAction
from labprogen.ui.chemical_list_field import build_chemical_list_field
from labprogen.ui.editor import MixtureChemicalDialog
from labprogen.ui.field_widgets import ADD_BUTTON_STYLE, LIST_ICON_BUTTON_STYLE, UnitValueField
from labprogen.ui.schema_fields import SchemaRecordDialog, SchemaValueField


@pytest.fixture(scope='module')
def app():
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


def flush():
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_method_add_edit_remove_uses_label_and_small_neutral_icons(app, monkeypatch):
    field = SchemaValueField(field_config('method', 'Separate'))
    field.resize(400, 100); field.show()
    original = {'type': 'Centrifugation', 'phase_to_keep': 'Solid', 'speed': '4000 rpm'}
    edited = {**original, 'speed': '6000 rpm'}
    seen = []
    def accept(dialog):
        seen.append(copy.deepcopy(dialog.initial))
        dialog.value = copy.deepcopy(original if len(seen) == 1 else edited)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(SchemaRecordDialog, 'exec', accept)
    add = next(b for b in field.findChildren(QToolButton) if b.text() == '+ Add')
    assert add.styleSheet() == ADD_BUTTON_STYLE and add.height() == 28
    add.click(); flush()
    assert field.get_value() == original
    assert not field.findChildren(QPushButton)
    label = next(label for label in field.findChildren(QLabel) if label.text() == 'Centrifugation')
    assert label.toolTip() == 'Centrifugation'
    edit, remove = [next(b for b in field.findChildren(QToolButton) if b.text() == symbol) for symbol in ['✎', '✕']]
    for button in [edit, remove]:
        assert button.size().width() == button.size().height() == 22
        assert button.styleSheet() == LIST_ICON_BUTTON_STYLE
        assert button.toolTip() and button.focusPolicy() == Qt.FocusPolicy.StrongFocus
    edit.click(); flush()
    assert field.get_value() == edited and seen[1] == original
    next(b for b in field.findChildren(QToolButton) if b.text() == '✕').click(); flush()
    assert field.get_value() == {}
    assert any(b.text() == '+ Add' for b in field.findChildren(QToolButton))
    field.close()


def test_long_method_names_wrap_without_widening_the_form(app):
    text = 'Long method ' * 30
    field = SchemaValueField(field_config('method', 'Separate'), {'type': text})
    field.setFixedWidth(360); field.show(); app.processEvents()
    label = field.findChild(QLabel)
    assert label.wordWrap() and label.toolTip() == text
    assert field.width() == 360
    for button in field.findChildren(QToolButton):
        assert button.geometry().right() <= field.width()
    field.close()


@pytest.mark.parametrize('value', ['4000 rpm', '1.20e3 rad/min', '0', '4000 ×g', '  2.00  revolutions/min  ', '1000', '>4000 rpm', '1,5 g', ''])
def test_unit_control_never_rewrites_untouched_values(app, value):
    field = UnitValueField(field_config('speed', 'Centrifugation'), value)
    assert field.get_value() == value
    field.set_read_only(True); field.set_read_only(False)
    assert field.get_value() == value
    if value == '4000 ×g':
        assert field.unit_combo.currentText() == '×g'
    if value == '1000':
        assert field.unit_combo.currentText() == ''
    field.deleteLater()


def test_centrifugation_and_filtration_use_confirmed_unit_preferences(app):
    dialog = SchemaRecordDialog('SeparationMethod', {'type': 'Centrifugation', 'phase_to_keep': 'Liquid', 'speed': '4000 rpm'})
    speed = dialog.trackers['speed']
    assert isinstance(speed, UnitValueField)
    assert 'rpm' in [speed.unit_combo.itemText(i) for i in range(speed.unit_combo.count())]
    assert '×g' not in [speed.unit_combo.itemText(i) for i in range(speed.unit_combo.count())]
    speed.number_edit.setText('6500')
    dialog._accept_value()
    assert dialog.value['speed'] == '6500 rpm'
    filtration = SchemaRecordDialog('SeparationMethod', {'type': 'Filtration', 'phase_to_keep': 'Solid', 'filter_pore_size': '0.45 µm'})
    assert isinstance(filtration.trackers['filter_pore_size'], UnitValueField)
    filtration._accept_value()
    assert filtration.value['filter_pore_size'] == '0.45 µm'
    dialog.deleteLater(); filtration.deleteLater()


@pytest.mark.parametrize('cls,key,value', [
    ('Cell', 'culture_age', '3 days'), ('Cell', 'viability', '90 %'), ('Cell', 'confluence', '75 %'),
    ('Polymer', 'melting_temperature', '180 °C'), ('Polymer', 'number_average_molar_mass', '25000 g/mol'),
    ('MixtureConstituent', 'concentration', '2 mmol/L'),
])
def test_physical_strings_use_units_without_changing_model_types(app, cls, key, value):
    dialog = SchemaRecordDialog(cls, {'type': cls, key: value})
    assert field_config(key, cls)['range'] == 'string'
    assert isinstance(dialog.trackers[key], UnitValueField)
    assert dialog._read()[key] == value
    dialog.deleteLater()


def test_non_quantities_keep_their_schema_editors(app):
    assert field_config('passage_number', 'Cell')['type'] == 'text'
    assert field_config('optical_density', 'Cell')['type'] == 'text'
    assert field_config('si_al_ratio', 'Zeolite')['type'] == 'text'
    assert field_config('size_range', 'Sieving')['type'] == 'text'
    assert field_config('temperature_stability', 'Medium')['type'] == 'dropdown'


def test_add_style_is_shared_by_chemicals_records_blocks_and_complex_actions(app, monkeypatch):
    field = build_chemical_list_field(None, [], param_key='chemical_list')
    monkeypatch.setattr('labprogen.ui.editor.pick_embedded_chemical', lambda *args, **kwargs: {'chemical_type': 'Substance', 'name': 'water'})
    field._add_btn.click()
    assert field.list_value == [{'chemical_type': 'Substance', 'name': 'water'}]
    record = SchemaValueField(field_config('repeat_units', 'PolymerMixture'))
    binding = ComplexActionParameter(0, 'Separate', 'method', 'Method', value={})
    complex_field = ParameterValueEditor(binding)
    chemical_block = ChemicalBlock('Cell', {})
    scalar_chemical, _ = chemical_block._get_field_widget('suspension_medium', {})
    for widget in [field.widget, record, complex_field.widget, scalar_chemical]:
        add = next(b for b in widget.findChildren(QToolButton) if b.text() == '+ Add')
        assert add.styleSheet() == ADD_BUTTON_STYLE
        assert add.height() == 28 and add.minimumWidth() == 60
        assert add.toolTip()
    before = record.get_value()
    record.set_read_only(True)
    assert not next(b for b in record.findChildren(QToolButton) if b.text() == '+ Add').isEnabled()
    assert record.get_value() == before


def test_units_save_through_normal_and_complex_forms_and_concentration_picker(app, monkeypatch):
    value = '40.00 unknown/unit'
    block = ElementaryAction('ChangeTemperature', {'temperature': value, 'process': 'Plate-heater'})
    observed = []
    def save():
        dialog = app.activeModalWidget()
        try:
            unit = dialog.findChild(UnitValueField, 'temperature')
            observed.append(unit.get_value())
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Save Changes').click()
        finally:
            if dialog.isVisible(): dialog.reject()
    QTimer.singleShot(0, save)
    block.open_editor()
    assert observed == [value] and block.params['temperature'] == value
    binding = ComplexActionParameter(0, 'ChangeTemperature', 'temperature', 'Temperature', value=value)
    editor = ParameterValueEditor(binding)
    assert editor.value() == value
    editor.widget.number_edit.setText('45')
    assert editor.value() == '45 unknown/unit'
    picker = MixtureChemicalDialog(initial_type='Substance', initial_concentration='2 mmol/L')
    picker._accept()
    assert picker.concentration == '2 mmol/L'
    picker.deleteLater()
