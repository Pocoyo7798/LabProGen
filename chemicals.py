from config import *

class Chemical:
    """Base class for chemicals"""
    def __init__(self, **kwargs):
        self.params = kwargs
    
    def to_dict(self):
        return {
            "chemical": self.__class__.__name__,
            "params": self.params
        }

class Molecule(Chemical):
    """Simple Molecule"""
    def __init__(self, name="", formula="", smile=""):
        super().__init__(**{
            KEY_NAME: name,
            KEY_FORMULA: formula,
            KEY_SMILES: smile
        })

class Material(Chemical):
    """Pure Crystalline Materials"""
    def __init__(self, name="", formula="", structure=""):
        super().__init__(**{
            KEY_NAME: name,
            KEY_FORMULA: formula,
            KEY_STRUCTURE: structure
        })