"""
schema_loader.py
Purpose: Load and prepare LinkML YAML schemas for use by the exporter and
validator. Provides helpers to load single files, recursively merge local
imports into a flattened validation schema, and produce brief schema
summaries for export metadata.
"""

from functools import lru_cache
import importlib
import copy
import sys
from pathlib import Path

from src.core.paths import get_app_dir, get_bundle_dir, is_frozen

ACTION_DATA_MODEL_SCHEMA = "action_data_model.yaml"


def get_schema_directory() -> Path:
    """Resolve the schema directory in source and frozen runtimes."""

    candidates: list[Path] = []
    bundle_dir = get_bundle_dir()
    app_dir = get_app_dir()

    if is_frozen():
        candidates.extend(
            [
                bundle_dir / "schema",
                bundle_dir / "src" / "schema",
                app_dir / "schema",
                app_dir.parent / "schema",
            ]
        )

    candidates.extend(
        [
            app_dir / "schema",
            Path.cwd() / "schema",
        ]
    )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return app_dir / "schema"


def ensure_six_meta_path_importer_compatibility() -> None:
    """Patch the six meta-path importer for runtimes that expect `_path`.

    PyInstaller/frozen Windows runtimes can expose `_SixMetaPathImporter`
    without the `_path` attribute that LinkML's import-time package discovery
    expects. Setting it to the six package path keeps the validator importable
    without affecting normal Python execution.
    """

    try:
        import six
    except Exception:
        return

    six_path = list(getattr(six, "__path__", []) or [])
    for importer in sys.meta_path:
        if type(importer).__name__ == "_SixMetaPathImporter" and not hasattr(importer, "_path"):
            try:
                importer._path = six_path  # type: ignore[attr-defined]
            except Exception:
                pass


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


def _merge_linkml_builtin_types(merged: dict) -> None:
    """Inline LinkML core types that recursive loading cannot resolve by path."""
    types_schema: dict | None = None
    try:
        import linkml_runtime.linkml_model as linkml_model

        types_path = Path(linkml_model.__file__).resolve().parent / "model" / "schema" / "types.yaml"
        if types_path.exists():
            types_schema = _load_yaml_file(str(types_path))
    except Exception:
        types_schema = None

    if not types_schema:
        merged.setdefault("types", {}).setdefault(
            "string",
            {"uri": "xsd:string", "base": "str", "description": "A character string"},
        )
        return

    for key, value in types_schema.items():
        if key == "imports":
            continue
        if isinstance(value, dict):
            merged.setdefault(key, {})
            builtin = copy.deepcopy(value)
            builtin.update(merged[key])
            merged[key] = builtin
        elif key not in merged:
            merged[key] = copy.deepcopy(value)


def load_linkml_schema(schema_name: str = ACTION_DATA_MODEL_SCHEMA) -> dict:
    schema_path = get_schema_directory() / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return _load_yaml_file(str(schema_path))


def load_linkml_schema_recursive(schema_name: str = ACTION_DATA_MODEL_SCHEMA) -> dict:
    """Load a schema and recursively merge local imports into a single mapping.

    This keeps the local schema layout intact while giving LinkML's validator a
    flattened view that does not depend on import-path resolution.
    """

    merged: dict = {}
    visited: set[str] = set()

    def _schema_filename(name: str) -> str:
        return name if name.endswith(".yaml") else f"{name}.yaml"

    def _load(name: str) -> None:
        filename = _schema_filename(name)
        if filename in visited:
            return
        visited.add(filename)

        schema = load_linkml_schema(filename)
        for key, value in schema.items():
            if key == "imports":
                continue
            if isinstance(value, dict):
                merged.setdefault(key, {})
                merged[key].update(copy.deepcopy(value))
            elif isinstance(value, list):
                merged.setdefault(key, [])
                for item in value:
                    if item not in merged[key]:
                        merged[key].append(copy.deepcopy(item))
            elif key not in merged:
                merged[key] = copy.deepcopy(value)

        for imp in schema.get("imports", []) or []:
            if not isinstance(imp, str):
                continue
            if imp in {"linkml:types", "linkml_runtime.linkml_model.types"}:
                _merge_linkml_builtin_types(merged)
                continue
            if imp.startswith(("http://", "https://")) or ":" in imp:
                continue
            _load(imp)

    _load(schema_name)
    merged["imports"] = []
    return merged


