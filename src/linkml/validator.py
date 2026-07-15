"""
schema_validator.py
Purpose: Provide convenience wrappers around the official LinkML validator
and a set of shadow/summary checks. Exposes functions to run strict and
non-strict validation on exporter-built instances and to convert validator
results into a compact project-friendly format.
"""

from dataclasses import dataclass
from collections import Counter

from src.core.config import is_field_required, KEY_GASES
from .loader import build_validation_schema, load_linkml_schema, ensure_six_meta_path_importer_compatibility
from .adapter import get_linkml_step_class


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
    """Validate the exported protocol with the official LinkML validator.
    
    Best-effort validation: only validates actions that have LinkML mappings.
    Actions defined in Python/config but not in LinkML are skipped without error.
    """

    try:
        ensure_six_meta_path_importer_compatibility()
        from linkml.validator import validate as linkml_validate
    except Exception as exc:
        return [
            ValidationMessage(
                level="warning",
                code="linkml.unavailable",
                message=f"Official LinkML validator is unavailable: {exc}",
                context={},
            )
        ]

    try:
        from .exporter import _activity_without_complex_steps, _normalize_linkml_instance, convert_protocol_to_linkml

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

    def _has_linkml_mapping(source_action: str | None, linkml_class: str | None) -> bool:
        """Check if action has a LinkML mapping (best-effort validation)."""
        if not source_action and not linkml_class:
            return False
        # Check if action is mapped to LinkML
        if source_action and get_linkml_step_class(source_action):
            return True
        # If no source_action but has linkml_class, assume it's valid
        if linkml_class:
            return True
        return False

    def _validate_instance(instance, class_name: str, activity_index: int, step_index: int | None = None, source_action: str | None = None, source_chemical: str | None = None, chemical_index: int | None = None, export_step: dict | None = None):
        if source_action == "ChangeAtmosphere" and isinstance(export_step, dict):
            meta = export_step.get("source_metadata") or {}
            gases_value = meta.get(KEY_GASES)
            if _is_blank(gases_value):
                messages.append(
                    ValidationMessage(
                        level="error",
                        code="validation.required_field_missing",
                        message="At least one chemical is required in Gases for ChangeAtmosphere.",
                        context={"activity_index": activity_index, "step_index": step_index} if step_index is not None else {"activity_index": activity_index},
                    )
                )

        try:
            report = linkml_validate(instance, schema=schema, target_class=class_name, strict=False)
            results = getattr(report, "results", []) or []
            for result in results:
                msg = _message_from_linkml_result(result)
                msg.context.update({"activity_index": activity_index})
                if step_index is not None:
                    msg.context["step_index"] = step_index
                if source_action:
                    msg.context["source_action"] = source_action
                if source_chemical:
                    msg.context["source_chemical"] = source_chemical
                if chemical_index is not None:
                    msg.context["chemical_index"] = chemical_index

                # Try to infer a step index and action from the validator path,
                # which is especially important for activity-level validation
                # errors that point into nested has_synthesis_step entries.
                path = msg.context.get("path")
                if isinstance(path, str) and "has_synthesis_step" in path and "step_index" not in msg.context:
                    parts = [p for p in path.split("/") if p]
                    for idx, part in enumerate(parts):
                        if part == "has_synthesis_step" and idx + 1 < len(parts):
                            next_part = parts[idx + 1]
                            if next_part.isdigit():
                                inferred_step_index = int(next_part)
                                msg.context["step_index"] = inferred_step_index
                                if not msg.context.get("source_action"):
                                    steps = instance.get("has_synthesis_step", []) if isinstance(instance, dict) else []
                                    if inferred_step_index < len(steps):
                                        inferred_action = steps[inferred_step_index].get("source_action")
                                        if inferred_action:
                                            msg.context["source_action"] = inferred_action
                                        # try to infer attached chemical index if present in path
                                        for j in range(idx + 2, len(parts)):
                                            if parts[j] == "attached_chemicals" and j + 1 < len(parts) and parts[j+1].isdigit():
                                                inferred_chem_index = int(parts[j+1])
                                                msg.context["chemical_index"] = inferred_chem_index
                                                if not msg.context.get("source_chemical"):
                                                    attached = steps[inferred_step_index].get("attached_chemicals", []) or []
                                                    if 0 <= inferred_chem_index < len(attached):
                                                        msg.context["source_chemical"] = attached[inferred_chem_index].get("chemical")
                                                break
                messages.append(msg)
        except Exception as exc:
            ctx = {"activity_index": activity_index}
            if step_index is not None:
                ctx["step_index"] = step_index
            if source_action:
                ctx["source_action"] = source_action
            if source_chemical:
                ctx["source_chemical"] = source_chemical
            messages.append(
                ValidationMessage(
                    level="error",
                    code="linkml.validation_failed",
                    message=f"LinkML validation failed for {class_name}: {exc}",
                    context=ctx,
                )
            )

    for activity_index, activity in enumerate(activities):
        activity_instance = _normalize_linkml_instance(_activity_without_complex_steps(activity))
        _validate_instance(activity_instance, target_class, activity_index)

        for step_index, step in enumerate(activity.get("has_synthesis_step", []) or []):
            if step.get("part_of_complex_action"):
                continue

            source_action = step.get("source_action")
            linkml_class = step.get("linkml_class")
            
            # Skip validation if action is not mapped to LinkML (best-effort)
            if not _has_linkml_mapping(source_action, linkml_class):
                messages.append(
                    ValidationMessage(
                        level="info",
                        code="linkml.unmapped_action",
                        message=f"Action '{source_action}' has no LinkML mapping; validation skipped.",
                        context={"activity_index": activity_index, "step_index": step_index},
                    )
                )
                continue
            
            step_class = linkml_class or "LabSynthesisStep"
            _validate_instance(
                _normalize_linkml_instance(step),
                step_class,
                activity_index,
                step_index,
                source_action,
                export_step=step,
            )

            for chem_index, chem in enumerate(step.get("attached_chemicals", []) or []):
                chem_class = chem.get("linkml_class") or "ChemicalEntity"
                # Pass the original step_index and the chemical index separately so
                # the UI can correctly identify the parent step and the chemical.
                _validate_instance(
                    _normalize_linkml_instance(chem),
                    chem_class,
                    activity_index,
                    step_index,
                    source_action,
                    chem.get("chemical"),
                    chemical_index=chem_index,
                )

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
