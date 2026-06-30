"""Shared parameter field widgets for complex-action dialogs."""

from __future__ import annotations

import json
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QWidget

from .block import configure_unit_decimal_input, format_decimal_for_input
from .complex_actions import ComplexActionParameter
from .config import FIELD_CONFIG

LOCKED_FIELD_TOOLTIP = (
    "The creator of this complex action marked this field as non-editable."
)

_LOCKED_LABEL_STYLE = "color: #94a3b8;"

LOCKED_LABEL_STYLE = _LOCKED_LABEL_STYLE

_LOCKED_WIDGET_STYLE = (
    "QLineEdit { background-color: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }"
    "QComboBox { background-color: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }"
    "QComboBox::drop-down:disabled { border: none; }"
    "QComboBox:disabled { background-color: #f1f5f9; color: #64748b; }"
)


def value_to_text(value: Any) -> str:
    if isinstance(value, list):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return ""
    return str(value)


def _parse_unit_parts(value: Any, param_key: str) -> tuple[str, str]:
    config = FIELD_CONFIG.get(param_key.lower(), {})
    units = config.get("units") or []
    default_unit = units[0] if units else ""
    text = str(value or "").strip()
    if " " in text:
        number, unit = text.rsplit(" ", 1)
        return format_decimal_for_input(number), unit
    if text in units:
        return "", text
    return format_decimal_for_input(text), default_unit


class ParameterValueEditor:
    """Widget + reader for one complex-action parameter value."""

    def __init__(
        self,
        binding: ComplexActionParameter,
        *,
        read_only: bool = False,
    ) -> None:
        self.binding = binding
        self._read_only = read_only
        config = FIELD_CONFIG.get(binding.param_key.lower(), {})
        self._field_type = config.get("type", "text")
        self.widget = self._build_widget(config)
        self._getter = self._build_getter()
        self._apply_locked_appearance(self._read_only)

    def _apply_locked_appearance(self, locked: bool) -> None:
        if locked:
            self.widget.setToolTip(LOCKED_FIELD_TOOLTIP)
            if self._field_type == "unit":
                self._unit_edit.setStyleSheet(_LOCKED_WIDGET_STYLE)
                self._unit_combo.setStyleSheet(_LOCKED_WIDGET_STYLE)
                self.widget.setStyleSheet("background-color: #f8fafc; border-radius: 4px;")
            elif self._field_type == "dropdown":
                self._dropdown_combo.setStyleSheet(_LOCKED_WIDGET_STYLE)
            else:
                self._line_edit.setStyleSheet(_LOCKED_WIDGET_STYLE)
            return

        self.widget.setToolTip("")
        if self._field_type == "unit":
            self._unit_edit.setStyleSheet("")
            self._unit_combo.setStyleSheet("")
            self.widget.setStyleSheet("")
        elif self._field_type == "dropdown":
            self._dropdown_combo.setStyleSheet("")
        else:
            self._line_edit.setStyleSheet("")

    def _build_widget(self, config: dict) -> QWidget:
        if self._field_type == "unit":
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)

            number, unit = _parse_unit_parts(self.binding.value, self.binding.param_key)
            if self.binding.unit and not unit:
                unit = self.binding.unit

            edit = QLineEdit(number)
            edit.setPlaceholderText(config.get("placeholder", "Value"))
            min_value = -273.15 if self.binding.param_key.lower() == "temperature" else 0.0
            configure_unit_decimal_input(edit, min_value=min_value)
            edit.setReadOnly(self._read_only)

            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(config.get("units", []))
            if unit:
                idx = combo.findText(unit)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setEditText(unit)
            combo.setEnabled(not self._read_only)

            layout.addWidget(edit, 2)
            layout.addWidget(combo, 1)
            self._unit_edit = edit
            self._unit_combo = combo
            return container

        if self._field_type == "dropdown":
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItem("Select...")
            combo.addItems(config.get("options", []))
            current = str(self.binding.value or "").strip()
            if current:
                idx = combo.findText(current)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                else:
                    combo.setEditText(current)
            combo.setEnabled(not self._read_only)
            self._dropdown_combo = combo
            return combo

        edit = QLineEdit(value_to_text(self.binding.value))
        edit.setReadOnly(self._read_only)
        self._line_edit = edit
        return edit

    def _build_getter(self) -> Callable[[], Any]:
        if self._field_type == "unit":
            def _get_unit() -> str:
                number = self._unit_edit.text().strip()
                unit = self._unit_combo.currentText().strip()
                if number and unit:
                    return f"{number} {unit}"
                return number or unit

            return _get_unit

        if self._field_type == "dropdown":
            def _get_dropdown() -> str:
                text = self._dropdown_combo.currentText().strip()
                return "" if text == "Select..." else text

            return _get_dropdown

        def _get_text() -> Any:
            text = self._line_edit.text().strip()
            if isinstance(self.binding.default_value, list):
                try:
                    return json.loads(text) if text else []
                except json.JSONDecodeError:
                    return text
            return text

        return _get_text

    def value(self) -> Any:
        return self._getter()

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only
        if self._field_type == "unit":
            self._unit_edit.setReadOnly(read_only)
            self._unit_combo.setEnabled(not read_only)
        elif self._field_type == "dropdown":
            self._dropdown_combo.setEnabled(not read_only)
        else:
            self._line_edit.setReadOnly(read_only)
        self._apply_locked_appearance(read_only)