def _strip_unsupported_metamodel_keys(schema: dict) -> dict:
    """Drop class keys the installed LinkML runtime cannot load.

    `closed` is kept in action_data_model.yaml as the intended constraint.
    This project's LinkML runtime does not accept ClassDefinition.closed, so
    unknown-field rejection is enforced in the validator instead.
    """
    cleaned = copy.deepcopy(schema)
    for class_def in (cleaned.get("classes") or {}).values():
        if isinstance(class_def, dict):
            class_def.pop("closed", None)
    return cleaned


def build_validation_schema(schema_name: str = ACTION_DATA_MODEL_SCHEMA) -> dict:
    """Load the validation schema without fabricating missing classes or slots."""
    return _strip_unsupported_metamodel_keys(load_linkml_schema_recursive(schema_name))


def _class_mro(schema: dict, class_name: str) -> list[str]:
    classes = schema.get("classes") or {}
    ordered: list[str] = []
    seen: set[str] = set()

    def walk(name: str) -> None:
        if not name or name in seen:
            return
        seen.add(name)
        class_def = classes.get(name) or {}
        parent = class_def.get("is_a")
        if isinstance(parent, str):
            walk(parent)
        ordered.append(name)

    walk(class_name)
    return ordered


def class_slot_constraints(class_name: str, schema: dict | None = None) -> dict:
    """Return allowed slots, required slots, and enum values for a class."""
    schema = schema or load_linkml_schema_recursive(ACTION_DATA_MODEL_SCHEMA)
    classes = schema.get("classes") or {}
    slot_defs = schema.get("slots") or {}
    enums = schema.get("enums") or {}

    allowed: set[str] = set()
    required: set[str] = set()
    enum_values: dict[str, set[str]] = {}
    ranges: dict[str, str] = {}
    multivalued: dict[str, bool] = {}

    for name in _class_mro(schema, class_name):
        class_def = classes.get(name) or {}
        for slot_name in class_def.get("slots") or []:
            if isinstance(slot_name, str):
                allowed.add(slot_name)
        usage = class_def.get("slot_usage") or {}
        for slot_name, spec in usage.items():
            if not isinstance(spec, dict):
                continue
            allowed.add(slot_name)
            if spec.get("required") is True:
                required.add(slot_name)
            elif spec.get("required") is False:
                required.discard(slot_name)
            if isinstance(spec.get("range"), str):
                ranges[slot_name] = spec["range"]
            if "multivalued" in spec:
                multivalued[slot_name] = bool(spec.get("multivalued"))

    for slot_name in list(allowed):
        slot_def = slot_defs.get(slot_name) or {}
        if slot_def.get("required") is True:
            required.add(slot_name)
        range_name = ranges.get(slot_name) or slot_def.get("range")
        if isinstance(range_name, str):
            ranges[slot_name] = range_name
            if range_name in enums:
                values = enums[range_name].get("permissible_values") or {}
                enum_values[slot_name] = set(values.keys())
        if slot_name not in multivalued:
            multivalued[slot_name] = bool(slot_def.get("multivalued"))

    for name in _class_mro(schema, class_name):
        usage = (classes.get(name) or {}).get("slot_usage") or {}
        for slot_name, spec in usage.items():
            if isinstance(spec, dict) and spec.get("required") is False:
                required.discard(slot_name)

    return {
        "allowed": allowed,
        "required": required,
        "enums": enum_values,
        "ranges": ranges,
        "multivalued": multivalued,
    }


def listed_action_classes(schema: dict | None = None) -> set[str]:
    schema = schema or load_linkml_schema_recursive(ACTION_DATA_MODEL_SCHEMA)
    classes = schema.get("classes") or {}
    names: set[str] = set()
    for name, class_def in classes.items():
        if not isinstance(class_def, dict):
            continue
        if class_def.get("is_a") == "Action" and not class_def.get("abstract"):
            names.add(name)
    return names


def listed_chemical_classes(schema: dict | None = None) -> set[str]:
    schema = schema or load_linkml_schema_recursive(ACTION_DATA_MODEL_SCHEMA)
    classes = schema.get("classes") or {}
    names: set[str] = set()
    for name, class_def in classes.items():
        if name in {"ChemicalEntity"}:
            continue
        if not isinstance(class_def, dict):
            continue
        current = name
        seen: set[str] = set()
        while current and current not in seen:
            seen.add(current)
            if current == "ChemicalEntity":
                names.add(name)
                break
            current = (classes.get(current) or {}).get("is_a")
    names.add("ChemicalEntity")
    names.add("Substance")
    names.add("Mixture")
    names.add("MixtureSubstance")
    return names


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
