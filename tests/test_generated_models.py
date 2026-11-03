"""Official model generation, schema evolution and draft/semantic boundaries."""

import copy
import importlib.util
import subprocess
import sys
from enum import Enum

import pytest
import yaml
from pydantic import ValidationError

from labprogen.generated import action_data_model as models
from labprogen.core.actions import Add, NoAction
from labprogen.core.chemicals import Substance
from labprogen.linkml.loader import class_slot_constraints, load_linkml_schema
from labprogen.linkml.models import model_class, to_model
from labprogen.linkml.validator import validate_linkml_protocol
from tools.generate_models import DEFAULT_OUTPUT, DEFAULT_SCHEMA, generate_source, main


def load_generated(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(name, None)
    return module


def test_generated_file_is_synchronized_and_check_writes_nothing():
    content = DEFAULT_OUTPUT.read_bytes()
    assert generate_source(DEFAULT_SCHEMA).encode() == content
    assert main(["--check"]) == 0
    assert DEFAULT_OUTPUT.read_bytes() == content


def test_check_detects_missing_and_stale_output_without_overwriting(tmp_path):
    target = tmp_path / "models.py"
    for data in [None, b"# stale\n"]:
        if data is not None:
            target.write_bytes(data)
        with pytest.raises(SystemExit) as error:
            main(["--output", str(target), "--check"])
        assert error.value.code == 1
        assert target.read_bytes() == data if data is not None else not target.exists()


def test_all_schema_classes_fields_required_flags_and_enums_are_generated():
    schema = load_linkml_schema()
    assert len(schema["classes"]) == 48
    for name in schema["classes"]:
        cls = model_class(name)
        constraints = class_slot_constraints(name)
        assert set(cls.model_fields) == constraints["allowed"], name
        assert {k for k, v in cls.model_fields.items() if v.is_required()} == constraints["required"], name
    for name, enum in schema["enums"].items():
        cls = getattr(models, name)
        assert issubclass(cls, Enum)
        assert {item.value for item in cls} == set(enum["permissible_values"])


def test_inheritance_mixins_and_relaxed_required_slots_match_schema():
    assert issubclass(models.Add, models.OneOffAction)
    assert issubclass(models.OneOffAction, models.Action)
    assert issubclass(models.Polymer, models.Substance)
    assert issubclass(models.Polymer, models.PolymerProperties)
    assert issubclass(models.Copolymer, models.CopolymerProperties)
    for name in ["Cell", "Polymer", "Copolymer", "Medium", "Zeolite", "BioProducts"]:
        obj = model_class(name)()
        assert obj.name is None
        assert not model_class(name).model_fields["name"].is_required()
    with pytest.raises(ValidationError):
        models.Substance()


def test_polymorphic_relations_and_structured_properties_are_preserved():
    data = {"protocol_name": "água", "laboratory_actions": [
        {"type": "Add", "chemical": [{"type": "Cell", "passage_number": 3,
         "genetic_modifications": [{"construct": "pLab"}]}], "duration": "1 s",
         "add_type": "Normal", "open_flame": "False"},
        {"type": "Separate", "method": {"type": "Sieving", "size_range": "1 mm", "phase_to_keep": "Oversize"}},
    ]}
    obj = to_model(data, "LabProcedure")
    assert isinstance(obj.laboratory_actions[0], models.Add)
    assert isinstance(obj.laboratory_actions[0].chemical[0], models.Cell)
    assert isinstance(obj.laboratory_actions[0].chemical[0].genetic_modifications[0], models.GeneticModification)
    assert isinstance(obj.laboratory_actions[1].method, models.Sieving)
    assert obj.model_dump(mode="json", exclude_none=True) == data


def test_models_validate_fields_but_do_not_replace_strict_schema_validation():
    with pytest.raises(ValidationError):
        models.NoAction()
    with pytest.raises(ValidationError):
        models.Sieving(phase_to_keep="Liquid", size_range="1 mm")
    with pytest.raises(ValidationError):
        models.Copolymer(repeat_units=[{"formula": "C2H4"}])
    with pytest.raises(ValidationError):
        models.Cell(unknown="retain rather than silently ignore")
    # Pydantic coercion is useful for model APIs; strict exports validate the
    # original dictionaries and must not silently repair their types.
    assert models.Cell(passage_number="3").passage_number == 3
    step = {"action": "ContinuousAddition", "params": {"chemical": [{"type": "Cell", "passage_number": "3"}],
            "continuous_add_type": "Continuous", "flow_rate": "1 mL/min"}}
    source = {"flows": [{"steps": [step]}]}
    before = copy.deepcopy(source)
    assert any(m.code == "validation.wrong_type" for m in validate_linkml_protocol(source))
    assert source == before
    # Required list presence and non-empty content are separate constraints.
    models.Add(chemical=[], duration="1 s", add_type="Normal", open_flame="False")
    missing = {"flows": [{"steps": [{"action": "Add", "params": {"duration": "1 s", "add_type": "Normal", "open_flame": "False"}}]}]}
    assert any(m.level == "error" for m in validate_linkml_protocol(missing))


def test_business_objects_are_drafts_adapted_to_generated_models():
    draft = Add(duration="1 s", type="Normal", open_flame="False")
    assert draft.model_class is models.Add
    with pytest.raises(ValidationError):
        draft.to_model()
    draft.add_chemical(Substance(name="water", quantity="2 mL"))
    typed = draft.to_model()
    assert isinstance(typed, models.Add)
    assert isinstance(typed.chemical[0], models.Substance)
    assert typed.chemical[0].quantity == "2 mL"
    assert isinstance(NoAction(duration="1 min").to_model(), models.NoAction)
    typed.chemical[0].name = "ethanol"
    assert draft.chemicals[0].params["name"] == "water"


def test_schema_evolution_is_generated_without_changing_official_schema(tmp_path):
    original = DEFAULT_SCHEMA.read_bytes()
    schema = yaml.safe_load(original)
    schema["classes"]["Heating"] = {"is_a": "Action", "attributes": {
        "temperature": {"range": "float", "required": True, "minimum_value": 0},
        "duration": {"range": "integer"},
        "method": {"range": "string", "ifabsent": "string(thermal)"},
        "enabled": {"range": "boolean"},
        "stages": {"range": "integer", "multivalued": True},
        "chemical": {"range": "ChemicalEntity"},
    }}
    schema["classes"]["Cell"]["attributes"] = {"test_score": {"range": "float"}}
    source = tmp_path / "action_data_model.yaml"
    source.write_text(yaml.safe_dump(schema, sort_keys=False))
    target = tmp_path / "models.py"
    assert main(["--schema", str(source), "--output", str(target)]) == 0
    assert generate_source(source) == target.read_text(encoding="utf-8")
    module = load_generated(target, "temporary_generated_model")
    obj = module.Heating(temperature=37.5, duration=5, stages=[1, 2], enabled=True,
                         chemical={"type": "Cell", "test_score": 0.9})
    assert isinstance(obj, module.Action)
    assert obj.temperature == 37.5 and obj.duration == 5
    assert obj.method == "thermal"
    assert isinstance(obj.chemical, module.Cell) and obj.chemical.test_score == 0.9
    assert module.Heating.model_fields["temperature"].is_required()
    assert not module.Heating.model_fields["duration"].is_required()
    assert class_slot_constraints("Heating", schema)["ranges"]["temperature"] == "float"
    with pytest.raises(ValidationError):
        module.Heating()
    with pytest.raises(ValidationError):
        module.Heating(temperature=-1)
    assert DEFAULT_SCHEMA.read_bytes() == original


def test_generation_is_independent_of_hash_seed_and_checkout_path(tmp_path):
    source = tmp_path / DEFAULT_SCHEMA.name
    source.write_bytes(DEFAULT_SCHEMA.read_bytes())
    first = tmp_path / "first.py"
    second = tmp_path / "second.py"
    import os
    for seed, output in [("7", first), ("91", second)]:
        subprocess.run([sys.executable, "-m", "tools.generate_models", "--schema", str(source), "--output", str(output)],
                       env=dict(os.environ, PYTHONHASHSEED=seed), check=True, capture_output=True)
    assert first.read_bytes() == second.read_bytes() == DEFAULT_OUTPUT.read_bytes()


def test_imports_use_checked_in_models_without_python_code_generators():
    code = '''
import importlib.abc, sys
class BlockCodeGenerators(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith(("linkml.generators.pydanticgen", "linkml.generators.pythongen")):
            raise ImportError("Code generation is unavailable at runtime")
sys.meta_path.insert(0, BlockCodeGenerators())
from labprogen.app import main
from labprogen.linkml.models import to_model
assert to_model({"type": "Cell", "passage_number": 3}).passage_number == 3
'''
    subprocess.run([sys.executable, "-c", code], check=True, capture_output=True)


def test_check_accepts_crlf_checkout_without_rewriting(tmp_path):
    target = tmp_path / "models.py"
    content = DEFAULT_OUTPUT.read_bytes().replace(b"\n", b"\r\n")
    target.write_bytes(content)
    assert main(["--output", str(target), "--check"]) == 0
    assert target.read_bytes() == content
