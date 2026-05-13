# config.py

# --- GLOBAL DEFAULTS ---
DEFAULT_PROTOCOL_NAME = "laboratory procedure"

# --- INTERNAL VARIABLE NAMES (KEYS) ---
KEY_DURATION = "duration"
KEY_TEMPERATURE = "temperature"
KEY_NAME = "name"
KEY_FORMULA = "formula"
KEY_SMILES = "smile"
KEY_STRUCTURE = "structure"
KEY_CHEMICAL = "chemical"
KEY_ADD_TYPE = "add_type"
KEY_OPEN_FLAME = "open_flame"
KEY_PHASE = "phase_to_keep"
KEY_METHOD = "method"
KEY_MIN_SIZE = "min_size"
KEY_MAX_SIZE = "max_size"
KEY_AGITATION_TYPE = "agitation_type"
KEY_SPEED = "speed"
KEY_GASES = "gases"
KEY_FLOW_RATE = "flow_rate"
KEY_PRESSURE = "pressure"
KEY_PROCESS = "process"
KEY_RAMP = "ramp"
KEY_POWER = "power"
KEY_RECIPIENT = "recipient"
KEY_MATERIAL = "material"
KEY_VOLUME = "volume"
KEY_MIXTURE_NAME = "mixture_name"
KEY_SUBSTANCE = "substance"
KEY_SUBSTANCE_LIST = "substance_list"
KEY_AMOUNT = "amount"
KEY_CONTINUOUS_ADD_TYPE = "continuous_add_type"
KEY_INCHI = "inchi"
KEY_BIGSMILES = "bigsmiles"
KEY_CIF = "cif"
KEY_QUANTITY = "quantity"
KEY_ATOMIC_COMP = "atomic_composition"
KEY_STRUCT_DESC = "structure_descriptor"
KEY_BASE_MAT = "base_material"
KEY_TEXTURAL_DESC = "textural_descriptors"
KEY_CHEM_DESC = "chemical_descriptors"
KEY_MAT_LIST = "materials_list"
KEY_BASE_COMPLEX = "base_complex_material"
KEY_FUNCTION = "function"
KEY_CONCENTRATION = "concentration"
KEY_PURITY = "purity"
KEY_STERILITY = "sterility"
KEY_SOLUBILITY = "solubility"
KEY_STATE = "state"
KEY_TEMPERATURE_STABILITY = "temperature_stability"
KEY_LIGHT_SENSITIVITY = "light_sensitivity"
KEY_OXIDATION_SENSITIVITY = "oxidation_sensitivity"
KEY_ORIGIN = "origin"
KEY_PRODUCTION_PHASE = "production_phase"
KEY_LOCATION = "location"
KEY_TOXICITY_TO_PRODUCER = "toxicity_to_producer"
KEY_ENTITY_PRIVACY = "entity_privacy"
KEY_ENTITY_ID = "entity_id"
KEY_PRODUCER = "entity_producer"
KEY_PRIVATE_PURITY = "entity_purity"

