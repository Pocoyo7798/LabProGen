"""Adapt semantic dictionaries to the checked-in, officially generated models."""

from labprogen.generated import action_data_model


def model_class(class_name):
    """Look up a generated schema class without importing a code generator."""
    if not isinstance(class_name, str):
        raise ValueError("Specify a generated class name or a semantic type designator.")
    cls = getattr(action_data_model, class_name, None)
    if not isinstance(cls, type) or not issubclass(cls, action_data_model.ConfiguredBaseModel) or cls is action_data_model.ConfiguredBaseModel:
        raise ValueError(f"No generated data model for '{class_name}'. Regenerate the models after schema changes.")
    return cls


def to_model(instance, class_name=None):
    """Create a typed semantic model; GUI drafts remain separate dictionaries.

    This performs Pydantic validation/coercion. Full LinkML validation and the
    application's strict, lossless checks still apply at the export boundary.
    """
    return model_class(class_name or instance.get("type")).model_validate(instance)
