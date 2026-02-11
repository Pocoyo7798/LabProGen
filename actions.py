from config import KEY_DURATION, KEY_TEMPERATURE, KEY_COMPONENT

class Action:
    """Base class for laboratory actions"""
    def __init__(self, **kwargs):
        self.params = kwargs
        self.chemicals = [] # Added to store attached chemicals

    def add_chemical(self, chemical):
        """Attaches a chemical object to this action"""
        self.chemicals.append(chemical)
    
    def to_dict(self):
        """Convert to dictionary including nested chemicals"""
        data = {
            "action": self.__class__.__name__,
            "params": self.params
        }
        if self.chemicals:
            # Export nested chemicals as a list of dictionaries
            data["chemicals"] = [c.to_dict() for c in self.chemicals]
        return data

class Add(Action):
    """Add a component to the reaction"""
    def __init__(self, component="", duration=0):
        # Use constants as keys in the params dictionary
        super().__init__(**{
            KEY_COMPONENT: component,
            KEY_DURATION: duration
        })

class ChangeTemperature(Action):
    """Change the temperature of the reaction"""
    def __init__(self, temperature=50):
        super().__init__(**{
            KEY_TEMPERATURE: temperature
        })

class Stir(Action):
    """Stir the reaction mixture"""
    def __init__(self, duration=30):
        super().__init__(**{
            KEY_DURATION: duration
        })