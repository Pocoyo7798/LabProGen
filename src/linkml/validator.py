"""
schema_validator.py
Purpose: Strict Action Data Model validation for exported procedures.
Unknown classes, unknown fields, missing required slots, wrong types, and
invalid enums are errors. There is no skip path for unmapped actions or
undeclared content.
"""

from dataclasses import dataclass
from collections import Counter

from src.core.config import canonical_action_name, canonical_chemical_name
from .adapter import (
    CHEMICAL_OBJECT_SLOTS,
    COMPLEX_ACTION_MARKER,
    ENTITY_CLASS_RANGES,
    get_linkml_chemical_class,
    get_linkml_step_class,
)
from .loader import (
    build_validation_schema,
    class_slot_constraints,
    ensure_six_meta_path_importer_compatibility,
    listed_action_classes,
    listed_chemical_classes,
    load_linkml_schema,
)


@dataclass
class ValidationMessage:
    level: str
    code: str
    message: str
    context: dict


def _message_from_linkml_result(result, fallback_level: str = "error") -> ValidationMessage:
    level = (
        getattr(result, "severity", None)
        or getattr(result, "level", None)
        or getattr(result, "status", None)
        or fallback_level
    )
    level_text = str(level).lower()
    if level_text.startswith("severity."):
        level_text = level_text.split(".", 1)[1]
    if level_text in {"fail", "fatal", "critical"}:
        level_text = "error"
    code = (
        getattr(result, "type", None)
        or getattr(result, "rule", None)
        or getattr(result, "code", None)
        or result.__class__.__name__
    )
    message = getattr(result, "message", None) or str(result)
    context = {
        key: value
        for key, value in {
            "path": getattr(result, "path", None),
            "instance": getattr(result, "instance", None),
            "source_class": getattr(result, "source_class", None),
            "target_class": getattr(result, "target_class", None),
            "slot": getattr(result, "slot", None),
        }.items()
        if value is not None
    }
    return ValidationMessage(level=level_text, code=str(code), message=message, context=context)


def _is_blank(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) == 0
    return False


def _error(code: str, message: str, **context) -> ValidationMessage:
    return ValidationMessage(level="error", code=code, message=message, context=context)


def _python_instance_checks(instance: dict, class_name: str, schema: dict, context: dict) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    constraints = class_slot_constraints(class_name, schema)
    allowed = constraints.get("allowed") or set()
    required = constraints.get("required") or set()
    enums = constraints.get("enums") or {}
    ranges = constraints.get("ranges") or {}
    multivalued = constraints.get("multivalued") or {}

    for key, value in instance.items():
        if key == "type":
            continue
        if key not in allowed:
            messages.append(
                _error(
                    "validation.unknown_field",
                    f"Unknown field '{key}' is not declared on '{class_name}'.",
                    field=key,
                    target_class=class_name,
                    **context,
                )
            )
            continue

        expected_range = ranges.get(key)
        is_multi = bool(multivalued.get(key))
        if expected_range in ENTITY_CLASS_RANGES:
            values = value if isinstance(value, list) else [value]
            if is_multi and not isinstance(value, list):
                messages.append(
                    _error(
                        "validation.wrong_type",
                        f"Field '{key}' on '{class_name}' must be a list of {expected_range} objects.",
                        field=key,
                        target_class=class_name,
                        **context,
                    )
                )
            for item in values:
                if isinstance(item, str) or not isinstance(item, dict):
                    messages.append(
                        _error(
                            "validation.wrong_type",
                            f"Field '{key}' on '{class_name}' must be a {expected_range} object, not {type(item).__name__}.",
                            field=key,
                            target_class=class_name,
                            **context,
                        )
                    )
        elif expected_range and expected_range not in schema.get("enums", {}):
            if expected_range == "string" and isinstance(value, (dict, list)):
                messages.append(
                    _error(
                        "validation.wrong_type",
                        f"Field '{key}' on '{class_name}' must be a string, not {type(value).__name__}.",
                        field=key,
                        target_class=class_name,
                        **context,
                    )
                )

        if key in enums and not _is_blank(value):
            text = str(value)
            if text not in enums[key]:
                messages.append(
                    _error(
                        "validation.invalid_enum",
                        f"Invalid value '{value}' for '{key}' on '{class_name}'.",
                        field=key,
                        target_class=class_name,
                        **context,
                    )
                )

    skip_required = set()
    if context.get("part_of_complex_action") and "source_chemical" not in context:
        skip_required = CHEMICAL_OBJECT_SLOTS
    for slot_name in required:
        if slot_name in skip_required:
            continue
        if _is_blank(instance.get(slot_name)):
            messages.append(
                _error(
                    "validation.required_field_missing",
                    f"Required field '{slot_name}' is missing on '{class_name}'.",
                    field=slot_name,
                    target_class=class_name,
                    **context,
                )
            )

    return messages


