"""Chemical domain objects whose fields follow the current LinkML schema."""

from .config import canonical_chemical_name
from .model import concrete_classes, default_params
from labprogen.linkml.models import model_class, to_model


class ChemicalEntity:
    def __init__(self, **kwargs):
        self.params = {**default_params(type(self).__name__), **kwargs}

    def to_model(self):
        """Convert a completed draft to its generated semantic data model."""
        from labprogen.linkml.adapter import chemical_record_to_instance
        return to_model(chemical_record_to_instance(self.to_dict()), type(self).__name__)

    def to_dict(self):
        return {'chemical': type(self).__name__, 'params': self.params}

    def to_linkml_dict(self):
        from labprogen.linkml.adapter import chemical_to_linkml_dict
        return chemical_to_linkml_dict(type(self).__name__, self.params)


# Domain wrappers use generated field definitions.
CHEMICAL_CLASSES = {name: type(name, (ChemicalEntity,), {'__module__': __name__, 'model_class': model_class(name)})
                    for name in concrete_classes('ChemicalEntity')}
globals().update(CHEMICAL_CLASSES)
Chemical = ChemicalEntity

# Import compatibility; new records always carry current schema names.
Molecules = CHEMICAL_CLASSES['Molecule']
Polymers = CHEMICAL_CLASSES['Polymer']
MixtureSubstance = CHEMICAL_CLASSES['MixtureConstituent']
HeterogeneousCatalysts = CHEMICAL_CLASSES['PorousMaterial']


def selectable_chemical_entity_types():
    return [name for name in CHEMICAL_CLASSES if name != 'MixtureConstituent']


def embedded_chemical_type_choices(*, for_solvent=False, include_concentration=True):
    return selectable_chemical_entity_types()
