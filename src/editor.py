import copy
import json
import re
from PySide6.QtWidgets import (
    QFileDialog, QGraphicsRectItem, QGraphicsView, QGraphicsScene, QDialog, QMessageBox, QPushButton, QToolTip,
    QVBoxLayout, QHBoxLayout, QWidget, QLabel, QComboBox, QFormLayout, QLineEdit, QToolButton, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QSizePolicy,
)
from PySide6.QtCore import Qt, QPointF, QTimer, QObject, QEvent
from PySide6.QtGui import QCursor, QFont, QPainter, QColor
from .block import (
    ElementaryAction,
    SupportAction,
    ChemicalBlock,
    ComplexActionBlock,
    configure_unit_decimal_input,
    format_decimal_for_input,
)
from .config import *
from .actions import *
from .chemicals import *
from .protocol import Protocol
from .linkml_adapter import convert_linkml_to_protocol, STEP_SLOT_TO_PARAM, CHEMICAL_SLOT_TO_PARAM
from .schema_exporter import convert_protocol_to_linkml, summarize_linkml_export
from .schema_validator import validate_linkml_protocol
from .procedure_text import build_procedure_text

PRIMARY_BUTTON_STYLE = (
    "QPushButton {"
    "background-color: #6b4cff; color: white; border-radius: 8px;"
    "padding: 6px 14px; font-weight: 600; border: none;"
    "}"
    "QPushButton:hover { background-color: #5a3fe6; }"
    "QPushButton:pressed { background-color: #4b33bf; }"
)

STATUS_BADGE_STYLE = {
    "neutral": "background-color: #f3f4f6; color: #4b5563; border: 1px solid #d1d5db;",
    "success": "background-color: #ecfdf3; color: #166534; border: 1px solid #86efac;",
    "info": "background-color: #eef2ff; color: #3730a3; border: 1px solid #c7d2fe;",
}


def normalize_preparation_procedure(procedure):
    """Canonicalize an embedded preparation procedure for storage in chemical params.

    ``preview_flows`` is only used on canvas-owned procedures where it may be a
    subset of ``flows`` (hidden flows linked via chemical_block_id). For chemicals
    inside a mixture list, storing a duplicate copy is redundant.
    """
    if not isinstance(procedure, dict):
        return procedure

    normalized = copy.deepcopy(procedure)
    flows = normalized.get("flows", [])
    preview = normalized.get("preview_flows")
    if preview is not None and preview == flows:
        normalized.pop("preview_flows", None)
    normalized["total_flows"] = len(flows)
    return normalized


def get_chemical_default_params(chemical_type: str) -> dict:
    """Return the default parameter dictionary for a chemical type."""
    defaults = {
        "Substance": {KEY_NAME: ""},
        "MixtureChemical": {"chemical_type": "Substance", KEY_FORMULA: "", KEY_CONCENTRATION: ""},
        "Material": {KEY_FORMULA: "", KEY_STRUCT_DESC: "", KEY_TEXTURAL_DESC: "", KEY_CHEM_DESC: ""},
        "Mixture": {KEY_NAME: "", KEY_CHEMICAL_LIST: []},
        "PerfectSingleCrystalMaterial": {KEY_FORMULA: "", KEY_CIF: ""},
        "Molecules": {
            KEY_ENTITY_TYPE: "Substance",
            KEY_NAME: "",
            KEY_FORMULA: "",
            KEY_SMILES: "",
            KEY_INCHI: "",
        },
        "Polymers": {
            KEY_ENTITY_TYPE: "Substance",
            KEY_NAME: "",
            KEY_FORMULA: "",
            KEY_BIGSMILES: "",
            KEY_INCHI: "",
        },
        "Media": {
            KEY_ENTITY_TYPE: "Substance",
            KEY_NAME: "",
            KEY_CHEMICAL_LIST: [],
            KEY_QUANTITY: "",
            KEY_FUNCTION: "",
            KEY_STATE: "",
            KEY_CONCENTRATION: "",
            KEY_PURITY: "",
            KEY_STERILITY: "",
            KEY_SOLUBILITY: "",
            KEY_TEMPERATURE_STABILITY: "",
            KEY_LIGHT_SENSITIVITY: "",
            KEY_OXIDATION_SENSITIVITY: "",
        },
        "Dispersion": {
            KEY_ENTITY_TYPE: "Mixture",
            KEY_NAME: "",
            KEY_CHEMICAL_LIST: [],
            KEY_SOLVENT: {},
        },
        "BioProducts": {
            KEY_ENTITY_TYPE: "Substance",
            KEY_NAME: "",
            KEY_ORIGIN: "",
            KEY_PRODUCTION_PHASE: "",
            KEY_LOCATION: "",
            KEY_TEMPERATURE_STABILITY: "",
            KEY_LIGHT_SENSITIVITY: "",
            KEY_OXIDATION_SENSITIVITY: "",
            KEY_TOXICITY_TO_PRODUCER: "",
        },
        "HeterogeneousCatalysts": {
            KEY_ENTITY_TYPE: "Substance",
            KEY_NAME: "",
            KEY_FORMULA: "",
            KEY_3D_STRUCTURE: "",
            KEY_CRYSTALLINITY: "",
            KEY_N2_ADSORPTION_BET_AREA: "",
            KEY_N2_ADSORPTION_MICROPORE_AREA: "",
            KEY_N2_ADSORPTION_MESOPORE_AREA: "",
            KEY_N2_ADSORPTION_TOTAL_VOLUME: "",
            KEY_N2_ADSORPTION_MICROPORE_VOLUME: "",
            KEY_N2_MESOPORE_VOLUME: "",
            KEY_PY_B_150: "",
            KEY_PY_B_450: "",
            KEY_PY_L_150: "",
            KEY_PY_L_450: "",
        },
    }
    return copy.deepcopy(defaults.get(chemical_type, {}))

NEW_COMPLEX_ACTION = "__new_complex_action__"


