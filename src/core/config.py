# config.py

# --- GLOBAL DEFAULTS ---
DEFAULT_PROTOCOL_NAME = "laboratory procedure"

# --- FEATURE FLAGS ---
ENABLE_VERTICAL_ORIENTATION_TOGGLE = False

# Support influences that cannot be toggled off on elementary actions (e.g. Change Recipient)
LOCKED_INFLUENCE_ACTIONS = frozenset({"ChangeRecipient"})

# --- PARAM KEYS ---

# Actions - shared
KEY_DURATION = "duration"
KEY_AMOUNT = "amount"

# Actions - Add
KEY_ADD_TYPE = "add_type"
KEY_ADD_QUANTITY = "add_quantity"
KEY_OPEN_FLAME = "open_flame"

# Actions - Separate
KEY_PHASE = "phase_to_keep"
KEY_METHOD = "method"

# Actions - Sieve
KEY_SIZE_RANGE = "size_range"
KEY_MIN_SIZE = "min_size"  # legacy load alias
KEY_MAX_SIZE = "max_size"  # legacy load alias

# Actions - ChangePressure / ContinuousAddition
KEY_GASES = "gases"  # legacy load alias
KEY_FLOW_RATE = "flow_rate"
KEY_PRESSURE = "pressure"

# Actions - ChangeTemperature
KEY_TEMPERATURE = "temperature"
KEY_PROCESS = "process"
KEY_RAMP = "ramp"
KEY_POWER = "power"

# Actions - ChangeRecipient
KEY_RECIPIENT = "recipient"
KEY_MATERIAL = "material"
KEY_VOLUME = "volume"

# Actions - ChangeAgitation
KEY_AGITATION_TYPE = "agitation_type"
KEY_SPEED = "speed"

# Actions - CollectSubProduct
KEY_SUBSTANCE = "substance"

# Actions - ContinuousAddition
KEY_CONTINUOUS_ADD_TYPE = "continuous_add_type"
KEY_SUBSTANCE_LIST = "substance_list"

# Actions - attached material
KEY_CHEMICAL = "chemical"

# First level
KEY_PREPARATION_PROCEDURE = "preparation_procedure"
KEY_ENTITY_ID = "entity_id"
KEY_PRODUCER = "entity_producer"
KEY_ENTITY_PURITY = "entity_purity"
KEY_CAS_NUMBER = "cas_number"

# Chemical - shared
KEY_NAME = "name"
KEY_FORMULA = "formula"
KEY_SMILES = "smile"
KEY_INCHI = "inchi"
KEY_BIGSMILES = "bigsmiles"
KEY_CIF = "cif"
KEY_QUANTITY = "quantity"
KEY_CONCENTRATION = "concentration"

# Chemical - Mixture
KEY_ENTITY_TYPE = "entity_type"
KEY_MIXTURE_TYPE = "mixture_type"
KEY_CHEMICAL_LIST = "chemical_list"

# Chemical - Medium
KEY_FUNCTION = "function"
KEY_STATE = "state"
KEY_PURITY = "purity"
KEY_STERILITY = "sterility"
KEY_SOLUBILITY = "solubility"
KEY_TEMPERATURE_STABILITY = "temperature_stability"
KEY_LIGHT_SENSITIVITY = "light_sensitivity"
KEY_OXIDATION_SENSITIVITY = "oxidation_sensitivity"

# Chemical - BioProducts
KEY_ORIGIN = "origin"
KEY_PRODUCTION_PHASE = "production_phase"
KEY_LOCATION = "location"
KEY_TOXICITY_TO_PRODUCER = "toxicity_to_producer"

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

# Chemical - HeterogeneousCatalysts
KEY_3D_STRUCTURE = "3d_structure"
KEY_CRYSTALLINITY = "crystallinity"
KEY_N2_ADSORPTION_BET_AREA = "n2_adsorption_bet_area"
KEY_N2_ADSORPTION_MICROPORE_AREA = "n2_adsorption_micropore_area"
KEY_N2_ADSORPTION_MESOPORE_AREA = "n2_adsorption_mesopore_area"
KEY_N2_ADSORPTION_TOTAL_VOLUME = "n2_adsorption_total_volume"
KEY_N2_ADSORPTION_MICROPORE_VOLUME = "n2_adsorption_micropore_volume"
KEY_N2_MESOPORE_VOLUME = "n2_mesopore_volume"
KEY_PY_B_150 = "py_b_150"
KEY_PY_B_450 = "py_b_450"
KEY_PY_L_150 = "py_l_150"
KEY_PY_L_450 = "py_l_450"

