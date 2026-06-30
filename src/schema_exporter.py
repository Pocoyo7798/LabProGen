"""
schema_exporter.py
Purpose: Build canonical LinkML-oriented export payloads from the internal
protocol representation. Responsibilities include assembling activities and
steps, normalizing exporter-only metadata for strict validation, running the
official LinkML validator in strict mode, and producing an optimized
registry+reference projection.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any, Literal

from .config import DEFAULT_PROTOCOL_NAME
from .linkml_adapter import (
    normalize_action_to_linkml,
    convert_slots_to_linkml_objects,
    get_linkml_chemical_class,
    get_linkml_chemical_slot,
    get_linkml_slot,
    get_linkml_step_class,
)
from .schema_loader import build_validation_schema, load_linkml_schema, schema_summary, ensure_six_meta_path_importer_compatibility


@dataclass
class ExportSummary:
    activity_count: int
    step_count: int
    chemical_count: int
    unmapped_fields: int


ExportMode = Literal["strict", "optimized"]


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

    mapped_slots = convert_slots_to_linkml_objects(mapped_slots)

    return _clean_dict(
        {
            "id": chemical.get("block_id") or chemical_name,
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

    # Add any unmapped fields from params as additional slots
    for key, value in params.items():
        if _is_blank(value):
            continue
        if key in {"duration", "temperature", "add_type", "open_flame", "phase_to_keep", "method", "min_size", "max_size", "speed", "flow_rate", "pressure", "process", "ramp", "power", "recipient", "material", "volume", "substance_list", "continuous_add_type", "amount", "chemical"}:
            continue

        slot = get_linkml_slot(key, action_name=action_name)
        if slot and slot not in mapped_slots:
            mapped_slots[slot] = value
        elif not slot:
            source_metadata[key] = value

    # Special handling for Repeat and ContinuousAddition
    if action_name == "Repeat" and "amount" in params:
        mapped_slots["repetition_count"] = params.get("amount")
    elif action_name == "ContinuousAddition" and "amount" in params:
        mapped_slots["has_intermittent_amount"] = normalize_action_to_linkml(action_name, params).get("has_intermittent_amount") or params.get("amount")

    # Convert simple values to proper LinkML objects for complex-typed slots (only once)
    mapped_slots = convert_slots_to_linkml_objects(mapped_slots)

    step_payload = {
        "id": step.get("block_id") or action_name,
        "block_id": step.get("block_id"),
        "source_action": action_name,
        "linkml_class": get_linkml_step_class(action_name),
        "slots": mapped_slots,
        "attached_chemicals": [_convert_chemical(c) for c in step.get("chemicals", [])],
        "subproduct_branch": _convert_step(step["subproduct_branch"]) if isinstance(step.get("subproduct_branch"), dict) else None,
        "source_metadata": source_metadata or None,
    }
    if step.get("part_of_complex_action"):
        step_payload["part_of_complex_action"] = True
        if step.get("complex_group_id"):
            step_payload["complex_group_id"] = step.get("complex_group_id")
        if step.get("complex_action_name"):
            step_payload["complex_action_name"] = step.get("complex_action_name")

    return _clean_dict(step_payload)


def _collect_material_entities(activities: list) -> dict[str, dict]:
    """Collect all unique MaterialEntity objects from activities.
    
    Returns a mapping of entity_id -> entity object.
    Deduplicates entities that appear in multiple steps.
    """
    entities = {}
    
    def extract_value(slot_value):
        if isinstance(slot_value, dict):
            if "alternative_label" in slot_value and "entity_id" in slot_value:
                eid = slot_value.get("entity_id")
                if eid not in entities:
                    entities[eid] = slot_value
            for nested in slot_value.values():
                extract_value(nested)
        elif isinstance(slot_value, list):
            for item in slot_value:
                extract_value(item)

    def extract_from_slots(slots: dict):
        if not isinstance(slots, dict):
            return
        for slot_value in slots.values():
            extract_value(slot_value)
    
    for activity in activities:
        for step in activity.get("has_synthesis_step", []) or []:
            extract_from_slots(step.get("slots", {}))
            for chem in step.get("attached_chemicals", []) or []:
                extract_from_slots(chem.get("slots", {}))
    
    return entities


def _materialize_references(activities: list) -> list:
    """Replace MaterialEntity objects with entity_id references.
    
    Converts embedded objects to lightweight references pointing to
    the normalized entity registry.
    """
    def replace_value(value):
        if isinstance(value, dict):
            if "alternative_label" in value and "entity_id" in value:
                return {"entity_id": value.get("entity_id")}
            return {k: replace_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [replace_value(item) for item in value]
        return value

    def replace_in_slots(slots: dict):
        if not isinstance(slots, dict):
            return slots
        return {key: replace_value(value) for key, value in slots.items()}
    
    materialized = []
    for activity in activities:
        new_activity = copy.deepcopy(activity)
        for step in new_activity.get("has_synthesis_step", []) or []:
            step["slots"] = replace_in_slots(step.get("slots", {}))
            for chem in step.get("attached_chemicals", []) or []:
                chem["slots"] = replace_in_slots(chem.get("slots", {}))
        materialized.append(new_activity)
    
    return materialized


def _normalize_linkml_instance(node: Any) -> Any:
    """Strip exporter-only metadata and return a strict LinkML instance.

    This keeps the semantic conversion logic in one place and allows the same
    canonical export data to be validated in strict mode and optionally
    transformed into an optimized internal representation.
    """
    if isinstance(node, list):
        return [_normalize_linkml_instance(item) for item in node]
    if not isinstance(node, dict):
        return node

    normalized: dict[str, Any] = {}
    slot_values = node.get("slots") if isinstance(node.get("slots"), dict) else {}

    for key, value in node.items():
        if key in {
            "id",
            "block_id",
            "source_action",
            "linkml_class",
            "source_metadata",
            "source_chemical",
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
        }:
            continue
        normalized[key] = _normalize_linkml_instance(value)

    for slot_name, slot_value in slot_values.items():
        normalized[slot_name] = _normalize_linkml_instance(slot_value)

    return normalized


def _build_protocol_export(protocol_data: dict) -> tuple[dict, list[dict], int, int, int]:
    """Convert the domain protocol into canonical LinkML-oriented activities.

    The canonical activities preserve inline MaterialEntity objects and act as
    the single source of truth for both strict and optimized export modes.
    """
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
                    "id": flow.get("flow_id") or flow.get("type") or "activity",
                    "class": "LabSynthesisActivity",
                    "flow_id": flow.get("flow_id"),
                    "flow_type": flow.get("type"),
                    "is_explicit_first": flow.get("is_explicit_first"),
                    "chemical_block_id": flow.get("chemical_block_id"),
                    "has_synthesis_step": converted_steps,
                }
            )
        )

    base_payload = {
        "linkml_schema": schema_summary(schema),
        "source_protocol_name": protocol_data.get("protocol_name", DEFAULT_PROTOCOL_NAME),
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

    return base_payload, activities, total_steps, total_chemicals, unmapped_fields


def _activity_without_complex_steps(activity: dict) -> dict:
    """Return an activity copy excluding steps that belong to a complex action."""
    filtered = copy.deepcopy(activity)
    filtered["has_synthesis_step"] = [
        step
        for step in (activity.get("has_synthesis_step") or [])
        if not step.get("part_of_complex_action")
    ]
    return filtered


def _validate_strict_mode(activities: list[dict]) -> None:
    """Enforce strict schema constraints against the canonical export data."""
    try:
        ensure_six_meta_path_importer_compatibility()
        from linkml.validator import validate as linkml_validate
    except Exception as exc:  # pragma: no cover - dependency error surface
        raise RuntimeError(f"LinkML validator is unavailable: {exc}") from exc

    schema = build_validation_schema()
    for idx, activity in enumerate(activities):
        instance = _normalize_linkml_instance(_activity_without_complex_steps(activity))
        report = linkml_validate(instance, schema=schema, target_class="LabSynthesisActivity", strict=True)
        results = getattr(report, "results", []) or []
        if results:
            first = results[0]
            raise ValueError(f"Strict LinkML validation failed for activity {idx}: {getattr(first, 'message', first)}")


def _build_optimized_export(strict_payload: dict) -> dict:
    """Derive an optimized graph-like view from the strict validated export."""
    activities = strict_payload.get("activities", []) if isinstance(strict_payload, dict) else []
    material_registry = _collect_material_entities(activities)
    materialized_activities = _materialize_references(activities)

    def _count_refs(value: Any) -> int:
        if isinstance(value, dict):
            if set(value.keys()) == {"entity_id"}:
                return 1
            return sum(_count_refs(v) for v in value.values())
        if isinstance(value, list):
            return sum(_count_refs(item) for item in value)
        return 0

    optimized_payload = copy.deepcopy(strict_payload)
    optimized_payload["activities"] = materialized_activities
    optimized_payload["materials"] = material_registry
    optimized_payload["summary"]["unique_materials"] = len(material_registry)
    optimized_payload["summary"]["reference_count"] = sum(_count_refs(activity) for activity in materialized_activities)

    return optimized_payload


def _expand_optimized_export(optimized_payload: dict) -> dict:
    """Reconstruct a strict-like payload from an optimized export."""
    if not isinstance(optimized_payload, dict):
        return optimized_payload

    materials = optimized_payload.get("materials", {}) if isinstance(optimized_payload.get("materials"), dict) else {}

    def expand_value(value: Any) -> Any:
        if isinstance(value, dict):
            if set(value.keys()) == {"entity_id"}:
                entity_id = value.get("entity_id")
                return copy.deepcopy(materials.get(entity_id, value))
            return {k: expand_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand_value(item) for item in value]
        return value

    reconstructed = copy.deepcopy(optimized_payload)
    reconstructed.pop("materials", None)
    reconstructed["activities"] = expand_value(reconstructed.get("activities", []))
    summary = reconstructed.get("summary") if isinstance(reconstructed.get("summary"), dict) else None
    if summary is not None:
        summary.pop("unique_materials", None)
        summary.pop("reference_count", None)

    return reconstructed


def convert_protocol_to_linkml(protocol_data: dict, mode: ExportMode = "strict") -> dict:
    """Convert the protocol into strict or optimized LinkML-oriented output.

    Strict mode is the default and emits the schema-compliant canonical export.
    Optimized mode derives a normalized registry + references view from the
    same canonical data, without introducing a second conversion pipeline.
    """
    strict_payload, activities, _, _, _ = _build_protocol_export(protocol_data)

    # Remove embedded application snapshot to avoid duplicating the internal
    # protocol within the semantic LinkML export. Consumers should reconstruct
    # the internal protocol from the semantic fields when needed.
    strict_payload.pop("source_protocol", None)

    if mode == "strict":
        _validate_strict_mode(activities)
        return strict_payload

    if mode == "optimized":
        optimized = _build_optimized_export(strict_payload)
        # ensure optimized export also does not contain the original protocol
        optimized.pop("source_protocol", None)
        return optimized

    raise ValueError("mode must be either 'strict' or 'optimized'")


def summarize_linkml_export(payload: dict) -> ExportSummary:
    summary = payload.get("summary", {}) if isinstance(payload, dict) else {}
    return ExportSummary(
        activity_count=int(summary.get("activity_count", 0)),
        step_count=int(summary.get("step_count", 0)),
        chemical_count=int(summary.get("chemical_count", 0)),
        unmapped_fields=int(summary.get("unmapped_fields", 0)),
    )
