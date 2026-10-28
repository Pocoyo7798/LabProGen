# config.py

# --- GLOBAL DEFAULTS ---
DEFAULT_PROTOCOL_NAME = "laboratory procedure"

# --- FEATURE FLAGS ---
ENABLE_VERTICAL_ORIENTATION_TOGGLE = False

# Support influences that cannot be toggled off on elementary actions (e.g. Change Recipient)
LOCKED_INFLUENCE_ACTIONS = frozenset()

# --- CHECKED SCHEMA REFERENCES ---
# Constants name application behaviours; they do not declare LinkML properties.
# A rename/removal must be reviewed instead of silently using the old key.
from labprogen.linkml.loader import schema_view

_SCHEMA_SLOT_REFERENCES = set()


def _slot_reference(name):
    if name not in schema_view().all_slots():
        raise ValueError(f"Obsolete schema reference: {name!r}. Review application integration and regenerate models.")
    _SCHEMA_SLOT_REFERENCES.add(name)
    return name


# --- PARAM KEYS (unwrapped strings are explicitly legacy names) ---

# Actions - shared
KEY_DURATION = _slot_reference("duration")
KEY_AMOUNT = _slot_reference("amount")

# Actions - Add
KEY_ADD_TYPE = _slot_reference("add_type")
KEY_ADD_QUANTITY = "add_quantity"
KEY_OPEN_FLAME = _slot_reference("open_flame")

# Actions - Separate
KEY_PHASE = _slot_reference("phase_to_keep")
KEY_METHOD = _slot_reference("method")

# Actions - Sieve
KEY_SIZE_RANGE = _slot_reference("size_range")
KEY_MIN_SIZE = "min_size"  # legacy load alias
KEY_MAX_SIZE = "max_size"  # legacy load alias

# Actions - ChangePressure / ContinuousAddition
KEY_GASES = "gases"  # legacy load alias
KEY_FLOW_RATE = _slot_reference("flow_rate")
KEY_PRESSURE = _slot_reference("pressure")

# Actions - ChangeTemperature
KEY_TEMPERATURE = _slot_reference("temperature")
KEY_PROCESS = _slot_reference("process")
KEY_RAMP = _slot_reference("ramp")
KEY_POWER = _slot_reference("power")

# Actions - ChangeContainer
KEY_RECIPIENT = _slot_reference("recipient")
KEY_MATERIAL = _slot_reference("material")
KEY_VOLUME = _slot_reference("volume")

# Actions - ChangeAgitation
KEY_AGITATION_TYPE = _slot_reference("agitation_type")
KEY_SPEED = _slot_reference("speed")

# Actions - CollectSubProduct
KEY_SUBSTANCE = "substance"

# Actions - ContinuousAddition
KEY_CONTINUOUS_ADD_TYPE = _slot_reference("continuous_add_type")
KEY_SUBSTANCE_LIST = "substance_list"

# Actions - attached material
KEY_CHEMICAL = _slot_reference("chemical")

# First level
KEY_PREPARATION_PROCEDURE = _slot_reference("preparation_procedure")
KEY_ENTITY_ID = _slot_reference("entity_id")
KEY_PRODUCER = _slot_reference("entity_producer")
KEY_ENTITY_PURITY = _slot_reference("entity_purity")
KEY_CAS_NUMBER = _slot_reference("cas_number")

# Chemical - shared
KEY_NAME = _slot_reference("name")
KEY_FORMULA = _slot_reference("formula")
KEY_SMILES = _slot_reference("smile")
KEY_INCHI = _slot_reference("inchi")
KEY_BIGSMILES = _slot_reference("bigsmiles")
KEY_CIF = "cif"
KEY_QUANTITY = _slot_reference("quantity")
KEY_CONCENTRATION = _slot_reference("concentration")

# Chemical - Mixture
KEY_ENTITY_TYPE = "entity_type"
KEY_MIXTURE_TYPE = "mixture_type"
KEY_CHEMICAL_LIST = _slot_reference("chemical_list")

# Chemical - Medium
KEY_FUNCTION = _slot_reference("function")
KEY_STATE = _slot_reference("state")
KEY_PURITY = _slot_reference("purity")
KEY_STERILITY = _slot_reference("sterility")
KEY_SOLUBILITY = _slot_reference("solubility")
KEY_TEMPERATURE_STABILITY = _slot_reference("temperature_stability")
KEY_LIGHT_SENSITIVITY = _slot_reference("light_sensitivity")
KEY_OXIDATION_SENSITIVITY = _slot_reference("oxidation_sensitivity")