# --- UI CONFIGURATION ---
FIELD_CONFIG = {
    # --- Actions - shared ---
    KEY_DURATION: {
        "label": "Duration",
        "type": "unit",
        "units": ["s", "min", "h"],
        "defaults": ["0", "10", "30"],
        "placeholder": "Time",
        "required": False,
        "required_if": [{"action": "Add"}, {"action": "NoModification"}],
    },
    KEY_AMOUNT: {
        "label": "Amount",
        "type": "text",
        "placeholder": "Number of times...",
        "required": False,
        "required_if": [{"action": "Repeat"}, {"action": "ContinuousAddition"}],
        "integer": True,
        "minimum": 1,
    },

    # --- Add ---
    KEY_ADD_QUANTITY: {"label": "Quantity", "type": "unit", "units": ["g", "ml", "L", "uL", "mg"], "defaults": ["0"], "placeholder": "Amount", "required": True},
    KEY_ADD_TYPE: {"label": "Type", "type": "dropdown", "options": ["Normal", "Dropwise", "Diffusion"], "required": True},
    KEY_OPEN_FLAME: {"label": "Open Flame", "type": "dropdown", "options": ["True", "False"], "required": True},
    KEY_CHEMICAL: {"label": "Chemical", "type": "text", "placeholder": "Chemical entity name...", "required": True},

    # --- Separate ---
    KEY_PHASE: {"label": "Phase to Keep", "type": "dropdown", "options": ["Liquid", "Solid", "Aqueous", "Organic"], "required": True},
    KEY_METHOD: {"label": "Method", "type": "dropdown", "options": ["Filtration", "Centrifugation", "Decantation"], "required": True},

    # --- Sieve ---
    KEY_SIZE_RANGE: {"label": "Size Range", "type": "text", "placeholder": "Particle size range...", "required": True},

    # --- ChangePressure / ContinuousAddition ---
    KEY_FLOW_RATE: {"label": "Flow Rate", "type": "unit", "units": ["mL/min", "L/h"], "defaults": ["0"], "placeholder": "Rate", "required": True},
    KEY_PRESSURE: {"label": "Pressure", "type": "unit", "units": ["bar", "atm", "Pa", "kPa"], "defaults": ["101.325"], "placeholder": "Pressure", "required": True},

    # --- ChangeTemperature ---
    KEY_TEMPERATURE: {"label": "Temperature", "type": "unit", "units": ["°C", "°F"], "defaults": ["50"], "placeholder": "Value", "required": True},
    KEY_PROCESS: {"label": "Process", "type": "dropdown", "options": ["Electrical", "Microwave", "Ice-bath", "Atmospheric"], "required": True},
    KEY_RAMP: {"label": "Ramp", "type": "unit", "units": ["°C/min", "K/min"], "defaults": ["0"], "placeholder": "Slope", "required": False},
    KEY_POWER: {"label": "Power", "type": "unit", "units": ["W", "kW"], "defaults": ["0"], "placeholder": "Power", "required": False},

    # --- ChangeRecipient ---
    KEY_RECIPIENT: {"label": "Recipient", "type": "dropdown", "options": ["Beaker", "Flask", "Autoclave"], "required": True},
    KEY_MATERIAL: {"label": "Material", "type": "dropdown", "options": ["Glass", "Plastic", "Ceramic"], "required": True},
    KEY_VOLUME: {"label": "Volume", "type": "unit", "units": ["μL", "mL", "L"], "defaults": ["0"], "placeholder": "Volume", "required": True},

    # --- ChangeAgitation ---
    KEY_AGITATION_TYPE: {"label": "Type", "type": "dropdown", "options": ["Manual", "Magnetic", "Mechanical", "Rotative", "None"], "required": True},
    KEY_SPEED: {"label": "Speed", "type": "unit", "units": ["rpm"], "defaults": ["0"], "placeholder": "Velocity", "required": False},

    # --- CollectSubProduct ---
    KEY_SUBSTANCE: {"label": "Substance", "type": "text", "placeholder": "Chemical entity...", "required": True},

    # --- ContinuousAddition ---
    KEY_CONTINUOUS_ADD_TYPE: {"label": "Type", "type": "dropdown", "options": ["Continuous", "Intermittent"], "required": True},
    KEY_SUBSTANCE_LIST: {
        "label": "Substance List",
        "type": "list",
        "placeholder": "Add chemical entities...",
        "required": True,
        "include_concentration": False,
    },

    # --- First level ---
    KEY_PREPARATION_PROCEDURE: {"label": "Preparation Procedure", "type": "text", "placeholder": "Description of preparation...", "required": False},
    KEY_ENTITY_ID: {"label": "ID", "type": "text", "placeholder": "Commercial or internal ID...", "required": False},
    KEY_PRODUCER: {"label": "Producer", "type": "text", "placeholder": "Institution that created the entity...", "required": False},
    KEY_ENTITY_PURITY: {"label": "Purity", "type": "text", "placeholder": "Degree of purity...", "required": False},
    KEY_CAS_NUMBER: {"label": "CAS Number", "type": "text", "placeholder": "Commercial identification number...", "required": False},

    # --- Chemical - shared ---
    KEY_NAME: {"label": "Name", "type": "text", "placeholder": "Entity or mixture name...", "required": True},
    KEY_FORMULA: {
        "label": "Formula",
        "labels_by_action": {"HeterogeneousCatalysts": "Chemical Formula"},
        "type": "text",
        "placeholder": "Chemical formula...",
        "required": False,
        "required_if": [{"action": "Molecules"}, {"action": "Polymers"}],
    },
    KEY_SMILES: {"label": "SMILE", "type": "text", "placeholder": "SMILE string...", "required": True},
    KEY_BIGSMILES: {"label": "BigSMILES", "type": "text", "placeholder": "BigSMILES string...", "required": True},
    KEY_INCHI: {"label": "InChi", "type": "text", "placeholder": "InChi string...", "required": False},
    KEY_QUANTITY: {"label": "Quantity", "type": "unit", "units": ["mg", "g", "kg", "mL", "L", "mol", "mmol"], "defaults": ["0"], "placeholder": "Amount", "required": True},
    KEY_CONCENTRATION: {
        "label": "Concentration",
        "type": "unit",
        "units": ["m/m", "vol/vol", "M", "g/L"],
        "defaults": ["0"],
        "placeholder": "Value",
        "required": False,
        "required_if": [{"action": "MixtureSubstance"}],
    },

    # --- Chemical - Mixture ---
    KEY_CHEMICAL_LIST: {
        "label": "Chemical List",
        "labels_by_action": {"Dispersion": "Substance"},
        "type": "list",
        "placeholder": "Manage chemicals...",
        "required": False,
        "include_concentration": True,
        "required_if": [
            {"action": "Mixture"},
            {"action": "Dispersion"},
            {"action": "Medium"},
        ],
    },

    # --- Chemical - Medium ---
    KEY_FUNCTION: {"label": "Function", "type": "dropdown", "options": ["Carbon Source", "Nitrogen Source", "Mineral", "Vitamin", "Growth Factor", "Inducer", "Precursor"], "required": False},
    KEY_STATE: {"label": "State", "type": "dropdown", "options": ["solid", "liquid", "semi-solid", "lyophilized", "frozen"], "required": False},
    KEY_PURITY: {"label": "Purity", "type": "dropdown", "options": ["technical", "reagent", "analytical", "molecular biology", "cell culture grade"], "required": False},
    KEY_STERILITY: {"label": "Sterility", "type": "dropdown", "options": ["sterile", "non-sterile", "filter-sterilized", "autoclavable"], "required": False},
    KEY_SOLUBILITY: {"label": "Solubility", "type": "text", "placeholder": "Solubility details...", "required": False},
    KEY_TEMPERATURE_STABILITY: {"label": "Temperature Stability", "type": "dropdown", "options": ["thermostable", "heat stable", "moderately stable", "heat labile", "very heat labile", "cryogenic storage required"], "required": False},
    KEY_LIGHT_SENSITIVITY: {"label": "Light Sensitivity", "type": "dropdown", "options": ["yes", "no"], "required": False},
    KEY_OXIDATION_SENSITIVITY: {"label": "Oxidation Sensitivity", "type": "dropdown", "options": ["oxidation stable", "oxidation sensitive", "highly oxidation sensitive", "oxygen reactive"], "required": False},

    # --- Chemical - BioProducts ---
    KEY_ORIGIN: {"label": "Origin", "type": "dropdown", "options": ["primary metabolite", "secondary metabolite", "recombinant protein"], "required": False},
    KEY_PRODUCTION_PHASE: {"label": "Production Phase", "type": "dropdown", "options": ["associated to growth", "not associated to growth", "mixed"], "required": False},
    KEY_LOCATION: {"label": "Location", "type": "dropdown", "options": ["intracellular", "extracellular", "membrane bound"], "required": False},
    KEY_TOXICITY_TO_PRODUCER: {"label": "Toxicity to Producer", "type": "dropdown", "options": ["inhibitory", "toxic", "neutral"], "required": True},

    # --- Chemical - Dispersion ---
    KEY_SOLVENT: {
        "label": "Solvent",
        "type": "single_chemical",
        "placeholder": "Add solvent...",
        "for_solvent": True,
        "required": False,
        "required_if": [{"action": "Dispersion"}],
    },

    # --- Chemical - HeterogeneousCatalysts ---
    KEY_3D_STRUCTURE: {"label": "3D Structure", "type": "text", "placeholder": "Crystal structure...", "required": False},
    KEY_CRYSTALLINITY: {"label": "Crystallinity", "type": "unit", "units": ["%"], "defaults": ["0"], "placeholder": "Crystal phase %...", "required": False},
    KEY_N2_ADSORPTION_BET_AREA: {"label": "N2 Adsorption BET Area", "type": "unit", "units": ["m²/g"], "defaults": ["0"], "placeholder": "Surface area...", "required": False},
    KEY_N2_ADSORPTION_MICROPORE_AREA: {"label": "N2 Micropore Area", "type": "unit", "units": ["m²/g"], "defaults": ["0"], "placeholder": "Micropore area...", "required": False},
    KEY_N2_ADSORPTION_MESOPORE_AREA: {"label": "N2 Mesopore Area", "type": "unit", "units": ["m²/g"], "defaults": ["0"], "placeholder": "Mesopore area...", "required": False},
    KEY_N2_ADSORPTION_TOTAL_VOLUME: {"label": "N2 Total Volume", "type": "unit", "units": ["cm³/g"], "defaults": ["0"], "placeholder": "Total adsorbed volume...", "required": False},
    KEY_N2_ADSORPTION_MICROPORE_VOLUME: {"label": "N2 Micropore Volume", "type": "unit", "units": ["cm³/g"], "defaults": ["0"], "placeholder": "Micropore volume...", "required": False},
    KEY_N2_MESOPORE_VOLUME: {"label": "N2 Mesopore Volume", "type": "unit", "units": ["cm³/g"], "defaults": ["0"], "placeholder": "Mesopore volume...", "required": False},
    KEY_PY_B_150: {"label": "Py-B (150°C)", "type": "text", "placeholder": "Pyridine Bronsted 150°C...", "required": False},
    KEY_PY_B_450: {"label": "Py-B (450°C)", "type": "text", "placeholder": "Pyridine Bronsted 450°C...", "required": False},
    KEY_PY_L_150: {"label": "Py-L (150°C)", "type": "text", "placeholder": "Pyridine Lewis 150°C...", "required": False},
    KEY_PY_L_450: {"label": "Py-L (450°C)", "type": "text", "placeholder": "Pyridine Lewis 450°C...", "required": False},
}


