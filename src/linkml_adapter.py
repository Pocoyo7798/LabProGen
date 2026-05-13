"""
linkml_adapter.py
Purpose: Adapter layer converting between the project's Python domain objects
and LinkML-shaped representations. Responsibilities include parsing and
normalizing raw parameter values (quantities, booleans, enums), building
schema-compliant LinkML objects for slots and entities, and performing
roundtrip conversion LinkML -> protocol internal format.
"""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass
from typing import Any

from .config import *


# Internal action names -> LinkML step classes in dcat_p_lab.yaml
ACTION_TO_LINKML_STEP = {
    "Add": "MaterialAdditionStep",
    "Grind": "GrindingStep",
    "Separate": "SeparationStep",
    "Sieve": "SievingStep",
    "Wait": "WaitingStep",
    "ChangeAtmosphere": "AtmosphereChangeStep",
    "ChangeTemperature": "TemperatureChangeStep",
    "ChangeRecipient": "RecipientChangeStep",
    "ChangeAgitation": "StirringStep",
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
    KEY_AGITATION_TYPE: "stirring_type",
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
    "PerfectSingleCrystalMaterial": "ChemicalEntity",
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


@dataclass(frozen=True)
class StructuredQuantity:
    value: float | int
    unit: str
    raw: str

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "unit": self.unit, "raw": self.raw}


_QUANTITY_RE = re.compile(r"^\s*(?P<value>-?\d+(?:[.,]\d+)?)\s*(?P<unit>.*\S)?\s*$")


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def normalize_boolean(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1", "on"}:
            return True
        if normalized in {"false", "no", "0", "off"}:
            return False
    return value


def parse_quantity(value: Any) -> StructuredQuantity | None:
    if _is_blank(value):
        return None

    text = str(value).strip()
    match = _QUANTITY_RE.match(text)
    if not match:
        return None

    unit = (match.group("unit") or "").strip()
    if not unit:
        return None

    numeric_text = match.group("value").replace(",", ".")
    try:
        numeric_value = float(numeric_text)
    except ValueError:
        return None

    if numeric_value.is_integer():
        numeric_value = int(numeric_value)

    return StructuredQuantity(value=numeric_value, unit=unit, raw=text)


def parse_gases(value: Any) -> list[str] | Any:
    if _is_blank(value):
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if not _is_blank(item)]
    text = str(value).strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    return parts if parts else [text]


def quantity_to_text(value: Any) -> Any:
    if _is_blank(value):
        return ""
    if isinstance(value, dict):
        raw = value.get("raw")
        if not _is_blank(raw):
            return raw
        num = value.get("value")
        unit = value.get("unit")
        if not _is_blank(num) and not _is_blank(unit):
            return f"{num} {unit}"
        if not _is_blank(num):
            return str(num)
        if not _is_blank(unit):
            return str(unit)
    return value


def boolean_to_text(value: Any) -> Any:
    if isinstance(value, bool):
        return "True" if value else "False"
    return value


def _quantity_or_raw(value: Any) -> dict[str, Any] | Any:
    if _is_blank(value):
        return None
    quantity = parse_quantity(value)
    return quantity.to_dict() if quantity else value


def add_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_added_material": params.get(KEY_CHEMICAL),
        "has_step_duration": _quantity_or_raw(params.get(KEY_DURATION)),
        "addition_type": params.get(KEY_ADD_TYPE),
        "has_open_flame": normalize_boolean(params.get(KEY_OPEN_FLAME)),
    }


def change_agitation_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    """Convert ChangeAgitation action parameters to StirringStep LinkML slots."""
    return {
        "stirring_type": params.get(KEY_AGITATION_TYPE),
        "has_stirring_speed": _quantity_or_raw(params.get(KEY_SPEED)),
    }


def separate_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "phase_to_keep": params.get(KEY_PHASE),
        "uses_separation_method": params.get(KEY_METHOD),
    }


def change_atmosphere_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_atmosphere_type": parse_gases(params.get(KEY_GASES)),
        "has_flow_rate": _quantity_or_raw(params.get(KEY_FLOW_RATE)),
        "has_pressure": _quantity_or_raw(params.get(KEY_PRESSURE)),
    }


def change_temperature_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_target_temperature": _quantity_or_raw(params.get(KEY_TEMPERATURE)),
        "heating_process": params.get(KEY_PROCESS),
        "has_heat_ramp": _quantity_or_raw(params.get(KEY_RAMP)),
        "has_microwave_power": _quantity_or_raw(params.get(KEY_POWER)),
    }