class ActionSelectionDialog(QDialog):
    def __init__(self, parent=None, *, complex_action_names: list[str] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Add Action")
        self.setMinimumWidth(680)
        self.selected_action = None
        self._complex_action_names = list(complex_action_names or [])
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Select an Action")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        main_layout.addWidget(title)
        
        # main container for columns
        grid = QHBoxLayout()
        
        # elementary actions column
        elem_layout = QVBoxLayout()
        elem_label = QLabel("Elementary Actions")
        elem_label.setStyleSheet("color: #6b4cff; font-weight: bold;")
        elem_layout.addWidget(elem_label)
        
        self.btn_elementary = {
            "Add": "+ Add",
            "Grind": "🔨 Grind",
            "Separate": "⚗ Separate",
            "Sieve": "🏁 Sieve",
            "Wait": "⏳ Wait"
        }
        
        for action_id, label in self.btn_elementary.items():
            btn = QPushButton(label)
            btn.clicked.connect(lambda checked=False, a=action_id: self.select_action(a))
            elem_layout.addWidget(btn)
        
        # push all elementary buttons to the top
        elem_layout.addStretch()

        # support actions column
        supp_layout = QVBoxLayout()
        supp_label = QLabel("Support Actions")
        supp_label.setStyleSheet("color: #3498db; font-weight: bold;")
        supp_layout.addWidget(supp_label)
        
        self.btn_support = {
            "ChangeAtmosphere": "☁ Change Atmosphere",
            "ChangeTemperature": "🌡 Change Temperature",
            "NewRecipient": "🧪 New Recipient",
            "ChangeAgitation": "🔄 Change Agitation",
            "Repeat": "🔁 Repeat",
            "ContinuousAddition": "➕ Continuous Addition"
        }
        
        for action_id, label in self.btn_support.items():
            btn = QPushButton(label)
            btn.setStyleSheet("background-color: #3498db;") 
            btn.clicked.connect(lambda checked=False, a=action_id: self.select_action(a))
            supp_layout.addWidget(btn)
        
        # push all support buttons to the top
        supp_layout.addStretch()

        complex_layout = QVBoxLayout()
        complex_label = QLabel("Complex Actions")
        complex_label.setStyleSheet("color: #0f766e; font-weight: bold;")
        complex_layout.addWidget(complex_label)

        for action_name in self._complex_action_names:
            btn = QPushButton(action_name)
            btn.setStyleSheet("background-color: #14b8a6; color: white;")
            btn.clicked.connect(
                lambda checked=False, name=action_name: self.select_action(name)
            )
            complex_layout.addWidget(btn)

        new_complex_btn = QPushButton("Add New Complex Action")
        new_complex_btn.setStyleSheet("background-color: #0d9488; color: white;")
        new_complex_btn.clicked.connect(
            lambda checked=False: self.select_action(NEW_COMPLEX_ACTION)
        )
        complex_layout.addWidget(new_complex_btn)
        complex_layout.addStretch()
            
        grid.addLayout(elem_layout)
        grid.addLayout(supp_layout)
        grid.addLayout(complex_layout)
        main_layout.addLayout(grid)
        
        self.adjustSize()
        self.setLayout(main_layout)
    
    def select_action(self, action):
        self.selected_action = action
        self.accept()

class ChemicalSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Chemical Entity")
        self.setMinimumWidth(350)
        self.selected_chemical = None
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("Select an Entity Type")
        title.setFont(QFont("Segoe UI", 12, QFont.Bold))
        layout.addWidget(title)
        
        # list of all entities from the data model
        # Second Level and Third Level chemicals
        entities = {
            # Ordered as requested by user
            # Third Level
            "BioProducts": "BioProducts",
            "Molecules": "Molecules",
            "Polymers": "Polymers",
            "Media": "Media",
            "Dispersion": "Dispersion (Mixture)",
            "HeterogeneousCatalysts": "HeterogeneousCatalysts",
        }
        
        for key, label in entities.items():
            btn = QPushButton(label)
            # use a green style for chemicals
            btn.setStyleSheet("background-color: #2ecc71;") 
            btn.clicked.connect(lambda checked=False, k=key: self.select_chemical(k))
            layout.addWidget(btn)
        
        self.adjustSize()
        self.setLayout(layout)
    
    def select_chemical(self, chemical):
        self.selected_chemical = chemical
        self.accept()


class UnifiedChemicalDetailsDialog(QDialog):
    """Single dialog for adding chemical entity with First Level fields.
    
    First Level fields are optional:
    - ID (commercial or internal)
    - Producer (institution)
    - Purity
    - CAS Number
    
    Preparation procedure is managed through import/create buttons.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Chemical Entity Details")
        self.setMinimumWidth(480)
        self.imported_procedure = None
        self.first_level_fields = {}

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        # First Level Chemical Entity Section
        first_label = QLabel("Chemical Information (optional)")
        first_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1f2937;")
        layout.addWidget(first_label)

        first_form = QFormLayout()
        first_form.setSpacing(10)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("Commercial or internal ID...")
        first_form.addRow("ID:", self.id_edit)

        self.producer_edit = QLineEdit()
        self.producer_edit.setPlaceholderText("Institution that created the entity...")
        first_form.addRow("Producer:", self.producer_edit)

        self.purity_edit = QLineEdit()
        self.purity_edit.setPlaceholderText("Degree of purity...")
        first_form.addRow("Purity:", self.purity_edit)

        self.cas_edit = QLineEdit()
        self.cas_edit.setPlaceholderText("Commercial identification number...")
        first_form.addRow("CAS Number:", self.cas_edit)

        layout.addLayout(first_form)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        layout.addWidget(sep)

        # Preparation Procedure Import Section
        proc_label = QLabel("Preparation Procedure (optional)")
        proc_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1f2937;")
        layout.addWidget(proc_label)

        proc_desc = QLabel("Import or create a preparation procedure for this entity")
        proc_desc.setStyleSheet("font-size: 11px; color: #6b7280;")
        layout.addWidget(proc_desc)

        import_btn = QPushButton("Import Procedure")
        import_btn.setMinimumHeight(32)
        import_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        import_btn.clicked.connect(self._import_procedure)
        layout.addWidget(import_btn)

        new_btn = QPushButton("Create New Procedure")
        new_btn.setMinimumHeight(32)
        new_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        new_btn.clicked.connect(self._new_procedure)
        layout.addWidget(new_btn)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setStyleSheet("padding: 8px 10px; border-radius: 6px; font-size: 11px;")
        self._set_status("No procedure selected.", "neutral")
        layout.addWidget(self.status)

        # Action Buttons
        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(92, 34)
        cancel_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        ok_btn = QPushButton("Add Chemical")
        ok_btn.setMinimumSize(92, 34)
        ok_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        ok_btn.clicked.connect(self._accept)
        button_row.addWidget(ok_btn)

        layout.addLayout(button_row)
        self.adjustSize()

    def _set_status(self, message, tone="neutral"):
        style = STATUS_BADGE_STYLE.get(tone, STATUS_BADGE_STYLE["neutral"])
        self.status.setText(message)
        self.status.setStyleSheet(f"padding: 8px 10px; border-radius: 6px; font-size: 11px; {style}")

    def _import_procedure(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Import Procedure", "", "JSON Files (*.json)")
        if not filename:
            return
        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or "flows" not in data:
                QMessageBox.warning(self, "Invalid File", "The selected file does not contain a valid protocol.")
                return
            self.imported_procedure = normalize_preparation_procedure(data)
            self._set_status(f"✓ Imported: {filename.split('/')[-1]}", "success")
        except Exception as e:
            QMessageBox.warning(self, "Import Error", f"Could not import procedure: {e}")

    def _new_procedure(self):
        # Top-level modal: nested exec() on the details dialog breaks on Linux.
        dialog = EntityProcedureEditorDialog(
            None,
            initial_procedure=self.imported_procedure,
        )
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.raise_()
        dialog.activateWindow()
        if dialog.exec() == QDialog.Accepted and dialog.procedure_data:
            self.imported_procedure = normalize_preparation_procedure(dialog.procedure_data)
            flow_count = len(self.imported_procedure.get("flows", []))
            self._set_status(f"✓ Procedure saved ({flow_count} flow(s))", "success")

    def _accept(self):
        # Collect First Level fields
        id_val = self.id_edit.text().strip()
        prod_val = self.producer_edit.text().strip()
        pur_val = self.purity_edit.text().strip()
        cas_val = self.cas_edit.text().strip()

        self.first_level_fields = {
            KEY_ENTITY_ID: id_val,
            KEY_PRODUCER: prod_val,
            KEY_ENTITY_PURITY: pur_val,
            KEY_CAS_NUMBER: cas_val,
        }
        
        self.accept()


def pick_embedded_chemical(parent, initial=None, *, for_solvent=False):
    """Pick one embedded chemical (e.g. mixture list item or dispersion solvent). Returns dict or None."""
    initial = dict(initial or {})
    parent_dialog = parent
    initial_type = initial.get("chemical_type", "Substance" if for_solvent else "Molecules")
    initial_concentration = "" if for_solvent else initial.get(KEY_CONCENTRATION, "")

    dlg = MixtureChemicalDialog(
        parent_dialog,
        initial_type=initial_type,
        initial_concentration=initial_concentration,
        for_solvent=for_solvent,
    )
    if dlg.exec() != QDialog.Accepted:
        return None

    details_dialog = UnifiedChemicalDetailsDialog(parent_dialog)
    details_dialog.id_edit.setText(initial.get(KEY_ENTITY_ID, ""))
    details_dialog.producer_edit.setText(initial.get(KEY_PRODUCER, ""))
    details_dialog.purity_edit.setText(initial.get(KEY_ENTITY_PURITY, ""))
    details_dialog.cas_edit.setText(initial.get(KEY_CAS_NUMBER, ""))
    if KEY_PREPARATION_PROCEDURE in initial:
        details_dialog.imported_procedure = normalize_preparation_procedure(
            initial[KEY_PREPARATION_PROCEDURE]
        )
        details_dialog._set_status("✓ Procedure loaded", "success")
    if details_dialog.exec() != QDialog.Accepted:
        return None

    params_dlg = MixtureChemicalParametersDialog(
        dlg.selected_chemical_type,
        parent_dialog,
        initial_params={**get_chemical_default_params(dlg.selected_chemical_type), **initial},
    )
    if params_dlg.exec() != QDialog.Accepted:
        return None

    result = {
        "chemical_type": dlg.selected_chemical_type,
        **params_dlg.chemical_params,
        **details_dialog.first_level_fields,
    }
    if not for_solvent:
        result[KEY_CONCENTRATION] = dlg.concentration
    if details_dialog.imported_procedure:
        result[KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
            details_dialog.imported_procedure
        )

    chem_name = result.get(KEY_NAME, "").strip()
    if not chem_name:
        QMessageBox.warning(
            parent_dialog,
            "Missing Chemical Name",
            f"Chemical '{dlg.selected_chemical_type}' must have a name field filled.",
        )
        return None
    return result


class MixtureChemicalParametersDialog(QDialog):
    """Second step dialog that reuses the normal chemical editor."""
    def __init__(self, chemical_type, parent=None, initial_params=None):
        super().__init__(parent)
        self.selected_chemical_type = chemical_type
        self.initial_params = initial_params or {}
        self.chemical_params = {}

    def exec(self):
        temp_params = get_chemical_default_params(self.selected_chemical_type)
        temp_params.update(self.initial_params)

        temp_block = ChemicalBlock(self.selected_chemical_type, temp_params, editor=self.parent())
        temp_block.open_editor()

        if getattr(temp_block, "_editor_accepted", False):
            self.chemical_params = temp_block.params.copy()
            return QDialog.Accepted

        return QDialog.Rejected


class MixtureChemicalDialog(QDialog):
    """First step dialog for a MixtureChemical item.
    
    Collects only the chemical type and concentration.
    """
    def __init__(self, parent=None, initial_type="Substance", initial_concentration="", for_solvent=False):
        super().__init__(parent)
        self.for_solvent = for_solvent
        self.setWindowTitle("Select Solvent" if for_solvent else "Edit Mixture Chemical")
        self.setMinimumWidth(420)
        self.selected_chemical_type = None
        self.concentration = ""

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        type_label = QLabel("Chemical Type")
        type_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1f2937;")
        layout.addWidget(type_label)

        self.type_combo = QComboBox()
        self.type_combo.addItem("Select...", "")
        if for_solvent:
            self.type_combo.addItem("Substance", "Substance")
            self.type_combo.addItem("Mixture", "Mixture")
        else:
            self.type_combo.addItem("Molecules", "Molecules")
            self.type_combo.addItem("BioProducts", "BioProducts")
            self.type_combo.addItem("Polymers", "Polymers")
            self.type_combo.addItem("Media", "Media")
            self.type_combo.addItem("HeterogeneousCatalysts", "HeterogeneousCatalysts")
        idx = self.type_combo.findData(initial_type)
        if idx < 0:
            idx = self.type_combo.findData("Substance" if for_solvent else "Molecules")
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)
        layout.addWidget(self.type_combo)

        self.conc_label = None
        self.conc_edit = None
        self.conc_unit = None
        if not for_solvent:
            conc_label = QLabel("Concentration")
            conc_label.setStyleSheet("font-size: 12px; font-weight: 600; color: #1f2937;")
            layout.addWidget(conc_label)
            self.conc_label = conc_label

            conc_container = QWidget()
            conc_layout = QHBoxLayout(conc_container)
            conc_layout.setContentsMargins(0, 0, 0, 0)
            conc_layout.setSpacing(8)

            self.conc_edit = QLineEdit()
            self.conc_edit.setPlaceholderText("Enter value")
            configure_unit_decimal_input(self.conc_edit, min_value=0.0)

            self.conc_unit = QComboBox()
            self.conc_unit.addItems(FIELD_CONFIG[KEY_CONCENTRATION].get("units", []))

            if initial_concentration:
                parts = initial_concentration.strip().split()
                if len(parts) == 2:
                    self.conc_edit.setText(format_decimal_for_input(parts[0]))
                    cidx = self.conc_unit.findText(parts[1])
                    if cidx >= 0:
                        self.conc_unit.setCurrentIndex(cidx)
                elif len(parts) == 1 and parts[0]:
                    self.conc_edit.setText(format_decimal_for_input(parts[0]))

            conc_layout.addWidget(self.conc_edit, 2)
            conc_layout.addWidget(self.conc_unit, 1)
            layout.addWidget(conc_container)

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(92, 34)
        cancel_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        next_btn = QPushButton("Next")
        next_btn.setMinimumSize(92, 34)
        next_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        next_btn.clicked.connect(self._accept)
        button_row.addWidget(next_btn)

        layout.addLayout(button_row)
        self.adjustSize()

    def _accept(self):
        self.selected_chemical_type = self.type_combo.currentData()
        if not self.selected_chemical_type:
            QMessageBox.warning(self, "Missing Required Field", "Please select a chemical type.")
            return
        if not self.for_solvent and self.conc_edit and self.conc_unit:
            value = self.conc_edit.text().strip()
            unit = self.conc_unit.currentText().strip()
            self.concentration = f"{value} {unit}" if value else ""
        else:
            self.concentration = ""
        self.accept()


class MixtureChemicalListDialog(QDialog):
    """Dialog to manage list of MixtureChemical items for a Mixture.
    
    Shows a table of chemicals with concentration, allows Add/Edit/Remove.
    """
    def __init__(self, parent=None, chemical_list=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Mixture Chemicals")
        self.setFixedSize(600, 400)
        
        if chemical_list is None:
            chemical_list = []
        self.chemical_list = chemical_list.copy() if isinstance(chemical_list, list) else []

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Chemicals in Mixture")
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1f2937;")
        layout.addWidget(title)

        # Table to display chemicals
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Type", "Formula/Name", "Concentration", "Actions"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        layout.addWidget(self.table)

        self._populate_table()

        # Buttons for list management
        list_btn_row = QHBoxLayout()
        
        add_btn = QPushButton("Add Chemical")
        add_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        add_btn.clicked.connect(self._add_chemical)
        list_btn_row.addWidget(add_btn)

        list_btn_row.addStretch()
        layout.addLayout(list_btn_row)

        # Dialog action buttons
        dialog_btn_row = QHBoxLayout()
        dialog_btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(92, 34)
        cancel_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        dialog_btn_row.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setMinimumSize(92, 34)
        ok_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        ok_btn.clicked.connect(self.accept)
        dialog_btn_row.addWidget(ok_btn)

        layout.addLayout(dialog_btn_row)

    def _populate_table(self):
        """Populate table with current chemicals."""
        self.table.setRowCount(len(self.chemical_list))
        for row, chem in enumerate(self.chemical_list):
            chem_type = chem.get("chemical_type", "Unknown")
            formula = chem.get(KEY_FORMULA, chem.get("name", "n/a"))
            concentration = chem.get(KEY_CONCENTRATION, "n/a")

            self.table.setItem(row, 0, QTableWidgetItem(chem_type))
            self.table.setItem(row, 1, QTableWidgetItem(formula))
            self.table.setItem(row, 2, QTableWidgetItem(concentration))

            # Edit/Remove buttons
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(0, 0, 0, 0)

            edit_btn = QPushButton("Edit")
            edit_btn.setMaximumWidth(50)
            edit_btn.clicked.connect(lambda checked=False, r=row: self._edit_chemical(r))
            actions_layout.addWidget(edit_btn)

            remove_btn = QPushButton("Remove")
            remove_btn.setMaximumWidth(70)
            remove_btn.clicked.connect(lambda checked=False, r=row: self._remove_chemical(r))
            actions_layout.addWidget(remove_btn)

            self.table.setCellWidget(row, 3, actions_widget)

    def _add_chemical(self):
        """Open dialog to add new chemical."""
        dialog = MixtureChemicalDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        # First Level Chemical Details (ID, Producer, Purity, Procedure)
        details_dialog = UnifiedChemicalDetailsDialog(self)
        if details_dialog.exec() != QDialog.Accepted:
            return

        params_dlg = MixtureChemicalParametersDialog(
            dialog.selected_chemical_type,
            self,
            initial_params=get_chemical_default_params(dialog.selected_chemical_type),
        )
        if params_dlg.exec() != QDialog.Accepted:
            return

        new_chem = {
            "chemical_type": dialog.selected_chemical_type,
            **params_dlg.chemical_params,
            **details_dialog.first_level_fields,
            KEY_CONCENTRATION: dialog.concentration,
        }
        if details_dialog.imported_procedure:
            new_chem[KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
                details_dialog.imported_procedure
            )
        
        # Validate that chemical has a name (required for all chemicals)
        chem_name = new_chem.get(KEY_NAME, "").strip()
        if not chem_name:
            QMessageBox.warning(self, "Missing Chemical Name", f"Chemical '{dialog.selected_chemical_type}' must have a name field filled.")
            return
        
        self.chemical_list.append(new_chem)
        self._populate_table()

    def _edit_chemical(self, row):
        """Open dialog to edit chemical at row."""
        if 0 <= row < len(self.chemical_list):
            chem = self.chemical_list[row]
            dialog = MixtureChemicalDialog(self, initial_type=chem.get("chemical_type", "Substance"), initial_concentration=chem.get(KEY_CONCENTRATION, ""))
            if dialog.exec() != QDialog.Accepted:
                return

            # First Level Chemical Details (ID, Producer, Purity, Procedure)
            details_dialog = UnifiedChemicalDetailsDialog(self)
            # Pre-fill with existing values
            details_dialog.id_edit.setText(chem.get(KEY_ENTITY_ID, ""))
            details_dialog.producer_edit.setText(chem.get(KEY_PRODUCER, ""))
            details_dialog.purity_edit.setText(chem.get(KEY_ENTITY_PURITY, ""))
            details_dialog.cas_edit.setText(chem.get(KEY_CAS_NUMBER, ""))
            if KEY_PREPARATION_PROCEDURE in chem:
                details_dialog.imported_procedure = normalize_preparation_procedure(
                    chem[KEY_PREPARATION_PROCEDURE]
                )
                details_dialog._set_status("✓ Procedure loaded", "success")
            if details_dialog.exec() != QDialog.Accepted:
                return

            params_dialog = MixtureChemicalParametersDialog(
                dialog.selected_chemical_type,
                self,
                initial_params={**get_chemical_default_params(chem.get("chemical_type", "Substance")), **chem},
            )
            if params_dialog.exec() != QDialog.Accepted:
                return

            self.chemical_list[row] = {
                "chemical_type": dialog.selected_chemical_type,
                **params_dialog.chemical_params,
                **details_dialog.first_level_fields,
                KEY_CONCENTRATION: dialog.concentration,
            }
            if details_dialog.imported_procedure:
                self.chemical_list[row][KEY_PREPARATION_PROCEDURE] = normalize_preparation_procedure(
                    details_dialog.imported_procedure
                )
            
            # Validate that chemical has a name (required for all chemicals)
            chem_name = self.chemical_list[row].get(KEY_NAME, "").strip()
            if not chem_name:
                QMessageBox.warning(self, "Missing Chemical Name", f"Chemical '{dialog.selected_chemical_type}' must have a name field filled.")
                return
            self._populate_table()

    def _remove_chemical(self, row):
        """Remove chemical at row."""
        if 0 <= row < len(self.chemical_list):
            del self.chemical_list[row]
            self._populate_table()

    def get_chemical_list(self):
        """Return the managed chemical list."""
        return self.chemical_list


class _ProcedureGuidePopupFilter(QObject):
    """Keep the guide popup open while the pointer is over the button or popup."""

    def __init__(self, editor: "Editor"):
        super().__init__(editor)
        self._editor = editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            self._editor._cancel_procedure_guide_hide()
            self._editor._show_procedure_guide_popup()
            return False
        if event.type() == QEvent.Type.Leave:
            self._editor._schedule_procedure_guide_hide()
            return False
        return False


class ExportProtocolDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Protocol")
        self.setMinimumWidth(420)
        self.export_kind = "protocol"
        self.export_format = "json"

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("Choose how to export the protocol")
        title.setStyleSheet("font-size: 13px; font-weight: 600; color: #1f2937;")
        layout.addWidget(title)

        kind_label = QLabel("Export type")
        layout.addWidget(kind_label)
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("Internal protocol", "protocol")
        self.kind_combo.addItem("LinkML (strict)", "linkml")
        self.kind_combo.addItem("Procedure guide (text)", "procedure_text")
        layout.addWidget(self.kind_combo)

        format_label = QLabel("File format")
        layout.addWidget(format_label)
        self.format_combo = QComboBox()
        self.format_combo.addItem("JSON", "json")
        self.format_combo.addItem("YAML", "yaml")
        self.format_combo.addItem("Plain text", "txt")
        layout.addWidget(self.format_combo)
        self.kind_combo.currentIndexChanged.connect(self._sync_export_format_options)
        self._sync_export_format_options()

        button_row = QHBoxLayout()
        button_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(92, 34)
        cancel_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_row.addWidget(cancel_btn)

        export_btn = QPushButton("Export")
        export_btn.setMinimumSize(92, 34)
        export_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        export_btn.clicked.connect(self._accept)
        button_row.addWidget(export_btn)

        layout.addLayout(button_row)

    def _sync_export_format_options(self) -> None:
        is_text_guide = self.kind_combo.currentData() == "procedure_text"
        self.format_combo.setEnabled(not is_text_guide)
        if is_text_guide:
            idx = self.format_combo.findData("txt")
            if idx >= 0:
                self.format_combo.setCurrentIndex(idx)

    def _accept(self):
        self.export_kind = self.kind_combo.currentData() or "protocol"
        self.export_format = self.format_combo.currentData() or "json"
        if self.export_kind == "procedure_text":
            self.export_format = "txt"
        self.accept()


class Editor(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setSceneRect(0, 0, 1200, 900)
        self.setWindowTitle("Laboratory Protocol Builder")
        self.blocks = []
        self.linked_sequence = []
        self.link_distance = 100  # Distance threshold for linking
        self.protocol = Protocol()
        self.protocol_data = {}
        self.open_entity_procedures = {}
        self.chemical_procedure_index = {}
        self.preview_mode = False
        self.complex_action_builder_mode = False
        self.complex_action_groups = {}
        self.show_complex_actions_collapsed = False
        self._complex_group_counter = 0
        self.show_support_actions = True
        self._support_hidden_positions = {}
        self._support_hidden_visibility = {}
        
        container = QWidget()
        main_layout = QVBoxLayout(container)
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        self._procedure_guide_pinned = False
        self._procedure_guide_hide_timer = QTimer(self)
        self._procedure_guide_hide_timer.setSingleShot(True)
        self._procedure_guide_hide_timer.setInterval(200)
        self._procedure_guide_hide_timer.timeout.connect(self._hide_procedure_guide_popup)

        # configure navigation behavior and rendering quality
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # ensure scrollbars appear when needed but don't clutter the UI
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # setup floating zoom, support toggle, and procedure guide
        self.setup_zoom_buttons()
        
        # Title bar
        self.title_label = QLabel("Laboratory Protocol Builder")
        title_font = self.title_label.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.title_label.setFont(title_font)
        main_layout.addWidget(self.title_label)
        
        # Button bar
        self.button_bar_widget = QWidget()
        button_layout = QHBoxLayout(self.button_bar_widget)
        button_layout.setSpacing(8)
        
        self.add_action_btn = QPushButton("+ Add Action")
        self.add_chemical_btn = QPushButton("🧪 Add Chemical")
        self.export_btn = QPushButton("📥 Export Protocol")
        self.import_btn = QPushButton("📂 Import Protocol")
        self.import_complex_dict_btn = QPushButton("📖 Import Complex Dict")
        
        self.add_action_btn.clicked.connect(self.show_action_dialog)
        self.add_chemical_btn.clicked.connect(self.add_chemical_block)
        self.export_btn.clicked.connect(self.export_protocol)
        self.import_btn.clicked.connect(self.import_protocol)
        self.import_complex_dict_btn.clicked.connect(self.import_complex_action_dictionary)
        
        self._button_bar_layout = button_layout
        self._main_toolbar_buttons = [
            self.add_action_btn,
            self.add_chemical_btn,
            self.export_btn,
            self.import_btn,
            self.import_complex_dict_btn,
        ]
        self._button_bar_has_trailing_stretch = False
        self._button_bar_builder_pad = False
        for btn in self._main_toolbar_buttons:
            button_layout.addWidget(btn, 1)
        self._sync_button_bar_layout()
        main_layout.addWidget(self.button_bar_widget)
        
        # Canvas
        self.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #d0d4db;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """)
        
        main_layout.addWidget(self, 1)

        container.setLayout(main_layout)
        self.container = container
        self.refresh_procedure_guide()

    def set_preview_mode(self, enabled=True):
        self.preview_mode = enabled
        widgets = [
            getattr(self, "title_label", None),
            getattr(self, "button_bar_widget", None),
            getattr(self, "overlay_widget", None),
            getattr(self, "zoom_controls_widget", None),
            getattr(self, "procedure_guide_popup", None),
        ]
        for widget in widgets:
            if widget:
                widget.setVisible(not enabled)

        self.setInteractive(not enabled)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def set_complex_action_builder_mode(self, enabled: bool = True) -> None:
        """Restrict editor to building a complex-action skeleton (no chemicals / param dialogs)."""
        self.complex_action_builder_mode = enabled
        if hasattr(self, "add_chemical_btn"):
            self.add_chemical_btn.setVisible(not enabled)
        if hasattr(self, "export_btn"):
            self.export_btn.setVisible(not enabled)
        if hasattr(self, "import_btn"):
            self.import_btn.setVisible(not enabled)
        if hasattr(self, "import_complex_dict_btn"):
            self.import_complex_dict_btn.setVisible(not enabled)
        if hasattr(self, "overlay_widget"):
            self.overlay_widget.setVisible(not enabled)
        if hasattr(self, "title_label"):
            self.title_label.setVisible(not enabled)
        self._sync_button_bar_layout()

    def _sync_button_bar_layout(self) -> None:
        """Main window: toolbar buttons share full width. Builder: Add Action matches one main-toolbar slot."""
        layout = getattr(self, "_button_bar_layout", None)
        buttons = getattr(self, "_main_toolbar_buttons", None)
        if layout is None or buttons is None:
            return

        builder = getattr(self, "complex_action_builder_mode", False)

        if self._button_bar_builder_pad:
            item = layout.takeAt(layout.count() - 1)
            if item is not None:
                del item
            self._button_bar_builder_pad = False

        if self._button_bar_has_trailing_stretch:
            item = layout.takeAt(layout.count() - 1)
            if item is not None:
                del item
            self._button_bar_has_trailing_stretch = False

        if builder:
            for btn in buttons:
                idx = layout.indexOf(btn)
                if idx >= 0:
                    layout.setStretch(idx, 1 if btn is self.add_action_btn else 0)
            self.add_action_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.add_action_btn.setMinimumHeight(40)
            layout.addStretch(4)
            self._button_bar_builder_pad = True
            return

        for btn in buttons:
            idx = layout.indexOf(btn)
            if idx >= 0:
                layout.setStretch(idx, 1)
        self.add_action_btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.add_action_btn.setMinimumHeight(0)

    def blocks_share_complex_group(self, block_a, block_b) -> bool:
        group_id = getattr(block_a, "complex_group_id", None)
        return bool(group_id and group_id == getattr(block_b, "complex_group_id", None))

    def get_complex_action_group(self, block):
        group_id = getattr(block, "complex_group_id", None)
        if not group_id:
            return None
        return self.complex_action_groups.get(group_id)

    def move_complex_group(self, anchor_block, dx: float, dy: float) -> None:
        """Move every block in a complex-action group together."""
        group = self.get_complex_action_group(anchor_block)
        if group is None:
            anchor_block.setPos(anchor_block.pos().x() + dx, anchor_block.pos().y() + dy)
            return

        targets = list(group.member_blocks)
        if group.surrogate_block is not None:
            targets.append(group.surrogate_block)

        moved: set = set()
        for block in targets:
            if block in moved:
                continue
            moved.add(block)
            block.setPos(block.pos().x() + dx, block.pos().y() + dy)
            if block in group.member_blocks and block.chem_below:
                self._move_branch(block.chem_below, dx, dy, moved)

    def _group_is_collapsed_display(self, group) -> bool:
        surrogate = group.surrogate_block
        return bool(
            getattr(self, "show_complex_actions_collapsed", False)
            and surrogate is not None
            and surrogate.isVisible()
        )

    def _groups_share_block(self, group, block) -> bool:
        if block is None:
            return False
        block_group = self.get_complex_action_group(block)
        if block_group is None or group is None:
            return False
        return block_group.group_id == group.group_id

    def _complex_group_connector(self, group, *, collapsed: bool):
        if collapsed and group.surrogate_block is not None:
            return group.surrogate_block
        return group.member_blocks[0]

    def _complex_group_tail_connector(self, group, *, collapsed: bool):
        if collapsed and group.surrogate_block is not None:
            return group.surrogate_block
        return group.member_blocks[-1]

    def _complex_group_link_width(self, group, *, collapsed: bool) -> float:
        if collapsed and group.surrogate_block is not None:
            return float(group.surrogate_block.rect().width())
        from .complex_action_protocol import _complex_group_horizontal_span

        return _complex_group_horizontal_span(group.member_blocks)

    def _can_be_left_neighbor_of_group(self, target, group) -> bool:
        if self._groups_share_block(group, target):
            return False
        if getattr(target, "is_complex_surrogate", False) and target.isVisible():
            return True
        if getattr(target, "part_of_complex_action", False):
            other = self.get_complex_action_group(target)
            if other is None or not other.member_blocks:
                return False
            return target is other.member_blocks[-1]
        return True

    def _can_be_right_neighbor_of_group(self, target, group) -> bool:
        if self._groups_share_block(group, target):
            return False
        if getattr(target, "is_complex_surrogate", False) and target.isVisible():
            return True
        if getattr(target, "part_of_complex_action", False):
            other = self.get_complex_action_group(target)
            if other is None or not other.member_blocks:
                return False
            return target is other.member_blocks[0]
        return True

    def _pluck_complex_group_externals(self, group, *, collapsed: bool):
        first = group.member_blocks[0]
        last = group.member_blocks[-1]
        head = self._complex_group_connector(group, collapsed=collapsed)
        tail = self._complex_group_tail_connector(group, collapsed=collapsed)

        old_left = head.prev_block
        old_right = tail.next_block

        if old_left is not None and not self.blocks_share_complex_group(head, old_left):
            old_left.next_block = None
            head.prev_block = None
            if not collapsed:
                first.prev_block = None

        if old_right is not None and not self.blocks_share_complex_group(tail, old_right):
            old_right.prev_block = None
            tail.next_block = None
            if not collapsed:
                last.next_block = None

        return old_left, old_right

    def _restore_complex_group_externals(self, group, old_left, old_right, *, collapsed: bool) -> None:
        head = self._complex_group_connector(group, collapsed=collapsed)
        tail = self._complex_group_tail_connector(group, collapsed=collapsed)
        first = group.member_blocks[0]
        last = group.member_blocks[-1]

        if old_left is not None and not self.blocks_share_complex_group(head, old_left):
            old_left.next_block = head
            head.prev_block = old_left
            if not collapsed:
                first.prev_block = old_left

        if old_right is not None and not self.blocks_share_complex_group(tail, old_right):
            old_right.prev_block = tail
            tail.next_block = old_right
            if not collapsed:
                last.next_block = old_right

    def _snap_complex_group_after(self, group, target, *, collapsed: bool, overlap: float) -> None:
        head = self._complex_group_connector(group, collapsed=collapsed)
        snap_x = target.pos().x() + target.rect().width() - overlap
        snap_y = target.pos().y()
        dx = snap_x - head.pos().x()
        dy = snap_y - head.pos().y()
        if abs(dx) > 0.01 or abs(dy) > 0.01:
            self.move_complex_group(head, dx, dy)

    def _snap_complex_group_before(self, group, target, *, collapsed: bool, overlap: float) -> None:
        tail = self._complex_group_tail_connector(group, collapsed=collapsed)
        snap_x = target.pos().x() - tail.rect().width() + overlap
        snap_y = target.pos().y()
        dx = snap_x - tail.pos().x()
        dy = snap_y - tail.pos().y()
        if abs(dx) > 0.01 or abs(dy) > 0.01:
            self.move_complex_group(tail, dx, dy)

    def _attach_complex_group_after(self, group, target, *, collapsed: bool, overlap: float) -> None:
        head = self._complex_group_connector(group, collapsed=collapsed)
        first = group.member_blocks[0]
        tail = target.next_block
        if tail is not None and not self.blocks_share_complex_group(head, tail):
            shift = self._complex_group_link_width(group, collapsed=collapsed) - overlap
            if shift > 0:
                self.push_chain(tail, shift)

        self._snap_complex_group_after(group, target, collapsed=collapsed, overlap=overlap)
        target.next_block = head
        head.prev_block = target
        if not collapsed:
            first.prev_block = target

        head.set_connected(True)
        target.set_connected(True)
        head.update()
        target.update()

    def _attach_complex_group_before(self, group, target, *, collapsed: bool, overlap: float) -> None:
        tail = self._complex_group_tail_connector(group, collapsed=collapsed)
        last = group.member_blocks[-1]
        head = self._complex_group_connector(group, collapsed=collapsed)

        self._snap_complex_group_before(group, target, collapsed=collapsed, overlap=overlap)
        tail.next_block = target
        target.prev_block = tail
        if not collapsed:
            last.next_block = target

        tail.set_connected(True)
        target.set_connected(True)
        tail.update()
        target.update()

    def finalize_complex_group_links(self, anchor_block) -> None:
        """Try to connect a dragged complex-action group to external neighbors."""
        group = self.get_complex_action_group(anchor_block)
        if group is None or not group.member_blocks:
            return

        collapsed = self._group_is_collapsed_display(group)
        head = self._complex_group_connector(group, collapsed=collapsed)
        tail = self._complex_group_tail_connector(group, collapsed=collapsed)
        overlap = 20

        old_left, old_right = self._pluck_complex_group_externals(group, collapsed=collapsed)
        linked = False

        target, zone = self._get_target_and_zone(head)
        if (
            target
            and zone == "RIGHT"
            and not isinstance(target, ChemicalBlock)
            and target.orientation == "horizontal"
            and self._can_be_left_neighbor_of_group(target, group)
        ):
            self._attach_complex_group_after(group, target, collapsed=collapsed, overlap=overlap)
            linked = True

        if not linked:
            target, zone = self._get_target_and_zone(tail)
            if (
                target
                and zone == "LEFT"
                and not isinstance(target, ChemicalBlock)
                and target.orientation == "horizontal"
                and self._can_be_right_neighbor_of_group(target, group)
            ):
                self._attach_complex_group_before(group, target, collapsed=collapsed, overlap=overlap)
                linked = True

        if not linked:
            self._restore_complex_group_externals(group, old_left, old_right, collapsed=collapsed)
        elif collapsed:
            from .complex_action_protocol import refresh_collapsed_group_layout

            refresh_collapsed_group_layout(self, group)

        self.reflow_entire_cluster(head)

    def _is_export_horizontal_flow_head(self, block) -> bool:
        """Find chain heads for export, independent of collapsed surrogate wiring."""
        if isinstance(block, ComplexActionBlock) or getattr(block, "is_complex_surrogate", False):
            return False
        prev = block.prev_block
        if prev is None:
            return self._is_horizontal_flow_head(block)
        if isinstance(prev, ComplexActionBlock):
            return False
        if getattr(prev, "part_of_complex_action", False):
            group = self.get_complex_action_group(prev)
            if group and prev is group.member_blocks[-1]:
                return False
        return False

    def _is_horizontal_flow_head(self, block) -> bool:
        if block.prev_block is not None:
            return False
        if block.next_block is not None:
            return True
        if block.is_first and block.orientation == "horizontal":
            return True
        if getattr(block, "part_of_complex_action", False):
            group = self.get_complex_action_group(block)
            if group and block is group.member_blocks[0]:
                return True
        return False

    def _toggle_support_visibility(self, checked: bool) -> None:
        self.show_support_actions = checked
        label = "Support actions visible" if checked else "Support actions hidden"
        self.support_toggle_btn.setText(label)
        if checked:
            self._restore_support_layout()
        else:
            self._apply_hidden_support_layout()

    def _apply_hidden_support_layout(self) -> None:
        if not self._support_hidden_positions:
            self._support_hidden_positions = {block: block.pos() for block in self.blocks}
            self._support_hidden_visibility = {block: block.isVisible() for block in self.blocks}

        supports = [block for block in self.blocks if isinstance(block, SupportAction)]
        supports.sort(key=lambda b: (b.pos().y(), b.pos().x()))

        for block in supports:
            block.setVisible(False)
            self._set_chemical_chain_visible(block.chem_below, False)
            self._reflow_visible_actions()

        self.adapt_scene_rect()

    def _restore_support_layout(self) -> None:
        for block in self.blocks:
            if block in self._support_hidden_positions:
                block.setPos(self._support_hidden_positions[block])
            if block in self._support_hidden_visibility:
                block.setVisible(self._support_hidden_visibility[block])

        self._support_hidden_positions = {}
        self._support_hidden_visibility = {}
        self.adapt_scene_rect()

    def _set_chemical_chain_visible(self, chem_block, visible: bool) -> None:
        curr = chem_block
        while curr:
            curr.setVisible(visible)
            curr = curr.below_block

    def _reflow_visible_actions(self) -> None:
        overlap, border_overlap, precision = 20, 6, 0.01

        def is_hidden_support(block) -> bool:
            return isinstance(block, SupportAction) and not self.show_support_actions

        def visible_prev(block):
            cur = block.prev_block
            while cur and is_hidden_support(cur):
                cur = cur.prev_block
            return cur

        def visible_next(block):
            cur = block.next_block
            while cur and is_hidden_support(cur):
                cur = cur.next_block
            return cur

        def visible_above(block):
            cur = block.above_block
            while cur and is_hidden_support(cur):
                cur = cur.above_block
            return cur

        def visible_below(block):
            cur = block.below_block
            while cur and is_hidden_support(cur):
                cur = cur.below_block
            return cur

        def is_visible_action(block) -> bool:
            return isinstance(block, (ElementaryAction, SupportAction)) and not is_hidden_support(block)

        def iter_visible_actions():
            for b in self.blocks:
                if is_visible_action(b):
                    yield b

        def reflow_chemicals_for_action(block):
            if hasattr(block, "chem_below") and block.chem_below:
                cb = block.chem_below
                self._set_chemical_chain_visible(cb, True)
                cb.toggle_orientation(block.orientation)
                a_rect, c_rect = block.rect(), cb.rect()

                if block.action == "SubProductCreation":
                    new_x = block.pos().x() - c_rect.width() + border_overlap
                    body_start_y = block.pos().y() + 18
                    body_h = a_rect.height() - 18
                    new_y = body_start_y + (body_h - c_rect.height()) / 2
                elif block.orientation == "vertical":
                    new_x = block.pos().x() - c_rect.width() + border_overlap
                    body_h = a_rect.height() - 18
                    new_y = block.pos().y() + (body_h - c_rect.height()) / 2
                else:
                    body_w = a_rect.width() - 18
                    new_x = block.pos().x() + (body_w - c_rect.width()) / 2
                    new_y = block.pos().y() + a_rect.height() - 4

                if abs(cb.pos().x() - new_x) > precision or abs(cb.pos().y() - new_y) > precision:
                    cb.setPos(new_x, new_y)
                self.reflow_chemicals(cb, block.orientation)

        def move_visible_component(block, dx, dy, stop=None, visited=None):
            if not block or (dx == 0 and dy == 0):
                return
            if visited is None:
                visited = set()
            if block in visited or block == stop:
                return
            visited.add(block)

            if is_hidden_support(block):
                return

            block.setPos(block.pos().x() + dx, block.pos().y() + dy)

            if hasattr(block, "chem_below") and block.chem_below:
                self._set_chemical_chain_visible(block.chem_below, True)
                curr = block.chem_below
                while curr:
                    curr.setPos(curr.pos().x() + dx, curr.pos().y() + dy)
                    curr = curr.below_block

            neighbors = [
                visible_next(block),
                visible_prev(block),
                visible_below(block),
                visible_above(block),
            ]
            for neighbor in neighbors:
                if neighbor and not isinstance(neighbor, ChemicalBlock):
                    move_visible_component(neighbor, dx, dy, stop=stop, visited=visited)

            if hasattr(block, "subproduct_below") and block.subproduct_below:
                sb = block.subproduct_below
                if not is_hidden_support(sb):
                    move_visible_component(sb, dx, dy, stop=stop, visited=visited)

        max_iter = max(10, len(self.blocks) * 2)
        for _ in range(max_iter):
            moved = False
            visible_actions = list(iter_visible_actions())

            for block in visible_actions:
                nxt = visible_next(block)
                if nxt:
                    target_x = block.pos().x() + block.rect().width() - overlap
                    target_y = block.pos().y()
                    dx = target_x - nxt.pos().x()
                    dy = target_y - nxt.pos().y()
                    if abs(dx) > precision or abs(dy) > precision:
                        move_visible_component(nxt, dx, dy, stop=block)
                        moved = True

                bb = visible_below(block)
                if bb and not isinstance(bb, ChemicalBlock):
                    target_x = block.pos().x() + (block.rect().width() - bb.rect().width()) / 2
                    target_y = block.pos().y() + block.rect().height() - overlap
                    dx = target_x - bb.pos().x()
                    dy = target_y - bb.pos().y()
                    if abs(dx) > precision or abs(dy) > precision:
                        move_visible_component(bb, dx, dy, stop=block)
                        moved = True

            for block in visible_actions:
                block.update()
                block.update_text()
                reflow_chemicals_for_action(block)

            if not moved:
                break

    def _reflow_import_layout(self) -> None:
        """Layout imported flows without moving horizontal anchors.

        Horizontal links pull blocks to the right; vertical links pull blocks upward
        toward their attachment block. This prevents vertical chains from detaching
        when blocks participate in both horizontal and vertical flows.
        """
        overlap, border_overlap, precision = 20, 6, 0.01

        def is_hidden_support(block) -> bool:
            return isinstance(block, SupportAction) and not self.show_support_actions

        def is_visible_action(block) -> bool:
            return isinstance(block, (ElementaryAction, SupportAction)) and not is_hidden_support(block)

        def visible_prev(block):
            cur = block.prev_block
            while cur and is_hidden_support(cur):
                cur = cur.prev_block
            return cur

        def visible_above(block):
            cur = block.above_block
            while cur and is_hidden_support(cur):
                cur = cur.above_block
            return cur

        def iter_visible_actions():
            for b in self.blocks:
                if is_visible_action(b):
                    yield b

        def reflow_chemicals_for_action(block):
            if hasattr(block, "chem_below") and block.chem_below:
                cb = block.chem_below
                self._set_chemical_chain_visible(cb, True)
                cb.toggle_orientation(block.orientation)
                a_rect, c_rect = block.rect(), cb.rect()

                if block.action == "SubProductCreation":
                    new_x = block.pos().x() - c_rect.width() + border_overlap
                    body_start_y = block.pos().y() + 18
                    body_h = a_rect.height() - 18
                    new_y = body_start_y + (body_h - c_rect.height()) / 2
                elif block.orientation == "vertical":
                    new_x = block.pos().x() - c_rect.width() + border_overlap
                    body_h = a_rect.height() - 18
                    new_y = block.pos().y() + (body_h - c_rect.height()) / 2
                else:
                    body_w = a_rect.width() - 18
                    new_x = block.pos().x() + (body_w - c_rect.width()) / 2
                    new_y = block.pos().y() + a_rect.height() - 4

                if abs(cb.pos().x() - new_x) > precision or abs(cb.pos().y() - new_y) > precision:
                    cb.setPos(new_x, new_y)
                self.reflow_chemicals(cb, block.orientation)

            if hasattr(block, "subproduct_below") and block.subproduct_below:
                sb = block.subproduct_below
                new_x = block.pos().x() + (block.rect().width() - sb.rect().width()) / 2
                new_y = block.pos().y() + block.rect().height() - 8
                if abs(sb.pos().x() - new_x) > precision or abs(sb.pos().y() - new_y) > precision:
                    sb.setPos(new_x, new_y)

        max_iter = max(10, len(self.blocks) * 2)
        for _ in range(max_iter):
            moved = False

            # Horizontal pass: move blocks based on prev only.
            for block in iter_visible_actions():
                prev = visible_prev(block)
                if not prev:
                    continue
                target_x = prev.pos().x() + prev.rect().width() - overlap
                target_y = prev.pos().y()
                if abs(block.pos().x() - target_x) > precision or abs(block.pos().y() - target_y) > precision:
                    block.setPos(target_x, target_y)
                    moved = True

            # Vertical pass: move above blocks based on their below block.
            for block in iter_visible_actions():
                above = visible_above(block)
                if not above:
                    continue
                target_x = block.pos().x() + (block.rect().width() - above.rect().width()) / 2
                target_y = block.pos().y() - above.rect().height() + overlap
                if abs(above.pos().x() - target_x) > precision or abs(above.pos().y() - target_y) > precision:
                    above.setPos(target_x, target_y)
                    moved = True

            for block in iter_visible_actions():
                block.update()
                block.update_text()
                has_conn = bool(
                    block.prev_block or block.next_block or
                    block.above_block or block.below_block or
                    (hasattr(block, "chem_below") and block.chem_below) or
                    (hasattr(block, "subproduct_below") and block.subproduct_below)
                )
                block.set_connected(has_conn)
                reflow_chemicals_for_action(block)

            if not moved:
                break

    def _reflow_component_layout(self, anchor_block) -> None:
        """Layout a connected component after edits (e.g., delete) without breaking links."""
        if not anchor_block:
            return

        cluster = self.get_full_cluster(anchor_block)
        if not cluster:
            return

        overlap, border_overlap, precision = 20, 6, 0.01

        def is_hidden_support(block) -> bool:
            return isinstance(block, SupportAction) and not self.show_support_actions

        def is_visible_action(block) -> bool:
            return (
                block in cluster
                and isinstance(block, (ElementaryAction, SupportAction))
                and not is_hidden_support(block)
            )

        def visible_prev(block):
            cur = block.prev_block
            while cur and (cur not in cluster or is_hidden_support(cur)):
                cur = cur.prev_block
            return cur if cur in cluster else None

        def visible_above(block):
            cur = block.above_block
            while cur and (cur not in cluster or is_hidden_support(cur)):
                cur = cur.above_block
            return cur if cur in cluster else None

        def iter_visible_actions():
            for b in cluster:
                if is_visible_action(b):
                    yield b

        def reflow_chemicals_for_action(block):
            if hasattr(block, "chem_below") and block.chem_below:
                cb = block.chem_below
                self._set_chemical_chain_visible(cb, not is_hidden_support(block))
                cb.toggle_orientation(block.orientation)
                a_rect, c_rect = block.rect(), cb.rect()

                if block.action == "SubProductCreation":
                    new_x = block.pos().x() - c_rect.width() + border_overlap
                    body_start_y = block.pos().y() + 18
                    body_h = a_rect.height() - 18
                    new_y = body_start_y + (body_h - c_rect.height()) / 2
                elif block.orientation == "vertical":
                    new_x = block.pos().x() - c_rect.width() + border_overlap
                    body_h = a_rect.height() - 18
                    new_y = block.pos().y() + (body_h - c_rect.height()) / 2
                else:
                    body_w = a_rect.width() - 18
                    new_x = block.pos().x() + (body_w - c_rect.width()) / 2
                    new_y = block.pos().y() + a_rect.height() - 4

                if abs(cb.pos().x() - new_x) > precision or abs(cb.pos().y() - new_y) > precision:
                    cb.setPos(new_x, new_y)
                self.reflow_chemicals(cb, block.orientation)

        max_iter = max(8, len(cluster) * 2)
        for _ in range(max_iter):
            moved = False

            # Horizontal pass: align to prev only.
            for block in iter_visible_actions():
                prev = visible_prev(block)
                if not prev:
                    continue
                target_x = prev.pos().x() + prev.rect().width() - overlap
                target_y = prev.pos().y()
                if abs(block.pos().x() - target_x) > precision or abs(block.pos().y() - target_y) > precision:
                    block.setPos(target_x, target_y)
                    moved = True

            # Vertical pass: align above to its below block.
            for block in iter_visible_actions():
                above = visible_above(block)
                if not above:
                    continue
                target_x = block.pos().x() + (block.rect().width() - above.rect().width()) / 2
                target_y = block.pos().y() - above.rect().height() + overlap
                if abs(above.pos().x() - target_x) > precision or abs(above.pos().y() - target_y) > precision:
                    above.setPos(target_x, target_y)
                    moved = True

            for block in iter_visible_actions():
                block.update()
                block.update_text()
                has_conn = bool(
                    block.prev_block or block.next_block or
                    block.above_block or block.below_block or
                    (hasattr(block, "chem_below") and block.chem_below) or
                    (hasattr(block, "subproduct_below") and block.subproduct_below)
                )
                block.set_connected(has_conn)
                reflow_chemicals_for_action(block)

            if not moved:
                break

    def _register_block_id(self, block, block_id=None):
        if block_id is None:
            block_id = len(self.blocks)
        block.block_id = block_id
        return block_id
    def get_open_entity_procedure(self, chemical_block_id):
        if chemical_block_id in self.chemical_procedure_index:
            return self.chemical_procedure_index[chemical_block_id]

        if isinstance(self.protocol_data, dict):
            for flow in self.protocol_data.get("flows", []):
                if flow.get("chemical_block_id") == chemical_block_id:
                    return {
                        "protocol_name": self.protocol_data.get("protocol_name", DEFAULT_PROTOCOL_NAME),
                        "total_flows": 1,
                        "flows": [copy.deepcopy(flow)],
                    }

        for block, procedure in self.open_entity_procedures.items():
            if getattr(block, "block_id", None) == chemical_block_id:
                return procedure
            for flow in procedure.get("flows", []):
                if flow.get("chemical_block_id") == chemical_block_id:
                    return procedure
                for step in flow.get("steps", []):
                    for chem in step.get("chemicals", []):
                        if chem.get("block_id") == chemical_block_id:
                            return procedure
        return None

    def load_protocol_data(self, data, include_hidden=False):
        """Load protocol JSON data into the scene."""
        if isinstance(data, dict) and "activities" in data and "flows" not in data:
            data = convert_linkml_to_protocol(data)

        self.scene.clear()
        self.blocks = []
        self.protocol = Protocol()
        self.protocol.actions = []
        self.protocol_data = copy.deepcopy(data) if isinstance(data, dict) else {}
        self.open_entity_procedures = {}
        self.chemical_procedure_index = {}
        self.complex_action_groups = {}
        self._complex_group_counter = 0

        if not isinstance(data, dict):
            return

        id_to_block = {}
        source_to_add_block = {}

        flows = data.get("flows", [])
        if include_hidden:
            visible_flows = flows
            hidden_flows = []
        else:
            visible_flows = [flow for flow in flows if "chemical_block_id" not in flow]
            hidden_flows = [flow for flow in flows if "chemical_block_id" in flow]

        def iter_chem_block_ids_from_steps(steps):
            for step in steps or []:
                for chem in step.get("chemicals", []):
                    chem_id = chem.get("block_id")
                    if isinstance(chem_id, int):
                        yield chem_id
                sub_branch = step.get("subproduct_branch")
                if isinstance(sub_branch, dict):
                    yield from iter_chem_block_ids_from_steps([sub_branch])

        for flow in visible_flows:
            flow_type = flow.get("type", "horizontal")
            is_explicit_first = flow.get("is_explicit_first", False)
            steps = flow.get("steps", [])
            prev_step_block = None

            for j, step in enumerate(steps):
                b_id = step.get("block_id")
                action_name = step.get("action")
                source_id = step.get("source_block_id", b_id)

                if action_name == "Add" and source_id in source_to_add_block:
                    new_block = source_to_add_block[source_id]
                    chem_list = step.get("chemicals", [])
                    self._reconstruct_chemicals(new_block, chem_list)
                elif b_id in id_to_block:
                    new_block = id_to_block[b_id]
                else:
                    new_block = self._reconstruct_block(step, flow_type, id_to_block)
                    if action_name == "Add":
                        source_to_add_block[source_id] = new_block

                self._register_block_id(new_block, b_id)

                if j == 0 and is_explicit_first:
                    new_block.is_first = True
                    new_block.update_visual_style()

                if prev_step_block and prev_step_block != new_block:
                    if flow_type == "vertical":
                        prev_step_block.below_block = new_block
                        new_block.above_block = prev_step_block
                    else:
                        prev_step_block.next_block = new_block
                        new_block.prev_block = prev_step_block

                prev_step_block = new_block

        if not include_hidden:
            owner_for_chem_id = {}
            grouped_hidden = {}
            pending = [copy.deepcopy(flow) for flow in hidden_flows]

            progressed = True
            while pending and progressed:
                progressed = False
                next_pending = []

                for flow in pending:
                    chemical_block_id = flow.get("chemical_block_id")
                    target_block = id_to_block.get(chemical_block_id)
                    owner_block = None

                    if isinstance(target_block, ChemicalBlock):
                        owner_block = target_block
                    elif chemical_block_id in owner_for_chem_id:
                        owner_block = owner_for_chem_id[chemical_block_id]

                    if not owner_block:
                        next_pending.append(flow)
                        continue

                    grouped_hidden.setdefault(owner_block, []).append(flow)
                    for chem_id in iter_chem_block_ids_from_steps(flow.get("steps", [])):
                        owner_for_chem_id[chem_id] = owner_block
                    progressed = True

                pending = next_pending

            for owner_block, owner_flows in grouped_hidden.items():
                procedure = self.open_entity_procedures.setdefault(owner_block, {
                    "protocol_name": data.get("protocol_name", DEFAULT_PROTOCOL_NAME),
                    "total_flows": 0,
                    "preview_flows": [],
                    "flows": []
                })

                owner_block_id = next((bid for bid, block in id_to_block.items() if block is owner_block), None)

                for flow in owner_flows:
                    stored_flow = copy.deepcopy(flow)
                    if stored_flow.get("chemical_block_id") == owner_block_id:
                        procedure["preview_flows"].append(copy.deepcopy(stored_flow))
                    procedure["flows"].append(stored_flow)

                procedure["total_flows"] = len(procedure["flows"])
                owner_block.imported_procedure = procedure
                if getattr(owner_block, "block_id", None) is not None:
                    self.chemical_procedure_index[owner_block.block_id] = procedure

        self._reflow_import_layout()

        self.update_linked_sequence()
        self.update_support_logic()

        if include_hidden:
            for b in self.blocks:
                b.setFlag(QGraphicsRectItem.ItemIsMovable, False)
                b.setFlag(QGraphicsRectItem.ItemIsSelectable, False)
                b.setAcceptHoverEvents(False)
            self.setInteractive(False)

    def wheelEvent(self, event):
        """zoom using ctrl + wheel and handle mousepad horizontal signals."""
        # only zoom if control key is pressed
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            zoom_in_factor = 1.15
            zoom_out_factor = 1 / zoom_in_factor

            # use only vertical delta for zooming logic
            angle = event.angleDelta().y()

            if angle > 0:
                scale_factor = zoom_in_factor
            elif angle < 0:
                scale_factor = zoom_out_factor
            else:
                return

            # check current scale to prevent infinite zoom out/in (crash prevention)
            current_scale = self.transform().m11()
            if (current_scale > 5.0 and scale_factor > 1) or (current_scale < 0.1 and scale_factor < 1):
                return

            self.scale(scale_factor, scale_factor)
        else:
            # allow normal scrolling/panning if ctrl is not pressed
            super().wheelEvent(event)

    def drawBackground(self, painter, rect):
        """fill the background with a clean solid color."""
        # light gray-blue background
        painter.fillRect(rect, QColor(241, 245, 249))
    
    def show_action_dialog(self):
        from .complex_actions import get_complex_action_registry

        registry = get_complex_action_registry()
        dialog = ActionSelectionDialog(
            self,
            complex_action_names=registry.list_names(),
        )
        if dialog.exec() != QDialog.Accepted or not dialog.selected_action:
            return

        if dialog.selected_action == NEW_COMPLEX_ACTION:
            from .complex_action_ui import start_new_complex_action_wizard

            start_new_complex_action_wizard(self)
            return

        registry = get_complex_action_registry()
        if registry.get(dialog.selected_action):
            from .complex_action_protocol import insert_complex_action

            insert_complex_action(self, dialog.selected_action)
            return

        action_map = {
            "Add": Add, "Grind": Grind, "Separate": Separate,
            "Sieve": Sieve, "Wait": Wait,
            "ChangeAtmosphere": ChangeAtmosphere, "ChangeTemperature": ChangeTemperature,
            "NewRecipient": NewRecipient, "ChangeAgitation": ChangeAgitation,
            "SubProductCreation": SubProductCreation, "Repeat": Repeat,
            "ContinuousAddition": ContinuousAddition,
        }

        default_params = {
            "Add": {
                KEY_DURATION: "0 s",
                KEY_ADD_QUANTITY: "0 g",
                KEY_ADD_TYPE: "",
                KEY_OPEN_FLAME: "",
            },
            "Grind": {},
            "Separate": {KEY_PHASE: "", KEY_METHOD: ""},
            "Sieve": {KEY_MIN_SIZE: "0 μm", KEY_MAX_SIZE: "0 μm"},
            "Wait": {KEY_DURATION: "10 min"},
            "ChangeAtmosphere": {KEY_GASES: [], KEY_FLOW_RATE: "0 mL/min", KEY_PRESSURE: "1 bar"},
            "ChangeTemperature": {
                KEY_TEMPERATURE: "50 °C",
                KEY_PROCESS: "",
                KEY_RAMP: "0 °C/min",
                KEY_POWER: "0 W",
            },
            "NewRecipient": {KEY_RECIPIENT: "", KEY_MATERIAL: "", KEY_VOLUME: "250 mL"},
            "ChangeAgitation": {KEY_AGITATION_TYPE: "", KEY_SPEED: "0 rpm"},
            "SubProductCreation": {KEY_SUBSTANCE: ""},
            "Repeat": {KEY_AMOUNT: "1"},
            "ContinuousAddition": {
                KEY_SUBSTANCE_LIST: "",
                KEY_CONTINUOUS_ADD_TYPE: "",
                KEY_AMOUNT: "1",
            },
        }

        params = default_params.get(dialog.selected_action, {})
        action_class = action_map.get(dialog.selected_action)

        if action_class:
            action = action_class(**params)
            self.protocol.add_action(action)
            self.add_block(dialog.selected_action, params)

    def import_complex_action_dictionary(self):
        from .complex_action_protocol import import_complex_action_dictionary

        import_complex_action_dictionary(self)

    def _toggle_complex_visibility(self, collapsed: bool) -> None:
        from .complex_action_protocol import apply_complex_visibility

        apply_complex_visibility(self, collapsed)

    def _collect_horizontal_flow_steps(self, start_block, get_step_data, local_path):
        """Walk a horizontal chain, expanding complex-action groups for export."""
        content = []
        current = start_block
        visited: set[int] = set()
        while current:
            block_id = id(current)
            if block_id in visited:
                break
            visited.add(block_id)

            if isinstance(current, ComplexActionBlock) or getattr(current, "is_complex_surrogate", False):
                group = self.complex_action_groups.get(getattr(current, "complex_group_id", None))
                if group and group.member_blocks:
                    for member in group.member_blocks:
                        content.extend(get_step_data(member, local_path))
                    current = current.next_block
                    if current is None and group.member_blocks:
                        current = group.member_blocks[-1].next_block
                    continue
                current = current.next_block
                continue

            group_id = getattr(current, "complex_group_id", None)
            if group_id:
                group = self.complex_action_groups.get(group_id)
                if group and current in group.member_blocks:
                    if current is group.member_blocks[0]:
                        for member in group.member_blocks:
                            content.extend(get_step_data(member, local_path))
                    current = group.member_blocks[-1].next_block
                    continue

            content.extend(get_step_data(current, local_path))
            current = current.next_block
        return content

    def _support_toggle_btn_style(self) -> str:
        return (
            "QToolButton {"
            "  background-color: #d6eaf8;"
            "  color: #2980b9;"
            "  border-radius: 12px;"
            "  padding: 4px 12px;"
            "  font-weight: 600;"
            "  border: 1px solid #85c1e9;"
            "}"
            "QToolButton:hover { background-color: #aed6f1; }"
            "QToolButton:checked {"
            "  background-color: #3498db;"
            "  color: #ffffff;"
            "  border: 1px solid #2980b9;"
            "}"
            "QToolButton:checked:hover { background-color: #2980b9; }"
        )

    def _complex_toggle_btn_style(self) -> str:
        return (
            "QToolButton {"
            "  background-color: #ccfbf1;"
            "  color: #0f766e;"
            "  border-radius: 12px;"
            "  padding: 4px 12px;"
            "  font-weight: 600;"
            "  border: 1px solid #99f6e4;"
            "}"
            "QToolButton:hover { background-color: #99f6e4; }"
            "QToolButton:checked {"
            "  background-color: #14b8a6;"
            "  color: #ffffff;"
            "  border: 1px solid #0f766e;"
            "}"
            "QToolButton:checked:hover { background-color: #0d9488; }"
        )

    def _procedure_guide_btn_style(self, pinned: bool = False) -> str:
        if pinned:
            return (
                "QToolButton {"
                "  background-color: #ddd6fe;"
                "  color: #5b21b6;"
                "  border-radius: 12px;"
                "  padding: 4px 12px;"
                "  font-weight: 600;"
                "  border: 2px solid #a78bfa;"
                "}"
                "QToolButton:hover { background-color: #c4b5fd; }"
            )
        return (
            "QToolButton {"
            "  background-color: #ede9fe;"
            "  color: #6d28d9;"
            "  border-radius: 12px;"
            "  padding: 4px 12px;"
            "  font-weight: 600;"
            "  border: 1px solid #c4b5fd;"
            "}"
            "QToolButton:hover { background-color: #ddd6fe; }"
        )

    def setup_zoom_buttons(self):
        """Top-right: support + procedure guide; bottom-right: zoom controls."""
        self.zoom_controls_widget = QWidget(self)
        zoom_only_layout = QHBoxLayout(self.zoom_controls_widget)
        zoom_only_layout.setSpacing(2)
        zoom_only_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_in = QPushButton("+")
        self.btn_out = QPushButton("-")
        self.btn_in.setObjectName("zoom_in")
        self.btn_out.setObjectName("zoom_out")
        self.btn_in.clicked.connect(self.zoom_in)
        self.btn_out.clicked.connect(self.zoom_out)
        zoom_only_layout.addWidget(self.btn_in)
        zoom_only_layout.addWidget(self.btn_out)
        self.zoom_controls_widget.adjustSize()

        self.overlay_widget = QWidget(self)
        overlay_layout = QVBoxLayout(self.overlay_widget)
        overlay_layout.setContentsMargins(0, 0, 0, 0)
        overlay_layout.setSpacing(6)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.support_toggle_btn = QToolButton()
        self.support_toggle_btn.setText("Support actions visible")
        self.support_toggle_btn.setCheckable(True)
        self.support_toggle_btn.setChecked(True)
        self.support_toggle_btn.setStyleSheet(self._support_toggle_btn_style())
        self.support_toggle_btn.toggled.connect(self._toggle_support_visibility)
        overlay_layout.addWidget(self.support_toggle_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.complex_toggle_btn = QToolButton()
        self.complex_toggle_btn.setText("Complex actions expanded")
        self.complex_toggle_btn.setCheckable(True)
        self.complex_toggle_btn.setChecked(False)
        self.complex_toggle_btn.setStyleSheet(self._complex_toggle_btn_style())
        self.complex_toggle_btn.toggled.connect(self._toggle_complex_visibility)
        overlay_layout.addWidget(self.complex_toggle_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.procedure_guide_btn = QToolButton(self.overlay_widget)
        self.procedure_guide_btn.setText("Procedure guide")
        self.procedure_guide_btn.setCheckable(False)
        self.procedure_guide_btn.setToolTip("Hover or click to preview the procedure text")
        self._apply_procedure_guide_btn_style(False)
        self.procedure_guide_btn.clicked.connect(self._on_procedure_guide_click)
        overlay_layout.addWidget(self.procedure_guide_btn, 0, Qt.AlignmentFlag.AlignRight)

        self.procedure_guide_popup = QFrame(self)
        self.procedure_guide_popup.setObjectName("procedureGuidePopup")
        self.procedure_guide_popup.hide()
        self.procedure_guide_popup.setStyleSheet(
            "#procedureGuidePopup {"
            "  background-color: #ffffff;"
            "  border: 1px solid #cbd5e1;"
            "  border-radius: 8px;"
            "}"
        )

        popup_layout = QVBoxLayout(self.procedure_guide_popup)
        popup_layout.setContentsMargins(10, 8, 10, 8)
        popup_layout.setSpacing(0)

        self.procedure_guide_label = QLabel()
        self.procedure_guide_label.setWordWrap(True)
        self.procedure_guide_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.procedure_guide_label.setStyleSheet(
            "color: #1f2937; font-size: 12px; background: transparent; border: none;"
        )
        popup_layout.addWidget(self.procedure_guide_label)

        self._procedure_guide_hover_filter = _ProcedureGuidePopupFilter(self)
        self.procedure_guide_btn.installEventFilter(self._procedure_guide_hover_filter)
        self.procedure_guide_popup.installEventFilter(self._procedure_guide_hover_filter)

        self.overlay_widget.adjustSize()
        self.update_overlay_widget_positions()

    def _apply_procedure_guide_btn_style(self, pinned: bool) -> None:
        if hasattr(self, "procedure_guide_btn"):
            self.procedure_guide_btn.setStyleSheet(self._procedure_guide_btn_style(pinned))

    def update_overlay_widget_positions(self) -> None:
        """Reposition floating controls over the canvas viewport."""
        padding = 15
        viewport_w = self.viewport().width()
        viewport_h = self.viewport().height()

        if hasattr(self, "overlay_widget"):
            self.overlay_widget.adjustSize()
            self.overlay_widget.move(viewport_w - self.overlay_widget.width() - padding, padding)
            if self.procedure_guide_popup.isVisible():
                self._position_procedure_guide_popup()

        if hasattr(self, "zoom_controls_widget"):
            self.zoom_controls_widget.adjustSize()
            zoom_x = viewport_w - self.zoom_controls_widget.width() - padding
            zoom_y = viewport_h - self.zoom_controls_widget.height() - padding
            self.zoom_controls_widget.move(zoom_x, zoom_y)

    def _fit_procedure_guide_popup(self) -> None:
        max_width = min(420, max(220, self.viewport().width() - 40))
        text = self.procedure_guide_label.text() or "No procedure steps yet."
        self.procedure_guide_label.setMaximumWidth(max_width)
        self.procedure_guide_label.setText(text)
        hint = self.procedure_guide_label.sizeHint()
        self.procedure_guide_popup.setFixedSize(hint.width() + 20, hint.height() + 16)

    def _position_procedure_guide_popup(self) -> None:
        padding = 15
        btn = self.procedure_guide_btn
        popup = self.procedure_guide_popup
        anchor = btn.mapTo(self, btn.rect().topLeft())
        x = anchor.x()
        y = anchor.y() - popup.height() - 8
        if y < padding:
            y = anchor.y() + btn.height() + 8
        max_x = max(padding, self.viewport().width() - popup.width() - padding)
        x = min(x, max_x)
        popup.move(x, y)

    def _show_procedure_guide_popup(self) -> None:
        self.refresh_procedure_guide()
        self._fit_procedure_guide_popup()
        self.procedure_guide_popup.show()
        self.procedure_guide_popup.raise_()
        self._position_procedure_guide_popup()

    def _hide_procedure_guide_popup(self) -> None:
        if self._procedure_guide_pinned:
            return
        self.procedure_guide_popup.hide()
        self._apply_procedure_guide_btn_style(False)

    def _schedule_procedure_guide_hide(self) -> None:
        if self._procedure_guide_pinned:
            return
        self._procedure_guide_hide_timer.start()

    def _cancel_procedure_guide_hide(self) -> None:
        self._procedure_guide_hide_timer.stop()

    def _on_procedure_guide_click(self) -> None:
        self._procedure_guide_pinned = not self._procedure_guide_pinned
        self._apply_procedure_guide_btn_style(self._procedure_guide_pinned)
        if self._procedure_guide_pinned:
            self._cancel_procedure_guide_hide()
            self._show_procedure_guide_popup()
        else:
            self.procedure_guide_popup.hide()

    def resizeEvent(self, event):
        """Reposition floating controls when the view is resized."""
        super().resizeEvent(event)
        self.update_overlay_widget_positions()

    def zoom_in(self):
        """increases the view scale."""
        self.scale(1.15, 1.15)

    def zoom_out(self):
        """decreases the view scale."""
        self.scale(1/1.15, 1/1.15)

    def adapt_scene_rect(self):
        """updates the canvas size based on the position of all blocks."""
        items_rect = self.scene.itemsBoundingRect()
        if items_rect.isNull():
            return
            
        new_rect = items_rect.adjusted(-500, -500, 500, 500)
        self.setSceneRect(new_rect)
    
    def add_block(self, action, params):
        """create an action block at a fixed starting position."""
        block = self._create_block_by_name(action, params)
        
        block.setPos(50, 50)
        
        self.update_linked_sequence()
        self.adapt_scene_rect()
        
        # update support ids and influences right after creation
        self.update_support_logic()
        
        if params and not getattr(self, "complex_action_builder_mode", False):
            block.open_editor()
            # If the editor was rejected (e.g., ESC pressed), remove the block
            if not block.get_editor_accepted():
                self.scene.removeItem(block)
                self.blocks.remove(block)
                self.update_linked_sequence()
                self.adapt_scene_rect()
                self.update_support_logic()

    def add_chemical_block(self):
        """show dialog and add the specific chemical entity to the scene."""
        if getattr(self, "complex_action_builder_mode", False):
            return
        dialog = ChemicalSelectionDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_chemical:
            details_dialog = UnifiedChemicalDetailsDialog(self)
            if details_dialog.exec() != QDialog.Accepted:
                return

            imported_procedure = (
                normalize_preparation_procedure(details_dialog.imported_procedure)
                if details_dialog.imported_procedure
                else None
            )
            entity_params = details_dialog.first_level_fields.copy()

            # mapping keys to classes from chemicals.py
            
            chemical_map = {
                "Substance": Substance,
                "Material": Material,
                "PerfectSingleCrystalMaterial": PerfectSingleCrystalMaterial,
                "Molecules": Molecules,
                "Polymers": Polymers,
                "Media": Media,
                "Dispersion": Dispersion,
                "BioProducts": BioProducts,
                "HeterogeneousCatalysts": HeterogeneousCatalysts,
            }
            
            chem_type = dialog.selected_chemical
            params = {**entity_params, **get_chemical_default_params(chem_type)}
            
            chem_class = chemical_map.get(chem_type)
            
            if chem_class:
                # create data object
                chemical_data = chem_class(**params)
                
                # create visual block
                block = ChemicalBlock(chem_type, params, editor=self)
                block.imported_procedure = imported_procedure
                if imported_procedure:
                    self.open_entity_procedures[block] = imported_procedure
                
                block.setPos(50, 50)
                
                self.scene.addItem(block)
                self.blocks.append(block)
                self._register_block_id(block)

                if imported_procedure:
                    self.chemical_procedure_index[block.block_id] = imported_procedure
                
                self.update_linked_sequence()
                self.adapt_scene_rect()
                self.centerOn(block)
                
                # refresh support action influences
                self.update_support_logic()
                
                block.open_editor()
                
                # If the editor was rejected (e.g., ESC pressed), remove the block
                if not block.get_editor_accepted():
                    self.scene.removeItem(block)
                    self.blocks.remove(block)
                    if block in self.open_entity_procedures:
                        del self.open_entity_procedures[block]
                    if block.block_id in self.chemical_procedure_index:
                        del self.chemical_procedure_index[block.block_id]
                    self.update_linked_sequence()
                    self.adapt_scene_rect()
                    self.update_support_logic()
    
    def update_linked_sequence(self):
        """Update the linked_sequence list based on current block linkages.
        Collects all blocks that are part of chains and sorts them by x-axis position.
        Includes both horizontally linked actions and vertically linked chemicals.
        """
        self.linked_sequence = []
        
        # Find all blocks that are part of chains (have prev_block, next_block, above_block, or below_block)
        linked_blocks = []
        for block in self.blocks:
            if block.prev_block or block.next_block or block.above_block or block.below_block:
                linked_blocks.append(block)
        
        # Sort by x-axis position (left to right)
        linked_blocks.sort(key=lambda b: b.pos().x())
        self.linked_sequence = linked_blocks

    def is_incompatible_horizontal_link(self, block1, block2):
        """Check if two blocks are incompatible for HORIZONTAL linking.
        Only Action blocks (Elementary/Support) can link horizontally.
        Chemical blocks cannot link horizontally to anything.
        Returns True if the link is incompatible, False otherwise.
        """
        is_chemical_1 = isinstance(block1, ChemicalBlock)
        is_chemical_2 = isinstance(block2, ChemicalBlock)
        
        # Chemical blocks cannot link horizontally to anything
        if is_chemical_1 or is_chemical_2:
            return True
        
        # Action blocks can link horizontally to other action blocks
        return False

    def is_incompatible_vertical_link(self, parent_block, child_block):
        """Check if two blocks are compatible for VERTICAL linking.
        Chemical blocks can link vertically to Action blocks (Elementary/Support) or other Chemical blocks.
        Returns True if the link is incompatible, False otherwise.
        """
        is_parent_action = isinstance(parent_block, (ElementaryAction, SupportAction))
        is_parent_chemical = isinstance(parent_block, ChemicalBlock)
        is_child_chemical = isinstance(child_block, ChemicalBlock)

        if is_child_chemical and is_parent_action and not self._can_attach_chemical_to(parent_block):
            return True
        
        # Child must always be a chemical block
        if not is_child_chemical:
            return True
        
        # Parent can be either an action block or a chemical block
        return not (is_parent_action or is_parent_chemical)

    def _can_attach_chemical_to(self, target) -> bool:
        """Chemicals may only attach to standalone actions, not complex-action members."""
        if target is None:
            return False
        if getattr(target, "part_of_complex_action", False):
            return False
        if getattr(target, "is_complex_surrogate", False):
            return False
        if isinstance(target, ComplexActionBlock):
            return False
        return True

    def _chemical_attach_rejection_message(self, target) -> str | None:
        """Return a user-facing reason when a chemical cannot attach to target."""
        if not self._can_attach_chemical_to(target):
            if getattr(target, "is_complex_surrogate", False):
                return f"Chemicals cannot be linked to complex action {target.action!r}"
            return "Chemicals cannot be linked to complex actions"
        allowed_for_chemicals = ["Add", "ChangeAtmosphere", "SubProductCreation"]
        if getattr(target, "action", None) not in allowed_for_chemicals:
            return f"Chemicals cannot be linked to {target.action}"
        return None

    def preview_link(self, moved_block):
        """Visual feedback for both horizontal and vertical snapping."""
        # Reset previous preview to their actual logical state
        if hasattr(self, 'preview_pair') and self.preview_pair:
            a, b = self.preview_pair
            for item in [a, b]:
                if item:
                    item.set_connected(self._is_block_connected(item))
            self.preview_pair = None

        moved_rect = moved_block.sceneBoundingRect()
        for other in self.blocks:
            if other is moved_block: continue
            
            other_rect = other.sceneBoundingRect()
            if moved_rect.intersects(other_rect):
                # Highlight potential connection temporarily
                moved_block.set_connected(True)
                other.set_connected(True)
                self.preview_pair = (moved_block, other)
                return
        
        # If no intersection, current moved block follows its logical state
        moved_block.set_connected(self._is_block_connected(moved_block))

    def _is_block_connected(self, block) -> bool:
        """Return whether block has at least one structural connection."""
        return bool(
            block.prev_block
            or block.next_block
            or block.above_block
            or block.below_block
            or (hasattr(block, "chem_below") and block.chem_below)
            or (hasattr(block, "subproduct_below") and block.subproduct_below)
        )
    
    def update_chemical_chain_below(self, chemical_block, parent_x, parent_y):
        """Recursively update positions of chemical blocks below a chemical block."""
        if chemical_block.below_block:
            chem_rect = chemical_block.rect()
            below_rect = chemical_block.below_block.rect()
            snap_x = parent_x + (chem_rect.width() - below_rect.width()) * 0.25
            snap_y = parent_y + chem_rect.height()
            chemical_block.below_block.setPos(snap_x, snap_y)
            # Recursively update the chain below
            self.update_chemical_chain_below(chemical_block.below_block, snap_x, snap_y)

    def find_last_chemical_in_chain(self, chemical_block):
        """Find the last chemical block in a vertical chain."""
        current = chemical_block
        while current.below_block:
            current = current.below_block
        return current
    
    def add_subproduct_branch(self, parent_block):
        """creates an anchored subproduct block without opening a popup."""
        params = {KEY_SUBSTANCE: []} # initialize substance as a list
        block = SupportAction("SubProductCreation", params, editor=self)
        
        block.toggle_orientation("vertical")
        block.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        
        self.scene.addItem(block)
        self.blocks.append(block)
        
        parent_block.subproduct_below = block
        block.above_block = parent_block
        
        self.reflow_entire_cluster(parent_block)
    
    def _find_vertical_target(self, moved_block):
        """find the closest vertical target and validate rules after identification."""
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()
        
        potential_target = None
        potential_role = None
        best_score = float('inf')
        rejected_complex_target = None
        rejected_complex_score = float('inf')

        for other in self.blocks:
            if other is moved_block: continue
            if not isinstance(moved_block, ChemicalBlock) and isinstance(other, ChemicalBlock): continue
            if isinstance(moved_block, ChemicalBlock) and not isinstance(other, ChemicalBlock):
                if not self._can_attach_chemical_to(other):
                    other_rect = other.sceneBoundingRect()
                    if moved_rect.intersects(other_rect):
                        score = abs(moved_center.x() - other_rect.center().x())
                        if score < rejected_complex_score:
                            rejected_complex_score = score
                            rejected_complex_target = other
                    continue
            
            other_rect = other.sceneBoundingRect()
            other_center = other_rect.center()

            if isinstance(moved_block, ChemicalBlock):
                # chemical logic: find the closest intersecting block
                if moved_rect.intersects(other_rect):
                    score = abs(moved_center.x() - other_center.x())
                    if score < best_score:
                        best_score = score
                        potential_target = other
                        potential_role = "child"
            else:
                # action flow logic: find the closest block in proximity
                dx = abs(moved_center.x() - other_center.x())
                if dx > other_rect.width() * 0.6: continue
                
                dy = moved_center.y() - other_center.y()
                max_d = (moved_rect.height() + other_rect.height()) / 2 + 50
                
                if -max_d < dy < -10: 
                    role = "parent"
                elif 10 < dy < max_d: 
                    role = "child"
                else: 
                    continue
                
                # validate orientation rules for flow
                if role == "parent" and moved_block.orientation != "vertical": continue
                if role == "child" and other.orientation != "vertical": continue
                
                score = dx + abs(dy)
                if score < best_score: 
                    best_score, potential_target, potential_role = score, other, role

        # validate rules for the identified potential target
        if potential_target:
            # check chemical attachment rules
            if isinstance(moved_block, ChemicalBlock) and not isinstance(potential_target, ChemicalBlock):
                rejection = self._chemical_attach_rejection_message(potential_target)
                if rejection:
                    QToolTip.showText(QCursor.pos(), rejection, self)
                    return None, None

            # check action flow rules (no actions below subproduct)
            if not isinstance(moved_block, ChemicalBlock) and potential_target.action == "SubProductCreation":
                if potential_role == "child":
                    QToolTip.showText(QCursor.pos(), "Only Chemicals can be linked here", self)
                    return None, None # reject link

        if (
            isinstance(moved_block, ChemicalBlock)
            and potential_target is None
            and rejected_complex_target is not None
        ):
            rejection = self._chemical_attach_rejection_message(rejected_complex_target)
            if rejection:
                QToolTip.showText(QCursor.pos(), rejection, self)

        return potential_target, potential_role
    
    def _link_action_as_child_vertical(self, moved_block, target_above):
        """links moved_block below target_above, moving only the incoming block."""
        overlap = 20
        
        # Calculate snap position based on the stable target
        target_pos = target_above.pos()
        snap_x = target_pos.x() + (target_above.rect().width() - moved_block.rect().width()) / 2
        # position exactly below using target's Y as anchor
        snap_y = target_pos.y() + target_above.rect().height() - overlap
        
        # Move the incoming block (and its cluster) to the snap position
        diff_x = snap_x - moved_block.pos().x()
        diff_y = snap_y - moved_block.pos().y()
        self._move_branch(moved_block, diff_x, diff_y)

        # Establish links
        old_child = target_above.below_block
        if old_child and not isinstance(old_child, ChemicalBlock):
            # Insertion case: open vertical space under the stable target.
            shift_y = moved_block.rect().height() - overlap
            if shift_y > 0:
                self._move_branch(old_child, 0, shift_y)
        if old_child and not isinstance(old_child, ChemicalBlock):
            moved_block.below_block = old_child
            old_child.above_block = moved_block
            
        target_above.below_block = moved_block
        moved_block.above_block = target_above
        
        # update visuals
        target_above.update()
        moved_block.update()
    
    def _link_action_flow_vertical(self, action, target):
        """Links an Action block to another Action block's vertical flow."""
        if not target or isinstance(target, ChemicalBlock):
            return
        
        # Insert between target and its current vertical child
        old_child = target.below_block
        target.below_block = action
        action.above_block = target
        
        if old_child:
            action.below_block = old_child
            old_child.above_block = action
        
        # Determine the start of the chain for reflow
        root = self.find_chain_start(target)
        self.reflow_chain(root)

    def _link_chemical_to_parent(self, chem, target):
        """Links chemical and positions it correctly based on target orientation."""
        if not self._can_attach_chemical_to(target):
            return

        border_overlap = 6

        if isinstance(target, (ElementaryAction, SupportAction)):
            old_stack = target.chem_below
            target.chem_below = chem
            chem.above_block = target
            if old_stack:
                if target.orientation == "vertical":
                    shift_x = -(chem.rect().width() - border_overlap)
                    self._move_branch(old_stack, shift_x, 0)
                else:
                    shift_y = chem.rect().height() - border_overlap
                    self._move_branch(old_stack, 0, shift_y)
                chem.below_block = old_stack
                old_stack.above_block = chem

            # Snap the incoming chemical to the stable action target
            if target.orientation == "vertical":
                body_h = target.rect().height() - 18
                snap_x = target.pos().x() - chem.rect().width() + border_overlap
                snap_y = target.pos().y() + (body_h - chem.rect().height()) / 2
            else:
                body_w = target.rect().width() - 18
                snap_x = target.pos().x() + (body_w - chem.rect().width()) / 2
                snap_y = target.pos().y() + target.rect().height() - 4
            chem.setPos(snap_x, snap_y)
            self.reflow_chemicals(chem, target.orientation)

        elif isinstance(target, ChemicalBlock):
            # Target is another Chemical
            old_child = target.below_block
            target.below_block = chem
            chem.above_block = target
            if old_child:
                if target.orientation == "vertical":
                    shift_x = -(chem.rect().width() - border_overlap)
                    self._move_branch(old_child, shift_x, 0)
                else:
                    shift_y = chem.rect().height() - border_overlap
                    self._move_branch(old_child, 0, shift_y)
                chem.below_block = old_child
                old_child.above_block = chem
            
            # Snap position manually before reflow to prevent jumping
            if target.orientation == "vertical":
                chem.setPos(target.pos().x() - chem.rect().width() + border_overlap, target.pos().y())
            else:
                chem.setPos(target.pos().x(), target.pos().y() + target.rect().height() - border_overlap)
            self.reflow_chemicals(chem, target.orientation)

    def _get_target_and_zone(self, moved_block):
        """
        Determines which block is under the moved_block and in which zone 
        (TOP, BOTTOM, LEFT, RIGHT) it was dropped.
        """
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()
        
        target = None
        best_overlap = 0
        rejected_complex_target = None
        rejected_complex_overlap = 0

        for other in self.blocks:
            if other is moved_block:
                continue
            if not other.isVisible():
                continue

            other_rect = other.sceneBoundingRect()

            if isinstance(moved_block, ChemicalBlock) and not isinstance(other, ChemicalBlock):
                if not self._can_attach_chemical_to(other):
                    if moved_rect.intersects(other_rect):
                        overlap = (
                            moved_rect.intersected(other_rect).width()
                            * moved_rect.intersected(other_rect).height()
                        )
                        if overlap > rejected_complex_overlap:
                            rejected_complex_overlap = overlap
                            rejected_complex_target = other
                    continue
            if not self._is_complex_linkable_endpoint(other):
                continue
            
            # Check for intersection
            if moved_rect.intersects(other_rect):
                # Calculate overlap area to pick the best target if overlapping multiple
                overlap = moved_rect.intersected(other_rect).width() * moved_rect.intersected(other_rect).height()
                if overlap > best_overlap:
                    best_overlap = overlap
                    target = other

        if not target:
            if (
                isinstance(moved_block, ChemicalBlock)
                and rejected_complex_target is not None
            ):
                rejection = self._chemical_attach_rejection_message(rejected_complex_target)
                if rejection:
                    QToolTip.showText(QCursor.pos(), rejection, self)
            return None, None

        # Determine zone based on relative center position
        target_center = target.sceneBoundingRect().center()
        
        # Calculate horizontal and vertical bias
        dx = moved_center.x() - target_center.x()
        dy = moved_center.y() - target_center.y()

        # If it's a chemical, it always wants to go to the ingredient zone (BOTTOM or SIDE)
        if isinstance(moved_block, ChemicalBlock):
            if target.orientation == "vertical": return target, "LEFT"
            return target, "BOTTOM"

        # For Action blocks, decide based on which distance is greater (Manhattan-ish)
        if abs(dx) > abs(dy):
            return target, "RIGHT" if dx > 0 else "LEFT"
        else:
            return target, "BOTTOM" if dy > 0 else "TOP"
    
    def check_and_link_horizontal_blocks(self, moved_block):
        """Handle horizontal linking while keeping stationary blocks anchored."""
        if getattr(moved_block, "part_of_complex_action", False):
            return
        if moved_block.orientation == "vertical":
            self.update_support_logic()
            return

        overlap = 20

        # 1. Sever old links (positions stay unchanged)
        old_p, old_n = self._pluck_horizontal(moved_block)

        # 2. Find target and drop zone
        target, zone = self._get_target_and_zone(moved_block)

        # 2.1 If the block came from the middle of a chain, close that gap.
        self._close_horizontal_gap(old_p, old_n, overlap)

        linked = False

        if target and self._would_split_complex_group(moved_block, target, zone):
            QToolTip.showText(
                QCursor.pos(),
                "Cannot insert actions inside a complex action",
                self,
            )

        # 3. Only process horizontal targets (target stays fixed)
        if (
            target
            and not isinstance(target, ChemicalBlock)
            and target.orientation == "horizontal"
            and not self._would_split_complex_group(moved_block, target, zone)
        ):
            if zone == "LEFT":
                if not target.is_first:
                    p = target.prev_block
                    # Insertion case: open space by pushing forward chain.
                    if p:
                        shift = moved_block.rect().width() - overlap
                        if shift > 0:
                            self.push_chain(target, shift)

                    snap_x = target.pos().x() - moved_block.rect().width() + overlap
                    snap_y = target.pos().y()
                    dx = snap_x - moved_block.pos().x()
                    dy = snap_y - moved_block.pos().y()
                    self._move_branch(moved_block, dx, dy)

                    moved_block.next_block = target
                    target.prev_block = moved_block
                    if p:
                        p.next_block = moved_block
                        moved_block.prev_block = p
                    linked = True
            elif zone == "RIGHT":
                if not moved_block.is_first:
                    n = target.next_block
                    # Insertion case: open space by pushing forward chain.
                    if n:
                        shift = moved_block.rect().width() - overlap
                        if shift > 0:
                            self.push_chain(n, shift)

                    snap_x = target.pos().x() + target.rect().width() - overlap
                    snap_y = target.pos().y()
                    dx = snap_x - moved_block.pos().x()
                    dy = snap_y - moved_block.pos().y()
                    self._move_branch(moved_block, dx, dy)

                    target.next_block = moved_block
                    moved_block.prev_block = target
                    if n:
                        moved_block.next_block = n
                        n.prev_block = moved_block
                    linked = True

        if not linked:
            moved_block.set_connected(bool(moved_block.prev_block or moved_block.next_block or moved_block.chem_below))
        self._realign_attached_branches(moved_block)

        self.update_linked_sequence()
        self.update_support_logic()

    def _move_branch(self, block, dx, dy, visited=None):
        """Recursively moves a block and all its downstream connections (Right, Down, and Chemicals)."""
        if not block: return
        if visited is None: visited = set()
        if block in visited: return
        visited.add(block)

        block.setPos(block.pos().x() + dx, block.pos().y() + dy)

        # Move everything that follows this block
        if block.next_block:
            self._move_branch(block.next_block, dx, dy, visited)
        if block.below_block:
            self._move_branch(block.below_block, dx, dy, visited)
        if hasattr(block, 'chem_below') and block.chem_below:
            self._move_branch(block.chem_below, dx, dy, visited)
        if hasattr(block, 'subproduct_below') and block.subproduct_below:
            self._move_branch(block.subproduct_below, dx, dy, visited)

    def _close_horizontal_gap(self, old_prev, old_next, overlap):
        """When removing from chain middle, move the forward side to fill the gap."""
        if not old_prev or not old_next:
            return
        target_x = old_prev.pos().x() + old_prev.rect().width() - overlap
        target_y = old_prev.pos().y()
        dx = target_x - old_next.pos().x()
        dy = target_y - old_next.pos().y()
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return
        self._move_branch(old_next, dx, dy, visited=set())

    def _realign_attached_branches(self, block):
        """Realign only branches attached to one block (chemicals/subproduct)."""
        if not block:
            return
        overlap = 20
        border_overlap = 6
        precision = 0.01

        # Keep subproduct anchor attached to the moved block.
        if hasattr(block, "subproduct_below") and block.subproduct_below:
            sb = block.subproduct_below
            new_x = block.pos().x() + (block.rect().width() - sb.rect().width()) / 2
            new_y = block.pos().y() + block.rect().height() - 8
            sb.setPos(new_x, new_y)

        # Keep first attached chemical anchored to this action block.
        if hasattr(block, "chem_below") and block.chem_below:
            cb = block.chem_below
            cb.toggle_orientation(block.orientation)
            a_rect, c_rect = block.rect(), cb.rect()

            if block.action == "SubProductCreation":
                new_x = block.pos().x() - c_rect.width() + border_overlap
                body_start_y = block.pos().y() + 18
                body_h = a_rect.height() - 18
                new_y = body_start_y + (body_h - c_rect.height()) / 2
            elif block.orientation == "vertical":
                new_x = block.pos().x() - c_rect.width() + border_overlap
                body_h = a_rect.height() - 18
                new_y = block.pos().y() + (body_h - c_rect.height()) / 2
            else:
                body_w = a_rect.width() - 18
                new_x = block.pos().x() + (body_w - c_rect.width()) / 2
                new_y = block.pos().y() + a_rect.height() - 4

            if abs(cb.pos().x() - new_x) > precision or abs(cb.pos().y() - new_y) > precision:
                cb.setPos(new_x, new_y)
            self.reflow_chemicals(cb, block.orientation)
    
    def _link_action_as_parent_vertical(self, moved_block, target_below):
        """links moved_block on top of target_below, moving only the incoming block."""
        overlap = 20
        
        # Calculate snap position based on the stable target
        target_pos = target_below.pos()
        # center moved_block over the target
        snap_x = target_pos.x() + (target_below.rect().width() - moved_block.rect().width()) / 2
        # position exactly above using the target's Y as anchor
        snap_y = target_pos.y() - moved_block.rect().height() + overlap
        
        # Move the incoming block (and its cluster) to the snap position
        diff_x = snap_x - moved_block.pos().x()
        diff_y = snap_y - moved_block.pos().y()
        self._move_branch(moved_block, diff_x, diff_y)

        # Establish links
        old_parent = target_below.above_block
        if old_parent and not isinstance(old_parent, ChemicalBlock):
            # Insertion case: open vertical space under the stable old parent.
            shift_y = moved_block.rect().height() - overlap
            if shift_y > 0:
                self._move_branch(target_below, 0, shift_y)
        if old_parent and not isinstance(old_parent, ChemicalBlock):
            old_parent.below_block = moved_block
            moved_block.above_block = old_parent
            
        moved_block.below_block = target_below
        target_below.above_block = moved_block
        
        # update visuals
        moved_block.update()
        target_below.update()
    
    def check_and_link_vertical_blocks(self, moved_block):
        """Handle vertical linking; keep stationary targets fixed unless inserting."""
        if getattr(moved_block, "part_of_complex_action", False):
            return
        if hasattr(self, 'preview_pair') and self.preview_pair:
            for item in self.preview_pair:
                if item:
                    item.set_connected(self._is_block_connected(item))
            self.preview_pair = None

        old_parent = moved_block.above_block
        old_child = moved_block.below_block

        # disconnect from current structure
        self._pluck_vertical(moved_block)

        target, role = self._find_vertical_target(moved_block)

        if target:
            if isinstance(moved_block, ChemicalBlock):
                # chemicals always connect to the block above
                self._link_chemical_to_parent(moved_block, target)
            elif role == "parent":
                # vertical action dropped on top half area
                self._link_action_as_parent_vertical(moved_block, target)
            else:
                # action dropped on bottom half area
                self._link_action_as_child_vertical(moved_block, target)
        else:
            # handle standalone state
            if isinstance(moved_block, ChemicalBlock):
                moved_block.toggle_orientation("horizontal")
                moved_block.set_connected(False)
            else:
                moved_block.below_block = None
                is_connected = bool(moved_block.prev_block or moved_block.next_block or moved_block.chem_below)
                moved_block.set_connected(is_connected)

        self.update_linked_sequence()
        self.update_support_logic()
    
    def _pluck_horizontal(self, block):
        """Sever horizontal links and stitch the old neighbors."""
        if getattr(block, "part_of_complex_action", False):
            return block.prev_block, block.next_block

        p, n = block.prev_block, block.next_block
        if p:
            p.next_block = n
        if n:
            n.prev_block = p
        block.prev_block = None
        block.next_block = None
        return p, n

    def _pluck_vertical(self, block):
        """Sever all vertical links and return the old neighbors."""
        p = block.above_block
        c = block.below_block
        
        if p:
            if isinstance(block, ChemicalBlock):
                if isinstance(p, ChemicalBlock): p.below_block = c
                else: p.chem_below = c
            else:
                if not isinstance(p, ChemicalBlock): p.below_block = c
        
        if c:
            c.above_block = p
            c.update()

        block.above_block = None
        block.below_block = None
        return p, c
    
    def _is_complex_linkable_endpoint(self, block) -> bool:
        if getattr(block, "is_complex_surrogate", False):
            return block.isVisible()
        if not getattr(block, "part_of_complex_action", False):
            return True
        group = self.get_complex_action_group(block)
        if group is None or not group.member_blocks:
            return False
        return block is group.member_blocks[0] or block is group.member_blocks[-1]

    def _allowed_complex_link_zone(self, target, zone: str | None) -> bool:
        """Only allow external links before the first or after the last complex step."""
        if zone not in {"LEFT", "RIGHT"}:
            return True
        if not getattr(target, "part_of_complex_action", False):
            return True
        group = self.get_complex_action_group(target)
        if group is None or not group.member_blocks:
            return False
        first = group.member_blocks[0]
        last = group.member_blocks[-1]
        if first is last:
            return True
        if zone == "LEFT":
            return target is first
        if zone == "RIGHT":
            return target is last
        return False

    def _would_split_complex_group(self, moved_block, target, zone: str | None) -> bool:
        if not self._allowed_complex_link_zone(target, zone):
            return True
        if getattr(moved_block, "part_of_complex_action", False):
            return True
        group = self.get_complex_action_group(target)
        if group is None:
            return False
        members = group.member_blocks
        if zone == "LEFT" and target in members and target is not members[0]:
            return True
        if zone == "RIGHT" and target in members and target is not members[-1]:
            return True
        return False

    def _find_horizontal_neighbors(self, moved_block):
        """Finds the closest left and right action blocks that intersect with moved_block."""
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()
        
        left, right = None, None
        lx, rx = None, None

        for other in self.blocks:
            if other is moved_block or isinstance(other, ChemicalBlock):
                continue
            if not self._is_complex_linkable_endpoint(other):
                continue
            
            # Skip if the other block is vertical
            if other.orientation == "vertical":
                continue

            if moved_rect.intersects(other.sceneBoundingRect()):
                oc = other.sceneBoundingRect().center()
                # Check horizontal proximity
                if abs(moved_center.x() - oc.x()) >= abs(moved_center.y() - oc.y()):
                    if oc.x() < moved_center.x(): # Other is on the left
                        if left is None or oc.x() > lx:
                            left, lx = other, oc.x()
                    else: # Other is on the right
                        if right is None or oc.x() < rx:
                            right, rx = other, oc.x()
        return left, right
    
    def push_chain(self, start_block, shift_x: float):
        """Push a horizontal tail and everything attached to it.

        This moves the chain starting at start_block to the right (or left)
        and keeps all attached branches (chemicals, vertical children, subproducts)
        traveling together.
        """
        if not start_block or shift_x == 0:
            return
        self._move_branch(start_block, shift_x, 0, visited=set())

    def get_full_cluster(self, start_block):
        """Finds all blocks connected in the same graph using BFS."""
        cluster = set()
        queue = [start_block]
        while queue:
            curr = queue.pop(0)
            if curr not in cluster:
                cluster.add(curr)
                # Check all 5 possible directions
                neighbors = [
                    curr.prev_block, curr.next_block, 
                    curr.above_block, curr.below_block, 
                    curr.chem_below
                ]
                for n in neighbors:
                    if n and n not in cluster:
                        queue.append(n)
        return cluster

    def get_cluster_heads(self, cluster):
        """Returns all blocks in the cluster that have no incoming connections."""
        heads = []
        for b in cluster:
            if isinstance(b, ChemicalBlock):
                continue
            # A head is an action block with no PREV and no ABOVE 
            has_above_action = b.above_block and not isinstance(b.above_block, ChemicalBlock)
            if not b.prev_block and not has_above_action:
                heads.append(b)
        return heads

    def reflow_entire_cluster(self, any_block):
        """synchronizes the graph and updates support logic."""
        if not any_block: return
        self.reflow_chain(any_block, visited=set())
        self.update_support_logic()

    def reflow_chain(self, block, visited=None):
        """recursive reflow with specific logic for subproducts, vertical and horizontal actions."""
        if not block or (visited and block in visited): return
        if visited is None: visited = set()
        visited.add(block)

        block.update()
        block.update_text()
        overlap, border_overlap, precision = 20, 6, 0.01

        # update connection highlight
        has_conn = bool(block.prev_block or block.next_block or 
                        block.above_block or block.below_block or 
                        (hasattr(block, 'chem_below') and block.chem_below) or
                        (hasattr(block, 'subproduct_below') and block.subproduct_below))
        block.set_connected(has_conn)

        # 1. horizontal flow (next/prev)
        if block.next_block:
            nb = block.next_block
            nb.setPos(block.pos().x() + block.rect().width() - overlap, block.pos().y())
            self.reflow_chain(nb, visited)
        if not isinstance(block, ChemicalBlock) and block.prev_block:
            pb = block.prev_block
            pb.setPos(block.pos().x() - pb.rect().width() + overlap, block.pos().y())
            self.reflow_chain(pb, visited)

        # 2. vertical action flow
        if block.below_block and not isinstance(block.below_block, ChemicalBlock):
            bb = block.below_block
            new_x = block.pos().x() + (block.rect().width() - bb.rect().width()) / 2
            new_y = block.pos().y() + block.rect().height() - overlap
            bb.setPos(new_x, new_y)
            self.reflow_chain(bb, visited)

        # 3. subproduct branch (anchored below separate)
        if hasattr(block, 'subproduct_below') and block.subproduct_below:
            sb = block.subproduct_below
            new_x = block.pos().x() + (block.rect().width() - sb.rect().width()) / 2
            new_y = block.pos().y() + block.rect().height() - 8
            sb.setPos(new_x, new_y)
            self.reflow_chain(sb, visited)

        # 4. align chemicals (ingredients)
        if hasattr(block, 'chem_below') and block.chem_below:
            cb = block.chem_below
            cb.toggle_orientation(block.orientation)
            a_rect, c_rect = block.rect(), cb.rect()
            
            if block.action == "SubProductCreation":
                # specific logic for subproduct: arrow is at the top
                new_x = block.pos().x() - c_rect.width() + border_overlap
                body_start_y = block.pos().y() + 18
                body_h = a_rect.height() - 18
                new_y = body_start_y + (body_h - c_rect.height()) / 2
                
            elif block.orientation == "vertical":
                # standard vertical action: arrow is at the bottom
                new_x = block.pos().x() - c_rect.width() + border_overlap
                body_h = a_rect.height() - 18
                new_y = block.pos().y() + (body_h - c_rect.height()) / 2
            else:
                # horizontal action alignment
                body_w = a_rect.width() - 18
                new_x = block.pos().x() + (body_w - c_rect.width()) / 2 
                new_y = block.pos().y() + a_rect.height() - 4

            if abs(cb.pos().x() - new_x) > precision or abs(cb.pos().y() - new_y) > precision:
                cb.setPos(new_x, new_y)
            
            self.reflow_chemicals(cb, block.orientation)
          
    def reflow_chemicals(self, first_chem, orientation):
        """Stacks chemicals based on orientation: Downwards if Horizontal, Leftwards if Vertical."""
        curr = first_chem
        border_overlap = 6
        
        while curr:
            curr.set_connected(True)
            if curr.below_block:
                nxt = curr.below_block
                nxt.toggle_orientation(orientation)
                
                if orientation == "vertical":
                    # Stack to the left: New chemical right border overlaps current left border
                    new_x = curr.pos().x() - nxt.rect().width() + border_overlap
                    new_y = curr.pos().y()
                else:
                    # Stack downwards: Standard vertical list
                    new_x = curr.pos().x()
                    new_y = curr.pos().y() + curr.rect().height() - border_overlap
                
                nxt.setPos(new_x, new_y)
                curr = nxt
            else:
                break
    
    def find_chain_start(self, block):
        """Helper to find the first block of a horizontal chain."""
        curr = block
        while curr and curr.prev_block:
            curr = curr.prev_block
        return curr

    def align_chain_vertical(self, start_block, target_y: float):
        """Align start_block and all following blocks (via next_block)
        to the same vertical position (target_y).
        """
        b = start_block
        while b:
            pos = b.pos()
            b.setPos(pos.x(), target_y)
            b = b.next_block

    def update_support_logic(self):
        """calculate support influences where vertical effects propagate into horizontal chains."""
        # 1. reset state for all blocks
        for b in self.blocks:
            b.support_id = None
            b.support_color = None
            b.influence_list = []
            b._inc_h = {} 
            b._inc_v = {}

        type_config = {
            "ChangeTemperature": ("CT", QColor(255, 20, 147)), 
            "ChangeAtmosphere": ("CA", QColor(46, 204, 113)),  
            "NewRecipient": ("NR", QColor(155, 89, 182)),
            "ChangeAgitation": ("AG", QColor(52, 152, 219)),
            "SubProductCreation": ("SP", QColor(231, 76, 60)),
            "Repeat": ("RE", QColor(230, 126, 34)),
            "ContinuousAddition": ("CD", QColor(26, 188, 156))
        }

        type_counters = {k: 1 for k in type_config.keys()}
        support_registry = {} 

        # 2. assign ids and colors to support action instances
        for b in self.blocks:
            if isinstance(b, SupportAction) and b.action in type_config:
                prefix, color = type_config[b.action]
                idx = type_counters[b.action]
                b.support_id = f"{prefix}{idx}"
                b.support_color = color
                support_registry[b] = {"id": b.support_id, "color": color, "action": b.action}
                type_counters[b.action] += 1

        # 3. propagate influences
        visited = set()

        def propagate(block, incoming_influences, source_type):
            if not block:
                return

            disabled_ids = getattr(block, "disabled_influences", set()) or set()
            block.available_influences = list(incoming_influences.values())
            filtered_incoming = {
                key: value for key, value in incoming_influences.items()
                if value.get("id") not in disabled_ids
            }
            
            # store incoming based on axis
            if source_type == "h":
                block._inc_h = filtered_incoming
            else:
                block._inc_v = filtered_incoming

            # merge logic: horizontal priority overwrites vertical if keys clash
            merged = block._inc_v.copy()
            merged.update(block._inc_h)

            # state check to handle intersections without infinite loops
            state_key = (block, tuple(sorted(merged.keys())), tuple(sorted([v['id'] for v in merged.values()])))
            if state_key in visited:
                return
            visited.add(state_key)

            # update display list for non-support blocks
            if not block.support_id:
                block.influence_list = list(merged.values())
            
            # prepare outgoing influences for the next steps
            out_influences = merged.copy()

            # if current block is a source, update the outgoing stream with its own info
            if block in support_registry:
                out_influences[block.action] = support_registry[block]

            # 4. follow horizontal flow: now carries merged state (including vertical hits)
            if block.next_block:
                propagate(block.next_block, out_influences, "h")

            # 5. follow vertical action flow: carries merged state
            if block.below_block and not isinstance(block.below_block, ChemicalBlock):
                propagate(block.below_block, out_influences, "v")
            
            # 6. update attached chemicals
            curr_chem = block.chem_below
            while curr_chem:
                curr_chem.influence_list = list(out_influences.values())
                curr_chem.update()
                curr_chem = curr_chem.below_block

        # identify all root blocks (is_first or blocks with no incoming action links)
        roots = [b for b in self.blocks if b.is_first or (not b.prev_block and not b.above_block)]
        for root in roots:
            propagate(root, {}, "h")
        
        for b in self.blocks:
            if isinstance(b, ElementaryAction) and b.available_influences:
                for inf in b.available_influences:
                    if inf.get("action") in LOCKED_INFLUENCE_ACTIONS and inf.get("id"):
                        b.disabled_influences.discard(inf["id"])

        # force redraw to show badges
        for b in self.blocks:
            b.update()

        self.refresh_procedure_guide()

    def collect_procedure_guide_steps(self) -> list[dict]:
        """Build guide steps from the main horizontal action chain (no imported flows)."""
        heads = [
            b
            for b in self.blocks
            if not isinstance(b, ChemicalBlock)
            and b.action != "SubProductCreation"
            and b.prev_block is None
            and (b.next_block is not None or b.is_first)
        ]
        if not heads:
            return []

        start = next((b for b in heads if b.is_first), heads[0])
        steps: list[dict] = []
        visited: set[int] = set()
        curr = start
        while curr and id(curr) not in visited:
            if isinstance(curr, ChemicalBlock):
                break
            visited.add(id(curr))
            steps.append(self._block_to_procedure_guide_step(curr))
            subproduct = getattr(curr, "subproduct_below", None)
            if subproduct is not None and id(subproduct) not in visited:
                steps.append(self._block_to_procedure_guide_step(subproduct))
            curr = curr.next_block
        return steps

    def _block_to_procedure_guide_step(self, block) -> dict:
        chemicals = []
        chem = getattr(block, "chem_below", None)
        while chem:
            chemicals.append(
                {
                    "chemical": chem.action,
                    "params": chem.params.copy(),
                }
            )
            chem = getattr(chem, "below_block", None)

        step = {
            "action": block.action,
            "params": block.params.copy(),
        }
        if block.action == "SubProductCreation":
            step["params"][KEY_SUBSTANCE] = chemicals
        elif chemicals:
            step["chemicals"] = chemicals
        return step

    def refresh_procedure_guide(self) -> None:
        if not hasattr(self, "procedure_guide_label"):
            return
        text = build_procedure_text(self.collect_procedure_guide_steps())
        self.procedure_guide_label.setText(text)
        if self.procedure_guide_popup.isVisible():
            self._fit_procedure_guide_popup()
            self._position_procedure_guide_popup()

    def keyPressEvent(self, event):
        """Handle key press events for the editor"""
        if event.key() == Qt.Key_Delete:
            # Delete selected block
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if hasattr(item, 'delete_block'):
                    item.delete_block()
        else:
            super().keyPressEvent(event)

    def _reconstruct_block(self, step_data, flow_type, id_to_block):
        """helper to create a block and its nested components during import."""
        action_name = step_data.get("action")
        params = step_data.get("params", {})
        b_id = step_data.get("block_id")
        
        new_block = self._create_block_by_name(action_name, params)
        # Imported workflows are reconstructed from the default creation position.
        new_block.setPos(50, 50)
        new_block.toggle_orientation(flow_type)
        id_to_block[b_id] = new_block
        self._register_block_id(new_block, b_id)

        # 1. handle subproduct branches
        if "subproduct_branch" in step_data:
            sub_data = step_data["subproduct_branch"]
            sub_block = self._reconstruct_block(sub_data, "vertical", id_to_block)
            # anchor subproduct specifically
            new_block.subproduct_below = sub_block
            sub_block.above_block = new_block
            sub_block.setFlag(QGraphicsRectItem.ItemIsMovable, False)

        # 2. handle chemicals (ingredients)
        # for subproducts, chemicals are inside params['substance']
        if action_name == "SubProductCreation":
            chem_list = params.get(KEY_SUBSTANCE, [])
        else:
            chem_list = step_data.get("chemicals", [])
            
        prev_chem = None
        for c_data in chem_list:
            chem_name = c_data.get("chemical")
            chem_params = c_data.get("params", {})
            cb = ChemicalBlock(chem_name, chem_params, editor=self)
            self.scene.addItem(cb)
            self.blocks.append(cb)
            self._register_block_id(cb, c_data.get("block_id"))
            
            if prev_chem is None:
                new_block.chem_below = cb
                cb.above_block = new_block
            else:
                prev_chem.below_block = cb
                cb.above_block = prev_chem
            prev_chem = cb
            
        return new_block

    def _create_block_by_name(self, name, params):
        """helper to instantiate the correct block class with proper colors."""
        elementary_list = ["Add", "Grind", "Separate", "Sieve", "Wait"]
        
        if name in elementary_list:
            block = ElementaryAction(name, params, editor=self)
        else:
            block = SupportAction(name, params, editor=self)
        
        self.scene.addItem(block)
        self.blocks.append(block)
        self._register_block_id(block)
        if isinstance(block, SupportAction) and not self.show_support_actions:
            block.setVisible(False)
        return block
    
    def _reconstruct_chemicals(self, action_block, chem_list):
        """helper to append chemicals to an existing action's stack."""
        # find the last chemical in the current stack
        curr = action_block.chem_below
        if curr:
            while curr.below_block:
                curr = curr.below_block
        
        for c_data in chem_list:
            cb = ChemicalBlock(c_data.get("chemical"), c_data.get("params", {}), editor=self)
            self.scene.addItem(cb)
            self.blocks.append(cb)
            self._register_block_id(cb, c_data.get("block_id"))
            
            if action_block.chem_below is None:
                action_block.chem_below = cb
                cb.above_block = action_block
            else:
                # 'curr' is now the last chemical
                curr.below_block = cb
                cb.above_block = curr
            curr = cb # update last chemical

    def import_protocol(self):
        """import protocol and reconstruct layout from the default start position."""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "import protocol",
            "",
            "Protocol Files (*.json *.yaml *.yml);;JSON Files (*.json);;YAML Files (*.yaml *.yml)",
        )
        if not filename: return

        try:
            if filename.lower().endswith((".yaml", ".yml")):
                try:
                    import yaml
                except ImportError as exc:
                    raise RuntimeError("PyYAML is required to import YAML protocol files.") from exc
                with open(filename, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                with open(filename, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if isinstance(data, dict) and "activities" in data and "flows" not in data:
                data = convert_linkml_to_protocol(data)
            self.load_protocol_data(data, include_hidden=False)

        except Exception as e:
            print(f"error importing protocol: {e}")

    def generate_protocol_output(self, show_feedback=True):
        """Build the protocol JSON structure from current editor blocks."""
        if not self.blocks:
            if show_feedback:
                print("no blocks to export.")
            return None

        # check for empty subproduct creation blocks
        empty_subproducts = [b for b in self.blocks if b.action == "SubProductCreation" and b.chem_below is None]
        if empty_subproducts:
            if show_feedback:
                QMessageBox.warning(self, "Export Error", "Every Sub Product Creation must have at least one chemical attached.")
            return None

        self._next_id = len(self.blocks)
        block_to_id = {block: i for i, block in enumerate(self.blocks)}
        flows_list = []
        next_flow_id = 1
        next_hidden_block_id = max(block_to_id.values(), default=-1) + 1
        visited_globally = set()

        def append_flow(flow_data):
            nonlocal next_flow_id
            flow_copy = copy.deepcopy(flow_data)
            ordered_flow = {"flow_id": next_flow_id}
            for key, value in flow_copy.items():
                if key == "flow_id":
                    continue
                ordered_flow[key] = value
            next_flow_id += 1
            flows_list.append(ordered_flow)
            return ordered_flow

        def get_step_data(block, local_visited):
            """extracts block data. allows intersection by ignoring visited_globally here."""
            if block in local_visited:
                return []

            local_visited.add(block)
            visited_globally.add(block) # used only for orphan validation at the end

            base_data = {
                "block_id": block_to_id[block],
                "action": block.action,
                "params": block.params.copy(),
            }
            if getattr(block, "part_of_complex_action", False):
                base_data["part_of_complex_action"] = True
                if getattr(block, "complex_group_id", None):
                    base_data["complex_group_id"] = block.complex_group_id
                if getattr(block, "complex_step_index", None) is not None:
                    base_data["complex_step_index"] = block.complex_step_index
                group = self.complex_action_groups.get(block.complex_group_id)
                if group is not None:
                    base_data["complex_action_name"] = group.definition_name

            # collect chemicals
            chemicals = []
            curr_chem = block.chem_below
            while curr_chem:
                visited_globally.add(curr_chem)
                chem_params = curr_chem.params.copy()
                chemicals.append({
                    "block_id": block_to_id[curr_chem],
                    "chemical": curr_chem.action,
                    "params": chem_params
                })
                curr_chem = curr_chem.below_block

            # handle subproduct branches
            sub_branch = None
            if hasattr(block, 'subproduct_below') and block.subproduct_below:
                # subproducts are vertical branches, we use a fresh local set
                res = get_step_data(block.subproduct_below, set())
                if res: sub_branch = res[0]

            # split Add logic
            if block.action == "Add" and len(chemicals) > 1:
                split_steps = []
                for i, chem in enumerate(chemicals):
                    step = base_data.copy()
                    step["block_id"] = block_to_id[block] if i == 0 else self._next_id
                    step["source_block_id"] = block_to_id[block]
                    if i > 0: self._next_id += 1
                    step["chemicals"] = [chem]
                    split_steps.append(step)
                return split_steps

            # standard action
            data = base_data.copy()
            if block.action == "SubProductCreation":
                data["params"][KEY_SUBSTANCE] = chemicals
            elif chemicals:
                data["chemicals"] = chemicals

            if sub_branch:
                data["subproduct_branch"] = sub_branch

            return [data]

        def collect_ids_from_step(step, id_set):
            if not isinstance(step, dict):
                return
            block_id = step.get("block_id")
            if isinstance(block_id, int):
                id_set.add(block_id)
            source_id = step.get("source_block_id")
            if isinstance(source_id, int):
                id_set.add(source_id)

            for chem in step.get("chemicals", []):
                if isinstance(chem, dict):
                    chem_id = chem.get("block_id")
                    if isinstance(chem_id, int):
                        id_set.add(chem_id)

            sub_branch = step.get("subproduct_branch")
            if isinstance(sub_branch, dict):
                collect_ids_from_step(sub_branch, id_set)

        def remap_step_ids(step, id_map):
            if not isinstance(step, dict):
                return
            block_id = step.get("block_id")
            if block_id in id_map:
                step["block_id"] = id_map[block_id]
            source_id = step.get("source_block_id")
            if source_id in id_map:
                step["source_block_id"] = id_map[source_id]

            for chem in step.get("chemicals", []):
                if isinstance(chem, dict):
                    chem_id = chem.get("block_id")
                    if chem_id in id_map:
                        chem["block_id"] = id_map[chem_id]

            sub_branch = step.get("subproduct_branch")
            if isinstance(sub_branch, dict):
                remap_step_ids(sub_branch, id_map)

        # --- 1. export horizontal flows ---
        for b in self.blocks:
            if isinstance(b, (ChemicalBlock, ComplexActionBlock)) or b.action == "SubProductCreation":
                continue
            group_id = getattr(b, "complex_group_id", None)
            if group_id:
                group = self.complex_action_groups.get(group_id)
                if group and b is not group.member_blocks[0]:
                    continue
            if self._is_export_horizontal_flow_head(b):
                local_path = set()
                content = self._collect_horizontal_flow_steps(b, get_step_data, local_path)
                append_flow({"type": "horizontal", "is_explicit_first": b.is_first, "steps": content})

        # --- 2. export vertical flows ---
        for b in self.blocks:
            if isinstance(b, ChemicalBlock) or b.action == "SubProductCreation": continue
            has_action_above = b.above_block is not None and not isinstance(b.above_block, ChemicalBlock)
            if not has_action_above:
                if b.below_block is not None or (b.is_first and b.orientation == "vertical"):
                    content = []
                    curr = b
                    local_path = set() # unique for this flow
                    while curr:
                        content.extend(get_step_data(curr, local_path))
                        curr = curr.below_block
                        if isinstance(curr, ChemicalBlock) or curr is None: break
                    append_flow({"type": "vertical", "is_explicit_first": b.is_first, "steps": content})

        # --- 3. append hidden open-entity procedures ---
        for block, procedure in self.open_entity_procedures.items():
            block_id = block_to_id.get(block)
            if block_id is None or not procedure:
                continue

            imported_flows = procedure.get("flows", [])
            imported_ids = set()
            for flow in imported_flows:
                for step in flow.get("steps", []):
                    collect_ids_from_step(step, imported_ids)

            imported_nested_chem_ids = {
                flow.get("chemical_block_id")
                for flow in imported_flows
                if isinstance(flow.get("chemical_block_id"), int)
            }
            imported_ids.update(imported_nested_chem_ids)

            id_map = {}
            for old_id in sorted(imported_ids):
                id_map[old_id] = next_hidden_block_id
                next_hidden_block_id += 1

            for flow in imported_flows:
                flow_copy = copy.deepcopy(flow)
                for step in flow_copy.get("steps", []):
                    remap_step_ids(step, id_map)

                source_chemical_block_id = flow_copy.get("chemical_block_id")
                if isinstance(source_chemical_block_id, int):
                    resolved_chemical_block_id = id_map.get(source_chemical_block_id, block_id)
                else:
                    resolved_chemical_block_id = block_id

                ordered_flow = {
                    "type": flow_copy.get("type", "horizontal"),
                    "is_explicit_first": flow_copy.get("is_explicit_first", False),
                    "chemical_block_id": resolved_chemical_block_id,
                    "steps": flow_copy.get("steps", []),
                }
                append_flow(ordered_flow)

        return Protocol.build_protocol_envelope(flows_list)
    
    def _ensure_exportable_flows(self, protocol_data) -> bool:
        if protocol_data.get("flows"):
            return True
        QMessageBox.warning(
            self,
            "Export Error",
            (
                "No exportable action flows were found.\n\n"
                "Connect actions in a horizontal chain, or ensure complex-action "
                "steps remain linked together."
            ),
        )
        return False

    def export_protocol(self):
        """Export either the internal protocol or the LinkML payload."""
        dialog = ExportProtocolDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        export_kind = dialog.export_kind
        export_format = dialog.export_format

        if export_kind == "procedure_text":
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Procedure Guide",
                "procedure_guide.txt",
                "Text Files (*.txt)",
            )
            if not filename:
                return
            if not filename.lower().endswith(".txt"):
                filename += ".txt"
            try:
                text = build_procedure_text(self.collect_procedure_guide_steps())
                with open(filename, "w", encoding="utf-8") as handle:
                    handle.write(text)
                print(f"procedure guide exported to {filename}")
            except OSError as exc:
                QMessageBox.critical(self, "Export Error", f"Failed to export procedure guide:\n{exc}")
            return

        default_name = "protocol.linkml" if export_kind == "linkml" else "protocol"
        default_name = f"{default_name}.{export_format}"

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Protocol",
            default_name,
            "JSON Files (*.json);;YAML Files (*.yaml *.yml)",
        )
        if not filename:
            return

        lower_name = filename.lower()
        if not lower_name.endswith((".json", ".yaml", ".yml")):
            filename += ".yaml" if export_format == "yaml" else ".json"

        final_output = self.generate_protocol_output(show_feedback=True)
        if not final_output:
            return
        if not self._ensure_exportable_flows(final_output):
            return

        try:
            payload = final_output
            
            # Validate against LinkML schema for both export kinds
            validation_msgs = validate_linkml_protocol(final_output)
            user_visible_msgs = [m for m in validation_msgs if m.level in {"error", "warning"}]
            
            # Report validation results
            if user_visible_msgs:
                msg_count = len(user_visible_msgs)
                error_count = sum(1 for m in user_visible_msgs if m.level == "error")
                warning_count = sum(1 for m in user_visible_msgs if m.level == "warning")
                print(f"[linkml-validation] errors={error_count}, warnings={warning_count}")
                
                # Show first few messages for context
                for i, msg in enumerate(user_visible_msgs[:5]):
                    print(f"  - [{msg.level}] {msg.code}: {msg.message}")
                if msg_count > 5:
                    print(f"  ... ({msg_count - 5} more messages)")
                
                # Block export if there are errors
                def _format_validation_notice(msg, label, protocol=None):
                    """Format validation errors in a user-friendly way with context about the block."""
                    ctx = msg.context or {}
                    code = getattr(msg, "code", "") or ""
                    message_text = msg.message.strip()

                    if code in {"linkml.unavailable", "schema.unavailable"}:
                        return (
                            f"{label}\n\n"
                            f"📍 Global validation\n\n"
                            f"{message_text}\n\n"
                            f"This is an environment or dependency issue, not a protocol field problem."
                        )
                    if code == "linkml.validation_prep_failed" and "Strict LinkML validation failed" not in message_text:
                        return (
                            f"{label}\n\n"
                            f"📍 Global validation\n\n"
                            f"{message_text}\n\n"
                            f"This is an environment or dependency issue, not a protocol field problem."
                        )
                    if code == "linkml.no_activities":
                        return (
                            f"{label}\n\n"
                            f"📍 Global validation\n\n"
                            f"{message_text}\n\n"
                            f"Ensure actions are connected in at least one horizontal flow."
                        )

                    def _humanize_name(name: str | None) -> str | None:
                        if not name:
                            return None
                        text = str(name).replace("_", " ")
                        text = re.sub(r"(?<!^)(?=[A-Z])", " ", text)
                        text = re.sub(r"\s+", " ", text).strip()
                        return text if text else None

                    def _extract_step_index(message: str) -> int | None:
                        """Extract the step index from a LinkML path such as /has_synthesis_step/7/..."""
                        path_match = re.search(r"(?:in\s+)?(?P<path>/[^\s]+)", message)
                        if not path_match:
                            return None
                        parts = [p for p in path_match.group("path").split("/") if p]
                        for idx, part in enumerate(parts):
                            if part == "has_synthesis_step" and idx + 1 < len(parts):
                                next_part = parts[idx + 1]
                                if next_part.isdigit():
                                    return int(next_part)
                        return None
                    
                    # 1. Find action name from validation context first
                    action_name = ctx.get("source_action")
                    chemical_name = ctx.get("source_chemical")
                    if not ctx.get("step_index"):
                        inferred_step_index = _extract_step_index(message_text)
                        if inferred_step_index is not None:
                            ctx["step_index"] = inferred_step_index
                    if not action_name and protocol and "activities" in protocol:
                        activity_idx = ctx.get("activity_index", 0)
                        step_idx = ctx.get("step_index")
                        if activity_idx < len(protocol["activities"]) and step_idx is not None:
                            activity = protocol["activities"][activity_idx]
                            steps = activity.get("has_synthesis_step", [])
                            if step_idx < len(steps):
                                action_name = steps[step_idx].get("source_action")
                    if not chemical_name and protocol and "activities" in protocol:
                        activity_idx = ctx.get("activity_index", 0)
                        step_idx = ctx.get("step_index")
                        if activity_idx < len(protocol["activities"]) and step_idx is not None:
                            activity = protocol["activities"][activity_idx]
                            steps = activity.get("has_synthesis_step", [])
                            if step_idx < len(steps):
                                attached = steps[step_idx].get("attached_chemicals", []) or []
                                chem_idx = ctx.get("chemical_index")
                                if isinstance(chem_idx, int) and 0 <= chem_idx < len(attached):
                                    chemical_name = attached[chem_idx].get("chemical")
                    
                    # 2. Extract field name and invalid value from error message
                    def extract_field_and_value():
                        """Extract field name and the invalid value from LinkML error message."""
                        field_label = None
                        invalid_value = None
                        slot_name = None
                        
                        # Try to extract slot name from path: /has_synthesis_step/7/has_atmosphere_type/0
                        path_match = re.search(r"in\s+(?P<path>/[^\s]+)", message_text)
                        if path_match:
                            path = path_match.group("path")
                            parts = [p for p in path.split("/") if p and not p.isdigit()]
                            if parts:
                                slot_name = parts[-1]
                                param_key = STEP_SLOT_TO_PARAM.get(slot_name) or CHEMICAL_SLOT_TO_PARAM.get(slot_name)
                                if param_key:
                                    field_label = FIELD_CONFIG.get(param_key, {}).get("label", slot_name)
                        
                        # Extract invalid value from quotes
                        value_match = re.search(r"'([^']*)' is not one of", message_text)
                        if not value_match:
                            value_match = re.search(r"'([^']*)' is not valid under any of the given schemas", message_text)
                        if value_match:
                            invalid_value = value_match.group(1)
                        
                        return field_label, invalid_value, slot_name
                    
                    # 3. Extract allowed values for enum errors
                    def extract_allowed_values():
                        """Extract the list of allowed values."""
                        if "is not one of" not in message_text and "allowed values" not in message_text.lower():
                            return []
                        list_match = re.search(r"\[([^\]]+)\]", message_text)
                        if list_match:
                            allowed_raw = list_match.group(1)
                            return [
                                item.strip().strip("'\"")
                                for item in allowed_raw.split(",")
                                if item.strip()
                            ]
                        return []
                    
                    field_label, invalid_value, slot_name = extract_field_and_value()
                    allowed_values = extract_allowed_values()
                    
                    # 4. Build user-friendly location string
                    location_parts = []
                    step_num = ctx.get("step_index", 0) + 1 if ctx.get("step_index") is not None else None
                    if chemical_name:
                        location_parts.append(f"Chemical: {_humanize_name(chemical_name) or chemical_name}")
                        if action_name:
                            location_parts.append(f"Parent block: {_humanize_name(action_name) or action_name}")
                    elif action_name:
                        location_parts.append(f"Block: {_humanize_name(action_name) or action_name}")
                    if step_num:
                        location_parts.append(f"Step #{step_num}")
                    activity_num = ctx.get("activity_index", 0) + 1
                    if activity_num > 1:
                        location_parts.append(f"Activity {activity_num}")
                    
                    location = " | ".join(location_parts) if location_parts else "Global validation"
                    
                    # 5. Build hint about what's wrong and what's allowed
                    hint_parts = []
                    if field_label:
                        hint_parts.append(f"Field: {field_label}")
                    if invalid_value:
                        hint_parts.append(f"Current value: '{invalid_value}' ❌")
                    if allowed_values:
                        allowed_str = ", ".join([f"'{v}'" for v in allowed_values])
                        hint_parts.append(f"Allowed values: {allowed_str}")
                    elif "not valid under any of the given schemas" in message_text:
                        hint_parts.append("Format: use value and unit (e.g., '12 mL' or '5 g').")
                    elif "Additional properties are not allowed" in message_text:
                        hint_parts.append("Expected: a simple value (e.g., '50 C' or '50 °C')")
                    elif slot_name and not field_label:
                        hint_parts.append(f"Field: {slot_name}")
                    
                    hint_text = "\n".join(hint_parts) if hint_parts else message_text
                    
                    # 6. Build final formatted message
                    return (
                        f"{label}\n\n"
                        f"📍 {location}\n\n"
                        f"{hint_text}\n\n"
                        f"👉 Review this step and fix the highlighted field."
                    )


                if error_count > 0:
                    first_error = next(m for m in user_visible_msgs if m.level == "error")
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Icon.Critical)
                    box.setWindowTitle("Validation Failed")
                    box.setText(
                        _format_validation_notice(
                            first_error,
                            f"Protocol validation failed ({error_count} error(s)).",
                            protocol=final_output
                        )
                    )
                    box.exec()
                    return
                elif warning_count > 0:
                    first_warning = next(m for m in user_visible_msgs if m.level == "warning")
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Icon.Warning)
                    box.setWindowTitle("Validation Warnings")
                    box.setText(
                        _format_validation_notice(
                            first_warning,
                            f"Protocol has {warning_count} validation warning(s).",
                            protocol=final_output
                        )
                    )
                    box.exec()
            else:
                print("[linkml-validation] passed (no issues)")
            
            if export_kind == "linkml":
                payload = convert_protocol_to_linkml(final_output, mode="strict")
                summary = summarize_linkml_export(payload)
                print(
                    f"[linkml-export:strict] activities={summary.activity_count} "
                    f"steps={summary.step_count} chemicals={summary.chemical_count} "
                    f"unmapped_fields={summary.unmapped_fields}"
                )

            with open(filename, "w", encoding="utf-8") as f:
                if filename.lower().endswith((".yaml", ".yml")):
                    f.write(self._to_yaml(payload))
                else:
                    json.dump(payload, f, indent=2, ensure_ascii=False)

            if export_kind == "linkml":
                print(f"linkml payload exported to {filename}")
            else:
                print(f"protocol exported to {filename} (validated against LinkML schema)")

        except Exception as e:
            print(f"error: {e}")
            QMessageBox.critical(self, "Export Error", f"Failed to export protocol:\n{e}")

    def export_linkml_protocol(self):
        """Backward-compatible helper for LinkML export."""
        self._export_linkml_protocol_legacy()

    def _export_linkml_protocol_legacy(self):
        final_output = self.generate_protocol_output(show_feedback=True)
        if not final_output:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export LinkML Payload",
            "protocol.linkml.json",
            "JSON Files (*.json);;YAML Files (*.yaml *.yml)",
        )
        if not filename:
            return

        if not filename.lower().endswith((".json", ".yaml", ".yml")):
            filename += ".json"

        try:
            payload = convert_protocol_to_linkml(final_output, mode="strict")
            summary = summarize_linkml_export(payload)
            print(
                f"[linkml-export:strict] activities={summary.activity_count} "
                f"steps={summary.step_count} chemicals={summary.chemical_count} "
                f"unmapped_fields={summary.unmapped_fields}"
            )

            with open(filename, "w", encoding="utf-8") as f:
                if filename.lower().endswith((".yaml", ".yml")):
                    f.write(self._to_yaml(payload))
                else:
                    json.dump(payload, f, indent=2, ensure_ascii=False)

            print(f"linkml payload exported to {filename}")
        except Exception as e:
            print(f"error exporting linkml payload: {e}")

    def _to_yaml(self, data):
        """Serialize protocol data to YAML without external dependencies."""
        lines = self._yaml_lines(data, 0)
        return "\n".join(lines) + "\n"

    def _yaml_lines(self, value, indent):
        space = " " * indent

        if isinstance(value, dict):
            if not value:
                return [space + "{}"]

            lines = []
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    if isinstance(item, dict) and not item:
                        lines.append(f"{space}{key}: {{}}")
                    elif isinstance(item, list) and not item:
                        lines.append(f"{space}{key}: []")
                    else:
                        lines.append(f"{space}{key}:")
                        lines.extend(self._yaml_lines(item, indent + 2))
                else:
                    lines.append(f"{space}{key}: {self._yaml_scalar(item)}")
            return lines

        if isinstance(value, list):
            if not value:
                return [space + "[]"]

            lines = []
            for item in value:
                if isinstance(item, (dict, list)):
                    if isinstance(item, dict) and not item:
                        lines.append(space + "- {}")
                    elif isinstance(item, list) and not item:
                        lines.append(space + "- []")
                    else:
                        lines.append(space + "-")
                        lines.extend(self._yaml_lines(item, indent + 2))
                else:
                    lines.append(f"{space}- {self._yaml_scalar(item)}")
            return lines

        return [space + self._yaml_scalar(value)]

    def _yaml_scalar(self, value):
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)