def _missing_required_chemical_entity_slot(instance: dict, class_name: str, schema: dict) -> bool:
    constraints = class_slot_constraints(class_name, schema)
    required = constraints.get("required") or set()
    return any(slot in CHEMICAL_OBJECT_SLOTS and _is_blank(instance.get(slot)) for slot in required)


def _nested_entity_class(item: dict, default_class: str) -> str:
    type_name = item.get("type") or item.get("linkml_class") or default_class
    if default_class == "MixtureSubstance":
        return "MixtureSubstance"
    return canonical_chemical_name(type_name) or type_name


def _walk_nested_entities(instance: dict, class_name: str, schema: dict, context: dict) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    constraints = class_slot_constraints(class_name, schema)
    ranges = constraints.get("ranges") or {}
    for slot_name, expected_range in ranges.items():
        if expected_range not in ENTITY_CLASS_RANGES:
            continue
        value = instance.get(slot_name)
        if _is_blank(value):
            continue
        items = value if isinstance(value, list) else [value]
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            nested_class = _nested_entity_class(item, expected_range)
            nested_context = dict(context)
            if slot_name in CHEMICAL_OBJECT_SLOTS:
                nested_context["chemical_index"] = index
                nested_context["source_chemical"] = nested_class
            messages.extend(_python_instance_checks(item, nested_class, schema, nested_context))
            messages.extend(_walk_nested_entities(item, nested_class, schema, nested_context))
    return messages


def _run_linkml_validate(instance: dict, class_name: str, schema: dict, linkml_validate, context: dict) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    try:
        report = linkml_validate(instance, schema=schema, target_class=class_name, strict=True)
        results = getattr(report, "results", []) or []
        for result in results:
            msg = _message_from_linkml_result(result)
            if msg.level in {"info", "warning"}:
                msg.level = "error"
            msg.context.update(context)
            messages.append(msg)
    except Exception as exc:
        messages.append(
            _error(
                "linkml.validation_failed",
                f"LinkML validation failed for {class_name}: {exc}",
                target_class=class_name,
                **context,
            )
        )
    return messages