def change_recipient_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_recipient_type": params.get(KEY_RECIPIENT),
        "has_vessel_material": params.get(KEY_MATERIAL),
        "has_vessel_volume": _quantity_or_raw(params.get(KEY_VOLUME)),
    }


def sieve_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_minimum_particle_size": _quantity_or_raw(params.get(KEY_MIN_SIZE)),
        "has_maximum_particle_size": _quantity_or_raw(params.get(KEY_MAX_SIZE)),
    }


def repeat_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "repetition_count": params.get(KEY_AMOUNT),
    }


def continuous_addition_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_added_material": params.get(KEY_SUBSTANCE_LIST),
        "continuous_addition_type": params.get(KEY_CONTINUOUS_ADD_TYPE),
        "has_intermittent_amount": _quantity_or_raw(params.get(KEY_AMOUNT)),
    }


ACTION_TO_ADAPTER = {
    "Add": add_to_linkml,
    "Separate": separate_to_linkml,
    "ChangeAtmosphere": change_atmosphere_to_linkml,
    "ChangeTemperature": change_temperature_to_linkml,
    "ChangeRecipient": change_recipient_to_linkml,
    "ChangeAgitation": change_agitation_to_linkml,
    "Sieve": sieve_to_linkml,
    "Repeat": repeat_to_linkml,
    "ContinuousAddition": continuous_addition_to_linkml,
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


LINKML_STEP_TO_ACTION = {
    "MaterialAdditionStep": "Add",
    "GrindingStep": "Grind",
    "SeparationStep": "Separate",
    "SievingStep": "Sieve",
    "WaitingStep": "Wait",
    "AtmosphereChangeStep": "ChangeAtmosphere",
    "TemperatureChangeStep": "ChangeTemperature",
    "RecipientChangeStep": "ChangeRecipient",
    "StirringStep": "ChangeAgitation",
    "SolutionPreparationStep": "NewMixture",
    "SubProductCreationStep": "SubProductCreation",
    "RepetitionBlock": "Repeat",
    "ContinuousAdditionStep": "ContinuousAddition",
}


LINKML_CHEMICAL_TO_SOURCE = {
    "ChemicalEntity": "Substance",
    "MaterialEntity": "Material",
    "ChemicalSubstance": "Mixture",
    "Polymer": "Polymers",
}


STEP_SLOT_TO_PARAM = {
    "has_added_material": KEY_CHEMICAL,
    "has_step_duration": KEY_DURATION,
    "addition_type": KEY_ADD_TYPE,
    "has_open_flame": KEY_OPEN_FLAME,
    "phase_to_keep": KEY_PHASE,
    "uses_separation_method": KEY_METHOD,
    "has_minimum_particle_size": KEY_MIN_SIZE,
    "has_maximum_particle_size": KEY_MAX_SIZE,
    "stirring_type": KEY_AGITATION_TYPE,
    "has_stirring_speed": KEY_SPEED,
    "has_atmosphere_type": KEY_GASES,
    "has_flow_rate": KEY_FLOW_RATE,
    "has_pressure": KEY_PRESSURE,
    "heating_process": KEY_PROCESS,
    "has_heat_ramp": KEY_RAMP,
    "has_microwave_power": KEY_POWER,
    "has_recipient_type": KEY_RECIPIENT,
    "has_vessel_material": KEY_MATERIAL,
    "has_vessel_volume": KEY_VOLUME,
    "continuous_addition_type": KEY_CONTINUOUS_ADD_TYPE,
    "has_intermittent_amount": KEY_AMOUNT,
    "repetition_count": KEY_AMOUNT,
}


CHEMICAL_SLOT_TO_PARAM = {
    "entity_privacy": "entity_privacy",
    "entity_id": "entity_id",
    "entity_producer": "entity_producer",
    "entity_purity": "entity_purity",
    "molecular_formula": KEY_FORMULA,
    "smiles": KEY_SMILES,
    "inchi": KEY_INCHI,
    "has_crystallographic_information_file": KEY_CIF,
    "alternative_label": KEY_NAME,
    "has_volume": KEY_QUANTITY,
    "has_mass": KEY_QUANTITY,
    "has_amount": KEY_QUANTITY,
    "has_concentration": KEY_CONCENTRATION,
    "has_physical_state": KEY_STATE,
}


def _slot_value_to_param_value(slot: str, value: Any) -> Any:
    if slot in {"uses_separation_method", "uses_washing_method"} and isinstance(value, dict):
        return value.get("id")
    if slot in {"has_open_flame"}:
        return boolean_to_text(value)
    if slot in {"has_step_duration", "has_stirring_speed", "has_flow_rate", "has_pressure", "has_heat_ramp", "has_microwave_power", "has_vessel_volume", "has_minimum_particle_size", "has_maximum_particle_size"}:
        return quantity_to_text(value)
    if slot == "has_atmosphere_type":
        if isinstance(value, list):
            return ", ".join(str(v) for v in value if not _is_blank(v))
        return value
    if slot == "has_intermittent_amount" and isinstance(value, dict):
        return quantity_to_text(value)
    # Convert material objects back to simple labels when present
    if isinstance(value, dict) and "alternative_label" in value:
        return value.get("alternative_label")
    if isinstance(value, list):
        new_list = []
        for item in value:
            if isinstance(item, dict) and "alternative_label" in item:
                new_list.append(item.get("alternative_label"))
            else:
                new_list.append(item)
        return new_list

    return value


def _convert_linkml_chemical_slots(slots: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for slot, value in (slots or {}).items():
        param_key = CHEMICAL_SLOT_TO_PARAM.get(slot)
        if not param_key:
            continue

        if slot in {"has_volume", "has_mass", "has_amount"}:
            params[param_key] = quantity_to_text(value)
            continue

        params[param_key] = value

    return params


def _linkml_step_name_to_action(step: dict[str, Any]) -> str:
    source_action = step.get("source_action")
    if isinstance(source_action, str) and source_action:
        return source_action
    linkml_class = step.get("linkml_class")
    if isinstance(linkml_class, str) and linkml_class:
        return LINKML_STEP_TO_ACTION.get(linkml_class, linkml_class)
    return "Add"


def _convert_linkml_step_slots(slots: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for slot, value in (slots or {}).items():
        param_key = STEP_SLOT_TO_PARAM.get(slot)
        if not param_key:
            continue

        params[param_key] = _slot_value_to_param_value(slot, value)

    return params


def _convert_linkml_step(step: dict[str, Any]) -> dict[str, Any]:
    step_payload: dict[str, Any] = {
        "block_id": step.get("block_id", 0),
        "action": _linkml_step_name_to_action(step),
        "params": _convert_linkml_step_slots(step.get("slots", {})),
    }

    attached_chemicals = []
    for chem in step.get("attached_chemicals", []) or []:
        chem_params = _convert_linkml_chemical_slots(chem.get("slots", {}))
        attached_chemicals.append(
            {
                "block_id": chem.get("block_id", 0),
                "chemical": chem.get("source_chemical")
                or LINKML_CHEMICAL_TO_SOURCE.get(chem.get("linkml_class"), chem.get("linkml_class") or "Chemical"),
                "params": chem_params,
            }
        )

    # Always include a 'chemicals' key for compatibility with internal protocol
    step_payload["chemicals"] = attached_chemicals

    sub_branch = step.get("subproduct_branch")
    if isinstance(sub_branch, dict):
        step_payload["subproduct_branch"] = _convert_linkml_step(sub_branch)

    # Keep compatibility if future payloads include multiple branches.
    sub_branches = step.get("subproduct_branches")
    if isinstance(sub_branches, list) and sub_branches:
        converted = [_convert_linkml_step(branch) for branch in sub_branches if isinstance(branch, dict)]
        if converted:
            step_payload["subproducts"] = converted

    return step_payload


def convert_linkml_to_protocol(linkml_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(linkml_payload, dict):
        return {"protocol_name": DEFAULT_PROTOCOL_NAME, "total_flows": 0, "flows": []}

    source_protocol = linkml_payload.get("source_protocol")
    if isinstance(source_protocol, dict) and source_protocol:
        return source_protocol

    flows: list[dict[str, Any]] = []
    activities = linkml_payload.get("activities", []) or []

    for idx, activity in enumerate(activities, start=1):
        steps: list[dict[str, Any]] = []
        for step in activity.get("has_synthesis_step", []) or []:
            steps.append(_convert_linkml_step(step))

        flow_obj = {
            "flow_id": activity.get("flow_id", idx),
            "type": activity.get("flow_type", "horizontal"),
            "steps": steps,
        }
        flows.append(flow_obj)

    return {
        "protocol_name": linkml_payload.get("source_protocol_name", DEFAULT_PROTOCOL_NAME),
        "flows": flows,
    }


def normalize_action_to_linkml(action_name: str, params: dict[str, Any]) -> dict[str, Any]:
    adapter = ACTION_TO_ADAPTER.get(action_name)
    if not adapter:
        return {}
    return adapter(params or {})


def build_material_entity(value: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
    """Build a minimal valid MaterialEntity preserving the material identifier.

    Uses alternative_label for the human-readable name and derives a stable,
    collision-proof id from a hash to satisfy LinkML identifier semantics.
    
    This avoids identifier collisions from case variations (water, Water, WATER).
    """
    if _is_blank(value):
        return None

    # Guard against double-wrapping if already built
    if isinstance(value, dict) and "alternative_label" in value:
        return value

    if isinstance(value, list):
        built_items = []
        for item in value:
            if _is_blank(item):
                continue
            # Guard against double-wrapping
            if isinstance(item, dict) and "alternative_label" in item:
                built_items.append(item)
                continue
            name = str(item).strip()
            # Use MD5 hash to create collision-proof identifier
            hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
            built_items.append({
                "id": hash_suffix,
                "alternative_label": name,
                "entity_id": hash_suffix,
            })
        return built_items if built_items else None

    name = str(value).strip()
    # Use MD5 hash to create collision-proof identifier (handles case variations)
    hash_suffix = hashlib.md5(name.encode()).hexdigest()[:8]
    return {
        "id": hash_suffix,
        "alternative_label": name,
        "entity_id": hash_suffix,
    }



def build_chemical_entity(value: Any) -> dict[str, Any] | None:
    """Build a minimal valid ChemicalEntity from a simple value."""
    if _is_blank(value):
        return None
    
    name = str(value).strip()
    if not name:
        return None
    
    return {
        "id": name.lower().replace(" ", "_"),
        "name": name,
    }


def build_duration(value: Any) -> dict[str, Any] | None:
    """Build a Duration object from value or StructuredQuantity."""
    if _is_blank(value):
        return None

    if isinstance(value, dict):
        numeric = value.get("value")
        unit = value.get("unit")
        raw = value.get("raw")
        if not _is_blank(numeric) and not _is_blank(unit):
            return {
                "value": numeric,
                "unit": unit,
                "raw": raw if not _is_blank(raw) else f"{numeric} {unit}",
            }
        return None

    qty = parse_quantity(value)
    if qty:
        return {
            "value": qty.value,
            "unit": qty.unit,
            "raw": qty.raw,
        }

    return None


def build_temperature(value: Any) -> dict[str, Any] | None:
    """Build a Temperature object from value or StructuredQuantity."""
    if _is_blank(value):
        return None

    if isinstance(value, dict):
        numeric = value.get("value")
        unit = value.get("unit")
        raw = value.get("raw")
        if not _is_blank(numeric) and not _is_blank(unit):
            return {
                "value": numeric,
                "unit": unit,
                "raw": raw if not _is_blank(raw) else f"{numeric} {unit}",
            }
        return None

    qty = parse_quantity(value)
    if qty:
        return {
            "value": qty.value,
            "unit": qty.unit,
            "raw": qty.raw,
        }

    return None


def build_generic_quantitative_attribute(value: Any) -> dict[str, Any] | None:
    """Build a generic QuantitativeAttribute from value or StructuredQuantity."""
    return build_duration(value)


def build_defined_term(value: Any) -> dict[str, Any] | list[dict[str, Any]] | None:
    if _is_blank(value):
        return None

    def normalize(term: str) -> str:
        return term.strip().lower().replace(" ", "_")

    if isinstance(value, dict):
        return value if value.get("id") else None

    if isinstance(value, list):
        built_items = []
        for item in value:
            if _is_blank(item):
                continue
            if isinstance(item, dict) and item.get("id"):
                built_items.append(item)
            else:
                built_items.append({"id": normalize(str(item))})
        return built_items if built_items else None

    return {"id": normalize(str(value))}


# Mapping of slot names to their expected type and builder functions
SLOT_BUILDERS: dict[str, tuple[str, callable]] = {
    # Material slots
    "has_added_material": ("MaterialEntity", build_material_entity),
    "has_initial_material": ("MaterialEntity", build_material_entity),
    "has_subproduct": ("MaterialEntity", build_material_entity),
    "uses_washing_material": ("MaterialEntity", build_material_entity),
    "uses_starting_material": ("MaterialEntity", build_material_entity),
    "uses_reactant": ("MaterialEntity", build_material_entity),
    "generated_product": ("MaterialEntity", build_material_entity),

    # Duration/Temperature slots
    "has_step_duration": ("Duration", build_duration),
    "has_duration": ("Duration", build_duration),
    "has_target_temperature": ("Temperature", build_temperature),
    "has_temperature": ("Temperature", build_temperature),

    # Other quantitative attributes
    "has_pressure": ("Pressure", build_generic_quantitative_attribute),
    "has_volume": ("Volume", build_generic_quantitative_attribute),
    "has_concentration": ("Concentration", build_generic_quantitative_attribute),
    "has_mass": ("Mass", build_generic_quantitative_attribute),
    "has_flow_rate": ("FlowRate", build_generic_quantitative_attribute),
    "has_heat_ramp": ("HeatRamp", build_generic_quantitative_attribute),
    "has_microwave_power": ("MicrowavePower", build_generic_quantitative_attribute),
    "has_stirring_speed": ("StirringSpeed", build_generic_quantitative_attribute),
    "has_vessel_volume": ("Volume", build_generic_quantitative_attribute),
    "has_minimum_particle_size": ("ParticleSize", build_generic_quantitative_attribute),
    "has_maximum_particle_size": ("ParticleSize", build_generic_quantitative_attribute),
    "has_intermittent_amount": ("Amount", build_generic_quantitative_attribute),
    "has_ph_value": ("PhValue", build_generic_quantitative_attribute),
    "has_density": ("Density", build_generic_quantitative_attribute),
    "has_molar_mass": ("MolarMass", build_generic_quantitative_attribute),
    "has_yield": ("Yield", build_generic_quantitative_attribute),
    "has_amount": ("Amount", build_generic_quantitative_attribute),
    "has_percentage_of_total": ("PercentageOfTotal", build_generic_quantitative_attribute),
    "has_molar_equivalent": ("MolarEquivalent", build_generic_quantitative_attribute),
    "uses_separation_method": ("DefinedTerm", build_defined_term),
    "uses_washing_method": ("DefinedTerm", build_defined_term),
}


MULTIVALUED_SLOTS: set[str] = set()


def convert_slots_to_linkml_objects(slots: dict[str, Any]) -> dict[str, Any]:
    """Convert simple slot values to proper LinkML objects based on slot definitions.

    This ensures that complex-typed slots receive structured objects instead of
    primitive values, making them valid according to the LinkML schema.
    """
    if not slots:
        return slots

    converted = {}
    for slot_name, value in slots.items():
        if _is_blank(value):
            converted[slot_name] = value
            continue

        if slot_name in SLOT_BUILDERS:
            _, builder = SLOT_BUILDERS[slot_name]
            built_value = builder(value)
            # Use the built object if builder succeeded, otherwise keep original
            final_value = built_value if built_value is not None else value
            if slot_name in MULTIVALUED_SLOTS and final_value is not None and not isinstance(final_value, list):
                final_value = [final_value]
            converted[slot_name] = final_value
        else:
            # No special builder, keep as-is
            converted[slot_name] = value

    return converted



def action_to_linkml_dict(action_name: str, params: dict[str, Any], chemicals: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {
        "source_action": action_name,
        "linkml_class": get_linkml_step_class(action_name),
        "slots": normalize_action_to_linkml(action_name, params or {}),
    }
    if chemicals:
        payload["attached_chemicals"] = chemicals
    return payload


def chemical_to_linkml_dict(chemical_name: str, params: dict[str, Any]) -> dict[str, Any]:
    slots: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if _is_blank(value):
            continue
        if key == KEY_QUANTITY:
            slot = get_linkml_chemical_slot(chemical_name, key) or get_linkml_slot(key)
            if slot:
                quantity = parse_quantity(value)
                slots[slot] = quantity.to_dict() if quantity else value
            continue

        slot = get_linkml_chemical_slot(chemical_name, key) or get_linkml_slot(key)
        if slot:
            slots[slot] = value

    return {
        "source_chemical": chemical_name,
        "linkml_class": get_linkml_chemical_class(chemical_name),
        "slots": slots,
    }
