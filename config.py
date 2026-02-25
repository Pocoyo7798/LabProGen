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
KEY_AMOUNT = "amount"

# --- UI CONFIGURATION ---
FIELD_CONFIG = {
    # Unit fields (Numeric + Dropdown)
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

    # Dropdown fields (Standalone selection)
    KEY_ADD_TYPE: {"label": "Add Type", "type": "dropdown", "options": ["Normal", "Dropwise", "Diffusion"]},
    KEY_STIR_TYPE: {"label": "Stirring Type", "type": "dropdown", "options": ["Manual", "Automatic"]},
    KEY_PHASE: {"label": "Phase to Keep", "type": "dropdown", "options": ["Liquid", "Solid", "Aqueous", "Organic"]},
    KEY_METHOD: {"label": "Method", "type": "dropdown", "options": ["Filtration", "Centrifugation", "Decantation"]},
    KEY_PROCESS: {"label": "Process", "type": "dropdown", "options": ["Electrical", "Microwave", "Ice-bath", "Atmospheric"]},
    KEY_RECIPIENT: {"label": "Recipient", "type": "dropdown", "options": ["Beaker", "Flask", "Autoclave"]},
    KEY_MATERIAL: {"label": "Material", "type": "dropdown", "options": ["Glass", "Plastic", "Ceramic"]},

    # Text fields
    KEY_CHEMICAL: {"label": "Chemical", "type": "text", "placeholder": "Chemical entity name..."},
    KEY_GASES: {"label": "Gases", "type": "text", "placeholder": "List of gases..."},
    KEY_SUBSTANCE: {"label": "Substance", "type": "text", "placeholder": "Chemical entity..."},
    KEY_MIXTURE_NAME: {"label": "Mixture Name", "type": "text", "placeholder": "Name of the mixture..."},
    KEY_AMOUNT: {"label": "Repetitions", "type": "text", "placeholder": "Number of times..."},
    KEY_NAME: {"label": "Name", "type": "text", "placeholder": "Entity name..."},
    KEY_FORMULA: {"label": "Formula", "type": "text", "placeholder": "Chemical formula..."},
    KEY_SMILES: {"label": "SMILES", "type": "text", "placeholder": "SMILES string..."},
}