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
    """Second Level: Chemical entities that do not have specific descriptors."""
    def __init__(self, name="", **kwargs):
        super().__init__(**{
            KEY_NAME: name,
            **kwargs
        })


class MixtureSubstance(ChemicalEntity):
    """Second Level: Chemical entity in a mixture with concentration.

    Used only within Mixture.chemical_list as array items.
    Stores: {chemical_type, params, concentration}
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

class Medium(Mixture):
    """Biological media purchased from a company or obtained from an external lab."""
    def __init__(
        self,
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
        super().__init__(name=name, chemical_list=chemical_list, **kwargs)
        self.params.update({
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


class Dispersion(Mixture):
    """Dispersion (Mixture): solutes in chemical_list plus one solvent."""
    def __init__(self, name="", chemical_list=None, solvent=None, **kwargs):
        if solvent is None:
            solvent = {}
        super().__init__(name=name, chemical_list=chemical_list, **kwargs)
        self.params[KEY_SOLVENT] = solvent

class BioProducts(ChemicalEntity):
    """Entities created by biological compounds like metabolites."""
    def __init__(
        self,
        name="",
        origin="",
        production_phase="",
        location="",
        temperature_stability="",
        light_sensitivity="",
        oxidation_sensitivity="",
        toxicity_to_producer="",
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


class HeterogeneousCatalysts(ChemicalEntity):
    """Substances that increase reaction rates with a different phase than the reaction medium."""
    def __init__(
        self,
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
        super().__init__(**{
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
