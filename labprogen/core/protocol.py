import json
import copy
from .actions import *
from .chemicals import *
from .config import DEFAULT_PROTOCOL_NAME, KEY_SUBSTANCE
from labprogen.linkml.adapter import convert_linkml_to_protocol
from labprogen.linkml.exporter import convert_protocol_to_linkml


class Protocol:
    """Represents a laboratory procedure protocol"""
    
    def __init__(self):
        self.actions = []
        self.complex_action_groups = None
    
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
        result = self.build_protocol_envelope(flows)
        if self.complex_action_groups is not None:
            result["complex_action_groups"] = copy.deepcopy(self.complex_action_groups)
        return result
    
    def to_json(self):
        """Convert protocol to JSON string"""
        data = self.to_protocol_dict() if self.complex_action_groups is not None else self.to_dict()
        return json.dumps(data, indent=2)

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
        from .config import canonical_action_name, migrate_action_params

        action_type = canonical_action_name(action_type)
        params = migrate_action_params(action_type, params)
        action_classes = ACTION_CLASSES

        # Keep unknown legacy types intact so editing/export can report them.
        action_class = action_classes.get(action_type)
        if action_class is None:
            action_class = type(action_type or "UnknownAction", (Action,), {})
        return action_class(**(params or {}))

    @staticmethod
    def _build_chemical(chemical_name, params):
        from .config import canonical_chemical_name, migrate_chemical_params

        chemical_name = canonical_chemical_name(chemical_name)
        params = migrate_chemical_params(chemical_name, params)
        chemical_classes = CHEMICAL_CLASSES

        chemical_class = chemical_classes.get(chemical_name)
        if chemical_class is None:
            chemical_class = type(chemical_name or "UnknownChemical", (Chemical,), {})
        return chemical_class(**(params or {}))

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
        action._complex_metadata = {key: copy.deepcopy(step[key]) for key in
            ("part_of_complex_action", "complex_group_id", "complex_action_name", "complex_step_index", "source_block_id") if key in step}

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
        if isinstance(data, dict) and "activities" in data and "flows" not in data:
            data = convert_linkml_to_protocol(data)
        if isinstance(data, dict) and "complex_action_groups" in data:
            protocol.complex_action_groups = copy.deepcopy(data["complex_action_groups"])

        for item in Protocol._iter_steps(data):
            action = Protocol._build_action_from_step(item)
            protocol.add_action(action)
        
        return protocol
