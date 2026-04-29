from functools import lru_cache
import importlib
from pathlib import Path


def get_schema_directory() -> Path:
    return Path(__file__).resolve().parent.parent / "schema"


def list_schema_files() -> list[str]:
    schema_dir = get_schema_directory()
    if not schema_dir.exists():
        return []
    return sorted(p.name for p in schema_dir.glob("*.yaml"))


@lru_cache(maxsize=8)
def _load_yaml_file(path_str: str) -> dict:
    try:
        yaml = importlib.import_module("yaml")
    except ImportError as exc:
        raise RuntimeError(
            "PyYAML is required to load LinkML schemas. Install with: pip install pyyaml"
        ) from exc

    path = Path(path_str)
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Schema file {path.name} does not contain a YAML mapping at the root.")
    return data


def load_linkml_schema(schema_name: str = "dcat_p_lab.yaml") -> dict:
    schema_path = get_schema_directory() / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return _load_yaml_file(str(schema_path))


def schema_summary(schema: dict) -> dict:
    classes = schema.get("classes", {}) if isinstance(schema, dict) else {}
    slots = schema.get("slots", {}) if isinstance(schema, dict) else {}
    enums = schema.get("enums", {}) if isinstance(schema, dict) else {}
    return {
        "name": schema.get("name", ""),
        "title": schema.get("title", ""),
        "class_count": len(classes),
        "slot_count": len(slots),
        "enum_count": len(enums),
    }
