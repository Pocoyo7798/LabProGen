from __future__ import annotations

import copy
from dataclasses import dataclass

from .linkml_adapter import normalize_action_to_linkml
from .schema_loader import load_linkml_schema, schema_summary
from .schema_mapping import (
    get_linkml_chemical_class,
    get_linkml_chemical_slot,
    get_linkml_slot,
    get_linkml_step_class,
)


@dataclass
class ExportSummary:
    activity_count: int
    step_count: int
    chemical_count: int
    unmapped_fields: int


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _clean_dict(d: dict) -> dict:
    cleaned = {}
    for key, value in d.items():
        if isinstance(value, dict):
            nested = _clean_dict(value)
            if not _is_blank(nested):
                cleaned[key] = nested
        elif isinstance(value, list):
            nested_list = []
            for item in value:
                if isinstance(item, dict):
                    item = _clean_dict(item)
                if not _is_blank(item):
                    nested_list.append(item)
            if nested_list:
                cleaned[key] = nested_list
        elif not _is_blank(value):
            cleaned[key] = value
    return cleaned


def _convert_chemical(chemical: dict) -> dict:
    chemical_name = chemical.get("chemical", "")
    params = chemical.get("params", {}) or {}
    mapped_slots: dict[str, object] = {}
    source_metadata: dict[str, object] = {}

    for key, value in params.items():
        if _is_blank(value):
            continue

        slot = get_linkml_chemical_slot(chemical_name, key) or get_linkml_slot(key, action_name=None)

        if slot:
            mapped_slots[slot] = value
        else:
            source_metadata[key] = value

    return _clean_dict(
        {
            "block_id": chemical.get("block_id"),
            "source_chemical": chemical_name,
            "linkml_class": get_linkml_chemical_class(chemical_name),
            "slots": mapped_slots,
            "source_metadata": source_metadata or None,
        }
    )


def _convert_step(step: dict) -> dict:
    action_name = step.get("action", "")
    params = step.get("params", {}) or {}
    mapped_slots: dict[str, object] = normalize_action_to_linkml(action_name, params)
    source_metadata: dict[str, object] = {}

    for key, value in params.items():
        if _is_blank(value):
            continue
        if key in {"duration", "temperature", "add_type", "open_flame", "phase_to_keep", "method", "min_size", "max_size", "stir_type", "speed", "gases", "flow_rate", "pressure", "process", "ramp", "power", "recipient", "material", "volume", "substance_list", "continuous_add_type", "amount", "chemical"}:
            continue

        slot = get_linkml_slot(key, action_name=action_name)
        if slot and slot not in mapped_slots:
            mapped_slots[slot] = value
        elif not slot:
            source_metadata[key] = value

    step_payload = {
        "block_id": step.get("block_id"),
        "source_action": action_name,
        "linkml_class": get_linkml_step_class(action_name),
        "slots": mapped_slots,
        "attached_chemicals": [_convert_chemical(c) for c in step.get("chemicals", [])],
        "subproduct_branch": _convert_step(step["subproduct_branch"]) if isinstance(step.get("subproduct_branch"), dict) else None,
        "source_metadata": source_metadata or None,
    }

    if action_name == "Repeat" and "amount" in params:
        step_payload["slots"]["repetition_count"] = params.get("amount")
    elif action_name == "ContinuousAddition" and "amount" in params:
        step_payload["slots"]["has_intermittent_amount"] = normalize_action_to_linkml(action_name, params).get("has_intermittent_amount") or params.get("amount")

    return _clean_dict(step_payload)


def convert_protocol_to_linkml(protocol_data: dict) -> dict:
    schema = load_linkml_schema()
    flows = protocol_data.get("flows", []) if isinstance(protocol_data, dict) else []

    activities = []
    total_steps = 0
    total_chemicals = 0
    unmapped_fields = 0

    for flow in flows:
        converted_steps = []
        for step in flow.get("steps", []):
            converted_step = _convert_step(step)
            converted_steps.append(converted_step)
            total_steps += 1
            total_chemicals += len(step.get("chemicals", []))
            unmapped_fields += len(converted_step.get("source_metadata", {}) or {})
            for chem in step.get("chemicals", []):
                unmapped_fields += len(_convert_chemical(chem).get("source_metadata", {}) or {})

        activities.append(
            _clean_dict(
                {
                    "class": "LabSynthesisActivity",
                    "flow_id": flow.get("flow_id"),
                    "flow_type": flow.get("type"),
                    "is_explicit_first": flow.get("is_explicit_first"),
                    "chemical_block_id": flow.get("chemical_block_id"),
                    "has_synthesis_step": converted_steps,
                }
            )
        )

    payload = {
        "linkml_schema": schema_summary(schema),
        "source_protocol_name": protocol_data.get("protocol_name", "laboratory procedure"),
        "schema_profile": schema.get("name", ""),
        "class": "LabSynthesisActivity",
        "activities": activities,
        "summary": {
            "activity_count": len(activities),
            "step_count": total_steps,
            "chemical_count": total_chemicals,
            "unmapped_fields": unmapped_fields,
        },
        "source_protocol": copy.deepcopy(protocol_data),
    }

    return payload


def summarize_linkml_export(payload: dict) -> ExportSummary:
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return ExportSummary(
        activity_count=int(summary.get("activity_count", 0)),
        step_count=int(summary.get("step_count", 0)),
        chemical_count=int(summary.get("chemical_count", 0)),
        unmapped_fields=int(summary.get("unmapped_fields", 0)),
    )