def validate_exported_activities(activities: list[dict]) -> list[ValidationMessage]:
    """Validate exporter-built activities against the closed Action Data Model."""
    try:
        ensure_six_meta_path_importer_compatibility()
        from linkml.validator import validate as linkml_validate
    except Exception as exc:
        return [
            _error(
                "linkml.unavailable",
                f"Official LinkML validator is unavailable: {exc}",
            )
        ]

    try:
        schema = build_validation_schema()
        from .exporter import _activity_without_complex_steps, _normalize_linkml_instance
    except Exception as exc:
        return [
            _error(
                "linkml.validation_prep_failed",
                f"Could not prepare LinkML validation input: {exc}",
            )
        ]

    messages: list[ValidationMessage] = []
    action_classes = listed_action_classes(schema)
    chemical_classes = listed_chemical_classes(schema)

    if not activities:
        messages.append(
            ValidationMessage(
                level="warning",
                code="linkml.no_activities",
                message="No activities were available for LinkML validation.",
                context={},
            )
        )
        return messages

    for activity_index, activity in enumerate(activities):
        filtered = _activity_without_complex_steps(activity)
        for step_index, step in enumerate(filtered.get("has_synthesis_step", []) or []):
            source_action = canonical_action_name(step.get("source_action") or "")
            context = {
                "activity_index": activity_index,
                "step_index": step_index,
                "source_action": source_action,
            }
            if step.get("part_of_complex_action"):
                context["part_of_complex_action"] = True
            if not source_action:
                messages.append(_error("mapping.missing_action", "Action name is missing.", **context))
                continue
            if source_action == COMPLEX_ACTION_MARKER:
                continue
            if source_action not in action_classes or not get_linkml_step_class(source_action):
                messages.append(
                    _error(
                        "mapping.unknown_action",
                        f"Action '{source_action}' is not defined in the Action Data Model.",
                        **context,
                    )
                )
                continue

            step_class = step.get("linkml_class") or get_linkml_step_class(source_action)
            instance = _normalize_linkml_instance(step)
            messages.extend(_python_instance_checks(instance, step_class, schema, context))
            messages.extend(_walk_nested_entities(instance, step_class, schema, context))
            skip_linkml = bool(
                context.get("part_of_complex_action")
                and _missing_required_chemical_entity_slot(instance, step_class, schema)
            )
            if not skip_linkml:
                messages.extend(_run_linkml_validate(instance, step_class, schema, linkml_validate, context))

            for chem_index, chem in enumerate(step.get("attached_chemicals", []) or []):
                chem_name = canonical_chemical_name(
                    chem.get("source_chemical") or chem.get("linkml_class") or ""
                )
                chem_context = {
                    **context,
                    "chemical_index": chem_index,
                    "source_chemical": chem_name,
                }
                if not chem_name:
                    messages.append(
                        _error(
                            "mapping.missing_chemical",
                            "Chemical entity class is missing.",
                            **chem_context,
                        )
                    )
                    continue
                if chem_name not in chemical_classes or not get_linkml_chemical_class(chem_name):
                    messages.append(
                        _error(
                            "mapping.unknown_chemical",
                            f"Chemical entity '{chem_name}' is not defined in the Action Data Model.",
                            **chem_context,
                        )
                    )
                    continue
                chem_class = chem.get("linkml_class") or get_linkml_chemical_class(chem_name)
                chem_instance = _normalize_linkml_instance(chem)
                messages.extend(_python_instance_checks(chem_instance, chem_class, schema, chem_context))
                messages.extend(_walk_nested_entities(chem_instance, chem_class, schema, chem_context))
                messages.extend(
                    _run_linkml_validate(chem_instance, chem_class, schema, linkml_validate, chem_context)
                )

    return messages


def validate_action_shadow(action_name: str, params: dict) -> list[ValidationMessage]:
    action_name = canonical_action_name(action_name)
    if action_name == COMPLEX_ACTION_MARKER:
        return []
    if not get_linkml_step_class(action_name):
        return [
            _error(
                "mapping.unknown_action",
                f"Action '{action_name}' is not defined in the Action Data Model.",
                action=action_name,
            )
        ]

    schema = load_linkml_schema()
    instance = {"type": action_name, **{key: value for key, value in (params or {}).items() if not _is_blank(value)}}
    return _python_instance_checks(instance, action_name, schema, {"action": action_name})


def validate_protocol_shadow(protocol_data: dict) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []
    try:
        _ = load_linkml_schema()
    except Exception as exc:
        return [
            _error(
                "schema.unavailable",
                f"LinkML schema could not be loaded: {exc}",
            )
        ]

    flows = protocol_data.get("flows", []) if isinstance(protocol_data, dict) else []
    for flow_idx, flow in enumerate(flows):
        for step_idx, step in enumerate(flow.get("steps", [])):
            action_name = step.get("action", "")
            params = step.get("params", {})
            for item in validate_action_shadow(action_name, params):
                item.context.update({"flow_index": flow_idx, "step_index": step_idx})
                messages.append(item)
    return messages


def validate_linkml_protocol(protocol_data: dict, target_class: str = "LabProcedure") -> list[ValidationMessage]:
    """Validate the exported protocol with the official LinkML validator."""
    try:
        ensure_six_meta_path_importer_compatibility()
        from linkml.validator import validate as linkml_validate  # noqa: F401
    except Exception as exc:
        return [
            _error(
                "linkml.unavailable",
                f"Official LinkML validator is unavailable: {exc}",
            )
        ]

    try:
        from .exporter import _build_protocol_export
        _, activities, _, _, _ = _build_protocol_export(protocol_data)
    except Exception as exc:
        return [
            _error(
                "linkml.validation_prep_failed",
                f"Could not prepare LinkML validation input: {exc}",
            )
        ]

    return validate_exported_activities(activities)


def summarize_validation_messages(messages: list[ValidationMessage]) -> dict:
    by_level = Counter()
    by_code = Counter()

    for msg in messages:
        by_level[msg.level] += 1
        by_code[msg.code] += 1

    return {
        "total": len(messages),
        "by_level": dict(sorted(by_level.items())),
        "by_code": dict(sorted(by_code.items())),
    }