# Chemical - BioProducts
KEY_ORIGIN = _slot_reference("origin")
KEY_PRODUCTION_PHASE = _slot_reference("production_phase")
KEY_LOCATION = _slot_reference("location")
KEY_TOXICITY_TO_PRODUCER = _slot_reference("toxicity_to_producer")

# Chemical - Dispersion
KEY_SOLVENT = "solvent"

# Chemical - Material
KEY_ATOMIC_COMP = "atomic_composition"
KEY_STRUCT_DESC = "structure_descriptor"
KEY_TEXTURAL_DESC = "textural_descriptors"
KEY_CHEM_DESC = "chemical_descriptors"
KEY_MAT_LIST = "materials_list"
KEY_BASE_MAT = "base_material"
KEY_BASE_COMPLEX = "base_complex_material"

# Chemical - PorousMaterial
KEY_3D_STRUCTURE = "3d_structure"
KEY_CRYSTALLINITY = _slot_reference("crystallinity")
KEY_N2_ADSORPTION_BET_AREA = _slot_reference("n2_adsorption_bet_area")
KEY_N2_ADSORPTION_MICROPORE_AREA = _slot_reference("n2_adsorption_micropore_area")
KEY_N2_ADSORPTION_MESOPORE_AREA = _slot_reference("n2_adsorption_mesopore_area")
KEY_N2_ADSORPTION_TOTAL_VOLUME = _slot_reference("n2_adsorption_total_volume")
KEY_N2_ADSORPTION_MICROPORE_VOLUME = _slot_reference("n2_adsorption_micropore_volume")
KEY_N2_MESOPORE_VOLUME = _slot_reference("n2_mesopore_volume")
KEY_PY_B_150 = _slot_reference("py_b_150")
KEY_PY_B_450 = _slot_reference("py_b_450")
KEY_PY_L_150 = _slot_reference("py_l_150")
KEY_PY_L_450 = _slot_reference("py_l_450")

