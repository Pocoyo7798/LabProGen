from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .config import (
    KEY_ADD_TYPE,
    KEY_AMOUNT,
    KEY_CHEMICAL,
    KEY_CONTINUOUS_ADD_TYPE,
    KEY_DURATION,
    KEY_FLOW_RATE,
    KEY_GASES,
    KEY_METHOD,
    KEY_MATERIAL,
    KEY_MAX_SIZE,
    KEY_MIN_SIZE,
    KEY_OPEN_FLAME,
    KEY_PHASE,
    KEY_POWER,
    KEY_PRESSURE,
    KEY_PROCESS,
    KEY_QUANTITY,
    KEY_RECIPIENT,
    KEY_RAMP,
    KEY_SPEED,
    KEY_STIR_TYPE,
    KEY_SUBSTANCE,
    KEY_SUBSTANCE_LIST,
    KEY_TEMPERATURE,
    KEY_VOLUME,
)


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


def stir_to_linkml(params: dict[str, Any]) -> dict[str, Any]:
    return {
        "has_step_duration": _quantity_or_raw(params.get(KEY_DURATION)),
        "has_stirring_speed": _quantity_or_raw(params.get(KEY_SPEED)),
        "stirring_type": params.get(KEY_STIR_TYPE),
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
    "Stir": stir_to_linkml,
    "Separate": separate_to_linkml,
    "ChangeAtmosphere": change_atmosphere_to_linkml,
    "ChangeTemperature": change_temperature_to_linkml,
    "ChangeRecipient": change_recipient_to_linkml,
    "Sieve": sieve_to_linkml,
    "Repeat": repeat_to_linkml,
    "ContinuousAddition": continuous_addition_to_linkml,
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
    "stirring_type": KEY_STIR_TYPE,
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


def _convert_linkml_step_slots(slots: dict[str, Any]) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for slot, value in (slots or {}).items():
        param_key = STEP_SLOT_TO_PARAM.get(slot)
        if not param_key:
            continue

        params[param_key] = _slot_value_to_param_value(slot, value)

    return params


def convert_linkml_to_protocol(linkml_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(linkml_payload, dict):
        return {"protocol_name": "laboratory procedure", "total_flows": 0, "flows": []}

    source_protocol = linkml_payload.get("source_protocol")
    if isinstance(source_protocol, dict) and source_protocol:
        return source_protocol

    flows: list[dict[str, Any]] = []
    activities = linkml_payload.get("activities", []) or []

    for idx, activity in enumerate(activities, start=1):
        steps: list[dict[str, Any]] = []
        for step in activity.get("has_synthesis_step", []) or []:
            step_payload: dict[str, Any] = {
                "block_id": step.get("block_id", 0),
                "action": step.get("source_action") or step.get("linkml_class") or "Add",
                "params": _convert_linkml_step_slots(step.get("slots", {})),
            }

            attached_chemicals = []
            for chem in step.get("attached_chemicals", []) or []:
                chem_params = _convert_linkml_chemical_slots(chem.get("slots", {}))
                attached_chemicals.append(
                    {
                        "block_id": chem.get("block_id", 0),
                        "chemical": chem.get("source_chemical") or chem.get("linkml_class") or "Chemical",
                        "params": chem_params,
                    }
                )

            if attached_chemicals:
                step_payload["chemicals"] = attached_chemicals

            sub_branch = step.get("subproduct_branch")
            if isinstance(sub_branch, dict):
                # preserve nested flows recursively if present
                step_payload["subproduct_branch"] = {
                    "block_id": sub_branch.get("block_id", 0),
                    "action": sub_branch.get("source_action") or sub_branch.get("linkml_class") or "SubProductCreation",
                    "params": _convert_linkml_step_slots(sub_branch.get("slots", {})),
                }

            steps.append(step_payload)

        flows.append(
            {
                "flow_id": activity.get("flow_id", idx),
                "type": activity.get("flow_type", "horizontal"),
                "is_explicit_first": bool(activity.get("is_explicit_first", False)),
                "steps": steps,
            }
        )

    return {
        "protocol_name": linkml_payload.get("source_protocol_name", "laboratory procedure"),
        "total_flows": len(flows),
        "flows": flows,
    }


def normalize_action_to_linkml(action_name: str, params: dict[str, Any]) -> dict[str, Any]:
    adapter = ACTION_TO_ADAPTER.get(action_name)
    if not adapter:
        return {}
    return adapter(params or {})
