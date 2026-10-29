"""Action domain objects matching the current Action Data Model."""

from .model import concrete_classes, default_params
from labprogen.linkml.models import model_class, to_model


class Action:
    def __init__(self, **kwargs):
        class_name = type(self).__name__
        legacy_type_slot = {"Add": "add_type", "ChangeAgitation": "agitation_type",
                            "ContinuousAddition": "continuous_add_type"}.get(class_name)
        if legacy_type_slot and "type" in kwargs:
            old_type = kwargs.pop("type")
            if legacy_type_slot in kwargs and kwargs[legacy_type_slot] != old_type:
                raise ValueError(f"Conflicting type arguments for {class_name}.")
            kwargs[legacy_type_slot] = old_type
        self.params = {**default_params(class_name), **kwargs}
        self.chemicals = []
        self.subproducts = []

    def to_model(self):
        """Convert a completed draft to its generated semantic data model."""
        from labprogen.linkml.adapter import flatten_exported_instance
        return to_model(flatten_exported_instance(self.to_linkml_dict()), type(self).__name__)

    def add_chemical(self, chemical):
        from .capabilities import can_attach_chemical_blocks
        if not can_attach_chemical_blocks(type(self).__name__):
            raise ValueError(f"Chemical Blocks cannot be attached to {type(self).__name__}: no compatible direct chemical relation.")
        self.chemicals.append(chemical)

    def add_subproduct(self, subproduct):
        self.subproducts.append(subproduct)

    def to_dict(self):
        data = {'action': type(self).__name__, 'params': self.params}
        data.update(getattr(self, '_complex_metadata', {}))
        if self.chemicals:
            data['chemicals'] = [c.to_dict() for c in self.chemicals]
        if self.subproducts:
            data['subproducts'] = [s.to_dict() for s in self.subproducts]
        return data

    def to_linkml_dict(self):
        from labprogen.linkml.adapter import action_to_linkml_dict
        data = action_to_linkml_dict(type(self).__name__, self.params,
                                    [c.to_linkml_dict() for c in self.chemicals])
        if self.subproducts:
            data['subproduct_branch'] = self.subproducts[0].to_linkml_dict()
            if len(self.subproducts) > 1:
                data['subproduct_branches'] = [s.to_linkml_dict() for s in self.subproducts]
        return data


ACTION_CLASSES = {name: type(name, (Action,), {'__module__': __name__, 'model_class': model_class(name)})
                  for name in concrete_classes('Action')}
globals().update(ACTION_CLASSES)
NoModification = ACTION_CLASSES['NoAction']
ChangeRecipient = ACTION_CLASSES['ChangeContainer']
