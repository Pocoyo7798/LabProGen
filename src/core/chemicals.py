from .config import *

class ChemicalEntity:
    """Base class for all chemical entities (First Level).
    
    Includes universal optional fields:
    - entity_id: Commercial or internal identifier
    - entity_producer: Institution that created the entity
    - entity_purity: Degree of purity
    - cas_number: Commercial identification number (CAS)
    
    Preparation procedure is managed visually through import/create buttons.
    """
    def __init__(self, entity_id="", entity_producer="", entity_purity="", cas_number="", **kwargs):
        self.params = {
            KEY_ENTITY_ID: entity_id,
            KEY_PRODUCER: entity_producer,
            KEY_ENTITY_PURITY: entity_purity,
            KEY_CAS_NUMBER: cas_number,
            **kwargs
        }
    
    def to_dict(self):
        """convert entity to dictionary for export."""
        return {
            "chemical": self.__class__.__name__,
            "params": self.params
        }

    def to_linkml_dict(self):
        from src.linkml.adapter import chemical_to_linkml_dict

        return chemical_to_linkml_dict(self.__class__.__name__, self.params)

class Substance(ChemicalEntity):
    """Second Level: Simple molecule that can be described by atom-level representations."""
    def __init__(self, name="", **kwargs):
        super().__init__(**{
            KEY_NAME: name,
            **kwargs
        })


class Molecules(Substance):
    """Third Level: Chemical entities described fully by formula + SMILES/InChi.
    
    Inherits from Substance with identical fields.
    """
    def __init__(self, name="", formula="", smile="", inchi="", **kwargs):
        super().__init__(name=name, **kwargs)
        self.params.update({
            KEY_FORMULA: formula,
            KEY_SMILES: smile,
            KEY_INCHI: inchi,
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
    """Mixture entity composed of other chemicals in a chemical list."""
    def __init__(self, name="", chemical_list=None, **kwargs):
        if chemical_list is None:
            chemical_list = []
        super().__init__(**{
            KEY_NAME: name,
            KEY_CHEMICAL_LIST: chemical_list,
            **kwargs
        })


class MixtureChemical(ChemicalEntity):
    """Third Level: Individual chemical in a mixture with concentration.
    
    Used only within Mixture.chemical_list as array items.
    Stores: {type, chemical_type, params, concentration}
    """
    def __init__(self, chemical_type="", params=None, concentration="", **kwargs):
        """
        Args:
            chemical_type: Name of the chemical class (e.g., 'Substance', 'Molecules')
            params: Dict of chemical-specific parameters
            concentration: Proportion in mixture (e.g., 'g/L', 'M', 'vol/vol')
        """
        if params is None:
            params = {}
        super().__init__(**{
            "chemical_type": chemical_type,
            **params,
            KEY_CONCENTRATION: concentration,
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

class Polymers(Molecules):
    """Third Level: Polymers using BigSMILES instead of SMILES.
    
    Inherits from Molecules, replaces smiles field with bigsmiles.
    """
    def __init__(self, name="", formula="", bigsmiles="", inchi="", **kwargs):
        super().__init__(name=name, formula=formula, smile=bigsmiles, inchi=inchi, **kwargs)
        # Replace SMILES with BigSMILES
        if KEY_SMILES in self.params:
            del self.params[KEY_SMILES]
        self.params[KEY_BIGSMILES] = bigsmiles

class Media(ChemicalEntity):
    """Biological media as Substance or Mixture (via entity_type)."""
    def __init__(
        self,
        entity_type="Substance",
        name="",
        chemical_list=None,
        quantity="",
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
        if chemical_list is None:
            chemical_list = []
        super().__init__(**{
            KEY_ENTITY_TYPE: entity_type,
            KEY_NAME: name,
            KEY_CHEMICAL_LIST: chemical_list if entity_type == "Mixture" else [],
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


class Dispersion(ChemicalEntity):
    """Dispersion (Mixture): solutes in chemical_list plus one solvent; always Mixture type."""
    def __init__(self, name="", chemical_list=None, solvent=None, **kwargs):
        if chemical_list is None:
            chemical_list = []
        if solvent is None:
            solvent = {}
        super().__init__(**{
            KEY_ENTITY_TYPE: "Mixture",
            KEY_NAME: name,
            KEY_CHEMICAL_LIST: chemical_list,
            KEY_SOLVENT: solvent,
            **kwargs
        })

class BioProducts(ChemicalEntity):
    """Biological products with production and localization metadata.

    Substance or Mixture (entity_type). Mixture uses name + chemical_list.
    """
    def __init__(
        self,
        entity_type="Substance",
        name="",
        chemical_list=None,
        origin="",
        production_phase="",
        location="",
        temperature_stability="",
        light_sensitivity="",
        oxidation_sensitivity="",
        toxicity_to_producer="",
        **kwargs,
    ):
        if chemical_list is None:
            chemical_list = []
        super().__init__(**{
            KEY_ENTITY_TYPE: entity_type,
            KEY_NAME: name,
            KEY_CHEMICAL_LIST: chemical_list if entity_type == "Mixture" else [],
            KEY_ORIGIN: origin,
            KEY_PRODUCTION_PHASE: production_phase,
            KEY_LOCATION: location,
            KEY_TEMPERATURE_STABILITY: temperature_stability,
            KEY_LIGHT_SENSITIVITY: light_sensitivity,
            KEY_OXIDATION_SENSITIVITY: oxidation_sensitivity,
            KEY_TOXICITY_TO_PRODUCER: toxicity_to_producer,
            **kwargs
        })


class HeterogeneousCatalysts(ChemicalEntity):
    """Heterogeneous catalysts as Substance or Mixture (entity_type). Mixture uses name + chemical_list."""
    def __init__(
        self,
        entity_type="Substance",
        name="",
        chemical_list=None,
        formula="",
        structure_3d="",
        crystallinity="",
        n2_bet_area="",
        n2_micropore_area="",
        n2_mesopore_area="",
        n2_total_volume="",
        n2_micropore_volume="",
        n2_mesopore_volume="",
        py_b_150="",
        py_b_450="",
        py_l_150="",
        py_l_450="",
        **kwargs,
    ):
        if chemical_list is None:
            chemical_list = []
        super().__init__(**{
            KEY_ENTITY_TYPE: entity_type,
            KEY_NAME: name,
            KEY_CHEMICAL_LIST: chemical_list if entity_type == "Mixture" else [],
            KEY_FORMULA: formula,
            KEY_3D_STRUCTURE: structure_3d,
            KEY_CRYSTALLINITY: crystallinity,
            KEY_N2_ADSORPTION_BET_AREA: n2_bet_area,
            KEY_N2_ADSORPTION_MICROPORE_AREA: n2_micropore_area,
            KEY_N2_ADSORPTION_MESOPORE_AREA: n2_mesopore_area,
            KEY_N2_ADSORPTION_TOTAL_VOLUME: n2_total_volume,
            KEY_N2_ADSORPTION_MICROPORE_VOLUME: n2_micropore_volume,
            KEY_N2_MESOPORE_VOLUME: n2_mesopore_volume,
            KEY_PY_B_150: py_b_150,
            KEY_PY_B_450: py_b_450,
            KEY_PY_L_150: py_l_150,
            KEY_PY_L_450: py_l_450,
            **kwargs
        })


# Backward compatibility alias
Chemical = ChemicalEntity
