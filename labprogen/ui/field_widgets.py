"""Shared presentation controls for list fields and string-valued quantities."""

import copy
import re

from PySide6.QtCore import QLocale, Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QSizePolicy, QToolButton, QWidget


ADD_BUTTON_STYLE = """
QToolButton {
    font-size: 14px; color: white; background-color: #6b4cff;
    border-radius: 6px; border: 1px solid #5a3fe6; padding: 0px 8px;
}
QToolButton:hover { background-color: #5a3fe6; }
QToolButton:pressed { background-color: #4b33bf; }
QToolButton:focus { border: 2px solid #4338ca; }
QToolButton:disabled { color: #94a3b8; background-color: #f1f5f9; border-color: #cbd5e1; }
"""

LIST_ICON_BUTTON_STYLE = """
QToolButton {
    background-color: #f8fafc; border: 1px solid #e2e8f0;
    border-radius: 5px; color: #334155;
}
QToolButton:hover { background-color: #eef2ff; border-color: #c7d2fe; }
QToolButton:pressed { background-color: #e0e7ff; }
QToolButton:focus { border: 2px solid #64748b; }
QToolButton:disabled { color: #94a3b8; background-color: #f1f5f9; }
"""


def compact_add_button(parent=None, *, tooltip='Add item'):
    button = QToolButton(parent)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.setText('+ Add')
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setAutoRaise(False)
    button.setFixedHeight(28)
    button.setMinimumWidth(60)
    button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
    button.setStyleSheet(ADD_BUTTON_STYLE)
    return button


def list_icon_button(text, tooltip, parent=None):
    button = QToolButton(parent)
    button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    button.setText(text)
    button.setToolTip(tooltip)
    button.setAccessibleName(tooltip)
    button.setFixedSize(22, 22)
    button.setStyleSheet(LIST_ICON_BUTTON_STYLE)
    return button


_NUMBER_AND_UNIT = re.compile(r'^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*(.*?)\s*$')


class UnitValueField(QWidget):
    """Edit a schema string without converting units or rewriting untouched data.

    Units are suggestions. Unlisted units, bare numbers and descriptive historical
    strings remain intact. This is not a second physical-quantity data model.
    """

    def __init__(self, config, value='', parent=None):
        super().__init__(parent)
        self._original = copy.deepcopy(value if value is not None else '')
        text = str(self._original)
        match = _NUMBER_AND_UNIT.fullmatch(text) if text else None
        self._raw = bool(text and not match)
        self.number_edit = QLineEdit(self)
        self.number_edit.setPlaceholderText(config.get('placeholder') or 'Value')
        self.unit_combo = QComboBox(self)
        self.unit_combo.setEditable(True)
        self.unit_combo.addItems(config.get('units', []))
        if match:
            number, unit = match.groups()
        elif text:
            number, unit = text, ''
        else:
            number, unit = '', self.unit_combo.currentText()
        self.number_edit.setText(number)
        if self.unit_combo.findText(unit) < 0:
            self.unit_combo.addItem(unit)
        self.unit_combo.setCurrentText(unit)
        if self._raw:
            self.unit_combo.setEnabled(False)
            self.number_edit.setToolTip('Existing text is preserved as entered; no unit conversion is applied.')
        else:
            validator = QDoubleValidator(self.number_edit)
            validator.setLocale(QLocale.c())
            self.number_edit.setValidator(validator)
        self._initial_controls = (number, unit)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.number_edit, 2)
        layout.addWidget(self.unit_combo, 1)
        # Preserve the existing (line edit, combo) tracker API used by block forms.
        self.number_edit._unit_value_field = self

    def get_value(self):
        number, unit = self.number_edit.text(), self.unit_combo.currentText()
        if (number, unit) == self._initial_controls:
            return copy.deepcopy(self._original)
        if self._raw:
            return number
        number, unit = number.strip(), unit.strip()
        return f'{number} {unit}' if number and unit else number

    def set_read_only(self, locked):
        self.number_edit.setReadOnly(locked)
        self.unit_combo.setEnabled(not locked and not self._raw)
