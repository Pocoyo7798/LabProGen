# config.py

# INTERNAL KEYS (These are the variable names used in code and JSON)
KEY_DURATION = "duration"
KEY_TEMPERATURE = "temperature"
KEY_COMPONENT = "component"
KEY_NAME = "name"
KEY_FORMULA = "formula"
KEY_SMILES = "smile"
KEY_STRUCTURE = "structure"

# UI CONFIGURATION (Labels, units, placeholders)
FIELD_CONFIG = {
    KEY_DURATION: {
        "label": "Duration",
        "type": "unit",
        "units": ["s", "min", "h"],
        "defaults": ["0", "30", "0.0"],
        "placeholder": "Value"
    },
    KEY_TEMPERATURE: {
        "label": "Temperature",
        "type": "unit",
        "units": ["°C", "°F"],
        "defaults": ["50", "50.0"],
        "placeholder": "Value"
    },
    KEY_COMPONENT: {
        "label": "Component",
        "type": "text",
        "placeholder": "Enter component name..."
    },
    KEY_NAME: {
        "label": "Name",
        "type": "text",
        "placeholder": "Enter chemical name..."
    },
    KEY_FORMULA: {
        "label": "Formula",
        "type": "text",
        "placeholder": "Enter chemical formula..."
    },
    KEY_SMILES: {
        "label": "SMILES",
        "type": "text",
        "placeholder": "Enter SMILES string..."
    },
    KEY_STRUCTURE: {
        "label": "Structure",
        "type": "text",
        "placeholder": "Describe structure..."
    }
}