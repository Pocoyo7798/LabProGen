from dataclasses import dataclass
from collections import Counter

from .config import is_field_required
from .schema_loader import load_linkml_schema
from .schema_mapping import get_linkml_step_class


@dataclass
class ValidationMessage:
    level: str
    code: str
    message: str
    context: dict


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
