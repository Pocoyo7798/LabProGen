"""Field contracts for the current Action Data Model, shared by domain and UI."""

from __future__ import annotations

import copy
from functools import lru_cache

from labprogen.linkml.loader import class_slot_constraints, load_linkml_schema, _class_mro


@lru_cache(maxsize=1)
def model_schema():
    return load_linkml_schema()


def concrete_classes(base):
    schema = model_schema()
    return [name for name, definition in schema['classes'].items()
            if name != base and base in _class_mro(schema, name)
            and not definition.get('abstract') and not definition.get('mixin')]


def default_params(class_name):
    """Empty values for declared fields, excluding serialization discriminators."""
    schema = model_schema()
    if class_name not in schema['classes']:
        return {}
    constraints = class_slot_constraints(class_name, schema)
    # Source slot order keeps related fields together, including inherited mixins.
    names = [name for name in schema['slots'] if name in constraints['allowed']]
    return {name: [] if constraints['multivalued'].get(name) else
            {} if constraints['ranges'].get(name) in schema['classes'] else ''
            for name in names if name not in {'type', 'id'}}


def field_contract(key, class_name=None):
    schema = model_schema()
    spec = copy.deepcopy(schema['slots'].get(key, {}))
    if class_name in schema['classes']:
        constraints = class_slot_constraints(class_name, schema)
        spec['required'] = key in constraints['required']
        spec['range'] = constraints['ranges'].get(key, spec.get('range', 'string'))
        spec['multivalued'] = constraints['multivalued'].get(key, False)
        spec['declared'] = key in constraints['allowed']
    return spec


def field_config(key, class_name=None):
    from .config import FIELD_CONFIG

    config = dict(FIELD_CONFIG.get(key, {}))
    schema = model_schema()
    spec = field_contract(key, class_name)
    config.setdefault('label', key.replace('_', ' ').capitalize())
    config['required'] = bool(spec.get('required'))
    config['range'] = spec.get('range', 'string')
    config['multivalued'] = bool(spec.get('multivalued'))
    range_name = config['range']
    if config['multivalued'] and range_name in schema.get('enums', {}):
        config.update(type='record', options=list(schema['enums'][range_name]['permissible_values']))
    elif range_name in schema.get('enums', {}):
        config.update(type='dropdown', options=list(schema['enums'][range_name]['permissible_values']))
    elif key == 'chemical_list':
        config.update(type='list', include_concentration=True)
    elif range_name == 'ChemicalEntity':
        config.update(type='list' if config['multivalued'] else 'single_chemical',
                      include_concentration=False, for_solvent=False)
    elif range_name in schema['classes'] or config['multivalued']:
        config['type'] = 'record'
    elif range_name == 'integer':
        config.update(type='text', integer=True, minimum=0)
    else:
        config.setdefault('type', 'text')
    return config
