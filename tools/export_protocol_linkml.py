#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.schema_exporter import convert_protocol_to_linkml, summarize_linkml_export


def _load_input(path: Path) -> dict:
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


def _dump_yaml(data: dict) -> str:
    def scalar(value):
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, bool):
            return "true" if value else "false"
        if value is None:
            return "null"
        return str(value)

    def lines(value, indent=0):
        pad = " " * indent
        if isinstance(value, dict):
            if not value:
                return [pad + "{}"]
            out = []
            for key, item in value.items():
                if isinstance(item, (dict, list)):
                    if not item:
                        out.append(f"{pad}{key}: {{}}" if isinstance(item, dict) else f"{pad}{key}: []")
                    else:
                        out.append(f"{pad}{key}:")
                        out.extend(lines(item, indent + 2))
                else:
                    out.append(f"{pad}{key}: {scalar(item)}")
            return out
        if isinstance(value, list):
            if not value:
                return [pad + "[]"]
            out = []
            for item in value:
                if isinstance(item, (dict, list)):
                    if not item:
                        out.append(pad + "- {}" if isinstance(item, dict) else pad + "- []")
                    else:
                        out.append(pad + "-")
                        out.extend(lines(item, indent + 2))
                else:
                    out.append(f"{pad}- {scalar(item)}")
            return out
        return [pad + scalar(value)]

    return "\n".join(lines(data)) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a protocol to a LinkML-aligned semantic payload.")
    parser.add_argument("protocol_file", help="Path to protocol file (.json/.yaml/.yml)")
    parser.add_argument("-o", "--output", help="Output file path (.json/.yaml/.yml)")
    args = parser.parse_args()

    input_path = Path(args.protocol_file).expanduser().resolve()
    if not input_path.exists():
        print(f"error: file not found: {input_path}")
        return 2

    try:
        protocol = _load_input(input_path)
    except Exception as exc:
        print(f"error: failed to load input protocol: {exc}")
        return 2

    payload = convert_protocol_to_linkml(protocol)
    summary = summarize_linkml_export(payload)

    output_path = Path(args.output).expanduser().resolve() if args.output else input_path.with_suffix(".linkml.json")
    if not output_path.suffix.lower() in {".json", ".yaml", ".yml"}:
        output_path = output_path.with_suffix(".linkml.json")

    try:
        with output_path.open("w", encoding="utf-8") as f:
            if output_path.suffix.lower() in {".yaml", ".yml"}:
                f.write(_dump_yaml(payload))
            else:
                json.dump(payload, f, indent=2, ensure_ascii=False)
    except Exception as exc:
        print(f"error: failed to write output: {exc}")
        return 2

    print(f"linkml export written to {output_path}")
    print(
        f"summary: activities={summary.activity_count}, steps={summary.step_count}, "
        f"chemicals={summary.chemical_count}, unmapped_fields={summary.unmapped_fields}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
