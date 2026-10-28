"""Editors for typed, nested values declared by the current LinkML schema."""

import copy

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
    QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)
from PySide6.QtGui import QIntValidator
from PySide6.QtCore import Qt
from .field_widgets import UnitValueField, compact_add_button, list_icon_button

from labprogen.core.model import concrete_classes, default_params, field_config, model_schema
from labprogen.linkml.loader import build_validation_schema, class_slot_constraints, ensure_six_meta_path_importer_compatibility


def _blank(value):
    return value is None or value == '' or value == [] or value == {}


def needs_retention(config, value):
    """Undeclared fields and incompatible historical shapes must stay lossless."""
    if not config.get('declared'):
        return True
    if _blank(value):
        return False
    if config.get('multivalued'):
        return not isinstance(value, list)
    if config.get('type') in {'record', 'single_chemical'}:
        return not isinstance(value, dict)
    return isinstance(value, (dict, list))


class RetainedValueField(QLineEdit):
    """Display a historical value without stringifying the stored data."""

    def __init__(self, value, parent=None):
        import json
        self._value = copy.deepcopy(value)
        super().__init__(value if isinstance(value, str) else json.dumps(value, ensure_ascii=False), parent)
        self.setReadOnly(True)
        self.setToolTip('Retained unchanged for review. This value does not match the current schema; export validation still applies.')

    def get_value(self):
        return copy.deepcopy(self._value)


def scalar_value(value, config):
    """Parse typed scalar input, retaining invalid drafts for strict validation."""
    if not isinstance(value, str) or not value:
        return value
    try:
        if config.get('range') == 'integer':
            return int(value)
        if config.get('range') in {'float', 'double', 'decimal'}:
            return float(value)
        if config.get('range') == 'boolean' and value in {'True', 'False'}:
            return value == 'True'
    except ValueError:
        pass
    return value


class SchemaValueField(QWidget):
    """A scalar record or list of records/primitive values, with modal editing."""

    def __init__(self, config, value=None, parent=None):
        super().__init__(parent)
        self.config = config
        self._value = copy.deepcopy(value if not _blank(value) else
                                    [] if config.get('multivalued') else {})
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._refresh()

    def get_value(self):
        return copy.deepcopy(self._value)

    def set_read_only(self, locked):
        self.setEnabled(not locked)

    def _refresh(self):
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if self.config.get('multivalued') and not isinstance(self._value, list):
            label = QLabel(f"Legacy value requires review: {self._value}", self)
            label.setWordWrap(True)
            self._layout.addWidget(label)
            clear = QPushButton('Clear legacy value', self)
            clear.clicked.connect(self._clear_legacy)
            self._layout.addWidget(clear)
            return
        values = self._value if self.config.get('multivalued') else ([] if _blank(self._value) else [self._value])
        for index, value in enumerate(values):
            row = QWidget(self)
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            if isinstance(value, dict):
                text = value.get('type') or value.get('name') or self.config['range']
            else:
                text = str(value)
            label = QLabel(str(text), row)
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMinimumWidth(0)
            label.setToolTip(str(text))
            label.setStyleSheet("color: #334155; padding: 4px 8px; background-color: #f1f5f9; border-radius: 4px;")
            edit = list_icon_button('✎', f'Edit {text}', row)
            edit.clicked.connect(lambda checked=False, i=index: self._edit(i))
            remove = list_icon_button('✕', f'Remove {text}', row)
            remove.clicked.connect(lambda checked=False, i=index: self._remove(i))
            layout.addWidget(label, 1)
            layout.addWidget(edit)
            layout.addWidget(remove)
            self._layout.addWidget(row)
        if self.config.get('multivalued') or not values:
            add = compact_add_button(self, tooltip=f"Add {self.config['label']}")
            add.clicked.connect(lambda: self._edit(None))
            self._layout.addWidget(add, alignment=Qt.AlignmentFlag.AlignLeft)

    def _clear_legacy(self):
        self._value = [] if self.config.get('multivalued') else {}
        self._refresh()

    def _remove(self, index):
        if self.config.get('multivalued'):
            self._value.pop(index)
        else:
            self._value = {}
        self._refresh()

    def _edit(self, index):
        multiple = self.config.get('multivalued')
        initial = (self._value[index] if multiple else self._value) if index is not None else None
        range_name = self.config['range']
        if range_name in model_schema()['classes']:
            dialog = SchemaRecordDialog(range_name, initial, self)
            if dialog.exec() != QDialog.Accepted:
                dialog.deleteLater()
                return
            value = dialog.value
            dialog.deleteLater()
        elif self.config.get('options'):
            options = self.config['options']
            value, accepted = QInputDialog.getItem(self, self.config['label'], 'Value:', options,
                max(0, options.index(initial) if initial in options else 0), False)
            if not accepted:
                return
        else:
            value, accepted = QInputDialog.getText(self, self.config['label'], 'Value:', text=str(initial or ''))
            if not accepted or not value.strip():
                return
            value = scalar_value(value.strip(), self.config)
        if multiple:
            if index is None:
                self._value.append(value)
            else:
                self._value[index] = value
        else:
            self._value = value
        self._refresh()


