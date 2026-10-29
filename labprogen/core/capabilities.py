"""Derives chemical attachment roles and action capabilities from LinkML metadata."""

from dataclasses import dataclass

from labprogen.linkml.loader import class_slot_contracts, schema_view
from .model import field_contract, range_is_subclass

CHEMICAL_ATTACHMENT_ANNOTATION = 'labprogen_chemical_attachment'
LEGACY_CHEMICAL_SLOT = 'chemical'


class ChemicalAttachmentRoleError(ValueError):
    """An attachment role is ambiguous or contradicts its field contract."""


def chemical_attachment_slot(class_name, *, schema=None):
    """Resolve the marked chemical link, with the historical name as a fallback.

    An explicit role declaration overrides the fallback, including false values.
    Every marked field must have a ChemicalEntity-compatible range.
    """
    slots = class_slot_contracts(class_name, schema)
    declared = False
    selected = []
    for name, slot in slots.items():
        annotations = slot.get('annotations', {})
        if CHEMICAL_ATTACHMENT_ANNOTATION not in annotations:
            continue
        declared = True
        annotation = annotations[CHEMICAL_ATTACHMENT_ANNOTATION]
        value = annotation.get('value') if isinstance(annotation, dict) else annotation
        if isinstance(value, str) and value.lower() in {'true', 'false'}:
            value = value.lower() == 'true'
        if not isinstance(value, bool):
            raise ChemicalAttachmentRoleError(f'{class_name}.{name}: {CHEMICAL_ATTACHMENT_ANNOTATION} must be boolean.')
        if value:
            selected.append(name)
    if len(selected) > 1:
        raise ChemicalAttachmentRoleError(f'{class_name}: multiple chemical attachment fields: {", ".join(selected)}.')
    if declared:
        name = selected[0] if selected else None
        if name and not range_is_subclass(slots[name].get('range'), 'ChemicalEntity', schema=schema):
            raise ChemicalAttachmentRoleError(f'{class_name}.{name}: chemical attachment range must be ChemicalEntity-compatible.')
        return name
    legacy = slots.get(LEGACY_CHEMICAL_SLOT)
    if legacy and range_is_subclass(legacy.get('range'), 'ChemicalEntity', schema=schema):
        return LEGACY_CHEMICAL_SLOT
    return None


@dataclass(frozen=True)
class ActionCapabilities:
    allows_chemical_blocks: bool = False
    requires_chemical_relation: bool = False
    chemical_slot: str | None = None


def get_action_capabilities(action_name, *, schema=None) -> ActionCapabilities:
    """Describe a concrete Action using its effective fields in the supplied schema."""
    if not isinstance(action_name, str) or not action_name:
        return ActionCapabilities()
    view = schema_view(schema)
    definition = view.all_classes().get(action_name)
    if (definition is None or definition.abstract or definition.mixin
            or 'Action' not in view.class_ancestors(action_name)):
        return ActionCapabilities()
    name = chemical_attachment_slot(action_name, schema=schema)
    if name is None:
        return ActionCapabilities()
    slot = field_contract(name, action_name, schema=schema)
    return ActionCapabilities(True, bool(slot['required']), name)


def can_attach_chemical_blocks(action_name, *, schema=None) -> bool:
    return get_action_capabilities(action_name, schema=schema).allows_chemical_blocks


def requires_canvas_chemical(action_name, *, params=None, part_of_complex_action=False, schema=None) -> bool:
    """Check a required relationship across inline values and complex-draft context."""
    if part_of_complex_action:
        return False
    capabilities = get_action_capabilities(action_name, schema=schema)
    inline = (params or {}).get(capabilities.chemical_slot)
    has_inline_value = inline is not None and inline != '' and inline != [] and inline != {}
    return capabilities.requires_chemical_relation and not has_inline_value