CHEMICAL_ENTITY_FIELD_KEYS = frozenset(
    {
        KEY_CHEMICAL,
        KEY_SUBSTANCE,
        KEY_SUBSTANCE_LIST,
        KEY_CHEMICAL_LIST,
        KEY_SOLVENT,
    }
)
ACTIONS_REQUIRING_ATTACHED_CHEMICAL = frozenset({"Add", "CollectSubProduct"})


def is_chemical_entity_field(field_key) -> bool:
    """True for fields whose value is a chemical entity or list of entities."""
    return str(field_key or "").lower() in CHEMICAL_ENTITY_FIELD_KEYS


def action_requires_attached_chemical(action_name, *, part_of_complex_action=False) -> bool:
    """Canvas-linked chemical entities are required except inside a complex action."""
    if part_of_complex_action:
        return False
    return canonical_action_name(action_name) in ACTIONS_REQUIRING_ATTACHED_CHEMICAL


def is_field_required(field_key, params=None, action_name=None):
    """Return whether a field is required, including conditional rules."""
    config = FIELD_CONFIG.get(str(field_key).lower(), {})
    required = config.get("required", True)

    for rule in config.get("required_if", []):
        if action_name and rule.get("action") and rule.get("action") != action_name:
            continue
        if rule.get("param"):
            if not params:
                continue
            if params.get(rule["param"]) != rule.get("equals"):
                continue
        required = True
        break

    return required


