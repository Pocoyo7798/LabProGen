"""English textual procedure guide from action steps (no imported chemical flows)."""

from __future__ import annotations

from typing import Any

from labprogen.core.config import (
    KEY_ADD_QUANTITY,
    KEY_ADD_TYPE,
    KEY_AGITATION_TYPE,
    KEY_AMOUNT,
    KEY_CONTINUOUS_ADD_TYPE,
    KEY_CONCENTRATION,
    KEY_DURATION,
    KEY_FLOW_RATE,
    KEY_FORMULA,
    KEY_NAME,
    KEY_MATERIAL,
    KEY_METHOD,
    KEY_NAME,
    KEY_OPEN_FLAME,
    KEY_PHASE,
    KEY_POWER,
    KEY_PRESSURE,
    KEY_PROCESS,
    KEY_RAMP,
    KEY_RECIPIENT,
    KEY_SIZE_RANGE,
    KEY_SPEED,
    KEY_SUBSTANCE,
    KEY_SUBSTANCE_LIST,
    KEY_TEMPERATURE,
    KEY_VOLUME,
)


def _s(value: Any) -> str:
    return str(value or "").strip()


def _format_name_list(names: list[str]) -> str:
    cleaned = [n for n in (_s(n) for n in names) if n]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def chemical_display_name(chem: dict) -> str:
    """Readable label for an attached chemical (name only, no type detail)."""
    if isinstance(chem.get("chemical"), dict):
        return chemical_display_name(chem["chemical"])
    params = chem.get("params") if isinstance(chem.get("params"), dict) else {}
    name = _s(params.get(KEY_NAME)) or _s(chem.get(KEY_NAME))
    if name:
        return name
    formula = _s(params.get(KEY_FORMULA)) or _s(chem.get(KEY_FORMULA))
    if formula:
        return formula
    return _s(chem.get("chemical") or chem.get("chemical_type") or chem.get("type")) or "material"


def chemical_names_from_step(step: dict) -> list[str]:
    chemicals = step.get("chemicals") or []
    if chemicals:
        return [chemical_display_name(c) for c in chemicals if isinstance(c, dict)]

    params = step.get("params", {}) if isinstance(step.get("params"), dict) else {}
    substance = params.get(KEY_SUBSTANCE)
    if isinstance(substance, list):
        return [chemical_display_name(c) for c in substance if isinstance(c, dict)]
    substances = params.get("chemical", params.get(KEY_SUBSTANCE_LIST))
    if isinstance(substances, list):
        return [chemical_display_name(c) for c in substances if isinstance(c, dict)]
    return []


def format_gas_entry_label(gas: dict) -> str:
    """Display label for a gas chemical: name (concentration with units)."""
    name = _s(gas.get(KEY_NAME))
    if not name and isinstance(gas.get("params"), dict):
        name = _s(gas["params"].get(KEY_NAME))
    if not name:
        name = chemical_display_name(gas)
    conc = _s(gas.get(KEY_CONCENTRATION))
    if not conc and isinstance(gas.get("params"), dict):
        conc = _s(gas["params"].get(KEY_CONCENTRATION))
    if conc:
        return f"{name} ({conc})"
    return name


def _gases_summary(gases: Any) -> str:
    if not isinstance(gases, list) or not gases:
        return "configured gases"
    parts = []
    for gas in gases:
        if isinstance(gas, dict):
            parts.append(format_gas_entry_label(gas))
        elif gas:
            parts.append(_s(gas))
    return _format_name_list(parts) or "configured gases"