# --- UI CONFIGURATION ---
# Presentation only: schema metadata is merged per class by core.model.field_config.
UI_FIELD_PREFERENCES = {
    # --- Actions - shared ---
    KEY_DURATION: {
        "label": "Duration",
        "type": "unit",
        "units": ["s", "min", "h"],
        "defaults": ["0", "10", "30"],
        "placeholder": "Time",
    },
    KEY_AMOUNT: {
        "label": "Amount",
        "type": "text",
        "placeholder": "Number of times...",
        "integer": True,
        "minimum": 1,
    },

    # --- Add ---
    KEY_ADD_QUANTITY: {"label": "Quantity", "type": "unit", "units": ["g", "ml", "L", "uL", "mg"], "defaults": ["0"], "placeholder": "Amount"},
    KEY_ADD_TYPE: {"label": "Type", "type": "dropdown"},
    KEY_OPEN_FLAME: {"label": "Open Flame", "type": "dropdown"},
    KEY_CHEMICAL: {"label": "Chemical", "type": "text", "placeholder": "Chemical entity name..."},

    # --- Separate ---
    KEY_PHASE: {"label": "Phase to Keep", "type": "dropdown"},
    KEY_METHOD: {"label": "Method", "type": "dropdown"},

    # --- Sieve ---
    KEY_SIZE_RANGE: {"label": "Size Range", "type": "text", "placeholder": "Particle size range..."},

    # --- ChangePressure / ContinuousAddition ---
    KEY_FLOW_RATE: {"label": "Flow Rate", "type": "unit", "units": ["mL/min", "L/h"], "defaults": ["0"], "placeholder": "Rate"},
    KEY_PRESSURE: {"label": "Pressure", "type": "unit", "units": ["bar", "atm", "Pa", "kPa"], "defaults": ["101.325"], "placeholder": "Pressure"},

    # --- ChangeTemperature ---
    KEY_TEMPERATURE: {"label": "Temperature", "type": "unit", "units": ["°C", "°F"], "defaults": ["50"], "placeholder": "Value"},
    KEY_PROCESS: {"label": "Process", "type": "dropdown"},
    KEY_RAMP: {"label": "Ramp", "type": "unit", "units": ["°C/min", "K/min"], "defaults": ["0"], "placeholder": "Slope"},
    KEY_POWER: {"label": "Power", "type": "unit", "units": ["W", "kW"], "defaults": ["0"], "placeholder": "Power"},

    # --- ChangeContainer ---
    KEY_RECIPIENT: {"label": "Recipient", "type": "dropdown"},
    KEY_MATERIAL: {"label": "Material", "type": "dropdown"},
    KEY_VOLUME: {"label": "Volume", "type": "unit", "units": ["μL", "mL", "L"], "defaults": ["0"], "placeholder": "Volume"},

    # --- ChangeAgitation ---
    KEY_AGITATION_TYPE: {"label": "Type", "type": "dropdown"},
    KEY_SPEED: {"label": "Speed", "type": "unit", "units": ["rpm"], "defaults": ["0"], "placeholder": "Velocity"},

    # --- CollectSubProduct ---
    KEY_SUBSTANCE: {"label": "Substance", "type": "text", "placeholder": "Chemical entity..."},

    # --- ContinuousAddition ---
    KEY_CONTINUOUS_ADD_TYPE: {"label": "Type", "type": "dropdown"},
    KEY_SUBSTANCE_LIST: {
        "label": "Substance List",
        "type": "list",
        "placeholder": "Add chemical entities...",
        "include_concentration": False,
    },

    # --- First level ---
    KEY_PREPARATION_PROCEDURE: {"label": "Preparation Procedure", "type": "text", "placeholder": "Description of preparation..."},
    KEY_ENTITY_ID: {"label": "ID", "type": "text", "placeholder": "Commercial or internal ID..."},
    KEY_PRODUCER: {"label": "Producer", "type": "text", "placeholder": "Institution that created the entity..."},
    KEY_ENTITY_PURITY: {"label": "Purity", "type": "text", "placeholder": "Degree of purity..."},
    KEY_CAS_NUMBER: {"label": "CAS Number", "type": "text", "placeholder": "Commercial identification number..."},

    # --- Chemical - shared ---
    KEY_NAME: {"label": "Name", "type": "text", "placeholder": "Entity or mixture name..."},
    KEY_FORMULA: {
        "label": "Formula",
        "labels_by_action": {"PorousMaterial": "Chemical Formula"},
        "type": "text",
        "placeholder": "Chemical formula...",
    },
    KEY_SMILES: {"label": "SMILE", "type": "text", "placeholder": "SMILE string..."},
    KEY_BIGSMILES: {"label": "BigSMILES", "type": "text", "placeholder": "BigSMILES string..."},
    KEY_INCHI: {"label": "InChi", "type": "text", "placeholder": "InChi string..."},
    KEY_QUANTITY: {"label": "Quantity", "type": "unit", "units": ["mg", "g", "kg", "mL", "L", "mol", "mmol"], "defaults": ["0"], "placeholder": "Amount"},
    KEY_CONCENTRATION: {
        "label": "Concentration",
        "type": "unit",
        "units": ["m/m", "vol/vol", "M", "g/L"],
        "defaults": ["0"],
        "placeholder": "Value",
    },

    # --- Chemical - Mixture ---
    KEY_CHEMICAL_LIST: {
        "label": "Chemical List",
        "type": "list",
        "placeholder": "Manage chemicals...",
        "include_concentration": True,
    },

    # --- Chemical - Medium ---
    KEY_FUNCTION: {"label": "Function", "type": "dropdown"},
    KEY_STATE: {"label": "State", "type": "dropdown"},
    KEY_PURITY: {"label": "Purity", "type": "dropdown"},
    KEY_STERILITY: {"label": "Sterility", "type": "dropdown"},
    KEY_SOLUBILITY: {"label": "Solubility", "type": "text", "placeholder": "Solubility details..."},
    KEY_TEMPERATURE_STABILITY: {"label": "Temperature Stability", "type": "dropdown"},
    KEY_LIGHT_SENSITIVITY: {"label": "Light Sensitivity", "type": "dropdown"},
    KEY_OXIDATION_SENSITIVITY: {"label": "Oxidation Sensitivity", "type": "dropdown"},

    # --- Chemical - BioProducts ---
    KEY_ORIGIN: {"label": "Origin", "type": "dropdown"},
    KEY_PRODUCTION_PHASE: {"label": "Production Phase", "type": "dropdown"},
    KEY_LOCATION: {"label": "Location", "type": "dropdown"},
    KEY_TOXICITY_TO_PRODUCER: {"label": "Toxicity to Producer", "type": "dropdown"},

    # --- Chemical - Dispersion ---
    KEY_SOLVENT: {
        "label": "Solvent",
        "type": "single_chemical",
        "placeholder": "Add solvent...",
        "for_solvent": True,
    },

    # --- Chemical - PorousMaterial ---
    KEY_3D_STRUCTURE: {"label": "3D Structure", "type": "text", "placeholder": "Crystal structure..."},
    KEY_CRYSTALLINITY: {"label": "Crystallinity", "type": "unit", "units": ["%"], "defaults": ["0"], "placeholder": "Crystal phase %..."},
    KEY_N2_ADSORPTION_BET_AREA: {"label": "N2 Adsorption BET Area", "type": "unit", "units": ["m²/g"], "defaults": ["0"], "placeholder": "Surface area..."},
    KEY_N2_ADSORPTION_MICROPORE_AREA: {"label": "N2 Micropore Area", "type": "unit", "units": ["m²/g"], "defaults": ["0"], "placeholder": "Micropore area..."},
    KEY_N2_ADSORPTION_MESOPORE_AREA: {"label": "N2 Mesopore Area", "type": "unit", "units": ["m²/g"], "defaults": ["0"], "placeholder": "Mesopore area..."},
    KEY_N2_ADSORPTION_TOTAL_VOLUME: {"label": "N2 Total Volume", "type": "unit", "units": ["cm³/g"], "defaults": ["0"], "placeholder": "Total adsorbed volume..."},
    KEY_N2_ADSORPTION_MICROPORE_VOLUME: {"label": "N2 Micropore Volume", "type": "unit", "units": ["cm³/g"], "defaults": ["0"], "placeholder": "Micropore volume..."},
    KEY_N2_MESOPORE_VOLUME: {"label": "N2 Mesopore Volume", "type": "unit", "units": ["cm³/g"], "defaults": ["0"], "placeholder": "Mesopore volume..."},
    KEY_PY_B_150: {"label": "Py-B (150°C)", "type": "text", "placeholder": "Pyridine Bronsted 150°C..."},
    KEY_PY_B_450: {"label": "Py-B (450°C)", "type": "text", "placeholder": "Pyridine Bronsted 450°C..."},
    KEY_PY_L_150: {"label": "Py-L (150°C)", "type": "text", "placeholder": "Pyridine Lewis 150°C..."},
    KEY_PY_L_450: {"label": "Py-L (450°C)", "type": "text", "placeholder": "Pyridine Lewis 450°C..."},
}


