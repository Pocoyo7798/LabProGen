import json
from .actions import *


class Protocol:
    """Represents a laboratory procedure protocol"""
    
    def __init__(self):
        self.actions = []
    
    def add_action(self, action):
        """Add an action to the protocol"""
        self.actions.append(action)
    
    def to_dict(self):
        """Convert protocol to dictionary"""
        return [action.to_dict() for action in self.actions]
    
    def to_json(self):
        """Convert protocol to JSON string"""
        return json.dumps(self.to_dict(), indent=2)
    
    def export(self, filename="protocol.json"):
        """Export protocol to a JSON file"""
        with open(filename, "w") as f:
            f.write(self.to_json())
    
    @staticmethod
    def from_dict(data):
        """Create a protocol from a dictionary"""
        protocol = Protocol()
        action_classes = {
            "Add": Add,
            "ChangeTemperature": ChangeTemperature,
            "Stir": Stir
        }
        
        for item in data:
            action_type = item.get("action")
            params = item.get("params", {})
            if action_type in action_classes:
                action = action_classes[action_type](**params)
                protocol.add_action(action)
        
        return protocol
