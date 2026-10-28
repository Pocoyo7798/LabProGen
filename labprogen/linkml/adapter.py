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
import json
import hashlib
from dataclasses import dataclass
from typing import Any

from labprogen.core.config import *
from labprogen.linkml.loader import (
    listed_action_classes,
    listed_chemical_classes,
)


# Schema names are canonical; legacy names are resolved by core.config.
ACTION_TO_LINKML_STEP = {name: name for name in listed_action_classes()}


# Legacy key migrations only; current schema keys pass through unchanged.
FIELD_TO_LINKML_SLOT = {
    KEY_SUBSTANCE_LIST: "chemical",
    KEY_3D_STRUCTURE: "three_d_structure",
}


CHEMICAL_TO_LINKML_CLASS = {name: name for name in listed_chemical_classes()}


CHEMICAL_FIELD_TO_LINKML_SLOT = {
    KEY_3D_STRUCTURE: "three_d_structure",
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
    """Parse gases field. Handles both legacy text format and new list of chemical objects.
    
    For chemical objects, extracts the name (KEY_NAME) which should be one of:
    'air', 'inert', 'nitrogen', 'argon', 'hydrogen', 'vacuum', 'autogeneous', 'oxygen'
    """
    if _is_blank(value):
        return []
    
    # If it's a list of chemical objects (new format)
    if isinstance(value, list):
        results = []
        for item in value:
            if isinstance(item, dict):
                # Extract chemical name from the chemical object
                # Prefer KEY_NAME, fallback to other possible name fields
                name = (item.get(KEY_NAME, "") or 
                        item.get("name", "") or
                        item.get("chemical_name", "")).strip()
                
                # Skip empty names - don't add to results
                if name:
                    results.append(name)
                else:
                    # Log warning if no name found - indicates incomplete chemical object
                    print(f"[parse_gases] Warning: Chemical object has no name field: {item}")
            else:
                # Legacy text items in list
                text = str(item).strip()
                if text and text not in results:  # Avoid duplicates
                    results.append(text)
        return results if results else []
    
    # Legacy text format - comma or semicolon separated
    text = str(value).strip()
    if not text:
        return []
    parts = [part.strip() for part in re.split(r"[,;]", text) if part.strip()]
    return parts if parts else []


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


def normalize_physical_state(value: Any) -> Any:
    if _is_blank(value):
        return value
    text = str(value).strip().upper().replace(" ", "_")
    state_map = {
        "LIQUID": "LIQUID",
        "SOLID": "SOLID",
        "GAS": "GASEOUS",
        "GASEOUS": "GASEOUS",
        "CRYSTAL": "CRYSTAL",
        "CRYSTALLINE": "CRYSTAL",
    }
    return state_map.get(text, text)


def _quantity_or_raw(value: Any) -> dict[str, Any] | Any:
    if _is_blank(value):
        return None
    if isinstance(value, dict):
        text = quantity_to_text(value)
        return text

    quantity = parse_quantity(value)
    return quantity.to_dict() if quantity else value


def physical_state_to_text(value: Any) -> Any:
    if _is_blank(value):
        return value
    text = str(value).strip().upper()
    reverse_map = {
        "LIQUID": "Liquid",
        "SOLID": "Solid",
        "GASEOUS": "Gas",
        "GAS": "Gas",
        "CRYSTAL": "Crystal",
    }
    return reverse_map.get(text, str(value))


def build_amount_of_substance(value: Any) -> dict[str, Any] | None:
    """Build an AmountOfSubstance object.

    Continuous addition uses a quantitative slot in the schema, so we keep a
    structured representation even when the UI only provides a bare number.
    """
    if _is_blank(value):
        return None

    if isinstance(value, dict):
        numeric = value.get("value")
        unit = value.get("unit")
        raw = value.get("raw")
        if not _is_blank(numeric):
            built: dict[str, Any] = {"value": numeric}
            if not _is_blank(unit):
                built["unit"] = unit
            built["raw"] = raw if not _is_blank(raw) else quantity_to_text(value) or str(numeric)
            return built
        return None

    qty = parse_quantity(value)
    if qty:
        return qty.to_dict()

    text = str(value).strip()
    if not text:
        return None

    try:
        numeric_value = float(text)
    except ValueError:
        return {"value": text, "raw": text}

    if numeric_value.is_integer():
        numeric_value = int(numeric_value)

    return {"value": numeric_value, "raw": text}


def get_linkml_step_class(action_name: str) -> str | None:
    action_name = canonical_action_name(action_name)
    mapped = ACTION_TO_LINKML_STEP.get(action_name)
    if mapped:
        return mapped
    if action_name in listed_action_classes():
        return action_name
    return None


def get_linkml_slot(field_key: str, action_name: str | None = None) -> str:
    """Map a domain field onto an Action Data Model slot; unknown keys are kept."""
    return FIELD_TO_LINKML_SLOT.get(field_key, field_key)


def get_linkml_chemical_class(chemical_name: str) -> str | None:
    chemical_name = canonical_chemical_name(chemical_name)
    mapped = CHEMICAL_TO_LINKML_CLASS.get(chemical_name)
    if mapped:
        return mapped
    if chemical_name in listed_chemical_classes():
        return chemical_name
    return None


def get_linkml_chemical_slot(chemical_name: str, field_key: str) -> str:
    """Map a chemical field onto an Action Data Model slot; unknown keys are kept."""
    return CHEMICAL_FIELD_TO_LINKML_SLOT.get(field_key, field_key)


from labprogen.core.model import chemical_fields, field_contract, range_is_subclass


def chemical_slot_for_action(action_name: str | None) -> str | None:
    fields = chemical_fields(canonical_action_name(action_name or ""))
    return next(iter(fields)) if len(fields) == 1 else None


def _mixture_relation(slot: str, class_name: str) -> bool:
    return range_is_subclass(field_contract(slot, class_name).get("range"), "MixtureConstituent")


COMPLEX_ACTION_MARKER = "ComplexAction"
# Import heuristics for older exports: Medium once owned concentration itself.
# This is compatibility, not a declaration of the current Medium contract.
_ENTITY_OWNED_CONCENTRATION_CLASSES = {"Medium"}


LINKML_STEP_TO_ACTION = {
    **{value: key for key, value in ACTION_TO_LINKML_STEP.items()},
    # Legacy export class names (import only)
    "MaterialAdditionStep": "Add",
    "GrindingStep": "Grind",
    "SeparationStep": "Separate",
    "SievingStep": "Sieve",
    "WaitingStep": "NoAction",
    "AtmosphereChangeStep": "ChangePressure",
    "TemperatureChangeStep": "ChangeTemperature",
    "RecipientChangeStep": "ChangeContainer",
    "StirringStep": "ChangeAgitation",
    "SubProductCreationStep": "CollectSubProduct",
    "RepetitionBlock": "Repeat",
    "ContinuousAdditionStep": "ContinuousAddition",
}


LINKML_CHEMICAL_TO_SOURCE = {
    **{value: key for key, value in CHEMICAL_TO_LINKML_CLASS.items()},
    "ChemicalEntity": "Substance",
    "MaterialEntity": "Substance",
    "ChemicalSubstance": "Mixture",
    "Polymer": "Polymer",
    "Catalyst": "PorousMaterial",
}


STEP_SLOT_TO_PARAM = {
    # Legacy export slot names (import only)
    "has_added_material": KEY_CHEMICAL,
    "has_step_duration": KEY_DURATION,
    "has_target_temperature": KEY_TEMPERATURE,
    "addition_type": KEY_ADD_TYPE,
    "has_open_flame": KEY_OPEN_FLAME,
    "uses_separation_method": KEY_METHOD,
    "has_minimum_particle_size": KEY_SIZE_RANGE,
    "stirring_type": KEY_AGITATION_TYPE,
    "has_stirring_speed": KEY_SPEED,
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
    "has_subproduct": KEY_SUBSTANCE,
}


CHEMICAL_SLOT_TO_PARAM = {
    **{value: key for key, value in CHEMICAL_FIELD_TO_LINKML_SLOT.items() if isinstance(value, str)},
    "three_d_structure": KEY_3D_STRUCTURE,
    "molecular_formula": KEY_FORMULA,
    "smiles": KEY_SMILES,
    "inchi": KEY_INCHI,
    "alternative_label": KEY_NAME,
    "has_volume": KEY_QUANTITY,
    "has_mass": KEY_QUANTITY,
    "has_amount": KEY_QUANTITY,
    "has_concentration": KEY_CONCENTRATION,
    "has_physical_state": KEY_STATE,
}


_CHEMICAL_WRAPPER_KEYS = {
    "chemical",
    "chemical_type",
    "params",
    "block_id",
    "slots",
    "linkml_class",
    "source_chemical",
    "id",
    "source_metadata",
    "attached_chemicals",
    "class",
    "type",
}

EXPORTER_ENVELOPE_KEYS = {
    "id",
    "block_id",
    "source_action",
    "source_chemical",
    "linkml_class",
    "source_metadata",
    "attached_chemicals",
    "class",
    "slots",
    "flow_id",
    "flow_type",
    "is_explicit_first",
    "chemical_block_id",
    "part_of_complex_action",
    "complex_group_id",
    "complex_action_name",
    "complex_step_index",
    "subproduct_branch",
    "subproduct_branches",
}


def _record_chemical_class(chemical: dict[str, Any]) -> str:
    if chemical.get("type") == "MixtureConstituent" or chemical.get("linkml_class") == "MixtureConstituent":
        return "MixtureConstituent"
    raw = chemical.get("chemical")
    if isinstance(raw, str) and raw.strip():
        return canonical_chemical_name(raw) or raw
    return canonical_chemical_name(
        chemical.get("chemical_type")
        or chemical.get("type")
        or chemical.get("source_chemical")
        or ""
    ) or ""


def _looks_like_mixture_substance(chemical: dict[str, Any], class_name: str) -> bool:
    """True for a flat mixture-list item, not a ChemicalEntity that owns concentration."""
    if class_name == "MixtureConstituent" or isinstance(chemical.get("chemical"), dict):
        return True
    if class_name in _ENTITY_OWNED_CONCENTRATION_CLASSES or class_name in {"Mixture", "Dispersion"}:
        return False
    return bool(chemical.get("chemical_type")) and KEY_CONCENTRATION in chemical


def _nested_chemical_params(chemical: dict[str, Any], params: dict[str, Any]) -> dict[str, Any]:
    nested_params = dict(params)
    skip = set(_CHEMICAL_WRAPPER_KEYS) | {KEY_CONCENTRATION}
    for key, value in chemical.items():
        if key in skip:
            continue
        nested_params.setdefault(key, value)
    nested_params.pop(KEY_CONCENTRATION, None)
    nested_params.pop("chemical_type", None)
    nested_params.pop("type", None)
    return nested_params


def _project_mixture_substance(chemical: dict[str, Any], class_name: str) -> dict[str, Any]:
    """Build a MixtureConstituent with nested ChemicalEntity and required concentration."""
    params = dict(chemical.get("params") or {})
    concentration = chemical.get(KEY_CONCENTRATION, params.get(KEY_CONCENTRATION))
    nested_record = chemical.get("chemical")
    if isinstance(nested_record, dict):
        nested = chemical_record_to_instance(nested_record, mixture_item=False)
    else:
        nested_type = canonical_chemical_name(
            (nested_record if isinstance(nested_record, str) else None)
            or chemical.get("chemical_type")
            or (class_name if class_name not in {"", "MixtureConstituent"} else None)
            or params.get("chemical_type")
            or "Substance"
        )
        nested = _finish_chemical_instance(nested_type, _nested_chemical_params(chemical, params))
    instance: dict[str, Any] = {"type": "MixtureConstituent", "chemical": nested}
    if class_name == "MixtureConstituent" and isinstance(nested_record, dict):
        for key, value in {**params, **chemical}.items():
            if key not in _CHEMICAL_WRAPPER_KEYS and key not in {"chemical", "chemical_type", "type", KEY_CONCENTRATION}:
                instance[key] = value
    if not _is_blank(concentration):
        instance[KEY_CONCENTRATION] = concentration
    return instance


def _finish_chemical_instance(
    class_name: str,
    params: dict[str, Any] | None,
    *,
    mixture_item: bool = False,
) -> dict[str, Any]:
    class_name = canonical_chemical_name(class_name) or class_name
    record = dict(params or {})
    if mixture_item or class_name == "MixtureConstituent":
        if class_name == "MixtureConstituent":
            record.setdefault("type", "MixtureConstituent")
        else:
            record.setdefault("chemical_type", class_name)
        return _project_mixture_substance(record, class_name)

    instance = {"type": get_linkml_chemical_class(class_name) or class_name}
    for key, value in (params or {}).items():
        if _is_blank(value) or key in {"chemical_type", "type"}:
            continue
        slot = get_linkml_chemical_slot(class_name, key)
        if slot in chemical_fields(class_name):
            instance[slot] = chemical_record_to_instance(value, mixture_item=_mixture_relation(slot, class_name))
        elif slot == KEY_PREPARATION_PROCEDURE and isinstance(value, dict):
            instance[slot] = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            instance[slot] = value
    return instance


def chemical_record_to_instance(chemical: Any, *, mixture_item: bool | None = None) -> Any:
    """Project a domain or exported chemical record onto an ADM instance.

    ``mixture_item=True`` is used for ``Mixture.chemical_list`` entries, which
    are MixtureConstituent objects. Other Chemical Entity slots (substance_list,
    solvent, chemical, substance) keep the concrete entity type, including
    All current ChemicalEntity subtypes are retained; composition entries carry
    concentration on the MixtureConstituent wrapper.
    """
    if chemical is None:
        return None
    if isinstance(chemical, list):
        converted = [
            chemical_record_to_instance(item, mixture_item=mixture_item) for item in chemical
        ]
        return [item for item in converted if item is not None]
    if not isinstance(chemical, dict):
        return chemical

    if "slots" in chemical or chemical.get("linkml_class") or chemical.get("source_chemical"):
        class_name = canonical_chemical_name(
            chemical.get("linkml_class")
            or chemical.get("source_chemical")
            or chemical.get("type")
            or "Substance"
        )
        merged = dict(chemical.get("slots") or {})
        extra = chemical.get("source_metadata") or {}
        if isinstance(extra, dict):
            for key, value in extra.items():
                merged.setdefault(key, value)
        return _finish_chemical_instance(class_name, merged, mixture_item=bool(mixture_item))

    class_name = _record_chemical_class(chemical)
    as_mixture = mixture_item is True or (
        mixture_item is not False and _looks_like_mixture_substance(chemical, class_name)
    )
    if as_mixture:
        return _project_mixture_substance(chemical, class_name)

    params = dict(chemical.get("params") or {})
    if not params:
        params = {key: value for key, value in chemical.items() if key not in _CHEMICAL_WRAPPER_KEYS}
    else:
        for key, value in chemical.items():
            if key not in _CHEMICAL_WRAPPER_KEYS:
                params.setdefault(key, value)

    if not class_name:
        class_name = "Substance"
    return _finish_chemical_instance(class_name, params)


def flatten_exported_instance(node: Any) -> Any:
    """Strip exporter envelope keys and keep unknown slots for closed validation."""
    if isinstance(node, list):
        return [flatten_exported_instance(item) for item in node]
    if not isinstance(node, dict):
        return node

    if any(
        key in node
        for key in ("slots", "linkml_class", "source_action", "source_chemical", "attached_chemicals")
    ):
        instance: dict[str, Any] = {}
        type_name = node.get("linkml_class") or node.get("type")
        if type_name:
            instance["type"] = type_name
        for key, value in (node.get("slots") or {}).items():
            instance[key] = flatten_exported_instance(value)
        extra = node.get("source_metadata") or {}
        if isinstance(extra, dict):
            for key, value in extra.items():
                instance.setdefault(key, flatten_exported_instance(value))
        attached = [flatten_exported_instance(chem) for chem in (node.get("attached_chemicals") or [])]
        if attached:
            slot_name = chemical_slot_for_action(node.get("source_action"))
            if slot_name and slot_name not in instance:
                instance[slot_name] = attached
        for key, value in node.items():
            if key in EXPORTER_ENVELOPE_KEYS:
                continue
            instance.setdefault(key, flatten_exported_instance(value))
        return instance

    return {key: flatten_exported_instance(value) for key, value in node.items()}


def _slot_value_to_param_value(slot: str, value: Any) -> Any:
    if slot in {"uses_separation_method", "uses_washing_method"} and isinstance(value, dict):
        return value.get("id")
    if slot in {"has_open_flame"}:
        return boolean_to_text(value)
    if slot in {
        "has_step_duration",
        "has_stirring_speed",
        "has_flow_rate",
        "has_pressure",
        "has_heat_ramp",
        "has_microwave_power",
        "has_vessel_volume",
        "has_minimum_particle_size",
        "has_maximum_particle_size",
    }:
        return quantity_to_text(value)
    if slot == "has_atmosphere_type":
        # Build gases as list of chemical objects for new internal format
        return build_gases(value)
    if slot == "has_physical_state":
        return physical_state_to_text(value)
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


def _convert_linkml_chemical_slots(slots: dict[str, Any], source_chemical: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for slot, value in (slots or {}).items():
        if slot == "type":
            continue
        param_key = CHEMICAL_SLOT_TO_PARAM.get(slot, slot)
        if source_chemical == "Polymer" and slot == "smiles":
            param_key = KEY_BIGSMILES

        if slot in {"has_volume", "has_mass", "has_amount"}:
            params[param_key] = quantity_to_text(value)
            continue

        if slot == "has_physical_state":
            params[param_key] = physical_state_to_text(value)
            continue

        if slot == KEY_PREPARATION_PROCEDURE and isinstance(value, str):
            try:
                decoded = json.loads(value)
                value = decoded if isinstance(decoded, dict) else value
            except (ValueError, TypeError):
                pass
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
        if slot == "type":
            continue
        param_key = STEP_SLOT_TO_PARAM.get(slot, slot)
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
        source_chemical = chem.get("source_chemical")
        chem_params = _convert_linkml_chemical_slots(chem.get("slots", {}), source_chemical)
        attached_chemicals.append(
            {
                "block_id": chem.get("block_id", 0),
                "chemical": source_chemical
                or LINKML_CHEMICAL_TO_SOURCE.get(chem.get("linkml_class"), chem.get("linkml_class") or "Chemical"),
                "params": chem_params,
            }
        )

    if not attached_chemicals and step_payload["action"] == "Add":
        for entity in step_payload["params"].get("chemical", []) or []:
            if isinstance(entity, dict):
                name = entity.get("type") or entity.get("chemical_type")
                attached_chemicals.append({"chemical": name,
                    "params": _convert_linkml_chemical_slots(entity, name)})
    if attached_chemicals and step_payload["action"] == "Add":
        # The canvas owns attached Add chemicals; do not also retain an inline copy.
        step_payload["params"].pop("chemical", None)

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
        for step in activity.get("laboratory_actions", activity.get("has_synthesis_step", [])) or []:
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
    """Project action params onto Action Data Model slots.

    Unknown keys are preserved so closed-schema validation can reject them
    instead of silently dropping undeclared content.
    """
    params = migrate_action_params(action_name, params)
    slots: dict[str, Any] = {}
    for key, value in params.items():
        if _is_blank(value):
            continue
        slot = FIELD_TO_LINKML_SLOT.get(key, key)
        if key == KEY_OPEN_FLAME:
            boolean_value = normalize_boolean(value)
            slots[slot] = "True" if boolean_value is True else ("False" if boolean_value is False else value)
        elif slot in chemical_fields(canonical_action_name(action_name)):
            slots[slot] = chemical_record_to_instance(value, mixture_item=_mixture_relation(slot, canonical_action_name(action_name)))
        else:
            slots[slot] = value
    return slots


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


def build_gases(value: Any) -> list[dict[str, Any]] | None:
    """Build list of gas chemical objects from LinkML atmosphere list.
    
    Converts LinkML has_atmosphere_type (list of gas names) into internal
    representation (list of chemical objects with minimal required fields).
    
    Gas names MUST be one of: 'air', 'inert', 'nitrogen', 'argon', 'hydrogen', 'vacuum', 'autogeneous', 'oxygen'
    """
    if _is_blank(value):
        return None
    
    if isinstance(value, list):
        gases = []
        for item in value:
            if _is_blank(item):
                continue
            # Skip if already a chemical object (shouldn't happen in imports, but handle it)
            if isinstance(item, dict) and "chemical_type" in item:
                # Ensure it has a name
                if not item.get(KEY_NAME, "").strip():
                    print(f"[build_gases] Warning: Gas chemical object missing {KEY_NAME}")
                gases.append(item)
                continue
            # Convert gas name string to chemical object
            gas_name = str(item).strip()
            if gas_name:
                gases.append({
                    "chemical_type": "Molecule",
                    KEY_NAME: gas_name,
                    KEY_FORMULA: "",
                    KEY_SMILES: "",
                    KEY_INCHI: "",
                })
        return gases if gases else None
    
    # Handle single string value
    gas_name = str(value).strip()
    if gas_name:
        return [{
            "chemical_type": "Molecule",
            KEY_NAME: gas_name,
            KEY_FORMULA: "",
            KEY_SMILES: "",
            KEY_INCHI: "",
        }]
    
    return None


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
    "has_physical_state": ("PhysicalState", normalize_physical_state),
    "has_heat_ramp": ("HeatRamp", build_generic_quantitative_attribute),
    "has_microwave_power": ("MicrowavePower", build_generic_quantitative_attribute),
    "has_stirring_speed": ("StirringSpeed", build_generic_quantitative_attribute),
    "has_vessel_volume": ("Volume", build_generic_quantitative_attribute),
    "has_minimum_particle_size": ("ParticleSize", build_generic_quantitative_attribute),
    "has_maximum_particle_size": ("ParticleSize", build_generic_quantitative_attribute),
    "has_intermittent_amount": ("AmountOfSubstance", build_amount_of_substance),
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
    """Keep Action Data Model string/enum slots as-is.

    Legacy export slot names still go through structured builders so old
    payloads can be read, but new validation instances are not rewritten into
    MaterialEntity hashes or untyped stubs.
    """
    if not slots:
        return slots

    converted = {}
    for slot_name, value in slots.items():
        if slot_name in SLOT_BUILDERS:
            _, builder = SLOT_BUILDERS[slot_name]
            built_value = builder(value)
            converted[slot_name] = built_value if built_value is not None else value
        else:
            converted[slot_name] = value
    return converted



def action_to_linkml_dict(action_name: str, params: dict[str, Any], chemicals: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload = {
        "source_action": action_name,
        "linkml_class": get_linkml_step_class(action_name),
        "slots": normalize_action_to_linkml(action_name, params or {}),
    }
    slots = payload.get("slots") or {}
    if chemicals:
        payload["attached_chemicals"] = chemicals
        action_name = canonical_action_name(action_name)
        slot_name = chemical_slot_for_action(action_name)
        if slot_name:
            existing = slots.get(slot_name)
            if action_name != "ContinuousAddition" or existing is None or isinstance(existing, str):
                slots[slot_name] = chemical_record_to_instance(chemicals)
        payload["slots"] = slots
    return payload


def chemical_to_linkml_dict(chemical_name: str, params: dict[str, Any]) -> dict[str, Any]:
    chemical_name = canonical_chemical_name(chemical_name)
    slots: dict[str, Any] = {}
    for key, value in (params or {}).items():
        if _is_blank(value):
            continue
        slot = CHEMICAL_FIELD_TO_LINKML_SLOT.get(key, key)
        if slot in chemical_fields(chemical_name):
            slots[slot] = chemical_record_to_instance(value, mixture_item=_mixture_relation(slot, chemical_name))
        else:
            slots[slot] = value

    return {
        "source_chemical": chemical_name,
        "linkml_class": get_linkml_chemical_class(chemical_name),
        "slots": slots,
    }