# Historical names are editing hints, never declarations in the current model.
LEGACY_FIELD_KEYS = frozenset({
    KEY_ADD_QUANTITY, KEY_MIN_SIZE, KEY_MAX_SIZE, KEY_GASES, KEY_SUBSTANCE,
    KEY_SUBSTANCE_LIST, KEY_CIF, KEY_ENTITY_TYPE, KEY_MIXTURE_TYPE, KEY_SOLVENT,
    KEY_ATOMIC_COMP, KEY_STRUCT_DESC, KEY_TEXTURAL_DESC, KEY_CHEM_DESC,
    KEY_MAT_LIST, KEY_BASE_MAT, KEY_BASE_COMPLEX, KEY_3D_STRUCTURE,
})
LEGACY_FIELD_PREFERENCES = {key: UI_FIELD_PREFERENCES.pop(key)
                            for key in LEGACY_FIELD_KEYS if key in UI_FIELD_PREFERENCES}

from .model import chemical_fields

CHEMICAL_ENTITY_FIELD_KEYS = chemical_fields()
# Canvas attachment is a GUI rule, distinct from LinkML required fields.
ACTIONS_REQUIRING_ATTACHED_CHEMICAL = frozenset({"Add"})

# Deliberate UI labels/order, not an enumeration of all model classes.
ACTION_BUTTON_LABELS = {
    "Add": "+ Add", "Grind": "🔨 Grind", "Separate": "⚗ Separate",
    "NoAction": "⏳ No Modification", "ChangeContainer": "🧪 Change Container",
    "ChangePressure": "☁ Change Pressure", "ChangeTemperature": "🌡 Change Temperature",
    "ChangeAgitation": "🔄 Change Agitation", "Repeat": "🔁 Repeat",
    "ContinuousAddition": "➕ Continuous Addition",
}


def is_chemical_entity_field(field_key, class_name=None) -> bool:
    return field_key in (chemical_fields(class_name) if class_name else CHEMICAL_ENTITY_FIELD_KEYS)


def action_requires_attached_chemical(action_name, *, part_of_complex_action=False) -> bool:
    """Canvas-linked chemical entities are required except inside a complex action."""
    if part_of_complex_action:
        return False
    return canonical_action_name(action_name) in ACTIONS_REQUIRING_ATTACHED_CHEMICAL


def is_field_required(field_key, params=None, action_name=None):
    """Only the class-scoped LinkML contract defines model requirements."""
    from .model import field_contract
    return bool(field_contract(str(field_key).lower(), action_name).get("required"))