class SchemaRecordDialog(QDialog):
    def __init__(self, range_name, initial=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(range_name.replace('_', ' '))
        self.resize(560, 650)
        self.value = None
        self.initial = copy.deepcopy(initial or {})
        if not isinstance(self.initial, dict):
            self.initial = {'type': self.initial}
        schema = model_schema()
        choices = concrete_classes(range_name)
        base = schema['classes'][range_name]
        if not base.get('abstract') and not base.get('mixin'):
            choices.insert(0, range_name)
        if range_name == 'ChemicalEntity':
            choices = [n for n in choices if n not in {'ChemicalEntity', 'MixtureConstituent'}]
        self.selector = QComboBox(self)
        self.selector.addItem('Select...')
        self.selector.addItems(choices)
        self._drafts = {self.initial.get('type') or range_name: self.initial}
        self._class_name = None
        layout = QVBoxLayout(self)
        layout.addWidget(self.selector)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        layout.addWidget(self.scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self._accept_value)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.trackers = {}
        self.selector.currentTextChanged.connect(self._show_class)
        selected = self.initial.get('type') or (choices[0] if len(choices) == 1 else None)
        if selected in choices:
            self.selector.setCurrentText(selected)
        self.selector.setVisible(len(choices) > 1)

    def _read(self):
        result = {}
        if self._class_name and 'type' in class_slot_constraints(self._class_name)['allowed']:
            result['type'] = self._class_name
        for key, tracker in self.trackers.items():
            if callable(getattr(tracker, "get_value", None)):
                value = tracker.get_value()
            elif isinstance(tracker, QComboBox):
                value = tracker.currentText()
                if value == 'Select...':
                    value = ''
            else:
                value = tracker.text().strip()
            config = field_config(key, self._class_name)
            value = scalar_value(value, config)
            if not _blank(value) or not config['declared']:
                result[key] = value
        return result

    def _show_class(self, class_name):
        if self._class_name:
            self._drafts[self._class_name] = self._read()
        self._class_name = class_name if class_name in model_schema()['classes'] else None
        self.trackers = {}
        container = QWidget(self)
        form = QFormLayout(container)
        self.scroll.setWidget(container)
        if not self._class_name:
            return
        initial = self._drafts.get(class_name, {})
        params = {**default_params(class_name), **{k: v for k, v in initial.items() if k != 'type'}}
        for key, value in params.items():
            config = field_config(key, class_name)
            if needs_retention(config, value):
                widget = RetainedValueField(value, container)
            elif config['range'] in model_schema()['classes'] or config.get('multivalued'):
                widget = SchemaValueField(config, value, container)
            elif config['type'] == 'unit':
                widget = UnitValueField(config, value, container)
            elif config['type'] == 'dropdown':
                widget = QComboBox(container)
                widget.addItem('Select...'); widget.addItems(config['options'])
                if not _blank(value) and str(value) not in config['options']:
                    widget.addItem(str(value))
                widget.setCurrentText(str(value) if not _blank(value) else 'Select...')
            else:
                widget = QLineEdit(str(value) if value is not None else '', container)
                if config['range'] == 'integer':
                    widget.setValidator(QIntValidator(int(config.get('minimum', -999_999_999)), int(config.get('maximum', 999_999_999)), widget))
            widget.setObjectName(key)
            label = config['label'] + (' *' if config['required'] else '') + (' [undeclared; retained]' if not config['declared'] else '')
            form.addRow(label, widget)
            self.trackers[key] = widget

    def _accept_value(self):
        if not self._class_name:
            QMessageBox.warning(self, 'Missing type', 'Select a type.')
            return
        try:
            value = self._read()
            ensure_six_meta_path_importer_compatibility()
            from linkml.validator import validate
            result = validate(value, schema=build_validation_schema(), target_class=self._class_name, strict=True)
            if result.results:
                QMessageBox.warning(self, 'Invalid value', '\n'.join(r.message for r in result.results))
                return
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self, 'Invalid value', str(exc))
            return
        self.value = value
        self.accept()