class EntityProcedureEditorDialog(QDialog):
    """Full protocol builder window for a chemical's preparation procedure."""

    def __init__(self, parent=None, initial_procedure=None):
        super().__init__(parent)
        self.setWindowTitle("Preparation Procedure Editor")
        self.resize(1200, 820)
        self.procedure_data = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.procedure_editor = Editor()
        if hasattr(self.procedure_editor, "title_label"):
            self.procedure_editor.title_label.setText("Preparation Procedure Editor")

        if initial_procedure:
            self.procedure_editor.load_protocol_data(
                normalize_preparation_procedure(initial_procedure),
                include_hidden=True,
            )

        layout.addWidget(self.procedure_editor.container, 1)

        button_bar = QWidget()
        button_layout = QHBoxLayout(button_bar)
        button_layout.setContentsMargins(16, 8, 16, 12)
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setMinimumSize(120, 36)
        cancel_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        save_btn = QPushButton("Save Procedure")
        save_btn.setMinimumSize(140, 36)
        save_btn.setStyleSheet(PRIMARY_BUTTON_STYLE)
        save_btn.clicked.connect(self._save_procedure)
        button_layout.addWidget(save_btn)

        layout.addWidget(button_bar)

    def _save_procedure(self):
        data = self.procedure_editor.generate_protocol_output(show_feedback=True)
        if data is None:
            data = Protocol.build_protocol_envelope([])
        self.procedure_data = normalize_preparation_procedure(data)
        self.accept()
