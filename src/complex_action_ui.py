"""UI for creating and finalizing user-defined complex actions."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from .block import field_label
from .complex_action_fields import LOCKED_FIELD_TOOLTIP, LOCKED_LABEL_STYLE, ParameterValueEditor
from .complex_actions import (
    ComplexActionDefinition,
    ComplexActionParameter,
    ComplexActionRegistry,
    apply_parameters_to_member_blocks,
    build_parameter_bindings,
    collect_flow_steps_from_editor,
    copy_instance_parameters,
    dictionary_filename,
    get_complex_action_registry,
    is_complex_action_step,
    parameters_to_block_params,
    step_display_name,
    validate_definition,
    validate_instance_parameters,
)
from .config import FIELD_CONFIG
from .editor import Editor

_BUTTON_STYLE = (
    "QPushButton {"
    "  background-color: #6b4cff; color: white; border-radius: 6px;"
    "  padding: 8px 16px; font-weight: 600;"
    "}"
    "QPushButton:hover { background-color: #5a3de6; }"
)

_SECTION_LABEL_STYLE = (
    "font-size: 13px; font-weight: 700; color: #334155; padding-top: 4px;"
)

_EMPTY_STEP_NOTE_STYLE = (
    "color: #94a3b8; font-style: italic; padding: 0 0 6px 0;"
)


def _add_action_section(
    layout: QVBoxLayout,
    *,
    action_name: str,
    step_index: int,
    show_separator: bool,
) -> QFormLayout:
    if show_separator:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #d1d5db;")
        layout.addWidget(line)

    header = QLabel(f"{action_name}  ·  step {step_index + 1}")
    header.setStyleSheet(_SECTION_LABEL_STYLE)
    layout.addWidget(header)

    form_host = QWidget()
    form = QFormLayout(form_host)
    form.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(form_host)
    return form


def _add_empty_step_note(form: QFormLayout, *, text: str | None = None) -> None:
    note = QLabel(text or "No configurable parameters for this step.")
    note.setStyleSheet(_EMPTY_STEP_NOTE_STYLE)
    form.addRow(note)


class ComplexActionFinalizeDialog(QDialog):
    """Single dialog: complex action name + grouped parameter configuration."""

    def __init__(
        self,
        steps: list[dict],
        *,
        registry: ComplexActionRegistry | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Define Complex Action")
        self.setMinimumWidth(560)
        self._steps = steps
        self._registry = registry or get_complex_action_registry()
        self._bindings = build_parameter_bindings(steps)
        self.definition: ComplexActionDefinition | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(14)

        title = QLabel("Complex Action Parameters")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #1e293b;")
        root.addWidget(title)

        name_group = QGroupBox("Complex Action Name")
        name_layout = QFormLayout(name_group)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Unique name for this complex action...")
        name_layout.addRow("Name:", self._name_edit)
        root.addWidget(name_group)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setSpacing(10)

        self._display_edits: dict[int, QLineEdit] = {}
        self._value_editors: dict[int, ParameterValueEditor] = {}
        self._editable_checks: dict[int, QCheckBox] = {}

        grouped: dict[int, list[tuple[int, ComplexActionParameter]]] = {}
        for index, binding in enumerate(self._bindings):
            grouped.setdefault(binding.step_index, []).append((index, binding))

        for position, step_index in enumerate(range(len(self._steps))):
            step = self._steps[step_index]
            action_name = step_display_name(step)
            items = grouped.get(step_index, [])
            form = _add_action_section(
                scroll_layout,
                action_name=action_name,
                step_index=step_index,
                show_separator=position > 0,
            )
            if not items:
                if is_complex_action_step(step):
                    _add_empty_step_note(
                        form,
                        text="Parameters are defined by the nested complex action.",
                    )
                else:
                    _add_empty_step_note(form)
                continue
            for binding_index, binding in items:
                self._display_edits[binding_index] = QLineEdit(binding.display_name)
                form.addRow("Label:", self._display_edits[binding_index])

                editor = ParameterValueEditor(binding, read_only=False)
                self._value_editors[binding_index] = editor
                form.addRow("Value:", editor.widget)

                editable = QCheckBox("Editable when used in protocols")
                editable.setChecked(binding.editable)
                editable.setStyleSheet(
                    "QCheckBox { spacing: 8px; padding: 4px 0 8px 0; color: #334155; }"
                    "QCheckBox::indicator { width: 16px; height: 16px; }"
                )
                self._editable_checks[binding_index] = editable
                form.addRow(editable)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        save_btn = QPushButton("Save Complex Action")
        save_btn.setStyleSheet(_BUTTON_STYLE)
        save_btn.clicked.connect(self._save)
        button_row.addWidget(save_btn)
        root.addLayout(button_row)

    def _collect_bindings(self) -> list[ComplexActionParameter]:
        updated: list[ComplexActionParameter] = []
        for index, binding in enumerate(self._bindings):
            value = self._value_editors[index].value()
            config = FIELD_CONFIG.get(binding.param_key.lower(), {})
            unit = binding.unit
            if config.get("type") == "unit" and isinstance(value, str) and " " in value:
                unit = value.rsplit(" ", 1)[-1]
            updated.append(
                ComplexActionParameter(
                    step_index=binding.step_index,
                    action=binding.action,
                    param_key=binding.param_key,
                    display_name=self._display_edits[index].text().strip()
                    or field_label(binding.param_key, binding.action),
                    editable=self._editable_checks[index].isChecked(),
                    unit=unit,
                    default_value=binding.default_value,
                    value=value,
                )
            )
        return updated

    def _save(self) -> None:
        name = self._name_edit.text().strip()
        definition = ComplexActionDefinition(
            name=name,
            steps=self._steps,
            parameters=self._collect_bindings(),
        )
        errors = validate_definition(definition, self._registry)
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        self.definition = definition
        self.accept()


class ComplexActionFlowEditorDialog(QDialog):
    """Flow builder for a new complex action (structure only, no param dialogs)."""

    def __init__(self, parent=None, *, registry: ComplexActionRegistry | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Complex Action - Flow")
        self.resize(1200, 820)
        self._registry = registry or get_complex_action_registry()
        self._parent_editor = parent if parent is not None and hasattr(parent, "complex_action_groups") else None
        self.definition: ComplexActionDefinition | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._flow_editor = Editor()
        self._flow_editor.set_complex_action_builder_mode(True)
        layout.addWidget(self._flow_editor.container, 1)

        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(16, 8, 16, 12)
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(120, 36)
        cancel_btn.setStyleSheet(_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        continue_btn = QPushButton("Continue to Parameters")
        continue_btn.setMinimumSize(180, 36)
        continue_btn.setStyleSheet(_BUTTON_STYLE)
        continue_btn.clicked.connect(self._continue_to_parameters)
        button_layout.addWidget(continue_btn)
        layout.addWidget(button_bar)

    def _continue_to_parameters(self) -> None:
        steps = collect_flow_steps_from_editor(self._flow_editor)
        if not steps:
            QMessageBox.warning(
                self,
                "Empty Flow",
                "Add at least one action to the flow before continuing.",
            )
            return

        finalize = ComplexActionFinalizeDialog(steps, registry=self._registry, parent=self)
        if finalize.exec() != QDialog.DialogCode.Accepted or finalize.definition is None:
            return

        self.definition = finalize.definition
        self._registry.register(self.definition)

        if self._parent_editor is not None:
            from .complex_action_protocol import materialize_complex_action

            materialize_complex_action(
                self._parent_editor,
                self.definition.name,
                self.definition.parameters,
                source_editor=self._flow_editor,
            )

        self._offer_dictionary_export(self.definition)
        self.accept()

    def _offer_dictionary_export(self, definition: ComplexActionDefinition) -> None:
        answer = QMessageBox.question(
            self,
            "Export Dictionary",
            (
                f"Complex action {definition.name!r} was saved.\n\n"
                "Export its dictionary file now to finish setup?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        default_name = dictionary_filename(definition.name)
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Complex Action Dictionary",
            default_name,
            "JSON Files (*.json)",
        )
        if not filename:
            return
        if not filename.lower().endswith(".json"):
            filename = f"{filename}.json"
        try:
            with open(filename, "w", encoding="utf-8") as handle:
                handle.write(definition.to_json())
            QMessageBox.information(
                self,
                "Dictionary Exported",
                f"Dictionary saved to:\n{filename}",
            )
        except OSError as exc:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Could not export dictionary:\n{exc}",
            )


def start_new_complex_action_wizard(parent=None) -> ComplexActionDefinition | None:
    """Open the full new-complex-action wizard; return the saved definition or None."""
    dialog = ComplexActionFlowEditorDialog(parent=parent)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.definition


class ComplexActionUseDialog(QDialog):
    """Configure a complex action instance before inserting it into a protocol."""

    def __init__(
        self,
        definition: ComplexActionDefinition,
        *,
        initial_parameters: list[ComplexActionParameter] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(definition.name)
        self.setMinimumWidth(520)
        self._definition = definition
        self._bindings = [
            ComplexActionParameter.from_dict(param.to_dict())
            for param in (initial_parameters or copy_instance_parameters(definition))
        ]

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(12)

        title = QLabel(f"Complex Action: {definition.name}")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #0f766e;")
        root.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)

        self._value_editors: dict[int, ParameterValueEditor] = {}
        grouped: dict[int, list[tuple[int, ComplexActionParameter]]] = {}
        for index, binding in enumerate(self._bindings):
            grouped.setdefault(binding.step_index, []).append((index, binding))

        for position, step_index in enumerate(range(len(definition.steps))):
            step = definition.steps[step_index]
            action_name = step_display_name(step)
            items = grouped.get(step_index, [])
            form = _add_action_section(
                scroll_layout,
                action_name=action_name,
                step_index=step_index,
                show_separator=position > 0,
            )
            if not items:
                if is_complex_action_step(step):
                    _add_empty_step_note(
                        form,
                        text="Parameters are defined by the nested complex action.",
                    )
                else:
                    _add_empty_step_note(form)
                continue
            for binding_index, binding in items:
                editor = ParameterValueEditor(binding, read_only=not binding.editable)
                self._value_editors[binding_index] = editor

                label = QLabel(binding.display_name + ":")
                if not binding.editable:
                    label.setStyleSheet(LOCKED_LABEL_STYLE)
                    label.setToolTip(LOCKED_FIELD_TOOLTIP)
                form.addRow(label, editor.widget)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        root.addWidget(scroll, 1)

        button_row = QHBoxLayout()
        button_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)
        ok_btn = QPushButton("Insert")
        ok_btn.setStyleSheet(_BUTTON_STYLE)
        ok_btn.clicked.connect(self._accept)
        button_row.addWidget(ok_btn)
        root.addLayout(button_row)

    def _collect_bindings(self) -> list[ComplexActionParameter]:
        updated: list[ComplexActionParameter] = []
        for index, binding in enumerate(self._bindings):
            if binding.editable:
                value = self._value_editors[index].value()
            else:
                value = binding.value
            updated.append(
                ComplexActionParameter(
                    step_index=binding.step_index,
                    action=binding.action,
                    param_key=binding.param_key,
                    display_name=binding.display_name,
                    editable=binding.editable,
                    unit=binding.unit,
                    default_value=binding.default_value,
                    value=value,
                )
            )
        return updated

    def _accept(self) -> None:
        parameters = self._collect_bindings()
        errors = validate_instance_parameters(parameters, self._definition)
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        self._bindings = parameters
        self.accept()

    def parameters(self) -> list[ComplexActionParameter]:
        return list(self._bindings)


def prompt_complex_action_use(
    definition: ComplexActionDefinition,
    *,
    initial_parameters: list[ComplexActionParameter] | None = None,
    parent=None,
) -> list[ComplexActionParameter] | None:
    dialog = ComplexActionUseDialog(
        definition,
        initial_parameters=initial_parameters,
        parent=parent,
    )
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return dialog.parameters()


def edit_complex_action_instance(surrogate_block) -> None:
    """Re-open the instance dialog for a complex-action surrogate block."""
    editor = getattr(surrogate_block, "editor", None)
    group_id = getattr(surrogate_block, "complex_group_id", None)
    if editor is None or not group_id:
        return
    group = editor.complex_action_groups.get(group_id)
    if group is None:
        return
    definition = get_complex_action_registry().get(group.definition_name)
    if definition is None:
        QMessageBox.warning(
            surrogate_block.editor,
            "Missing Definition",
            f"Complex action {group.definition_name!r} is not in the local registry.",
        )
        return
    parameters = prompt_complex_action_use(
        definition,
        initial_parameters=group.parameters,
        parent=editor.container if hasattr(editor, "container") else None,
    )
    if parameters is None:
        return
    group.parameters = parameters
    apply_parameters_to_member_blocks(group)
    surrogate_block.params = parameters_to_block_params(group.definition_name, parameters)
    surrogate_block.update_text()
    if hasattr(editor, "update_support_logic"):
        editor.update_support_logic()
