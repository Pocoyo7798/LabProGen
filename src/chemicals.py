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
    """simple molecule that can be described by atom-level representations."""
    def __init__(self, formula="", smile="", inchi="", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_SMILES: smile,
            KEY_INCHI: inchi
        })

class Material(Chemical):
    """generic material with structural, textural and chemical descriptors."""
    def __init__(self, formula="", structure_descriptor="", textural_descriptors="", chemical_descriptors="", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_STRUCT_DESC: structure_descriptor,
            KEY_TEXTURAL_DESC: textural_descriptors,
            KEY_CHEM_DESC: chemical_descriptors
        })

class Mixture(Chemical):
    """mixture entity represented by name."""
    def __init__(self, name="", **kwargs):
        super().__init__(**{
            KEY_NAME: name
        })

class PerfectSingleCrystalMaterial(Chemical):
    """perfect single crystal material with formula and CIF file reference."""
    def __init__(self, formula="", cif="", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_CIF: cif
        })

class Polymers(Chemical):
    """polymer entity represented by BigSMILES."""
    def __init__(self, bigsmiles="", **kwargs):
        super().__init__(**{
            KEY_BIGSMILES: bigsmiles
        })

class Media(Chemical):
    """cell-culture media entity with functional and quality descriptors."""
    def __init__(
        self,
        quantity="0 g",
        function="",
        state="",
        concentration="",
        purity="",
        sterility="",
        solubility="",
        temperature_stability="",
        light_sensitivity="",
        oxidation_sensitivity="",
        **kwargs,
    ):
        super().__init__(**{
            KEY_QUANTITY: quantity,
            KEY_FUNCTION: function,
            KEY_STATE: state,
            KEY_CONCENTRATION: concentration,
            KEY_PURITY: purity,
            KEY_STERILITY: sterility,
            KEY_SOLUBILITY: solubility,
            KEY_TEMPERATURE_STABILITY: temperature_stability,
            KEY_LIGHT_SENSITIVITY: light_sensitivity,
            KEY_OXIDATION_SENSITIVITY: oxidation_sensitivity,
        })

class BioProducts(Chemical):
    """biological products with production and localization metadata."""
    def __init__(
        self,
        name="",
        origin="",
        production_phase="",
        location="",
        temperature_stability="",
        light_sensitivity="",
        oxidation_sensitivity="",
        toxicity_to_producer="neutral",
        **kwargs,
    ):
        super().__init__(**{
            KEY_NAME: name,
            KEY_ORIGIN: origin,
            KEY_PRODUCTION_PHASE: production_phase,
            KEY_LOCATION: location,
            KEY_TEMPERATURE_STABILITY: temperature_stability,
            KEY_LIGHT_SENSITIVITY: light_sensitivity,
            KEY_OXIDATION_SENSITIVITY: oxidation_sensitivity,
            KEY_TOXICITY_TO_PRODUCER: toxicity_to_producer
        })