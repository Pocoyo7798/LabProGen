"""LinkML contracts and their presentation in the existing editors.

Structural constraints always come from the official SchemaView. Presentation
preferences cannot declare a field, change its type or relax its constraints.
"""

from __future__ import annotations

import copy
from functools import lru_cache

from labprogen.linkml.loader import class_slot_contracts, load_linkml_schema, schema_view
from labprogen.linkml.models import model_class


@lru_cache(maxsize=1)
def model_schema():
    return load_linkml_schema()


def concrete_classes(base, *, schema=None):
    view = schema_view(schema)
    return [str(name) for name, cls in view.all_classes().items()
            if name != base and base in view.class_ancestors(name)
            and not cls.abstract and not cls.mixin]


def default_params(class_name):
    """Editable drafts: model defaults when provided, otherwise empty values.

    Blank required fields are allowed in drafts, never in validated exports.
    """
    schema = model_schema()
    if class_name not in schema['classes']:
        return {}
    slots = class_slot_contracts(class_name)
    fields = model_class(class_name).model_fields
    names = [name for name in schema.get('slots', {}) if name in fields]
    names.extend(name for name in fields if name not in names)
    result = {}
    for name in names:
        if name in {'type', 'id'}:
            continue
        field = fields[name]
        default = field.get_default(call_default_factory=True) if not field.is_required() else None
        if default is not None:
            result[name] = copy.deepcopy(default)
        else:
            slot = slots.get(name, {})
            result[name] = [] if slot.get('multivalued') else {} if slot.get('range') in schema['classes'] else ''
    return result


def field_contract(key, class_name=None, *, schema=None):
    """No global fallback for a slot that is absent from the requested class."""
    view = schema_view(schema)
    if class_name is not None:
        spec = class_slot_contracts(class_name, schema).get(key)
    else:
        # Global slots are useful for presentation only; attributes need a class.
        from linkml_runtime.dumpers import json_dumper
        slot = view.get_slot(key, attributes=False)
        spec = json_dumper.to_dict(slot) if slot else None
    if spec is None:
        return {'declared': False, 'required': False, 'multivalued': False, 'range': None}
    return {**copy.deepcopy(spec), 'declared': True,
            'required': bool(spec.get('required')), 'multivalued': bool(spec.get('multivalued')),
            'range': spec.get('range') or view.schema.default_range or 'string'}


def range_is_subclass(range_name, base, *, schema=None):
    view = schema_view(schema)
    return range_name in view.all_classes() and base in view.class_ancestors(range_name)


def chemical_fields(class_name=None, *, schema=None):
    """Chemical relations, including subclasses and class-scoped attributes."""
    view = schema_view(schema)
    classes = [class_name] if class_name is not None else view.all_classes()
    return frozenset(name for cls in classes for name, slot in class_slot_contracts(cls, schema).items()
                     if range_is_subclass(slot.get('range'), 'ChemicalEntity', schema=schema))


def field_config(key, class_name=None, *, schema=None):
    from .config import UI_FIELD_PREFERENCES, LEGACY_FIELD_PREFERENCES

    spec = field_contract(key, class_name, schema=schema)
    preferences = UI_FIELD_PREFERENCES if spec['declared'] else LEGACY_FIELD_PREFERENCES
    config = copy.deepcopy(preferences.get(key, {}))
    config['label'] = config.get('labels_by_action', {}).get(class_name) or config.get('label') or spec.get('title') or key.replace('_', ' ').capitalize()
    config.setdefault('placeholder', spec.get('description', ''))
    config.update(spec)
    # Model constraints override widget preferences. GUI minima may be stricter
    # business rules (Repeat), but never override an explicit schema boundary.
    if spec.get('minimum_value') is not None:
        config['minimum'] = spec['minimum_value']
    if spec.get('maximum_value') is not None:
        config['maximum'] = spec['maximum_value']
    if not spec['declared']:
        config.update(type='retained', required=False)
        return config
    view = schema_view(schema)
    range_name = spec['range']
    config.pop('options', None)
    if range_name in view.all_enums():
        config.update(type='record' if spec['multivalued'] else 'dropdown',
                      options=list(view.get_enum(range_name).permissible_values))
    elif range_is_subclass(range_name, 'ChemicalEntity', schema=schema):
        config.update(type='list' if spec['multivalued'] else 'single_chemical',
                      include_concentration=range_is_subclass(range_name, 'MixtureConstituent', schema=schema),
                      for_solvent=False)
    elif range_name in view.all_classes() or spec['multivalued']:
        config['type'] = 'record'
    elif range_name == 'boolean':
        config.update(type='dropdown', options=['True', 'False'])
    elif range_name in {'integer', 'float', 'double', 'decimal'}:
        config.update(type='text', integer=range_name == 'integer')
    else:
        # A stale enum preference must not leave an empty dropdown after a type change.
        if config.get('type') in {'dropdown', 'list', 'single_chemical', 'record'}:
            config['type'] = 'text'
        config.setdefault('type', 'text')
    return config
