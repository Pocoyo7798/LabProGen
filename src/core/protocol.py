import json
from .actions import *
from .chemicals import *
from .config import DEFAULT_PROTOCOL_NAME
from src.linkml.adapter import convert_linkml_to_protocol
from src.linkml.exporter import convert_protocol_to_linkml


class Protocol:
    """Represents a laboratory procedure protocol"""
    
    def __init__(self):
        self.actions = []
    
    def add_action(self, action):
        """Add an action to the protocol"""
        self.actions.append(action)

    @staticmethod
    def build_protocol_envelope(flows, protocol_name=DEFAULT_PROTOCOL_NAME):
        """Build the canonical protocol container used across editor/domain adapters."""
        return {
            "protocol_name": protocol_name,
            "total_flows": len(flows or []),
            "flows": flows or [],
        }
    
    def to_dict(self):
        """Convert protocol to dictionary"""
        return [action.to_dict() for action in self.actions]

    def to_protocol_dict(self):
        """Convert protocol domain actions to the editor's protocol envelope."""
        flows = [
            {
                "flow_id": 1,
                "type": "horizontal",
                "is_explicit_first": False,
                "steps": [action.to_dict() for action in self.actions],
            }
        ]
        return self.build_protocol_envelope(flows)
    
    def to_json(self):
        """Convert protocol to JSON string"""
        return json.dumps(self.to_dict(), indent=2)

    def to_linkml_dict(self, mode="strict"):
        """Convert protocol to the canonical LinkML-aligned semantic payload."""
        return convert_protocol_to_linkml(self.to_protocol_dict(), mode=mode)

    def to_optimized_linkml_dict(self):
        """Convert protocol to the optimized graph-style LinkML export."""
        return convert_protocol_to_linkml(self.to_protocol_dict(), mode="optimized")
    
    def export(self, filename="protocol.json"):
        """Export protocol to a JSON file"""
        with open(filename, "w") as f:
            f.write(self.to_json())

    @staticmethod
    def from_linkml_dict(linkml_data):
        """Create a protocol from a LinkML semantic payload."""
        return Protocol.from_dict(convert_linkml_to_protocol(linkml_data))

    @staticmethod
    def _build_action(action_type, params):
        action_classes = {
            "Add": Add,
            "Grind": Grind,
            "Separate": Separate,
            "Sieve": Sieve,
            "Wait": Wait,
            "ChangeAtmosphere": ChangeAtmosphere,
            "ChangeTemperature": ChangeTemperature,
            "NewRecipient": NewRecipient,
            "ChangeAgitation": ChangeAgitation,
            "SubProductCreation": SubProductCreation,
            "Repeat": Repeat,
            "ContinuousAddition": ContinuousAddition,
        }

        action_class = action_classes.get(action_type, Action)
        try:
            return action_class(**(params or {}))
        except TypeError:
            if action_type and action_type not in action_classes:
                dynamic_action_class = type(action_type, (Action,), {})
                return dynamic_action_class(**(params or {}))
            return Action(**(params or {}))

    @staticmethod
    def _build_chemical(chemical_name, params):
        chemical_classes = {
            "Substance": Substance,
            "Material": Material,
            "Mixture": Mixture,
            "PerfectSingleCrystalMaterial": PerfectSingleCrystalMaterial,
            "Polymers": Polymers,
            "Media": Media,
            "Dispersion": Dispersion,
            "BioProducts": BioProducts,
        }
        chemical_class = chemical_classes.get(chemical_name, Chemical)
        try:
            return chemical_class(**(params or {}))
        except TypeError:
            return Chemical(**(params or {}))

    @staticmethod
    def _iter_steps(data):
        if isinstance(data, dict) and "activities" in data and "flows" not in data:
            data = convert_linkml_to_protocol(data)

        if isinstance(data, dict):
            flows = data.get("flows", []) or []
            for flow in flows:
                for step in flow.get("steps", []) or []:
                    yield step
            return

        for item in data or []:
            yield item

    @staticmethod
    def _build_action_from_step(step):
        action_type = step.get("action")
        params = step.get("params", {})
        action = Protocol._build_action(action_type, params)

        for chem_data in step.get("chemicals", []) or []:
            chem = Protocol._build_chemical(chem_data.get("chemical"), chem_data.get("params", {}))
            action.add_chemical(chem)

        for chem_data in (params.get(KEY_SUBSTANCE, []) or []):
            if isinstance(chem_data, dict):
                chem = Protocol._build_chemical(chem_data.get("chemical"), chem_data.get("params", {}))
                action.add_chemical(chem)

        sub_branch = step.get("subproduct_branch")
        if isinstance(sub_branch, dict):
            sub_action = Protocol._build_action_from_step(sub_branch)
            action.add_subproduct(sub_action)

        for sub_step in step.get("subproducts", []) or []:
            if isinstance(sub_step, dict):
                sub_action = Protocol._build_action_from_step(sub_step)
                action.add_subproduct(sub_action)

        return action
    
    @staticmethod
    def from_dict(data):
        """Create a protocol from a legacy protocol dictionary or step list."""
        protocol = Protocol()

        for item in Protocol._iter_steps(data):
            action = Protocol._build_action_from_step(item)
            protocol.add_action(action)
        
        return protocol
