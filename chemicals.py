class Chemical:
    """Base class for laboratory actions"""
    def __init__(self, **kwargs):
        self.params = kwargs
    
    def to_dict(self):
        return {
            "action": self.__class__.__name__,
            "params": self.params
        }


class Molecule(Chemical):
    """Simple Molecule"""
    def __init__(self, name="", formula="", smile=""):
        super().__init__(name=name, formula=formula, smile=smile)

class Material(Chemical):
    """Pure Crystalline Materials"""
    def __init__(self, name="", formula="", structure=""):
        super().__init__(name=name, formula=formula, structure=structure)