ACTION_NAME_ALIASES = {
    "Wait": "NoModification",
    "ChangeAtmosphere": "ChangePressure",
    "NewRecipient": "ChangeRecipient",
    "SubProductCreation": "CollectSubProduct",
}

CHEMICAL_NAME_ALIASES = {
    "Media": "Medium",
    "MixtureChemical": "MixtureSubstance",
    "Material": "Substance",
    "PerfectSingleCrystalMaterial": "Molecules",
}


def canonical_action_name(name):
    """Map legacy action names to the current Action Data Model names."""
    if not name:
        return name
    return ACTION_NAME_ALIASES.get(str(name), str(name))


def canonical_chemical_name(name):
    """Map legacy chemical entity names to the current Action Data Model names."""
    if not name:
        return name
    return CHEMICAL_NAME_ALIASES.get(str(name), str(name))


def migrate_action_params(action_name, params=None):
    """Normalize stored action params to the current Action Data Model fields."""
    action_name = canonical_action_name(action_name)
    data = dict(params or {})
    if action_name == "Sieve":
        if not str(data.get(KEY_SIZE_RANGE) or "").strip():
            min_size = str(data.get(KEY_MIN_SIZE) or "").strip()
            max_size = str(data.get(KEY_MAX_SIZE) or "").strip()
            if min_size or max_size:
                data[KEY_SIZE_RANGE] = " - ".join(part for part in (min_size, max_size) if part)
        data.pop(KEY_MIN_SIZE, None)
        data.pop(KEY_MAX_SIZE, None)
    elif action_name == "ChangePressure":
        data.pop(KEY_GASES, None)
        data.pop(KEY_FLOW_RATE, None)
        data.setdefault(KEY_PRESSURE, data.get(KEY_PRESSURE) or "101.325 kPa")
    elif action_name == "ContinuousAddition":
        data.setdefault(KEY_FLOW_RATE, "0 mL/min")
        substances = data.get(KEY_SUBSTANCE_LIST)
        if not isinstance(substances, list):
            if substances is None or (isinstance(substances, str) and not str(substances).strip()):
                data[KEY_SUBSTANCE_LIST] = []
    return data


