from .config import *

class Chemical:
    """base class for chemical entities."""
    def __init__(self, **kwargs):
        self.params = kwargs
    
    def to_dict(self):
        """convert entity to dictionary for export."""
        return {
            "chemical": self.__class__.__name__,
            "params": self.params
        }

class Substance(Chemical):
    """simple chemical described by atoms."""
    def __init__(self, formula="", smile="", inchi="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_SMILES: smile,
            KEY_INCHI: inchi,
            KEY_QUANTITY: quantity
        })

class UnknownSubstance(Chemical):
    """substance with a specific market name but imprecise composition."""
    def __init__(self, name="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_NAME: name,
            KEY_QUANTITY: quantity
        })

class Solution(Chemical):
    """mixture of solvent and solutes."""
    def __init__(self, solvent="", solutes="", quantity="0 mL", **kwargs):
        super().__init__(**{
            KEY_SOLVENT: solvent,
            KEY_SOLUTES: solutes,
            KEY_QUANTITY: quantity
        })

class Material(Chemical):
    """perfect single crystal solid chemical substance."""
    def __init__(self, atomic_composition="", structure_descriptor="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_ATOMIC_COMP: atomic_composition,
            KEY_STRUCT_DESC: structure_descriptor,
            KEY_QUANTITY: quantity
        })

class ComplexMaterial(Chemical):
    """non-perfect multi-crystal substance with structural defects."""
    def __init__(self, base_material="", textural_descriptors="", chemical_descriptors="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_BASE_MAT: base_material,
            KEY_TEXTURAL_DESC: textural_descriptors,
            KEY_CHEM_DESC: chemical_descriptors,
            KEY_QUANTITY: quantity
        })

class HeterogeneousMaterial(Chemical):
    """material composed of at least two different perfect single crystal types."""
    def __init__(self, materials_list="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_MAT_LIST: materials_list,
            KEY_QUANTITY: quantity
        })

class ComplexHeterogeneousMaterial(Chemical):
    """material composed of at least two different non-perfect multi-crystal types."""
    def __init__(self, base_complex_material="", textural_descriptors="", chemical_descriptors="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_BASE_COMPLEX: base_complex_material,
            KEY_TEXTURAL_DESC: textural_descriptors,
            KEY_CHEM_DESC: chemical_descriptors,
            KEY_QUANTITY: quantity
        })