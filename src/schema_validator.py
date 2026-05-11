"""
schema_validator.py
Purpose: Provide convenience wrappers around the official LinkML validator
and a set of shadow/summary checks. Exposes functions to run strict and
non-strict validation on exporter-built instances and to convert validator
results into a compact project-friendly format.
"""

from dataclasses import dataclass
from collections import Counter

from .config import is_field_required
from .schema_loader import build_validation_schema, load_linkml_schema
from .schema_mapping import get_linkml_step_class


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
    return False


def validate_action_shadow(action_name: str, params: dict) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    if not get_linkml_step_class(action_name):
        messages.append(
            ValidationMessage(
                level="warning",
                code="mapping.missing_action",
                message=f"No LinkML step mapping found for action '{action_name}'.",
                context={"action": action_name},
            )
        )

    for key, value in (params or {}).items():
        if is_field_required(key, params=params, action_name=action_name) and _is_blank(value):
            messages.append(
                ValidationMessage(
                    level="warning",
                    code="validation.required_field_missing",
                    message=f"Required field '{key}' is blank for action '{action_name}'.",
                    context={"action": action_name, "field": key},
                )
            )

    return messages


def validate_protocol_shadow(protocol_data: dict) -> list[ValidationMessage]:
    messages: list[ValidationMessage] = []

    # Best-effort schema availability check for phase 2 shadow mode.
    try:
        _ = load_linkml_schema()
    except Exception as exc:
        messages.append(
            ValidationMessage(
                level="warning",
                code="schema.unavailable",
                message=f"LinkML schema could not be loaded: {exc}",
                context={},
            )
        )
        return messages

    flows = protocol_data.get("flows", []) if isinstance(protocol_data, dict) else []
    for flow_idx, flow in enumerate(flows):
        for step_idx, step in enumerate(flow.get("steps", [])):
            action_name = step.get("action", "")
            params = step.get("params", {})
            for item in validate_action_shadow(action_name, params):
                item.context.update({"flow_index": flow_idx, "step_index": step_idx})
                messages.append(item)

    return messages


def validate_linkml_protocol(protocol_data: dict, target_class: str = "LabSynthesisActivity") -> list[ValidationMessage]:
    """Validate the exported protocol with the official LinkML validator."""

    try:
        from linkml.validator import validate as linkml_validate
    except Exception as exc:
        return [
            ValidationMessage(
                level="error",
                code="linkml.unavailable",
                message=f"Official LinkML validator is unavailable: {exc}",
                context={},
            )
        ]

    try:
        from .schema_exporter import _normalize_linkml_instance, convert_protocol_to_linkml

        payload = convert_protocol_to_linkml(protocol_data)
        schema = build_validation_schema()
    except Exception as exc:
        return [
            ValidationMessage(
                level="error",
                code="linkml.validation_prep_failed",
                message=f"Could not prepare LinkML validation input: {exc}",
                context={},
            )
        ]

    messages: list[ValidationMessage] = []
    activities = payload.get("activities", []) if isinstance(payload, dict) else []
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

    def _validate_instance(instance, class_name: str, activity_index: int, step_index: int | None = None):
        try:
            report = linkml_validate(instance, schema=schema, target_class=class_name, strict=False)
            results = getattr(report, "results", []) or []
            for result in results:
                msg = _message_from_linkml_result(result)
                msg.context.update({"activity_index": activity_index})
                if step_index is not None:
                    msg.context["step_index"] = step_index
                messages.append(msg)
        except Exception as exc:
            ctx = {"activity_index": activity_index}
            if step_index is not None:
                ctx["step_index"] = step_index
            messages.append(
                ValidationMessage(
                    level="error",
                    code="linkml.validation_failed",
                    message=f"LinkML validation failed for {class_name}: {exc}",
                    context=ctx,
                )
            )

    for activity_index, activity in enumerate(activities):
        activity_instance = _normalize_linkml_instance(activity)
        _validate_instance(activity_instance, target_class, activity_index)

        for step_index, step in enumerate(activity.get("has_synthesis_step", []) or []):
            step_class = step.get("linkml_class") or "LabSynthesisStep"
            _validate_instance(_normalize_linkml_instance(step), step_class, activity_index, step_index)

            for chem_index, chem in enumerate(step.get("attached_chemicals", []) or []):
                chem_class = chem.get("linkml_class") or "ChemicalEntity"
                chem_ctx_index = step_index * 1000 + chem_index
                _validate_instance(_normalize_linkml_instance(chem), chem_class, activity_index, chem_ctx_index)

    return messages


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
