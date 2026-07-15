"""Generate article-style Methods prose from exported protocol data."""

from __future__ import annotations

import json
from typing import Any

from .client import AieduClient
from src.text.procedure_text import build_procedure_text, main_flow_steps_from_protocol


def compact_protocol_for_prompt(protocol_data: dict[str, Any]) -> dict[str, Any]:
    """Keep export-relevant fields while reducing prompt size."""
    flows = []
    for flow in protocol_data.get("flows") or []:
        if not isinstance(flow, dict):
            continue
        if flow.get("chemical_block_id") is not None:
            continue
        steps = []
        for step in flow.get("steps") or []:
            if not isinstance(step, dict):
                continue
            compact_step = {
                "action": step.get("action"),
                "params": step.get("params") or {},
            }
            if step.get("chemicals"):
                compact_step["chemicals"] = step.get("chemicals")
            if step.get("subproduct_branch"):
                compact_step["subproduct_branch"] = step.get("subproduct_branch")
            steps.append(compact_step)
        flows.append(
            {
                "flow_id": flow.get("flow_id"),
                "type": flow.get("type"),
                "steps": steps,
            }
        )
    return {
        "protocol_name": protocol_data.get("protocol_name"),
        "total_flows": len(flows),
        "flows": flows,
    }


def build_procedure_guide_text(
    protocol_data: dict[str, Any] | None,
    *,
    procedure_guide_text: str | None = None,
) -> str:
    if procedure_guide_text and procedure_guide_text.strip():
        return procedure_guide_text.strip()
    steps = main_flow_steps_from_protocol(protocol_data or {})
    return build_procedure_text(steps)


def build_article_prompt(
    protocol_data: dict[str, Any],
    *,
    procedure_guide_text: str | None = None,
    language: str = "English",
) -> str:
    """Build the LLM prompt for article-style Methods text."""
    compact = compact_protocol_for_prompt(protocol_data)
    guide = build_procedure_guide_text(protocol_data, procedure_guide_text=procedure_guide_text)
    protocol_json = json.dumps(compact, indent=2, ensure_ascii=False)

    return f"""You are a scientific writing assistant for laboratory protocols.

Convert the protocol below into prose suitable for the Methods section of a research article.

Requirements:
- Write in {language}.
- Use past tense and third person.
- Be precise with materials, quantities, temperatures, durations, atmosphere, and equipment.
- Do not invent steps, chemicals, or parameters that are not supported by the input.
- Merge closely related consecutive steps when it improves readability.
- Keep the result self-contained and publication-ready.

Input A: procedure guide (human-readable summary)
{guide}

Input B: structured protocol export (JSON)
{protocol_json}

Output format:
1. One-line suggested Methods subsection title.
2. The Methods text (one or more paragraphs; numbered substeps are allowed when helpful).
"""


def generate_article_text(
    protocol_data: dict[str, Any],
    *,
    procedure_guide_text: str | None = None,
    client: AieduClient | None = None,
    language: str = "English",
) -> str:
    """Call the configured LLM and return article-style Methods prose."""
    prompt = build_article_prompt(
        protocol_data,
        procedure_guide_text=procedure_guide_text,
        language=language,
    )
    llm = client or AieduClient.from_env()
    return llm.complete(prompt)
