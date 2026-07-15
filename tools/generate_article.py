#!/usr/bin/env python3
"""CLI helper to generate article text from an exported protocol JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.llm.article import build_procedure_guide_text, generate_article_text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate article-style Methods text from a LabProGen protocol export."
    )
    parser.add_argument("protocol", type=Path, help="Path to protocol JSON export")
    parser.add_argument(
        "--procedure-guide",
        type=Path,
        help="Optional procedure guide text file to include as LLM context",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Write generated text to this file instead of stdout",
    )
    args = parser.parse_args()

    protocol_data = json.loads(args.protocol.read_text(encoding="utf-8"))
    guide_text = None
    if args.procedure_guide:
        guide_text = args.procedure_guide.read_text(encoding="utf-8")
    else:
        guide_text = build_procedure_guide_text(protocol_data)

    text = generate_article_text(
        protocol_data,
        procedure_guide_text=guide_text,
    )

    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"article text written to {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
