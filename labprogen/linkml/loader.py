"""Load LinkML schemas, resolve effective slot metadata and flatten local imports."""

from functools import lru_cache
import importlib
import copy
import sys
from pathlib import Path

from labprogen.core.paths import get_app_dir, get_bundle_dir, is_frozen

ACTION_DATA_MODEL_SCHEMA = "action_data_model.yaml"


def get_schema_directory() -> Path:
    """Resolve schemas from application assets, never from the working directory."""

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

    candidates.append(bundle_dir / "schema")

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return bundle_dir / "schema"


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
    """Flatten schema imports and apply runtime metamodel compatibility."""
    return _strip_unsupported_metamodel_keys(load_linkml_schema_recursive(schema_name))


@lru_cache(maxsize=8)
def _schema_view_from_json(source: str):
    from linkml_runtime.linkml_model.meta import SchemaDefinition
    from linkml_runtime.utils.schemaview import SchemaView
    import json

    return SchemaView(SchemaDefinition(**_strip_unsupported_metamodel_keys(json.loads(source))))


@lru_cache(maxsize=1)
def _default_schema_view():
    from linkml_runtime.linkml_model.meta import SchemaDefinition
    from linkml_runtime.utils.schemaview import SchemaView

    return SchemaView(SchemaDefinition(**build_validation_schema()))


def schema_view(schema: dict | None = None):
    """Official, induced LinkML metadata; explicit schemas are isolated snapshots.

    Treat the returned view as read-only. In particular, never mutate its slots.
    """
    if schema is None:
        return _default_schema_view()
    import json
    return _schema_view_from_json(json.dumps(schema, sort_keys=True))


def _class_mro(schema: dict, class_name: str) -> list[str]:
    """Ancestor membership, including mixins, resolved by LinkML itself."""
    view = schema_view(schema)
    return list(reversed(view.class_ancestors(class_name))) if class_name in view.all_classes() else []


@lru_cache(maxsize=512)
def _contracts_for_view(view, class_name):
    from linkml_runtime.dumpers import json_dumper

    if class_name not in view.all_classes():
        return {}
    return {str(slot.name): json_dumper.to_dict(slot)
            for slot in view.class_induced_slots(class_name)}


def class_slot_contracts(class_name: str, schema: dict | None = None) -> dict:
    """Class-scoped slots including attributes, inheritance and slot_usage."""
    return copy.deepcopy(_contracts_for_view(schema_view(schema), class_name))


def class_slot_constraints(class_name: str, schema: dict | None = None) -> dict:
    """Compatibility projection of official class-scoped LinkML metadata."""
    slots = class_slot_contracts(class_name, schema)
    view = schema_view(schema)
    return {
        "allowed": set(slots),
        "required": {name for name, slot in slots.items() if slot.get("required")},
        "enums": {name: set(view.get_enum(slot["range"]).permissible_values)
                  for name, slot in slots.items() if slot.get("range") in view.all_enums()},
        "ranges": {name: slot.get("range", "string") for name, slot in slots.items()},
        "multivalued": {name: bool(slot.get("multivalued")) for name, slot in slots.items()},
    }


def _listed_classes(base: str, schema: dict | None = None) -> set[str]:
    view = schema_view(schema)
    return {str(name) for name, cls in view.all_classes().items()
            if not cls.abstract and not cls.mixin and base in view.class_ancestors(name)}


def listed_action_classes(schema: dict | None = None) -> set[str]:
    return _listed_classes("Action", schema)


def listed_chemical_classes(schema: dict | None = None) -> set[str]:
    return _listed_classes("ChemicalEntity", schema)


def schema_summary(schema: dict) -> dict:
    classes = schema.get("classes", {}) if isinstance(schema, dict) else {}
    slots = schema.get("slots", {}) if isinstance(schema, dict) else {}
    enums = schema.get("enums", {}) if isinstance(schema, dict) else {}
    return {
        "name": schema.get("name", ""),
        "title": schema.get("title", ""),
        "version": schema.get("version", ""),
        "class_count": len(classes),
        "slot_count": len(slots),
        "enum_count": len(enums),
    }
