from config import KEY_DURATION, KEY_TEMPERATURE, KEY_COMPONENT

class Action:
    """Base class for laboratory actions"""
    def __init__(self, **kwargs):
        self.params = kwargs
    
    def to_dict(self):
        return {
            "action": self.__class__.__name__,
            "params": self.params
        }

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