def migrate_chemical_params(chemical_name, params=None):
    """Normalize stored chemical params to the current Action Data Model fields."""
    chemical_name = canonical_chemical_name(chemical_name)
    data = dict(params or {})
    if chemical_name in {
        "Medium",
        "Dispersion",
        "BioProducts",
        "HeterogeneousCatalysts",
        "Molecules",
        "Polymers",
        "Substance",
        "Mixture",
    }:
        data.pop(KEY_ENTITY_TYPE, None)
    if chemical_name == "BioProducts":
        data.pop(KEY_CHEMICAL_LIST, None)
    if chemical_name == "HeterogeneousCatalysts":
        data.pop(KEY_NAME, None)
        data.pop(KEY_CHEMICAL_LIST, None)
    nested = data.get("chemical_type")
    if nested:
        data["chemical_type"] = canonical_chemical_name(nested)
    nested_list = data.get(KEY_CHEMICAL_LIST)
    if isinstance(nested_list, list):
        migrated_list = []
        for item in nested_list:
            if not isinstance(item, dict):
                migrated_list.append(item)
                continue
            nested_item = dict(item)
            nested_type = nested_item.get("chemical_type")
            if nested_type:
                nested_item["chemical_type"] = canonical_chemical_name(nested_type)
            migrated_list.append(nested_item)
        data[KEY_CHEMICAL_LIST] = migrated_list
    return data


