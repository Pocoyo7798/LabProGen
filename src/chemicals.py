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

class Material(Chemical):
    """perfect single crystal solid chemical substance."""
    def __init__(self, atomic_composition="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_ATOMIC_COMP: atomic_composition,
            KEY_QUANTITY: quantity
        })

class ComplexMaterial(Chemical):
    """non-perfect multi-crystal substance with structural defects."""
    def __init__(self, base_material="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_BASE_MAT: base_material,
            KEY_QUANTITY: quantity
        })

class Mixture(Chemical):
    """generic mixture entity represented only by total quantity."""
    def __init__(self, quantity="0 mL", **kwargs):
        super().__init__(**{
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
    def __init__(self, base_complex_material="", quantity="0 g", **kwargs):
        super().__init__(**{
            KEY_BASE_COMPLEX: base_complex_material,
            KEY_QUANTITY: quantity
        })

class Polymers(Chemical):
    """entity composed of repeating structural units."""
    def __init__(self, **kwargs):
        super().__init__(**{})

class Media(Chemical):
    """cell-culture media entity with functional and quality descriptors."""
    def __init__(self, quantity="0 g", function="Carbon Source", concentration="0 g/L", purity="technical", sterility="sterile", solubility="", **kwargs):
        super().__init__(**{
            KEY_QUANTITY: quantity,
            KEY_FUNCTION: function,
            KEY_CONCENTRATION: concentration,
            KEY_PURITY: purity,
            KEY_STERILITY: sterility,
            KEY_SOLUBILITY: solubility
        })

class BioProducts(Chemical):
    """biological products with production and localization metadata."""
    def __init__(self, name="", origin="primary metabolite", production_phase="associated to growth", location="intracellular", toxicity_to_producer="neutral", **kwargs):
        super().__init__(**{
            KEY_NAME: name,
            KEY_ORIGIN: origin,
            KEY_PRODUCTION_PHASE: production_phase,
            KEY_LOCATION: location,
            KEY_TOXICITY_TO_PRODUCER: toxicity_to_producer
        })