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

from .config import (
    KEY_CAS_NUMBER,
    KEY_CONCENTRATION,
    KEY_ENTITY_ID,
    KEY_ENTITY_PURITY,
    KEY_FORMULA,
    KEY_GASES,
    KEY_NAME,
    KEY_PREPARATION_PROCEDURE,
    KEY_PRODUCER,
)
from .procedure_text import format_gas_entry_label

_ADD_BUTTON_STYLE = (
    "QToolButton {"
    "  font-size: 14px;"
    "  color: white;"
    "  background-color: #6b4cff;"
    "  border-radius: 6px;"
    "  border: 1px solid #5a3fe6;"
    "  padding: 0px; margin: 0px;"
    "}"
    "QToolButton:hover { background-color: #5a3fe6; }"
    "QToolButton:pressed { background-color: #4b33bf; }"
)

_LIST_ICON_BUTTON_STYLE = (
    "QToolButton {"
    "  background-color: #f8fafc;"
    "  border: 1px solid #e2e8f0;"
    "  border-radius: 5px;"
    "  color: #334155;"
    "}"
    "QToolButton:hover { background-color: #eef2ff; border-color: #c7d2fe; }"
    "QToolButton:pressed { background-color: #e0e7ff; }"
)


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
    ) -> None:
        self._parent = parent
        self._dialog_parent_override = dialog_parent
        self.param_key = param_key
        self.list_value = value if isinstance(value, list) else (value or [])
        self._read_only = read_only
        self._is_gas_list = param_key == KEY_GASES
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

        add_btn = QToolButton()
        add_btn.setText("+ Add")
        add_btn.setToolTip("Add chemical")
        add_btn.setAutoRaise(False)
        add_btn.setFixedHeight(28)
        add_btn.setMinimumWidth(60)
        add_btn.setStyleSheet(_ADD_BUTTON_STYLE)
        add_btn.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
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
        from .editor import (
            MixtureChemicalDialog,
            MixtureChemicalParametersDialog,
            UnifiedChemicalDetailsDialog,
            get_chemical_default_params,
            normalize_preparation_procedure,
        )

        dlg = MixtureChemicalDialog(self._dialog_parent())
        if self._open_dialog(dlg) != QDialog.DialogCode.Accepted:
            return

        details_dialog = UnifiedChemicalDetailsDialog(self._dialog_parent())
        if self._open_dialog(details_dialog) != QDialog.DialogCode.Accepted:
            return

        params_dlg = MixtureChemicalParametersDialog(
            dlg.selected_chemical_type,
            self._dialog_parent(),
            initial_params=get_chemical_default_params(dlg.selected_chemical_type),
        )
        if params_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        new_chem = {
            "chemical_type": dlg.selected_chemical_type,
            **params_dlg.chemical_params,
            **details_dialog.first_level_fields,
            KEY_CONCENTRATION: dlg.concentration,
        }
        if details_dialog.imported_procedure:
            new_chem[KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
                details_dialog.imported_procedure
            )

        chem_name = new_chem.get(KEY_NAME, "").strip()
        if not chem_name:
            QMessageBox.warning(
                self._dialog_parent(),
                "Missing Chemical Name",
                f"Chemical '{dlg.selected_chemical_type}' must have a name field filled.",
            )
            return

        self.list_value.append(new_chem)
        self._update_tags()

    def _edit_chemical(self, index: int) -> None:
        from .editor import (
            MixtureChemicalDialog,
            MixtureChemicalParametersDialog,
            UnifiedChemicalDetailsDialog,
            get_chemical_default_params,
            normalize_preparation_procedure,
        )

        chem = self.list_value[index]

        dlg = MixtureChemicalDialog(
            self._dialog_parent(),
            initial_type=chem.get("chemical_type", "Substance"),
            initial_concentration=chem.get(KEY_CONCENTRATION, ""),
        )
        if self._open_dialog(dlg) != QDialog.DialogCode.Accepted:
            return

        details_dialog = UnifiedChemicalDetailsDialog(self._dialog_parent())
        details_dialog.id_edit.setText(chem.get(KEY_ENTITY_ID, ""))
        details_dialog.producer_edit.setText(chem.get(KEY_PRODUCER, ""))
        details_dialog.purity_edit.setText(chem.get(KEY_ENTITY_PURITY, ""))
        details_dialog.cas_edit.setText(chem.get(KEY_CAS_NUMBER, ""))
        if KEY_PREPARATION_PROCEDURE in chem:
            details_dialog.imported_procedure = normalize_preparation_procedure(
                chem[KEY_PREPARATION_PROCEDURE]
            )
            details_dialog._set_status("✓ Procedure loaded", "success")
        if self._open_dialog(details_dialog) != QDialog.DialogCode.Accepted:
            return

        params_dlg = MixtureChemicalParametersDialog(
            dlg.selected_chemical_type,
            self._dialog_parent(),
            initial_params={
                **get_chemical_default_params(dlg.selected_chemical_type),
                **chem,
            },
        )
        if params_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        updated = {
            "chemical_type": dlg.selected_chemical_type,
            **params_dlg.chemical_params,
            **details_dialog.first_level_fields,
            KEY_CONCENTRATION: dlg.concentration,
        }
        if details_dialog.imported_procedure:
            updated[KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
                details_dialog.imported_procedure
            )

        chem_name = updated.get(KEY_NAME, "").strip()
        if not chem_name:
            QMessageBox.warning(
                self._dialog_parent(),
                "Missing Chemical Name",
                f"Chemical '{dlg.selected_chemical_type}' must have a name field filled.",
            )
            return

        self.list_value[index] = updated
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
            else:
                chem_type = chem.get("chemical_type", "Unknown")
                formula = chem.get(KEY_FORMULA, "n/a")
                conc = chem.get(KEY_CONCENTRATION, "")
                row_text = f"{chem_type}: {formula}"
                if conc:
                    row_text += f" ({conc})"

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

            edit_btn = QToolButton()
            edit_btn.setText("✎")
            edit_btn.setFixedSize(22, 22)
            edit_btn.setStyleSheet(_LIST_ICON_BUTTON_STYLE)
            edit_btn.setEnabled(not self._read_only)
            edit_btn.clicked.connect(lambda _checked=False, i=idx: self._edit_chemical(i))

            remove_btn = QToolButton()
            remove_btn.setText("✕")
            remove_btn.setFixedSize(22, 22)
            remove_btn.setStyleSheet(
                _LIST_ICON_BUTTON_STYLE
                + "QToolButton { font-weight: bold; color: #6b7280; }"
                + "QToolButton:hover { color: #ef4444; }"
            )
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
) -> ChemicalListField:
    return ChemicalListField(
        parent,
        value,
        param_key=param_key,
        read_only=read_only,
        dialog_parent=dialog_parent,
    )
