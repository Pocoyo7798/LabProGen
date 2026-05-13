from .config import *

class ChemicalEntity:
    """Base class for all chemical entities (First Level).
    
    Includes universal optional fields:
    - entity_id: Commercial or internal identifier
    - entity_producer: Institution that created the entity
    - entity_purity: Degree of purity
    
    Preparation procedure is managed visually through import/create buttons.
    """
    def __init__(self, entity_id="", entity_producer="", entity_purity="", **kwargs):
        self.params = {
            KEY_ENTITY_ID: entity_id,
            KEY_PRODUCER: entity_producer,
            KEY_ENTITY_PURITY: entity_purity,
            **kwargs
        }
    
    def to_dict(self):
        """convert entity to dictionary for export."""
        return {
            "chemical": self.__class__.__name__,
            "params": self.params
        }

    def to_linkml_dict(self):
        from .linkml_adapter import chemical_to_linkml_dict

        return chemical_to_linkml_dict(self.__class__.__name__, self.params)

class Substance(ChemicalEntity):
    """simple molecule that can be described by atom-level representations."""
    def __init__(self, formula="", smile="", inchi="", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_SMILES: smile,
            KEY_INCHI: inchi,
            **kwargs
        })

class Material(ChemicalEntity):
    """generic material with structural, textural and chemical descriptors."""
    def __init__(self, formula="", structure_descriptor="", textural_descriptors="", chemical_descriptors="", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_STRUCT_DESC: structure_descriptor,
            KEY_TEXTURAL_DESC: textural_descriptors,
            KEY_CHEM_DESC: chemical_descriptors,
            **kwargs
        })

class Mixture(ChemicalEntity):
    """mixture entity represented by name."""
    def __init__(self, name="", **kwargs):
        super().__init__(**{
            KEY_NAME: name,
            **kwargs
        })

class PerfectSingleCrystalMaterial(ChemicalEntity):
    """perfect single crystal material with formula and CIF file reference."""
    def __init__(self, formula="", cif="", **kwargs):
        super().__init__(**{
            KEY_FORMULA: formula,
            KEY_CIF: cif,
            **kwargs
        })

class Polymers(ChemicalEntity):
    """polymer entity represented by BigSMILES."""
    def __init__(self, bigsmiles="", **kwargs):
        super().__init__(**{
            KEY_BIGSMILES: bigsmiles,
            **kwargs
        })

class Media(ChemicalEntity):
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
            **kwargs
        })

class BioProducts(ChemicalEntity):
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
            KEY_TOXICITY_TO_PRODUCER: toxicity_to_producer,
            **kwargs
        })
# Backward compatibility alias
Chemical = ChemicalEntity
