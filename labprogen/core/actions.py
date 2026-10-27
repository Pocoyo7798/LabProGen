"""Action domain objects matching the current Action Data Model."""

from .model import concrete_classes, default_params


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

    def add_chemical(self, chemical):
        self.chemicals.append(chemical)

    def add_subproduct(self, subproduct):
        self.subproducts.append(subproduct)

    def to_dict(self):
        data = {'action': type(self).__name__, 'params': self.params}
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


ACTION_CLASSES = {name: type(name, (Action,), {'__module__': __name__})
                  for name in concrete_classes('Action')}
globals().update(ACTION_CLASSES)
NoModification = ACTION_CLASSES['NoAction']
ChangeRecipient = ACTION_CLASSES['ChangeContainer']
