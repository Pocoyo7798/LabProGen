"""Shared chemical list field widget (+ Add / edit / remove)."""

from __future__ import annotations

from typing import Any

from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from labprogen.core.config import (
    UI_FIELD_PREFERENCES,
    KEY_CHEMICAL_LIST,
    KEY_CONCENTRATION,
    KEY_FORMULA,
    KEY_GASES,
)
from labprogen.text.procedure_text import format_gas_entry_label

from .field_widgets import compact_add_button, list_icon_button


class ChemicalListField:
    """Mutable chemical list with the same UI used on protocol action blocks."""

    def __init__(
        self,
        parent: QWidget,
        value: Any,
        *,
        param_key: str,
        read_only: bool = False,
        dialog_parent: QWidget | None = None,
        config: dict | None = None,
    ) -> None:
        self._parent = parent
        self._dialog_parent_override = dialog_parent
        self.param_key = param_key
        self.list_value = value if isinstance(value, list) else (value or [])
        if not isinstance(self.list_value, list):
            self.list_value = []
        self._read_only = read_only
        self._is_gas_list = param_key == KEY_GASES
        config = config if config is not None else UI_FIELD_PREFERENCES.get(str(param_key).lower(), {})
        self._include_concentration = bool(
            config.get("include_concentration", param_key == KEY_CHEMICAL_LIST)
        )
        self.widget = self._build_widget()

    def _dialog_parent(self) -> QWidget:
        """Prefer the modal dialog that currently hosts this field."""
        if self._dialog_parent_override is not None:
            return self._dialog_parent_override

        app = QApplication.instance()
        if app is not None:
            modal = app.activeModalWidget()
            if modal is not None:
                return modal

        current: QWidget | None = self.widget
        while current is not None:
            if isinstance(current, QDialog):
                return current
            current = current.parentWidget()
        return self._parent

    def _open_dialog(self, dialog: QDialog) -> int:
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        return dialog.exec()

    def set_read_only(self, read_only: bool) -> None:
        self._read_only = read_only
        self._add_btn.setEnabled(not read_only)
        self._update_tags()

    def _build_widget(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        add_btn = compact_add_button(container, tooltip="Add chemical")
        add_btn.setEnabled(not self._read_only)
        add_btn.clicked.connect(self._add_chemical)
        self._add_btn = add_btn

        button_layout.addWidget(add_btn)
        layout.addLayout(button_layout)

        rows_container = QWidget()
        rows_layout = QVBoxLayout(rows_container)
        rows_layout.setContentsMargins(0, 0, 0, 0)
        rows_layout.setSpacing(4)
        self._rows_layout = rows_layout
        layout.addWidget(rows_container)

        self._update_tags()
        container._chemical_list_field = self
        return container

    def _add_chemical(self) -> None:
        try:
            self._add_chemical_impl()
        except Exception as exc:
            QMessageBox.critical(
                self._dialog_parent(),
                "Add Chemical",
                f"Could not open the chemical dialog.\n\n{exc}",
            )

    def _add_chemical_impl(self) -> None:
        from .editor import pick_embedded_chemical

        picked = pick_embedded_chemical(
            self._dialog_parent(),
            {},
            include_concentration=self._include_concentration,
        )
        if not picked:
            return
        self.list_value.append(picked)
        self._update_tags()

    def _edit_chemical(self, index: int) -> None:
        from .editor import pick_embedded_chemical

        chem = self.list_value[index]
        picked = pick_embedded_chemical(
            self._dialog_parent(),
            chem,
            include_concentration=self._include_concentration,
        )
        if not picked:
            return
        self.list_value[index] = picked
        self._update_tags()

    def _remove_chemical(self, index: int) -> None:
        if 0 <= index < len(self.list_value):
            del self.list_value[index]
            self._update_tags()

    def _update_tags(self) -> None:
        while self._rows_layout.count():
            child = self._rows_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for idx, chem in enumerate(self.list_value):
            if self._is_gas_list:
                row_text = format_gas_entry_label(chem)
            elif self._include_concentration:
                chem_type = chem.get("chemical_type", "Unknown")
                formula = chem.get(KEY_FORMULA, "n/a")
                conc = chem.get(KEY_CONCENTRATION, "")
                row_text = f"{chem_type}: {formula}"
                if conc:
                    row_text += f" ({conc})"
            else:
                from labprogen.text.procedure_text import chemical_display_name

                chem_type = chem.get("chemical_type") or chem.get("type") or chem.get("chemical") or "Unknown"
                name = chemical_display_name(chem)
                row_text = f"{chem_type}: {name}" if name else str(chem_type)

            row_widget = QWidget()
            row_widget.setFixedHeight(28)
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)

            text_label = QLabel()
            text_label.setToolTip(row_text)
            text_label.setStyleSheet(
                "background-color: #e0e7ff; color: #3730a3; padding: 4px 8px; "
                "border-radius: 4px; font-size: 11px; border: 1px solid #c7d2fe;"
            )
            text_label.setFixedHeight(28)
            text_label.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            text_label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
            fm = QFontMetrics(text_label.font())
            text_label.setText(
                fm.elidedText(row_text, Qt.TextElideMode.ElideRight, 220)
            )

            edit_btn = list_icon_button("✎", "Edit chemical", row_widget)
            edit_btn.setEnabled(not self._read_only)
            edit_btn.clicked.connect(lambda _checked=False, i=idx: self._edit_chemical(i))

            remove_btn = list_icon_button("✕", "Remove chemical", row_widget)
            remove_btn.setEnabled(not self._read_only)
            remove_btn.clicked.connect(
                lambda _checked=False, i=idx: self._remove_chemical(i)
            )

            row_layout.addWidget(text_label, 1)
            row_layout.addWidget(edit_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            row_layout.addWidget(remove_btn, 0, Qt.AlignmentFlag.AlignVCenter)
            self._rows_layout.addWidget(row_widget)

        self._rows_layout.addStretch()


def build_chemical_list_field(
    parent: QWidget,
    value: Any,
    *,
    param_key: str,
    read_only: bool = False,
    dialog_parent: QWidget | None = None,
    config: dict | None = None,
) -> ChemicalListField:
    return ChemicalListField(
        parent,
        value,
        param_key=param_key,
        read_only=read_only,
        dialog_parent=dialog_parent,
        config=config,
    )