def sentence_for_step(step: dict) -> str:
    """Render one English sentence for an action step."""
    action = _s(step.get("action"))
    params = step.get("params") if isinstance(step.get("params"), dict) else {}
    names = chemical_names_from_step(step)
    names_text = _format_name_list(names)

    if action == "ChangeContainer":
        recipient = _s(params.get(KEY_RECIPIENT)) or "recipient"
        material = _s(params.get(KEY_MATERIAL))
        volume = _s(params.get(KEY_VOLUME))
        details = ", ".join(p for p in (material, volume) if p)
        if details:
            return f"Change to {recipient} recipient ({details})."
        return f"Change to {recipient} recipient."

    if action == "Add":
        quantity = _s(params.get(KEY_ADD_QUANTITY))
        add_type = _s(params.get(KEY_ADD_TYPE))
        duration = _s(params.get(KEY_DURATION))
        open_flame = _s(params.get(KEY_OPEN_FLAME))
        meta = ", ".join(p for p in (quantity, add_type) if p)
        if names_text:
            base = f"Add {names_text}"
        else:
            base = "Add material"
        if meta:
            base += f" ({meta})"
        if duration:
            base += f" for {duration}"
        if open_flame and open_flame.lower() == "true":
            base += " with open flame"
        return base + "."

    if action == "ChangeTemperature":
        temperature = _s(params.get(KEY_TEMPERATURE)) or "target temperature"
        process = _s(params.get(KEY_PROCESS))
        ramp = _s(params.get(KEY_RAMP))
        power = _s(params.get(KEY_POWER))
        verb = "Cool to" if process.lower() == "ice-bath" else "Heat to"
        sentence = f"{verb} {temperature}"
        if process:
            sentence += f" ({process})"
        extras = ", ".join(p for p in (ramp, power) if p)
        if extras:
            sentence += f"; {extras}"
        return sentence + "."

    if action == "NoAction":
        duration = _s(params.get(KEY_DURATION)) or "the specified time"
        return f"Wait for {duration}."

    if action == "ChangePressure":
        pressure = _s(params.get(KEY_PRESSURE))
        if pressure:
            return f"Change pressure to {pressure}."
        return "Change pressure."

    if action == "ChangeAgitation":
        agitation = _s(params.get(KEY_AGITATION_TYPE)) or "agitation"
        speed = _s(params.get(KEY_SPEED))
        if speed:
            return f"Agitate using {agitation} at {speed}."
        return f"Agitate using {agitation}."

    if action == "Separate":
        method_data = params.get(KEY_METHOD)
        phase = _s(method_data.get(KEY_PHASE) if isinstance(method_data, dict) else params.get(KEY_PHASE)) or "selected phase"
        method = _s(method_data.get("type") if isinstance(method_data, dict) else method_data) or "separation"
        return f"Separate and keep the {phase} phase by {method}."

    if action == "Sieve":
        size_range = _s(params.get(KEY_SIZE_RANGE))
        duration = _s(params.get(KEY_DURATION))
        if size_range and duration:
            return f"Sieve {size_range} for {duration}."
        if size_range:
            return f"Sieve {size_range}."
        if duration:
            return f"Sieve the solid for {duration}."
        return "Sieve the solid."

    if action == "Grind":
        duration = _s(params.get(KEY_DURATION))
        if duration:
            return f"Grind the material for {duration}."
        return "Grind the material."

    if action == "Repeat":
        amount = _s(params.get(KEY_AMOUNT)) or "1"
        repeat_word = "time"
        try:
            if int(float(amount.split()[0])) != 1:
                repeat_word = "times"
        except (ValueError, IndexError):
            repeat_word = "times"
        return f"Repeat the previous steps {amount} {repeat_word}."

    if action == "ContinuousAddition":
        mode = _s(params.get(KEY_CONTINUOUS_ADD_TYPE)) or "continuous"
        amount = _s(params.get(KEY_AMOUNT))
        substances = params.get("chemical", params.get(KEY_SUBSTANCE_LIST))
        if isinstance(substances, list):
            substances_text = _format_name_list(
                [chemical_display_name(item) for item in substances if isinstance(item, dict)]
            )
        else:
            substances_text = _s(substances)
        flow_rate = _s(params.get(KEY_FLOW_RATE))
        sentence = f"Apply {mode.lower()} addition"
        if substances_text:
            sentence += f" of {substances_text}"
        if amount:
            sentence += f" ({amount} cycles)"
        if flow_rate:
            sentence += f" at {flow_rate}"
        return sentence + "."

    if action == "CollectSubProduct":
        if params.get("phase_to_keep"):
            return f"Collect subproduct and keep the {params['phase_to_keep']} phase."
        if names_text:
            return f"Create subproduct from {names_text}."
        return "Create subproduct."

    return f"Perform {action or 'step'}."


def main_flow_steps_from_protocol(protocol_data: dict | None) -> list[dict]:
    """Return steps from the primary canvas flow, excluding imported chemical procedures."""
    if not isinstance(protocol_data, dict):
        return []
    steps: list[dict] = []
    for flow in protocol_data.get("flows") or []:
        if flow.get("chemical_block_id") is not None:
            continue
        for step in flow.get("steps") or []:
            if isinstance(step, dict):
                steps.append(step)
    return steps


def build_procedure_text(steps: list[dict]) -> str:
    """Join step sentences into a numbered plain-text guide (one step per line)."""
    if not steps:
        return "No procedure steps yet."
    lines = []
    for index, step in enumerate(steps, start=1):
        sentence = sentence_for_step(step)
        lines.append(f"{index}. {sentence}")
    return "\n".join(lines)
