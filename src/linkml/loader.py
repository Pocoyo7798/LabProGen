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


def load_linkml_schema(schema_name: str = "dcat_p_lab.yaml") -> dict:
    schema_path = get_schema_directory() / schema_name
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    return _load_yaml_file(str(schema_path))


def load_linkml_schema_recursive(schema_name: str = "dcat_p_lab.yaml") -> dict:
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
            if imp.startswith(("http://", "https://")) or ":" in imp:
                continue
            _load(imp)

    _load(schema_name)
    merged["imports"] = []
    return merged


def build_validation_schema(schema_name: str = "dcat_p_lab.yaml") -> dict:
    """Build a validation-friendly schema with local imports merged and stubs added."""

    schema = load_linkml_schema_recursive(schema_name)
    classes = schema.setdefault("classes", {})
    slots = schema.setdefault("slots", {})
    enums = schema.setdefault("enums", {})
    types = schema.setdefault("types", {})

    qualitative_string_slots = {
        "molecular_formula",
        "smiles",
        "inchi",
        "inchikey",
        "iupac_name",
    }

    for class_def in classes.values():
        if isinstance(class_def, dict) and class_def.get("mixin"):
            class_def.pop("mixin", None)

    primitive_ranges = {
        "string",
        "boolean",
        "integer",
        "float",
        "double",
        "decimal",
        "uri",
        "curie",
        "ncname",
        "nodeidentifier",
        "jsonpointer",
        "jsonpath",
        "sparqlpath",
        "objectidentifier",
        "date",
        "datetime",
        "time",
        "duration",
    }

    def is_primitive(name: object) -> bool:
        return isinstance(name, str) and name in primitive_ranges

    def looks_like_class(name: object) -> bool:
        return isinstance(name, str) and bool(name) and name[0].isupper() and " " not in name and ":" not in name

    def looks_like_slot(name: object) -> bool:
        return isinstance(name, str) and bool(name) and name[0].islower() and " " not in name and ":" not in name

    def add_class_stub(name: str) -> None:
        classes.setdefault(name, {"description": f"Auto-stub for validation: {name}", "slots": []})

    def add_slot_stub(name: str) -> None:
        slots.setdefault(name, {"description": f"Auto-stub for validation: {name}", "range": "string"})

    changed = True
    while changed:
        changed = False

        for class_name, class_def in list(classes.items()):
            if not isinstance(class_def, dict):
                continue

            for parent_key in ("is_a", "mixin", "mixins", "implements"):
                parent_value = class_def.get(parent_key)
                values = parent_value if isinstance(parent_value, list) else ([parent_value] if parent_value else [])
                for parent in values:
                    if looks_like_class(parent) and parent not in classes and parent not in enums and parent not in types:
                        add_class_stub(parent)
                        changed = True

            for slot_name, slot_usage in (class_def.get("slot_usage") or {}).items():
                if looks_like_slot(slot_name) and slot_name not in slots:
                    add_slot_stub(slot_name)
                    changed = True
                if isinstance(slot_usage, dict):
                    rng = slot_usage.get("range")
                    if looks_like_class(rng) and not is_primitive(rng) and rng not in classes and rng not in enums and rng not in types:
                        add_class_stub(rng)
                        changed = True

            for slot_name in class_def.get("slots", []) or []:
                if looks_like_slot(slot_name) and slot_name not in slots:
                    add_slot_stub(slot_name)
                    changed = True

        for slot_name, slot_def in list(slots.items()):
            if not isinstance(slot_def, dict):
                continue

            parent = slot_def.get("is_a")
            if looks_like_slot(parent) and parent not in slots:
                add_slot_stub(parent)
                changed = True

            rng = slot_def.get("range")
            if looks_like_class(rng) and not is_primitive(rng) and rng not in classes and rng not in enums and rng not in types:
                add_class_stub(rng)
                changed = True

            binding_ranges = slot_def.get("bindings") or []
            for binding in binding_ranges:
                if isinstance(binding, dict):
                    br = binding.get("range")
                    if looks_like_class(br) and br not in classes and br not in enums and br not in types:
                        add_class_stub(br)
                        changed = True

    for slot_name, slot_def in slots.items():
        if slot_name in qualitative_string_slots and isinstance(slot_def, dict):
            slot_def["range"] = "string"

    # Ensure quantity-like classes keep their value/unit/raw structure during
    # validation even when the external imported base classes are not available.
    qa = classes.get("QuantitativeAttribute")
    if isinstance(qa, dict):
        qa_slots = qa.get("slots")
        if not isinstance(qa_slots, list) or not qa_slots:
            qa["slots"] = ["value", "unit", "raw"]

    return schema


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