# --- UI CONFIGURATION ---
FIELD_CONFIG = {
    # unit fields
    KEY_DURATION: {"label": "Duration", "type": "unit", "units": ["s", "min", "h"], "defaults": ["0", "10", "30"], "placeholder": "Time", "required": True},
    KEY_TEMPERATURE: {"label": "Temperature", "type": "unit", "units": ["°C", "°F"], "defaults": ["50"], "placeholder": "Value", "required": True},
    KEY_MIN_SIZE: {"label": "Min Size", "type": "unit", "units": ["μm", "mm", "m"], "defaults": ["0"], "placeholder": "Size", "required": True},
    KEY_MAX_SIZE: {"label": "Max Size", "type": "unit", "units": ["μm", "mm", "m"], "defaults": ["0"], "placeholder": "Size", "required": True},
    KEY_SPEED: {"label": "Speed", "type": "unit", "units": ["rpm"], "defaults": ["0"], "placeholder": "Velocity", "required": False},
    KEY_FLOW_RATE: {"label": "Flow Rate", "type": "unit", "units": ["mL/min", "L/h"], "defaults": ["0"], "placeholder": "Rate", "required": True},
    KEY_PRESSURE: {"label": "Pressure", "type": "unit", "units": ["bar", "atm", "Pa", "kPa"], "defaults": ["1"], "placeholder": "Pressure", "required": True},
    KEY_RAMP: {"label": "Ramp", "type": "unit", "units": ["°C/min", "K/min"], "defaults": ["0"], "placeholder": "Slope", "required": False},
    KEY_POWER: {"label": "Power", "type": "unit", "units": ["W", "kW"], "defaults": ["0"], "placeholder": "Power", "required": False},
    KEY_VOLUME: {"label": "Volume", "type": "unit", "units": ["μL", "mL", "L"], "defaults": ["0"], "placeholder": "Volume", "required": True},
    KEY_QUANTITY: {"label": "Quantity", "type": "unit", "units": ["mg", "g", "kg", "mL", "L", "mol", "mmol"], "defaults": ["0"], "placeholder": "Amount", "required": True},
    KEY_CONCENTRATION: {"label": "Concentration", "type": "unit", "units": ["g/L", "mM", "% (w/v)", "% (v/v)"], "defaults": ["0"], "placeholder": "Value", "required": False},

    # dropdown fields
    KEY_ADD_TYPE: {"label": "Add Type", "type": "dropdown", "options": ["Normal", "Dropwise", "Diffusion"], "required": True},
    KEY_OPEN_FLAME: {"label": "Open Flame", "type": "dropdown", "options": ["True", "False"], "required": True},
    KEY_CONTINUOUS_ADD_TYPE: {"label": "Type", "type": "dropdown", "options": ["Continuous", "Intermittent"], "required": True},
    KEY_AGITATION_TYPE: {"label": "Type", "type": "dropdown", "options": ["Manual", "Automatic", "None"], "required": True},
    KEY_PHASE: {"label": "Phase to Keep", "type": "dropdown", "options": ["Liquid", "Solid", "Aqueous", "Organic"], "required": True},
    KEY_METHOD: {"label": "Method", "type": "dropdown", "options": ["Filtration", "Centrifugation", "Decantation"], "required": True},
    KEY_PROCESS: {"label": "Process", "type": "dropdown", "options": ["Electrical", "Microwave", "Ice-bath", "Atmospheric"], "required": True},
    KEY_RECIPIENT: {"label": "Recipient", "type": "dropdown", "options": ["Beaker", "Flask", "Autoclave"], "required": True},
    KEY_MATERIAL: {"label": "Material", "type": "dropdown", "options": ["Glass", "Plastic", "Ceramic"], "required": True},
    KEY_FUNCTION: {"label": "Function", "type": "dropdown", "options": ["Carbon Source", "Nitrogen Source", "Mineral", "Vitamin", "Growth Factor", "Inducer", "Precursor"], "required": False},
    KEY_STATE: {"label": "State", "type": "dropdown", "options": ["Liquid", "Solid", "Gas"], "required": False},
    KEY_PURITY: {"label": "Purity", "type": "dropdown", "options": ["technical", "reagent", "analytical", "molecular biology", "cell culture grade"], "required": False},
    KEY_STERILITY: {"label": "Sterility", "type": "dropdown", "options": ["sterile", "non-sterile", "filter-sterilized", "autoclavable"], "required": False},
    KEY_ORIGIN: {"label": "Origin", "type": "dropdown", "options": ["primary metabolite", "secondary metabolite", "recombinant protein"], "required": False},
    KEY_PRODUCTION_PHASE: {"label": "Production Phase", "type": "dropdown", "options": ["associated to growth", "not associated to growth", "mixed"], "required": False},
    KEY_LOCATION: {"label": "Location", "type": "dropdown", "options": ["intracellular", "extracellular", "membrane bound"], "required": False},
    KEY_TEMPERATURE_STABILITY: {"label": "Temperature Stability", "type": "dropdown", "options": ["stable", "sensitive"], "required": False},
    KEY_LIGHT_SENSITIVITY: {"label": "Light Sensitivity", "type": "dropdown", "options": ["yes", "no"], "required": False},
    KEY_OXIDATION_SENSITIVITY: {"label": "Oxidation Sensitivity", "type": "dropdown", "options": ["yes", "no"], "required": False},
    KEY_TOXICITY_TO_PRODUCER: {"label": "Toxicity to Producer", "type": "dropdown", "options": ["inhibitory", "toxic", "neutral"], "required": True},
    KEY_ENTITY_PRIVACY: {"label": "Entity Type", "type": "dropdown", "options": ["Open Entity", "Private Entity"], "required": True},

    # text fields
    KEY_NAME: {"label": "Name", "type": "text", "placeholder": "Entity name...", "required": True},
    KEY_FORMULA: {"label": "Formula", "type": "text", "placeholder": "Chemical formula...", "required": True},
    KEY_SMILES: {"label": "SMILE", "type": "text", "placeholder": "SMILE string...", "required": True},
    KEY_BIGSMILES: {"label": "BigSMILES", "type": "text", "placeholder": "BigSMILES string...", "required": True},
    KEY_INCHI: {"label": "InChi", "type": "text", "placeholder": "InChi string...", "required": False},
    KEY_CIF: {"label": "CIF", "type": "text", "placeholder": "Crystallographic Information File...", "required": True},
    KEY_ATOMIC_COMP: {"label": "Atomic Comp.", "type": "text", "placeholder": "Atoms and % m/m...", "required": True},
    KEY_STRUCT_DESC: {"label": "Structure Desc.", "type": "text", "placeholder": "Structure description...", "required": True},
    KEY_TEXTURAL_DESC: {"label": "Textural Desc.", "type": "text", "placeholder": "Textural properties...", "required": True},
    KEY_CHEM_DESC: {"label": "Chem Desc.", "type": "text", "placeholder": "Chemical descriptors...", "required": True},
    KEY_MAT_LIST: {"label": "Materials List", "type": "text", "placeholder": "List of materials...", "required": True},
    KEY_BASE_MAT: {"label": "Base Material", "type": "text", "placeholder": "Base entity name...", "required": True},
    KEY_BASE_COMPLEX: {"label": "Base Complex", "type": "text", "placeholder": "Base complex entity...", "required": True},
    KEY_CHEMICAL: {"label": "Chemical", "type": "text", "placeholder": "Chemical entity name...", "required": True},
    KEY_SUBSTANCE_LIST: {"label": "Substance List", "type": "text", "placeholder": "List of chemical entities...", "required": True},
    KEY_GASES: {"label": "Gases", "type": "text", "placeholder": "List of gases...", "required": True},
    KEY_SOLUBILITY: {"label": "Solubility", "type": "text", "placeholder": "Solubility details...", "required": False},
    KEY_ENTITY_ID: {"label": "ID", "type": "text", "placeholder": "Commercial or internal ID...", "required": True},
    KEY_PRODUCER: {"label": "Producer", "type": "text", "placeholder": "Institution that created the entity...", "required": True},
    KEY_PRIVATE_PURITY: {"label": "Purity", "type": "text", "placeholder": "Degree of purity...", "required": False},
    KEY_SUBSTANCE: {"label": "Substance", "type": "text", "placeholder": "Chemical entity...", "required": True},
    KEY_MIXTURE_NAME: {"label": "Mixture Name", "type": "text", "placeholder": "Name of the mixture...", "required": True},
    KEY_AMOUNT: {
        "label": "Amount",
        "type": "text",
        "placeholder": "Number of times...",
        "required": False,
        "required_if": [
            {"action": "Repeat"},
            {"action": "ContinuousAddition", "param": KEY_CONTINUOUS_ADD_TYPE, "equals": "Intermittent"}
        ]
    },
}


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