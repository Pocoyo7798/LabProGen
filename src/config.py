# config.py

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
KEY_STIR_TYPE = "stir_type"
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
    KEY_DURATION: {"label": "Duration", "type": "unit", "units": ["s", "min", "h"], "defaults": ["0", "10", "30"], "placeholder": "Time"},
    KEY_TEMPERATURE: {"label": "Temperature", "type": "unit", "units": ["°C", "°F"], "defaults": ["50"], "placeholder": "Value"},
    KEY_MIN_SIZE: {"label": "Min Size", "type": "unit", "units": ["μm", "mm", "m"], "defaults": ["0"], "placeholder": "Size"},
    KEY_MAX_SIZE: {"label": "Max Size", "type": "unit", "units": ["μm", "mm", "m"], "defaults": ["0"], "placeholder": "Size"},
    KEY_SPEED: {"label": "Speed", "type": "unit", "units": ["rpm"], "defaults": ["0"], "placeholder": "Velocity"},
    KEY_FLOW_RATE: {"label": "Flow Rate", "type": "unit", "units": ["mL/min", "L/h"], "defaults": ["0"], "placeholder": "Rate"},
    KEY_PRESSURE: {"label": "Pressure", "type": "unit", "units": ["bar", "atm", "Pa", "kPa"], "defaults": ["1"], "placeholder": "Pressure"},
    KEY_RAMP: {"label": "Ramp", "type": "unit", "units": ["°C/min", "K/min"], "defaults": ["0"], "placeholder": "Slope"},
    KEY_POWER: {"label": "Power", "type": "unit", "units": ["W", "kW"], "defaults": ["0"], "placeholder": "Power"},
    KEY_VOLUME: {"label": "Volume", "type": "unit", "units": ["μL", "mL", "L"], "defaults": ["0"], "placeholder": "Volume"},
    KEY_QUANTITY: {"label": "Quantity", "type": "unit", "units": ["mg", "g", "kg", "mL", "L", "mol", "mmol"], "defaults": ["0"], "placeholder": "Amount"},
    KEY_CONCENTRATION: {"label": "Concentration", "type": "unit", "units": ["g/L", "mM", "% (w/v)", "% (v/v)"], "defaults": ["0"], "placeholder": "Value"},

    # dropdown fields
    KEY_ADD_TYPE: {"label": "Add Type", "type": "dropdown", "options": ["Normal", "Dropwise", "Diffusion"]},
    KEY_OPEN_FLAME: {"label": "Open Flame", "type": "dropdown", "options": ["True", "False"]},
    KEY_CONTINUOUS_ADD_TYPE: {"label": "Type", "type": "dropdown", "options": ["Continuous", "Intermittent"]},
    KEY_STIR_TYPE: {"label": "Stirring Type", "type": "dropdown", "options": ["Manual", "Automatic"]},
    KEY_PHASE: {"label": "Phase to Keep", "type": "dropdown", "options": ["Liquid", "Solid", "Aqueous", "Organic"]},
    KEY_METHOD: {"label": "Method", "type": "dropdown", "options": ["Filtration", "Centrifugation", "Decantation"]},
    KEY_PROCESS: {"label": "Process", "type": "dropdown", "options": ["Electrical", "Microwave", "Ice-bath", "Atmospheric"]},
    KEY_RECIPIENT: {"label": "Recipient", "type": "dropdown", "options": ["Beaker", "Flask", "Autoclave"]},
    KEY_MATERIAL: {"label": "Material", "type": "dropdown", "options": ["Glass", "Plastic", "Ceramic"]},
    KEY_FUNCTION: {"label": "Function", "type": "dropdown", "options": ["Carbon Source", "Nitrogen Source", "Mineral", "Vitamin", "Growth Factor", "Inducer", "Precursor"]},
    KEY_PURITY: {"label": "Purity", "type": "dropdown", "options": ["technical", "reagent", "analytical", "molecular biology", "cell culture grade"]},
    KEY_STERILITY: {"label": "Sterility", "type": "dropdown", "options": ["sterile", "non-sterile", "filter-sterilized", "autoclavable"]},
    KEY_ORIGIN: {"label": "Origin", "type": "dropdown", "options": ["primary metabolite", "secondary metabolite", "recombinant protein"]},
    KEY_PRODUCTION_PHASE: {"label": "Production Phase", "type": "dropdown", "options": ["associated to growth", "not associated to growth", "mixed"]},
    KEY_LOCATION: {"label": "Location", "type": "dropdown", "options": ["intracellular", "extracellular", "membrane bound"]},
    KEY_TOXICITY_TO_PRODUCER: {"label": "Toxicity to Producer", "type": "dropdown", "options": ["inhibitory", "toxic", "neutral"]},
    KEY_ENTITY_PRIVACY: {"label": "Entity Type", "type": "dropdown", "options": ["Open Entity", "Private Entity"]},

    # text fields
    KEY_NAME: {"label": "Name", "type": "text", "placeholder": "Entity name..."},
    KEY_FORMULA: {"label": "Formula", "type": "text", "placeholder": "Chemical formula..."},
    KEY_SMILES: {"label": "SMILE", "type": "text", "placeholder": "SMILE string..."},
    KEY_INCHI: {"label": "InChi", "type": "text", "placeholder": "InChi string..."},
    KEY_ATOMIC_COMP: {"label": "Atomic Comp.", "type": "text", "placeholder": "Atoms and % m/m..."},
    KEY_STRUCT_DESC: {"label": "Structure Desc.", "type": "text", "placeholder": "Structure description..."},
    KEY_TEXTURAL_DESC: {"label": "Textural Desc.", "type": "text", "placeholder": "Textural properties..."},
    KEY_CHEM_DESC: {"label": "Chem Desc.", "type": "text", "placeholder": "Chemical descriptors..."},
    KEY_MAT_LIST: {"label": "Materials List", "type": "text", "placeholder": "List of materials..."},
    KEY_BASE_MAT: {"label": "Base Material", "type": "text", "placeholder": "Base entity name..."},
    KEY_BASE_COMPLEX: {"label": "Base Complex", "type": "text", "placeholder": "Base complex entity..."},
    KEY_CHEMICAL: {"label": "Chemical", "type": "text", "placeholder": "Chemical entity name..."},
    KEY_SUBSTANCE_LIST: {"label": "Substance List", "type": "text", "placeholder": "List of chemical entities..."},
    KEY_GASES: {"label": "Gases", "type": "text", "placeholder": "List of gases..."},
    KEY_SOLUBILITY: {"label": "Solubility", "type": "text", "placeholder": "Solubility details..."},
    KEY_ENTITY_ID: {"label": "ID", "type": "text", "placeholder": "Commercial or internal ID..."},
    KEY_PRODUCER: {"label": "Producer", "type": "text", "placeholder": "Institution that created the entity..."},
    KEY_PRIVATE_PURITY: {"label": "Purity", "type": "text", "placeholder": "Degree of purity..."},
    KEY_SUBSTANCE: {"label": "Substance", "type": "text", "placeholder": "Chemical entity..."},
    KEY_MIXTURE_NAME: {"label": "Mixture Name", "type": "text", "placeholder": "Name of the mixture..."},
    KEY_AMOUNT: {"label": "Amount", "type": "text", "placeholder": "Number of times..."},
}