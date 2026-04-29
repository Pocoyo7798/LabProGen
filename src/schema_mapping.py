from .config import *


# Internal action names -> LinkML step classes in dcat_p_lab.yaml
ACTION_TO_LINKML_STEP = {
    "Add": "MaterialAdditionStep",
    "Grind": "GrindingStep",
    "Separate": "SeparationStep",
    "Sieve": "SievingStep",
    "Stir": "StirringStep",
    "Wait": "WaitingStep",
    "ChangeAtmosphere": "AtmosphereChangeStep",
    "ChangeTemperature": "TemperatureChangeStep",
    "ChangeRecipient": "RecipientChangeStep",
    "NewMixture": "SolutionPreparationStep",
    "SubProductCreation": "SubProductCreationStep",
    "Repeat": "RepetitionBlock",
    "ContinuousAddition": "ContinuousAdditionStep",
}


# Internal field keys -> LinkML slots in dcat_p_lab.yaml
FIELD_TO_LINKML_SLOT = {
    KEY_DURATION: "has_step_duration",
    KEY_TEMPERATURE: "has_target_temperature",
    KEY_CHEMICAL: "has_added_material",
    KEY_ADD_TYPE: "addition_type",
    KEY_OPEN_FLAME: "has_open_flame",
    KEY_PHASE: "phase_to_keep",
    KEY_METHOD: "uses_separation_method",
    KEY_MIN_SIZE: "has_minimum_particle_size",
    KEY_MAX_SIZE: "has_maximum_particle_size",
    KEY_STIR_TYPE: "stirring_type",
    KEY_SPEED: "has_stirring_speed",
    KEY_GASES: "has_atmosphere_type",
    KEY_FLOW_RATE: "has_flow_rate",
    KEY_PRESSURE: "has_pressure",
    KEY_PROCESS: "heating_process",
    KEY_RAMP: "has_heat_ramp",
    KEY_POWER: "has_microwave_power",
    KEY_RECIPIENT: "has_recipient_type",
    KEY_MATERIAL: "has_vessel_material",
    KEY_VOLUME: "has_vessel_volume",
    KEY_MIXTURE_NAME: "name",
    KEY_SUBSTANCE: "has_subproduct",
    KEY_SUBSTANCE_LIST: "has_added_material",
    KEY_CONTINUOUS_ADD_TYPE: "continuous_addition_type",
}


CHEMICAL_TO_LINKML_CLASS = {
    "Substance": "ChemicalEntity",
    "Material": "MaterialEntity",
    "Mixture": "ChemicalSubstance",
    "PerfectSingleCrystalMaterial": "MaterialEntity",
    "Polymers": "Polymer",
    "Media": "ChemicalSubstance",
    "BioProducts": "ChemicalSubstance",
    # Legacy/older protocol exports kept as fallback for migration compatibility
    "ComplexMaterial": "MaterialEntity",
    "HeterogeneousMaterial": "MaterialEntity",
    "ComplexHeterogeneousMaterial": "MaterialEntity",
}


CHEMICAL_FIELD_TO_LINKML_SLOT = {
    "entity_privacy": "entity_privacy",
    "entity_id": "entity_id",
    "entity_producer": "entity_producer",
    "entity_purity": "entity_purity",
    "Substance": {
        KEY_FORMULA: "molecular_formula",
        KEY_SMILES: "smiles",
        KEY_INCHI: "inchi",
    },
    "Material": {
        KEY_ATOMIC_COMP: "alternative_label",
        KEY_FORMULA: "molecular_formula",
    },
    "Mixture": {
        KEY_NAME: "alternative_label",
        KEY_QUANTITY: "has_volume",
    },
    "PerfectSingleCrystalMaterial": {
        KEY_FORMULA: "molecular_formula",
        KEY_CIF: "has_crystallographic_information_file",
    },
    "Polymers": {
        KEY_BIGSMILES: "alternative_label",
    },
    "Media": {
        KEY_QUANTITY: "has_volume",
        KEY_CONCENTRATION: "has_concentration",
        KEY_STATE: "has_physical_state",
    },
    "BioProducts": {
        KEY_NAME: "alternative_label",
    },
    "ComplexMaterial": {
        KEY_BASE_MAT: "alternative_label",
    },
    "HeterogeneousMaterial": {
        KEY_MAT_LIST: "alternative_label",
    },
    "ComplexHeterogeneousMaterial": {
        KEY_BASE_COMPLEX: "alternative_label",
    },
}


def get_linkml_step_class(action_name: str) -> str | None:
    return ACTION_TO_LINKML_STEP.get(action_name)


def get_linkml_slot(field_key: str, action_name: str | None = None) -> str | None:
    if field_key == KEY_AMOUNT:
        if action_name == "ContinuousAddition":
            return "has_intermittent_amount"
        if action_name == "Repeat":
            return "repetition_count"

    return FIELD_TO_LINKML_SLOT.get(field_key)


def get_linkml_chemical_class(chemical_name: str) -> str | None:
    return CHEMICAL_TO_LINKML_CLASS.get(chemical_name)


def get_linkml_chemical_slot(chemical_name: str, field_key: str) -> str | None:
    return CHEMICAL_FIELD_TO_LINKML_SLOT.get(chemical_name, {}).get(field_key) or CHEMICAL_FIELD_TO_LINKML_SLOT.get(field_key)
