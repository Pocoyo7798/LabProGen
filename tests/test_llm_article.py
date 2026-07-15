"""Tests for LLM article prompt building."""

from src.llm.client import extract_message_content, parse_aiedu_response
from src.llm.article import (
    build_article_prompt,
    build_procedure_guide_text,
    compact_protocol_for_prompt,
)


SAMPLE_PROTOCOL = {
    "protocol_name": "Test protocol",
    "flows": [
        {
            "flow_id": 1,
            "type": "horizontal",
            "steps": [
                {
                    "action": "Add",
                    "params": {"duration": "5 min", "add_quantity": "10 g"},
                    "chemicals": [
                        {
                            "chemical": "Molecules",
                            "params": {"name": "Water"},
                        }
                    ],
                },
                {
                    "action": "Wait",
                    "params": {"duration": "10 min"},
                },
            ],
        }
    ],
}


def test_compact_protocol_for_prompt_skips_imported_flows():
    protocol = {
        **SAMPLE_PROTOCOL,
        "flows": [
            *SAMPLE_PROTOCOL["flows"],
            {"flow_id": 2, "chemical_block_id": 99, "steps": [{"action": "Grind", "params": {}}]},
        ],
    }
    compact = compact_protocol_for_prompt(protocol)
    assert compact["total_flows"] == 1
    assert len(compact["flows"][0]["steps"]) == 2


def test_build_procedure_guide_text_from_protocol():
    text = build_procedure_guide_text(SAMPLE_PROTOCOL)
    assert "Add Water" in text
    assert "Wait for 10 min" in text


def test_build_article_prompt_includes_guide_and_json():
    prompt = build_article_prompt(
        SAMPLE_PROTOCOL,
        procedure_guide_text="1. Add Water (10 g) for 5 min.",
    )
    assert "Methods section" in prompt
    assert "Add Water" in prompt
    assert '"action": "Wait"' in prompt


def test_extract_message_content_from_stream_chunk():
    payload = (
        '{"type":"message","content":{"content":"Generated methods paragraph."}}'
    )
    assert extract_message_content(payload) == "Generated methods paragraph."


def test_parse_aiedu_ndjson_with_ai_content_shape():
    payload = "\n".join(
        [
            '{"type":"start","content":"Processing"}',
            '{"type":"message","content":{"type":"ai","content":"Methods text.","response_metadata":{"model_name":"claude-opus-4-7","stop_reason":"end_turn"}}}',
            '{"type":"done","content":"run-id"}',
        ]
    )
    parsed = parse_aiedu_response(payload)
    assert parsed.text == "Methods text."
    assert parsed.model_name == "claude-opus-4-7"
    assert parsed.refused is False


def test_parse_aiedu_detects_model_refusal():
    payload = (
        '{"type":"message","content":{"type":"ai","content":"","response_metadata":'
        '{"model_name":"claude-opus-4-7","stop_reason":"refusal"}}}'
    )
    parsed = parse_aiedu_response(payload)
    assert parsed.text == ""
    assert parsed.refused is True
    assert parsed.stop_reason == "refusal"
