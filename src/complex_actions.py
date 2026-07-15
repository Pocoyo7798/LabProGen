"""User-defined complex actions: model, registry, validation, and dictionary I/O."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import FIELD_CONFIG, is_field_required

ELEMENTARY_ACTIONS = frozenset({"Add", "Grind", "Separate", "Sieve", "Wait"})
SUPPORT_ACTIONS = frozenset({
    "ChangeAtmosphere",
    "ChangeTemperature",
    "NewRecipient",
    "ChangeAgitation",
    "Repeat",
    "ContinuousAddition",
})
FLOW_ACTIONS = ELEMENTARY_ACTIONS | SUPPORT_ACTIONS | frozenset({"SubProductCreation"})

COMPLEX_ACTION_MARKER = "ComplexAction"
KEY_COMPLEX_ACTION_NAME = "complex_action_name"
KEY_COMPLEX_PARAMETERS = "parameters"

DEFAULT_ACTION_PARAMS: dict[str, dict[str, Any]] = {
    "Add": {
        "duration": "0 s",
        "add_quantity": "0 g",
        "add_type": "",
        "open_flame": "",
    },
    "Grind": {},
    "Separate": {"phase_to_keep": "", "method": ""},
    "Sieve": {"min_size": "0 μm", "max_size": "0 μm"},
    "Wait": {"duration": "10 min"},
    "ChangeAtmosphere": {"gases": [], "flow_rate": "0 mL/min", "pressure": "1 bar"},
    "ChangeTemperature": {
        "temperature": "50 °C",
        "process": "",
        "ramp": "0 °C/min",
        "power": "0 W",
    },
    "NewRecipient": {"recipient": "", "material": "", "volume": "250 mL"},
    "ChangeAgitation": {"agitation_type": "", "speed": "0 rpm"},
    "SubProductCreation": {"substance": ""},
    "Repeat": {"amount": "1"},
    "ContinuousAddition": {
        "substance_list": "",
        "continuous_add_type": "",
        "amount": "1",
    },
}


def default_action_params(action_name: str) -> dict[str, Any]:
    """Return a shallow copy of default params for an action type."""
    return dict(DEFAULT_ACTION_PARAMS.get(action_name, {}))


def sequence_signature(steps: list[dict[str, Any]]) -> tuple[str, ...]:
    """Canonical action-type sequence used for uniqueness checks."""
    return tuple(step_action_signature(step) for step in steps)


def is_complex_action_step(step: dict[str, Any]) -> bool:
    return str(step.get("action", "")) == COMPLEX_ACTION_MARKER


def step_action_signature(step: dict[str, Any]) -> str:
    action = str(step.get("action", ""))
    if action == COMPLEX_ACTION_MARKER:
        name = str((step.get("params") or {}).get(KEY_COMPLEX_ACTION_NAME, ""))
        return f"{COMPLEX_ACTION_MARKER}:{name}"
    return action


def step_display_name(step: dict[str, Any]) -> str:
    if is_complex_action_step(step):
        return str((step.get("params") or {}).get(KEY_COMPLEX_ACTION_NAME, "Complex action"))
    return str(step.get("action", ""))


def _parse_unit_from_value(value: Any, param_key: str) -> str:
    config = FIELD_CONFIG.get(str(param_key).lower(), {})
    units = config.get("units") or []
    if not isinstance(value, str):
        return units[0] if units else ""
    text = value.strip()
    for unit in sorted(units, key=len, reverse=True):
        if text.endswith(f" {unit}") or text == unit:
            return unit
    return units[0] if units else ""


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, dict)):
        return len(value) == 0
    return False


@dataclass
class ComplexActionParameter:
    step_index: int
    action: str
    param_key: str
    display_name: str
    editable: bool = True
    unit: str = ""
    default_value: Any = ""
    value: Any = ""
    host_step_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "step_index": self.step_index,
            "action": self.action,
            "param_key": self.param_key,
            "display_name": self.display_name,
            "editable": self.editable,
            "unit": self.unit,
            "default_value": self.default_value,
            "value": self.value,
        }
        if self.host_step_index is not None:
            payload["host_step_index"] = self.host_step_index
        return payload

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplexActionParameter:
        host_step_index = data.get("host_step_index")
        return cls(
            step_index=int(data.get("step_index", 0)),
            action=str(data.get("action", "")),
            param_key=str(data.get("param_key", "")),
            display_name=str(data.get("display_name", "")),
            editable=bool(data.get("editable", True)),
            unit=str(data.get("unit", "")),
            default_value=data.get("default_value", ""),
            value=data.get("value", data.get("default_value", "")),
            host_step_index=int(host_step_index) if host_step_index is not None else None,
        )


@dataclass
class ComplexActionDefinition:
    name: str
    steps: list[dict[str, Any]]
    parameters: list[ComplexActionParameter] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "complex_action_name": self.name,
            "version": 1,
            "steps": self.steps,
            "parameters": [param.to_dict() for param in self.parameters],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComplexActionDefinition:
        name = str(data.get("complex_action_name") or data.get("name") or "").strip()
        steps = [dict(step) for step in data.get("steps", []) or []]
        parameters = [
            ComplexActionParameter.from_dict(item)
            for item in data.get("parameters", []) or []
        ]
        return cls(name=name, steps=steps, parameters=parameters)

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> ComplexActionDefinition:
        return cls.from_dict(json.loads(text))


def build_parameter_bindings(steps: list[dict[str, Any]]) -> list[ComplexActionParameter]:
    """Create parameter bindings from a flow skeleton (one entry per param key)."""
    from .block import field_label

    bindings: list[ComplexActionParameter] = []
    for step_index, step in enumerate(steps):
        action = str(step.get("action", ""))
        if is_complex_action_step(step):
            continue
        params = dict(step.get("params") or default_action_params(action))
        for param_key, default_value in params.items():
            bindings.append(
                ComplexActionParameter(
                    step_index=step_index,
                    action=action,
                    param_key=param_key,
                    display_name=field_label(param_key, action),
                    editable=True,
                    unit=_parse_unit_from_value(default_value, param_key),
                    default_value=default_value,
                    value=default_value,
                )
            )
    return bindings


def collect_flow_steps_from_editor(editor) -> list[dict[str, Any]]:
    """Collect the main horizontal action chain from an editor (no chemicals)."""
    from .complex_action_protocol import _horizontal_chain_from_editor

    chain = _horizontal_chain_from_editor(editor)
    if not chain:
        return []

    steps: list[dict[str, Any]] = []
    visited_groups: set[str] = set()
    index = 0
    while index < len(chain):
        block = chain[index]
        group_id = getattr(block, "complex_group_id", None)
        if getattr(block, "part_of_complex_action", False) and group_id:
            if group_id not in visited_groups:
                visited_groups.add(group_id)
                group = getattr(editor, "complex_action_groups", {}).get(group_id)
                if group is not None:
                    steps.append(complex_action_step_from_group(group))
            while index < len(chain) and getattr(chain[index], "complex_group_id", None) == group_id:
                index += 1
            continue

        steps.append({
            "action": block.action,
            "params": dict(block.params or default_action_params(block.action)),
        })
        subproduct = getattr(block, "subproduct_below", None)
        if subproduct is not None:
            steps.append({
                "action": subproduct.action,
                "params": dict(subproduct.params or default_action_params(subproduct.action)),
            })
        index += 1
    return steps


def validate_definition(
    definition: ComplexActionDefinition,
    registry: ComplexActionRegistry | None = None,
    *,
    exclude_name: str | None = None,
    check_registry_uniqueness: bool = True,
) -> list[str]:
    """Return human-readable validation errors (empty list means valid)."""
    errors: list[str] = []
    name = definition.name.strip()
    if not name:
        errors.append("Complex action name is required.")
    if not definition.steps:
        errors.append("The complex action must contain at least one action.")
    for step in definition.steps:
        action = step.get("action")
        if is_complex_action_step(step):
            nested_name = str((step.get("params") or {}).get(KEY_COMPLEX_ACTION_NAME, "")).strip()
            if not nested_name:
                errors.append("Nested complex action step is missing a name.")
            elif registry is not None and registry.get(nested_name) is None:
                errors.append(f"Unknown nested complex action: {nested_name!r}.")
            elif registry is not None:
                nested_definition = registry.get(nested_name)
                if nested_definition is not None:
                    nested_params = parameters_from_block_params(step.get("params") or {})
                    errors.extend(validate_instance_parameters(nested_params, nested_definition))
            continue
        if action not in FLOW_ACTIONS:
            errors.append(f"Unsupported action in flow: {action!r}.")

    if check_registry_uniqueness and registry is not None and name:
        if registry.has_name(name, exclude=exclude_name):
            errors.append(f"A complex action named {name!r} already exists.")
        if registry.has_sequence(definition.steps, exclude_name=exclude_name or name):
            errors.append("A complex action with this exact action sequence already exists.")

    step_params: dict[int, dict[str, Any]] = {}
    for param in definition.parameters:
        if param.host_step_index is not None:
            continue
        step_params.setdefault(param.step_index, {})[param.param_key] = param.value

    seen_required: set[tuple[int, str]] = set()
    for param in definition.parameters:
        if param.host_step_index is not None:
            continue
        action = ""
        if 0 <= param.step_index < len(definition.steps):
            step = definition.steps[param.step_index]
            if is_complex_action_step(step):
                continue
            action = str(step.get("action", ""))
        params = step_params.get(param.step_index, {})
        if not is_field_required(param.param_key, params=params, action_name=action):
            continue
        key = (param.step_index, param.param_key)
        if key in seen_required:
            continue
        seen_required.add(key)
        if _is_blank(param.value):
            label = param.display_name or param.param_key
            errors.append(
                f"Required parameter {label!r} ({action}) must have a value."
            )
    return errors


def expand_definition_steps(
    steps: list[dict[str, Any]],
    parameters: list[ComplexActionParameter] | None = None,
) -> list[dict[str, Any]]:
    """Expand a step list to elementary/support actions, resolving nested complex actions."""
    registry = get_complex_action_registry()
    value_map: dict[tuple[int | None, int, str], Any] = {
        (param.host_step_index, param.step_index, param.param_key): param.value
        for param in (parameters or [])
    }
    result: list[dict[str, Any]] = []

    for step_index, step in enumerate(steps):
        action = str(step.get("action", ""))
        if is_complex_action_step(step):
            params_dict = dict(step.get("params") or {})
            nested_name = str(params_dict.get(KEY_COMPLEX_ACTION_NAME, "")).strip()
            nested_definition = registry.get(nested_name)
            if nested_definition is None:
                continue
            nested_params = _nested_instance_parameters(
                step_index,
                params_dict,
                parameters,
            )
            result.extend(expand_definition_steps(nested_definition.steps, nested_params))
            continue

        params = dict(step.get("params") or default_action_params(action))
        for key in list(params.keys()):
            if (None, step_index, key) in value_map:
                params[key] = value_map[(None, step_index, key)]
        result.append({"action": action, "params": params})
    return result


def _nested_instance_parameters(
    host_step_index: int,
    params_dict: dict[str, Any],
    parameters: list[ComplexActionParameter] | None,
) -> list[ComplexActionParameter]:
    """Resolve nested complex-action parameters for one outer step."""
    defaults = parameters_from_block_params(params_dict)
    by_key = {(param.step_index, param.param_key): param for param in defaults}
    for param in parameters or []:
        if param.host_step_index != host_step_index:
            continue
        by_key[(param.step_index, param.param_key)] = ComplexActionParameter(
            step_index=param.step_index,
            action=param.action,
            param_key=param.param_key,
            display_name=param.display_name,
            editable=param.editable,
            unit=param.unit,
            default_value=param.default_value,
            value=param.value,
            host_step_index=None,
        )
    return list(by_key.values())


def apply_parameter_values(
    steps: list[dict[str, Any]],
    parameters: list[ComplexActionParameter],
) -> list[dict[str, Any]]:
    """Return steps with parameter values applied from bindings."""
    return expand_definition_steps(steps, parameters)


def expand_complex_action(definition: ComplexActionDefinition) -> list[dict[str, Any]]:
    """Expand a complex action to elementary/support steps for protocol export."""
    return expand_definition_steps(definition.steps, definition.parameters)


class ComplexActionRegistry:
    """In-memory store of user-defined complex actions."""

    def __init__(self) -> None:
        self._by_name: dict[str, ComplexActionDefinition] = {}

    def list_names(self) -> list[str]:
        return sorted(self._by_name)

    def get(self, name: str) -> ComplexActionDefinition | None:
        return self._by_name.get(name.strip())

    def register(self, definition: ComplexActionDefinition) -> None:
        self._by_name[definition.name.strip()] = definition

    def remove(self, name: str) -> None:
        self._by_name.pop(name.strip(), None)

    def has_name(self, name: str, *, exclude: str | None = None) -> bool:
        key = name.strip()
        if exclude and key == exclude.strip():
            return False
        return key in self._by_name

    def has_sequence(
        self,
        steps: list[dict[str, Any]],
        *,
        exclude_name: str | None = None,
    ) -> bool:
        signature = sequence_signature(steps)
        for name, definition in self._by_name.items():
            if exclude_name and name == exclude_name.strip():
                continue
            if sequence_signature(definition.steps) == signature:
                return True
        return False

    def validate_new(self, definition: ComplexActionDefinition) -> list[str]:
        return validate_definition(definition, self)


_GLOBAL_REGISTRY = ComplexActionRegistry()


def get_complex_action_registry() -> ComplexActionRegistry:
    return _GLOBAL_REGISTRY


@dataclass
class ComplexActionGroup:
    """One complex-action usage in a protocol (expanded members + optional surrogate)."""

    group_id: str
    definition_name: str
    parameters: list[ComplexActionParameter]
    member_blocks: list[Any] = field(default_factory=list)
    surrogate_block: Any | None = None
    chain_wired_collapsed: bool = False
    collapsed_tail_shift: float = 0.0

    def __post_init__(self) -> None:
        if not hasattr(self, "chain_wired_collapsed"):
            self.chain_wired_collapsed = False
        if not hasattr(self, "collapsed_tail_shift"):
            self.collapsed_tail_shift = 0.0

    def expanded_steps(self) -> list[dict[str, Any]]:
        return expand_definition_steps(
            _definition_steps(self.definition_name),
            self.parameters,
        )


def _definition_steps(definition_name: str) -> list[dict[str, Any]]:
    definition = get_complex_action_registry().get(definition_name)
    if definition is None:
        return []
    return definition.steps


def build_instance_parameters(
    definition: ComplexActionDefinition,
    existing: list[ComplexActionParameter] | None = None,
) -> list[ComplexActionParameter]:
    """Build the full parameter list for configuring a complex-action instance."""
    registry = get_complex_action_registry()
    existing_map = {
        (param.host_step_index, param.step_index, param.param_key): param
        for param in (existing or [])
    }
    result: list[ComplexActionParameter] = []

    for param in definition.parameters:
        key = (None, param.step_index, param.param_key)
        if key in existing_map:
            result.append(ComplexActionParameter.from_dict(existing_map[key].to_dict()))
            continue
        copied = ComplexActionParameter.from_dict(param.to_dict())
        copied.host_step_index = None
        result.append(copied)

    for outer_index, step in enumerate(definition.steps):
        if not is_complex_action_step(step):
            continue
        params_dict = step.get("params") or {}
        nested_name = str(params_dict.get(KEY_COMPLEX_ACTION_NAME, "")).strip()
        nested_definition = registry.get(nested_name)
        nested_defaults = parameters_from_block_params(params_dict)
        editable_map = {
            (item.step_index, item.param_key): item.editable
            for item in (nested_definition.parameters if nested_definition else [])
        }
        display_map = {
            (item.step_index, item.param_key): item.display_name
            for item in (nested_definition.parameters if nested_definition else [])
        }
        for default in nested_defaults:
            key = (outer_index, default.step_index, default.param_key)
            if key in existing_map:
                result.append(ComplexActionParameter.from_dict(existing_map[key].to_dict()))
                continue
            result.append(
                ComplexActionParameter(
                    step_index=default.step_index,
                    action=default.action,
                    param_key=default.param_key,
                    display_name=display_map.get(
                        (default.step_index, default.param_key),
                        default.display_name,
                    ),
                    editable=editable_map.get(
                        (default.step_index, default.param_key),
                        default.editable,
                    ),
                    unit=default.unit,
                    default_value=default.default_value,
                    value=default.value,
                    host_step_index=outer_index,
                )
            )
    return result


@dataclass(frozen=True)
class InstanceDialogSection:
    """One UI section when configuring a complex-action instance."""

    display_index: int
    action_name: str
    host_step_index: int | None = None
    inner_step_index: int | None = None
    top_step_index: int | None = None


def iter_instance_dialog_sections(
    definition: ComplexActionDefinition,
) -> list[InstanceDialogSection]:
    """Flatten outer steps, expanding nested complex actions into their member steps."""
    registry = get_complex_action_registry()
    sections: list[InstanceDialogSection] = []
    display_index = 0

    for outer_index, step in enumerate(definition.steps):
        if is_complex_action_step(step):
            nested_name = str((step.get("params") or {}).get(KEY_COMPLEX_ACTION_NAME, "")).strip()
            nested_definition = registry.get(nested_name)
            if nested_definition is None:
                sections.append(
                    InstanceDialogSection(
                        display_index=display_index,
                        action_name=step_display_name(step),
                        host_step_index=outer_index,
                    )
                )
                display_index += 1
                continue
            for inner_index, inner_step in enumerate(nested_definition.steps):
                sections.append(
                    InstanceDialogSection(
                        display_index=display_index,
                        action_name=str(inner_step.get("action", "")),
                        host_step_index=outer_index,
                        inner_step_index=inner_index,
                    )
                )
                display_index += 1
            continue

        sections.append(
            InstanceDialogSection(
                display_index=display_index,
                action_name=str(step.get("action", "")),
                top_step_index=outer_index,
            )
        )
        display_index += 1
    return sections


def bindings_for_instance_section(
    bindings: list[ComplexActionParameter],
    section: InstanceDialogSection,
) -> list[tuple[int, ComplexActionParameter]]:
    """Return binding indices that belong to one flattened dialog section."""
    items: list[tuple[int, ComplexActionParameter]] = []
    for index, binding in enumerate(bindings):
        if section.top_step_index is not None:
            if binding.host_step_index is None and binding.step_index == section.top_step_index:
                items.append((index, binding))
            continue
        if section.inner_step_index is not None:
            if (
                binding.host_step_index == section.host_step_index
                and binding.step_index == section.inner_step_index
            ):
                items.append((index, binding))
            continue
        if section.host_step_index is not None and binding.host_step_index == section.host_step_index:
            items.append((index, binding))
    return items


def copy_instance_parameters(definition: ComplexActionDefinition) -> list[ComplexActionParameter]:
    """Deep copy definition parameters for a new protocol instance."""
    return build_instance_parameters(definition)


def validate_instance_parameters(
    parameters: list[ComplexActionParameter],
    definition: ComplexActionDefinition,
) -> list[str]:
    """Validate parameter values when inserting or editing a complex action instance."""
    registry = get_complex_action_registry()
    errors: list[str] = []

    top_level = [param for param in parameters if param.host_step_index is None]
    errors.extend(
        validate_definition(
            ComplexActionDefinition(
                name=definition.name,
                steps=definition.steps,
                parameters=top_level,
            ),
            registry,
            check_registry_uniqueness=False,
        )
    )

    for outer_index, step in enumerate(definition.steps):
        if not is_complex_action_step(step):
            continue
        nested_name = str((step.get("params") or {}).get(KEY_COMPLEX_ACTION_NAME, "")).strip()
        nested_definition = registry.get(nested_name)
        if nested_definition is None:
            continue
        nested_params = [
            ComplexActionParameter.from_dict(param.to_dict())
            for param in parameters
            if param.host_step_index == outer_index
        ]
        for param in nested_params:
            param.host_step_index = None
        errors.extend(validate_instance_parameters(nested_params, nested_definition))

    return errors


def parameters_to_block_params(
    definition_name: str,
    parameters: list[ComplexActionParameter],
) -> dict[str, Any]:
    return {
        KEY_COMPLEX_ACTION_NAME: definition_name,
        KEY_COMPLEX_PARAMETERS: [param.to_dict() for param in parameters],
    }


def parameters_from_block_params(params: dict[str, Any]) -> list[ComplexActionParameter]:
    raw = params.get(KEY_COMPLEX_PARAMETERS, [])
    if not isinstance(raw, list):
        return []
    return [ComplexActionParameter.from_dict(item) for item in raw if isinstance(item, dict)]


def steps_match_definition(steps: list[dict[str, Any]], definition: ComplexActionDefinition) -> bool:
    if len(steps) != len(definition.steps):
        return False
    for step, expected in zip(steps, definition.steps):
        if step_action_signature(step) != step_action_signature(expected):
            return False
    return True


def find_sequence_ranges(
    step_actions: list[str],
    definition: ComplexActionDefinition,
) -> list[tuple[int, int]]:
    """Return [start, end) index ranges where step_actions matches definition sequence."""
    expanded_signature = [
        str(step.get("action", ""))
        for step in expand_definition_steps(definition.steps, definition.parameters)
    ]
    size = len(expanded_signature)
    if size == 0:
        return []
    ranges: list[tuple[int, int]] = []
    for start in range(0, len(step_actions) - size + 1):
        if step_actions[start : start + size] == expanded_signature:
            ranges.append((start, start + size))
    return ranges


def apply_parameters_to_member_blocks(group: ComplexActionGroup) -> None:
    """Sync materialized block.params from group parameter bindings."""
    steps = group.expanded_steps()
    for index, block in enumerate(group.member_blocks):
        if index >= len(steps):
            break
        block.params = dict(steps[index].get("params") or {})
        if hasattr(block, "update_text"):
            block.update_text()


def sync_group_parameters_from_members(group: ComplexActionGroup) -> None:
    """Update group parameter values from current member block params."""
    value_map: dict[tuple[int, str], Any] = {}
    for index, block in enumerate(group.member_blocks):
        for key, value in (block.params or {}).items():
            value_map[(index, key)] = value
    for param in group.parameters:
        key = (param.step_index, param.param_key)
        if key in value_map:
            param.value = value_map[key]


def complex_action_step_from_group(group: ComplexActionGroup) -> dict[str, Any]:
    sync_group_parameters_from_members(group)
    return {
        "action": COMPLEX_ACTION_MARKER,
        "params": parameters_to_block_params(group.definition_name, group.parameters),
    }


def dictionary_filename(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*]+', "_", name.strip())
    return f"{safe or 'complex_action'}.json"


COMPLEX_ACTIONS_CONFIG_VERSION = 1
DEFAULT_COMPLEX_ACTIONS_CONFIG_NAME = "complex_actions.json"


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def get_complex_actions_config_path(
    filename: str = DEFAULT_COMPLEX_ACTIONS_CONFIG_NAME,
) -> Path:
    return get_project_root() / "config" / filename


def parse_complex_actions_payload(data: Any) -> list[dict[str, Any]]:
    """Normalize JSON payload to a list of complex-action definition dicts."""
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("complex_actions"), list):
        return [item for item in data["complex_actions"] if isinstance(item, dict)]
    if data.get("complex_action_name") or data.get("name") or data.get("steps"):
        return [data]
    return []


def definitions_from_payload(data: Any) -> list[ComplexActionDefinition]:
    """Parse one or more complex-action definitions from JSON payload."""
    definitions: list[ComplexActionDefinition] = []
    for item in parse_complex_actions_payload(data):
        definition = ComplexActionDefinition.from_dict(item)
        if definition.name.strip() and definition.steps:
            definitions.append(definition)
    return definitions


def _read_config_payload(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {
            "version": COMPLEX_ACTIONS_CONFIG_VERSION,
            "complex_actions": data,
        }
    return {"version": COMPLEX_ACTIONS_CONFIG_VERSION, "complex_actions": []}


def load_complex_actions_config(
    registry: ComplexActionRegistry | None = None,
    *,
    path: Path | str | None = None,
) -> int:
    """Load default complex actions from the config file into the registry."""
    registry = registry or get_complex_action_registry()
    config_path = Path(path) if path is not None else get_complex_actions_config_path()
    if not config_path.exists():
        return 0

    try:
        payload = _read_config_payload(config_path)
    except (OSError, json.JSONDecodeError):
        return 0

    loaded = 0
    for definition in definitions_from_payload(payload):
        registry.register(definition)
        loaded += 1
    return loaded


def append_definitions_to_config(
    definitions: list[ComplexActionDefinition],
    *,
    path: Path | str | None = None,
) -> int:
    """Merge definitions into the config file, replacing entries with the same name."""
    if not definitions:
        return 0

    config_path = Path(path) if path is not None else get_complex_actions_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    by_name: dict[str, ComplexActionDefinition] = {}
    if config_path.exists():
        try:
            payload = _read_config_payload(config_path)
            for definition in definitions_from_payload(payload):
                by_name[definition.name] = definition
        except (OSError, json.JSONDecodeError):
            by_name = {}

    for definition in definitions:
        by_name[definition.name] = definition

    payload = {
        "version": COMPLEX_ACTIONS_CONFIG_VERSION,
        "complex_actions": [
            by_name[name].to_dict() for name in sorted(by_name)
        ],
    }
    with config_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return len(definitions)


def register_complex_action_definitions(
    definitions: list[ComplexActionDefinition],
    *,
    registry: ComplexActionRegistry | None = None,
    persist: bool = True,
    config_path: Path | str | None = None,
) -> int:
    """Register definitions in memory and optionally append them to the config file."""
    registry = registry or get_complex_action_registry()
    for definition in definitions:
        registry.register(definition)
    if persist and definitions:
        append_definitions_to_config(definitions, path=config_path)
    return len(definitions)