ACTION_NAME_ALIASES = {
    "Wait": "NoAction", "NoModification": "NoAction",
    "ChangeAtmosphere": "ChangePressure", "NewRecipient": "ChangeContainer",
    "ChangeRecipient": "ChangeContainer", "SubProductCreation": "CollectSubProduct",
    "Sieve": "Separate",
}
CHEMICAL_NAME_ALIASES = {
    "Media": "Medium", "MixtureChemical": "MixtureConstituent",
    "MixtureSubstance": "MixtureConstituent", "Molecules": "Molecule",
    "Polymers": "Polymer", "HeterogeneousCatalysts": "PorousMaterial",
    "Material": "Substance", "PerfectSingleCrystalMaterial": "Molecule",
}


def canonical_action_name(name):
    return ACTION_NAME_ALIASES.get(str(name), str(name)) if name else name


def canonical_chemical_name(name):
    return CHEMICAL_NAME_ALIASES.get(str(name), str(name)) if name else name


def migrate_action_params(action_name, params=None):
    """Perform lossless structural migrations; missing information stays missing."""
    action_name = canonical_action_name(action_name)
    data = dict(params or {})
    if action_name == "Separate":
        method = data.get(KEY_METHOD)
        if not method and any(k in data for k in (KEY_SIZE_RANGE, KEY_MIN_SIZE, KEY_MAX_SIZE)):
            method = {"type": "Sieving"}
        if isinstance(method, str) and method.strip():
            method = {"type": "Sieving" if method == "Sieve" else method}
        if isinstance(method, dict):
            method = dict(method)
            for key in (KEY_PHASE, KEY_SIZE_RANGE, "filter_pore_size", KEY_SPEED):
                if key in data:
                    method.setdefault(key, data.pop(key))
            sizes = [str(data.pop(k)) for k in (KEY_MIN_SIZE, KEY_MAX_SIZE) if data.get(k)]
            if sizes:
                method.setdefault(KEY_SIZE_RANGE, " - ".join(sizes))
            data[KEY_METHOD] = method
    if action_name == "ContinuousAddition" and KEY_SUBSTANCE_LIST in data:
        old = data.pop(KEY_SUBSTANCE_LIST)
        if data.get(KEY_CHEMICAL) and old and data[KEY_CHEMICAL] != old:
            raise ValueError("Conflicting chemical and substance_list values; review this action before migration.")
        data.setdefault(KEY_CHEMICAL, [] if old is None or old == "" else old)
    return data


def migrate_chemical_params(chemical_name, params=None):
    """Preserve unrepresentable legacy fields for review instead of dropping them."""
    data = dict(params or {})
    for key in ("chemical_type", "type"):
        if key in data:
            data[key] = canonical_chemical_name(data[key])
    for key, value in list(data.items()):
        if isinstance(value, list):
            data[key] = [migrate_chemical_params(item.get("chemical_type") or item.get("type"), item)
                         if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict) and key != KEY_PREPARATION_PROCEDURE:
            data[key] = migrate_chemical_params(value.get("chemical_type") or value.get("type"), value)
    return data


def validate_schema_references(schema=None):
    """Report stale application/presentation bindings without inventing aliases."""
    view = schema_view(schema)
    slots = set(view.all_slots())
    classes = set(view.all_classes())
    errors = [f"Obsolete slot reference: {name}" for name in sorted(_SCHEMA_SLOT_REFERENCES - slots)]
    errors.extend(f"Obsolete presentation field: {name}" for name in sorted(set(UI_FIELD_PREFERENCES) - slots))
    targets = set(ACTION_NAME_ALIASES.values()) | set(CHEMICAL_NAME_ALIASES.values()) | set(ACTIONS_REQUIRING_ATTACHED_CHEMICAL) | set(ACTION_BUTTON_LABELS)
    # Application behaviours require these model families; they are integration
    # anchors, not a second enumeration of every model class.
    targets.update({"Action", "OneOffAction", "PersistentAction", "ChemicalEntity", "MixtureConstituent", "CollectSubProduct"})
    errors.extend(f"Obsolete class reference: {name}" for name in sorted(targets - classes))
    for key, preferences in UI_FIELD_PREFERENCES.items():
        for cls in preferences.get('labels_by_action', {}):
            if cls not in classes or key not in view.class_slots(cls):
                errors.append(f"Obsolete presentation binding: {cls}.{key}")
    return errors


# Compatibility view for context-free presentation consumers only. Class-bound
# editors must use field_config(key, class_name); this table is not a contract.
from .model import field_config as schema_field_config
FIELD_CONFIG = {str(slot): schema_field_config(str(slot)) for slot in schema_view().all_slots(attributes=False)}
