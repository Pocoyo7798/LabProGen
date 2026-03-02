from config import *

class Action:
    """Base class for all laboratory actions."""
    def __init__(self, **kwargs):
        self.params = kwargs
        self.chemicals = [] # stores attached Chemical entities
        self.subproducts = [] # stores subproducts created in this action

    def add_chemical(self, chemical):
        """attaches a chemical ingredient to this action."""
        self.chemicals.append(chemical)
    
    def add_subproduct(self, subproduct):
        self.subproducts.append(subproduct)

    def to_dict(self):
        data = {"action": self.__class__.__name__, "params": self.params}
        if self.chemicals:
            data["chemicals"] = [c.to_dict() for c in self.chemicals]
        if self.subproducts:
            data["subproducts"] = [s.to_dict() for s in self.subproducts]
        return data

# --- Elementary Actions ---

class Add(Action):
    """Addition of a chemical entity."""
    def __init__(self, chemical="", duration="0 s", type="Normal", **kwargs):
        super().__init__(**{
            KEY_CHEMICAL: chemical,
            KEY_DURATION: duration,
            KEY_ADD_TYPE: type
        })

class Grind(Action):
    """Triturate a solid substance. Has no specific parameters."""
    def __init__(self, **kwargs):
        super().__init__()

class Separate(Action):
    """Physical separation of two different phases."""
    def __init__(self, phase_to_keep="Liquid", method="Filtration", **kwargs):
        super().__init__(**{
            KEY_PHASE: phase_to_keep,
            KEY_METHOD: method
        })

class Sieve(Action):
    """Screening of solid particles by size."""
    def __init__(self, min_size="0 μm", max_size="0 μm", **kwargs):
        super().__init__(**{
            KEY_MIN_SIZE: min_size,
            KEY_MAX_SIZE: max_size
        })

class Stir(Action):
    """Agitation of a mixture."""
    def __init__(self, duration="30 min", type="Automatic", speed="0 rpm", **kwargs):
        super().__init__(**{
            KEY_DURATION: duration,
            KEY_STIR_TYPE: type,
            KEY_SPEED: speed
        })

class Wait(Action):
    """Time passes with nothing happening."""
    def __init__(self, duration="10 min", **kwargs):
        super().__init__(**{
            KEY_DURATION: duration
        })

# --- Support Actions ---

class ChangeAtmosphere(Action):
    """Modification of the atmosphere composition."""
    def __init__(self, gases="", flow_rate="0 mL/min", pressure="1 bar", **kwargs):
        super().__init__(**{
            KEY_GASES: gases,
            KEY_FLOW_RATE: flow_rate,
            KEY_PRESSURE: pressure
        })

class ChangeTemperature(Action):
    """Temperature modification."""
    def __init__(self, temperature="50 °C", process="Electrical", ramp="0 °C/min", power="0 W", **kwargs):
        super().__init__(**{
            KEY_TEMPERATURE: temperature,
            KEY_PROCESS: process,
            KEY_RAMP: ramp,
            KEY_POWER: power
        })

class ChangeRecipient(Action):
    """Modification of the mixture recipient."""
    def __init__(self, recipient="Beaker", material="Glass", volume="250 mL", **kwargs):
        super().__init__(**{
            KEY_RECIPIENT: recipient,
            KEY_MATERIAL: material,
            KEY_VOLUME: volume
        })

class NewMixture(Action):
    """Indication of starting a new mixture."""
    def __init__(self, mixture_name="", **kwargs):
        super().__init__(**{
            KEY_MIXTURE_NAME: mixture_name
        })

class SubProductCreation(Action):
    """Indication that another product will not follow the main path."""
    def __init__(self, substance="", **kwargs):
        super().__init__(**{
            KEY_SUBSTANCE: substance
        })

class Repeat(Action):
    """Indication of the number of repetitions of the elementary actions."""
    def __init__(self, amount="1", **kwargs):
        super().__init__(**{
            KEY_AMOUNT: amount
        })