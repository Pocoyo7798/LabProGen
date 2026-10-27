"""Chemical domain objects whose fields follow the current LinkML schema."""

from .config import canonical_chemical_name
from .model import concrete_classes, default_params


class ChemicalEntity:
    def __init__(self, **kwargs):
        self.params = {**default_params(type(self).__name__), **kwargs}

    def to_dict(self):
        return {'chemical': type(self).__name__, 'params': self.params}

    def to_linkml_dict(self):
        from labprogen.linkml.adapter import chemical_to_linkml_dict
        return chemical_to_linkml_dict(type(self).__name__, self.params)


# Concrete wrappers preserve the domain API without duplicating schema fields.
CHEMICAL_CLASSES = {name: type(name, (ChemicalEntity,), {'__module__': __name__})
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
