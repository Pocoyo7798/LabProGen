#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schema_validator import validate_protocol_shadow, summarize_validation_messages


def _load_protocol(path: Path) -> dict:
    suffix = path.suffix.lower()

    if suffix == ".json":
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    if suffix in {".yaml", ".yml"}:
        try:
            import yaml
        except ImportError as exc:
            raise RuntimeError(
                "PyYAML is required to read YAML protocol files. Install with: pip install pyyaml"
            ) from exc

        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                raise ValueError("YAML root must be a mapping/object.")
            return data

    raise ValueError("Unsupported file extension. Use .json, .yaml or .yml")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate protocol export against LinkML mappings in shadow mode."
    )
    parser.add_argument("protocol_file", help="Path to protocol file (.json/.yaml/.yml)")
    parser.add_argument(
        "--show-all",
        action="store_true",
        help="Print all validation messages instead of only first 20.",
    )

    args = parser.parse_args()
    path = Path(args.protocol_file).expanduser().resolve()

    if not path.exists():
        print(f"error: file not found: {path}")
        return 2

    try:
        protocol = _load_protocol(path)
    except Exception as exc:
        print(f"error: failed to load protocol file: {exc}")
        return 2

    messages = validate_protocol_shadow(protocol)
    summary = summarize_validation_messages(messages)

    print(f"schema-shadow summary for {path.name}")
    print(f"  total: {summary['total']}")
    print(f"  by_level: {summary['by_level']}")
    print(f"  by_code: {summary['by_code']}")

    limit = len(messages) if args.show_all else min(20, len(messages))
    for msg in messages[:limit]:
        print(f"- [{msg.level}] {msg.code}: {msg.message} | context={msg.context}")

    if not args.show_all and len(messages) > limit:
        print(f"... ({len(messages) - limit} more messages hidden; use --show-all)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
