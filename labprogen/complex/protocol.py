"""Protocol editor integration for user-defined complex actions."""

from __future__ import annotations

import json
import copy
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from labprogen.ui.block import ChemicalBlock, ComplexActionBlock, ElementaryAction, SupportAction
from .actions import (
    ComplexActionGroup,
    ComplexActionParameter,
    apply_parameter_values,
    copy_instance_parameters,
    find_sequence_ranges,
    get_complex_action_registry,
    parameters_to_block_params,
    register_complex_action_definitions,
)
from .ui import prompt_complex_action_use

if TYPE_CHECKING:
    from labprogen.ui.editor import Editor


def _horizontal_chain_from_editor(editor: Editor | None) -> list:
    """Return the primary horizontal action chain from an editor."""
    if editor is None:
        return []
    from labprogen.ui.block import ChemicalBlock

    heads = [
        b
        for b in editor.blocks
        if not isinstance(b, ChemicalBlock)
        and b.action != "CollectSubProduct"
        and not isinstance(b, ComplexActionBlock)
        and b.prev_block is None
        and (b.next_block is not None or getattr(b, "is_first", False))
    ]
    if not heads:
        heads = [
            b
            for b in editor.blocks
            if not isinstance(b, ChemicalBlock)
            and not isinstance(b, ComplexActionBlock)
            and b.prev_block is None
        ]
    if not heads:
        return []

    start = next((b for b in heads if getattr(b, "is_first", False)), heads[0])
    chain: list = []
    visited: set[int] = set()
    current = start
    while current and id(current) not in visited:
        if isinstance(current, (ChemicalBlock, ComplexActionBlock)):
            break
        visited.add(id(current))
        chain.append(current)
        current = current.next_block
    return chain


def _group_anchor_point(editor: Editor) -> tuple[float, float]:
    """Pick a free placement point for a new complex-action group."""
    candidates = [
        b
        for b in editor.blocks
        if not isinstance(b, ComplexActionBlock)
        and getattr(b, "isVisible", lambda: True)()
    ]
    if not candidates:
        return 50.0, 50.0
    max_right = max(b.sceneBoundingRect().right() for b in candidates)
    min_y = min(b.pos().y() for b in candidates)
    return max_right + 40.0, min_y


def _mark_complex_member(block) -> None:
    block.part_of_complex_action = True


def _position_complex_group(
    editor: Editor,
    member_blocks: list,
    *,
    source_editor: Editor | None = None,
) -> None:
    """Place member blocks together, preserving builder layout when possible."""
    if not member_blocks:
        return

    source_chain = _horizontal_chain_from_editor(source_editor)
    if source_chain and len(source_chain) == len(member_blocks):
        anchor_x, anchor_y = _group_anchor_point(editor)
        source_x = source_chain[0].pos().x()
        source_y = source_chain[0].pos().y()
        dx = anchor_x - source_x
        dy = anchor_y - source_y
        for src, dst in zip(source_chain, member_blocks):
            dst.setPos(src.pos().x() + dx, src.pos().y() + dy)
        return

    anchor_x, anchor_y = _group_anchor_point(editor)
    member_blocks[0].setPos(anchor_x, anchor_y)
    editor.reflow_entire_cluster(member_blocks[0])


def next_group_id(editor: Editor) -> str:
    counter = getattr(editor, "_complex_group_counter", 0) + 1
    while f"complex_{counter}" in editor.complex_action_groups:
        counter += 1
    editor._complex_group_counter = counter
    return f"complex_{counter}"


def insert_complex_action(editor: Editor, definition_name: str) -> bool:
    registry = get_complex_action_registry()
    definition = registry.get(definition_name)
    if definition is None:
        return False

    parameters = prompt_complex_action_use(
        definition,
        parent=getattr(editor, "container", None),
    )
    if parameters is None:
        return False

    materialize_complex_action(editor, definition.name, parameters)
    return True


def materialize_complex_action(
    editor: Editor,
    definition_name: str,
    parameters,
    *,
    source_editor: Editor | None = None,
) -> ComplexActionGroup | None:
    registry = get_complex_action_registry()
    definition = registry.get(definition_name)
    if definition is None:
        return None

    expanded_steps = apply_parameter_values(definition.steps, parameters)
    if not expanded_steps:
        return None

    group_id = next_group_id(editor)
    member_blocks = []
    prev_block = None

    for step_index, step in enumerate(expanded_steps):
        block = _create_member_block(editor, step["action"], step.get("params") or {})
        block.complex_group_id = group_id
        block.complex_step_index = step_index
        _mark_complex_member(block)
        if prev_block is not None:
            prev_block.next_block = block
            block.prev_block = prev_block
        member_blocks.append(block)
        prev_block = block

    _position_complex_group(editor, member_blocks, source_editor=source_editor)

    surrogate_params = parameters_to_block_params(definition_name, parameters)
    surrogate = ComplexActionBlock(definition_name, surrogate_params, editor=editor)
    surrogate.complex_group_id = group_id
    surrogate.is_complex_surrogate = True
    editor.scene.addItem(surrogate)
    editor.blocks.append(surrogate)
    editor._register_block_id(surrogate)
    if member_blocks:
        surrogate.setPos(member_blocks[0].pos())
    surrogate.setVisible(False)

    group = ComplexActionGroup(
        group_id=group_id,
        definition_name=definition_name,
        parameters=[ComplexActionParameter.from_dict(p.to_dict()) for p in parameters],
        member_blocks=member_blocks,
        surrogate_block=surrogate,
        definition=copy.deepcopy(definition),
    )

    editor.complex_action_groups[group_id] = group
    editor.update_linked_sequence()
    editor.adapt_scene_rect()
    editor.update_support_logic()
    return group


def _create_member_block(editor: Editor, action_name: str, params: dict):
    from labprogen.complex.actions import ELEMENTARY_ACTIONS
    elementary_list = ELEMENTARY_ACTIONS
    if action_name in elementary_list:
        block = ElementaryAction(action_name, params, editor=editor)
    else:
        block = SupportAction(action_name, params, editor=editor)
    editor.scene.addItem(block)
    editor.blocks.append(block)
    editor._register_block_id(block)
    if isinstance(block, SupportAction) and not editor.show_support_actions:
        block.setVisible(False)
    return block


def check_complex_metadata(data):
    """Reject unsupported container versions before clearing an existing scene."""
    metadata = data.get("complex_action_groups")
    if metadata is None:
        return
    if (not isinstance(metadata, dict) or metadata.get("version") != 1
            or not isinstance(metadata.get("groups"), list)):
        raise ValueError("Unsupported complex-action metadata. Expected version 1 with a groups list.")
    identifiers = set()
    for record in metadata["groups"]:
        if (not isinstance(record, dict) or not isinstance(record.get("group_id"), str)
                or not record["group_id"] or record["group_id"] in identifiers
                or ("name" in record and not isinstance(record["name"], str))):
            raise ValueError("Invalid or duplicate complex-action group identifier/name.")
        identifiers.add(record["group_id"])


def serialize_complex_groups(editor):
    """Presentation metadata lives in the protocol/export envelope, never slots."""
    from .actions import snapshot_group_definition

    previous = (getattr(editor, "protocol_data", {}) or {}).get("complex_action_groups")
    metadata = copy.deepcopy(previous) if previous else {"version": 1, "groups": []}
    restored_ids = getattr(editor, "_restored_complex_group_ids", set())
    records = {item["group_id"]: item for item in metadata["groups"] if item["group_id"] not in restored_ids}
    for group_id, group in editor.complex_action_groups.items():
        definition = snapshot_group_definition(group)
        records[group_id] = {**records.get(group_id, {}), "group_id": group_id,
                             "name": group.definition_name,
                             "parameters": [p.to_dict() for p in definition.parameters]}
    if not records:
        return None
    metadata.update(groups=list(records.values()), collapsed=bool(editor.show_complex_actions_collapsed))
    return metadata


def restore_complex_groups(editor, data, imported_steps):
    """Restore explicitly identified groups; never recognize groups by sequence.

    Invalid/incomplete groups remain ordinary actions with their original markers
    retained on save. Warnings expose the problem without removing actions.
    """
    from .actions import ComplexActionDefinition, build_parameter_bindings

    warnings = []
    metadata = data.get("complex_action_groups") or {}
    records = {}
    for record in metadata.get("groups", []):
        if isinstance(record, dict) and isinstance(record.get("group_id"), str):
            records[record["group_id"]] = record
    candidates = {}
    for step, block in imported_steps:
        if not step.get("part_of_complex_action"):
            continue
        group_id = step.get("complex_group_id")
        if not isinstance(group_id, str) or not group_id:
            warnings.append("Complex-action member has no group identifier; kept as an ordinary action.")
            continue
        members = candidates.setdefault(group_id, [])
        if not any(existing is block for _, existing in members):
            members.append((step, block))
    for group_id, entries in candidates.items():
        record = records.get(group_id, {})
        names = {step["complex_action_name"] for step, _ in entries
                 if isinstance(step.get("complex_action_name"), str) and step["complex_action_name"].strip()}
        if record.get("name"):
            names.add(record["name"])
        members = [block for _, block in entries]
        indices = [step.get("complex_step_index") for step, _ in entries]
        ordered = all(index is None for index in indices) or indices == list(range(len(members)))
        contiguous = all(left.next_block is right for left, right in zip(members, members[1:]))
        if len(names) != 1 or not ordered or not contiguous or any(block.complex_group_id for block in members):
            warnings.append(f"Complex group {group_id!r} is inconsistent or incomplete; actions and markers were retained.")
            continue
        name = next(iter(names))
        steps = [{"action": block.action, "params": copy.deepcopy(block.params)} for block in members]
        parameters = build_parameter_bindings(steps)
        try:
            saved = [ComplexActionParameter.from_dict(p) for p in record.get("parameters", [])]
            for binding in saved:
                if (binding.host_step_index is not None or binding.step_index < 0 or binding.step_index >= len(members)
                        or binding.action != members[binding.step_index].action
                        or binding.param_key not in members[binding.step_index].params):
                    raise ValueError("binding does not identify an imported member field")
            overrides = {(p.step_index, p.param_key): p for p in saved}
            for index, parameter in enumerate(parameters):
                saved_parameter = overrides.get((parameter.step_index, parameter.param_key))
                if saved_parameter is not None:
                    saved_parameter.value = parameter.value  # Actual member data is authoritative.
                    parameters[index] = saved_parameter
        except (AttributeError, KeyError, TypeError, ValueError):
            warnings.append(f"Complex group {group_id!r} has invalid parameter metadata; actions and markers were retained.")
            continue
        definition = ComplexActionDefinition(name, steps, parameters)
        surrogate = ComplexActionBlock(name, parameters_to_block_params(name, parameters), editor=editor)
        surrogate.complex_group_id = group_id
        editor.scene.addItem(surrogate)
        editor.blocks.append(surrogate)
        editor._register_block_id(surrogate)
        surrogate.setPos(members[0].pos())
        surrogate.setVisible(False)
        for index, block in enumerate(members):
            block.complex_group_id = group_id
            block.complex_step_index = index
            _mark_complex_member(block)
        editor.complex_action_groups[group_id] = ComplexActionGroup(
            group_id, name, parameters, member_blocks=members, surrogate_block=surrogate, definition=definition)
    editor._restored_complex_group_ids = set(editor.complex_action_groups)
    return warnings


def import_complex_action_dictionary(editor: Editor) -> bool:
    filename, _ = QFileDialog.getOpenFileName(
        editor.container if hasattr(editor, "container") else None,
        "Import Complex Action Dictionary",
        "",
        "JSON Files (*.json)",
    )
    if not filename:
        return False
    try:
        with open(filename, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        QMessageBox.critical(
            editor.container if hasattr(editor, "container") else None,
            "Import Error",
            f"Could not read dictionary file:\n{exc}",
        )
        return False

    from .actions import definitions_from_payload

    definitions = definitions_from_payload(data)
    if not definitions:
        QMessageBox.warning(
            editor.container if hasattr(editor, "container") else None,
            "Invalid Dictionary",
            "The dictionary file does not contain any valid complex action definitions.",
        )
        return False

    register_complex_action_definitions(definitions)
    names = ", ".join(repr(defn.name) for defn in definitions)
    QMessageBox.information(
        editor.container if hasattr(editor, "container") else None,
        "Dictionary Imported",
        (
            f"Loaded {len(definitions)} complex action(s): {names}.\n"
            "Use Add Action to insert a complex-action instance.\n"
            "Definitions were appended to the default config file."
        ),
    )
    return True


def attach_matching_groups(editor: Editor, definition) -> int:
    """Find expanded action sequences matching definition and register as complex groups."""
    chains = _horizontal_chains(editor)
    attached = 0
    used_blocks: set[int] = set()

    for chain in chains:
        action_names = [block.action for block in chain]
        for start, end in find_sequence_ranges(action_names, definition):
            members = chain[start:end]
            if any(id(block) in used_blocks for block in members):
                continue
            if any(getattr(block, "complex_group_id", None) for block in members):
                continue
            parameters = copy_instance_parameters(definition)
            apply_parameters_to_member_blocks_from_members(definition, members, parameters)
            group_id = next_group_id(editor)
            for index, block in enumerate(members):
                block.complex_group_id = group_id
                block.complex_step_index = index
                _mark_complex_member(block)
                used_blocks.add(id(block))

            surrogate_params = parameters_to_block_params(definition.name, parameters)
            surrogate = ComplexActionBlock(definition.name, surrogate_params, editor=editor)
            surrogate.complex_group_id = group_id
            editor.scene.addItem(surrogate)
            editor.blocks.append(surrogate)
            editor._register_block_id(surrogate)
            first = members[0]
            surrogate.setPos(first.pos())
            surrogate.setVisible(editor.show_complex_actions_collapsed)

            group = ComplexActionGroup(
                group_id=group_id,
                definition_name=definition.name,
                parameters=[ComplexActionParameter.from_dict(p.to_dict()) for p in parameters],
                member_blocks=members,
                surrogate_block=surrogate,
                definition=copy.deepcopy(definition),
            )
            editor.complex_action_groups[group_id] = group
            if editor.show_complex_actions_collapsed:
                for block in members:
                    block.setVisible(False)
                surrogate.is_first = first.is_first
                surrogate.orientation = getattr(first, "orientation", "horizontal")
                _wire_surrogate_into_chain(group)
                _layout_collapsed_group(editor, group)
            attached += 1
    if attached:
        editor.adapt_scene_rect()
    return attached


def apply_parameters_to_member_blocks_from_members(definition, members, parameters) -> None:
    for index, block in enumerate(members):
        for param in parameters:
            if param.step_index != index:
                continue
            if param.param_key in (block.params or {}):
                param.value = block.params[param.param_key]


def _horizontal_chains(editor: Editor) -> list[list]:
    chains: list[list] = []
    for block in editor.blocks:
        if isinstance(block, (ChemicalBlock, ComplexActionBlock)):
            continue
        if block.action == "CollectSubProduct":
            continue
        if block.prev_block is not None:
            continue
        if block.next_block is None and not block.is_first:
            continue
        chain = []
        current = block
        while current:
            if isinstance(current, ComplexActionBlock):
                break
            chain.append(current)
            current = current.next_block
        if chain:
            chains.append(chain)
    return chains


def _complex_group_horizontal_span(members: list) -> float:
    """Scene width from the first member's left edge to the last member's right edge."""
    if not members:
        return 140.0
    first, last = members[0], members[-1]
    if first is last:
        return float(first.rect().width())
    return (last.pos().x() + last.rect().width()) - first.pos().x()


def _set_surrogate_span_width(surrogate, width: float) -> None:
    if not hasattr(surrogate, "_default_rect_width"):
        surrogate._default_rect_width = float(surrogate.rect().width())
    height = float(surrogate.rect().height())
    surrogate.setRect(0, 0, max(width, surrogate._default_rect_width), height)
    surrogate.update_text()
    surrogate.update()


def _restore_surrogate_span_width(surrogate) -> None:
    default = float(getattr(surrogate, "_default_rect_width", surrogate.rect().width()))
    height = float(surrogate.rect().height())
    surrogate.setRect(0, 0, default, height)
    surrogate.update_text()
    surrogate.update()


def _layout_collapsed_group(editor: Editor, group: ComplexActionGroup, *, overlap: float = 20) -> None:
    """Size the surrogate to the expanded footprint and pull the right tail flush."""
    members = group.member_blocks
    surrogate = group.surrogate_block
    if not members or surrogate is None:
        return

    if abs(getattr(group, "collapsed_tail_shift", 0.0)) > 0.01:
        return

    first = members[0]
    span = _complex_group_horizontal_span(members)
    surrogate.setPos(first.pos().x(), first.pos().y())
    _set_surrogate_span_width(surrogate, span)

    ext_next = surrogate.next_block
    if ext_next is None:
        group.collapsed_tail_shift = 0.0
        return

    target_x = first.pos().x() + span - overlap
    dx = target_x - ext_next.pos().x()
    if abs(dx) > 0.01:
        editor.push_chain(ext_next, dx)
    group.collapsed_tail_shift = dx


def refresh_collapsed_group_layout(editor: Editor, group: ComplexActionGroup, *, overlap: float = 20) -> None:
    """Recompute collapsed surrogate width and right-tail position after external linking."""
    shift = getattr(group, "collapsed_tail_shift", 0.0)
    surrogate = group.surrogate_block
    if surrogate is not None and abs(shift) > 0.01:
        ext_next = surrogate.next_block
        if ext_next is not None:
            editor.push_chain(ext_next, -shift)
        group.collapsed_tail_shift = 0.0
    _layout_collapsed_group(editor, group, overlap=overlap)


def _undo_collapsed_group_layout(editor: Editor, group: ComplexActionGroup) -> None:
    """Restore surrogate width and move the right tail back to the last member edge."""
    shift = getattr(group, "collapsed_tail_shift", 0.0)
    surrogate = group.surrogate_block
    if surrogate is not None and abs(shift) > 0.01:
        ext_next = surrogate.next_block
        if ext_next is not None:
            editor.push_chain(ext_next, -shift)
        group.collapsed_tail_shift = 0.0
    if surrogate is not None:
        _restore_surrogate_span_width(surrogate)


def apply_complex_visibility(editor: Editor, collapsed: bool) -> None:
    editor.show_complex_actions_collapsed = collapsed
    label = "Complex actions collapsed" if collapsed else "Complex actions expanded"
    if hasattr(editor, "complex_toggle_btn"):
        editor.complex_toggle_btn.setText(label)

    for group in editor.complex_action_groups.values():
        surrogate = group.surrogate_block
        if surrogate is None:
            continue
        if collapsed:
            if group.member_blocks:
                first = group.member_blocks[0]
                surrogate.setPos(first.pos().x(), first.pos().y())
                surrogate.is_first = first.is_first
                surrogate.orientation = getattr(first, "orientation", "horizontal")
            _wire_surrogate_into_chain(group)
            _layout_collapsed_group(editor, group)
            surrogate.setVisible(True)
            for block in group.member_blocks:
                block.setVisible(False)
                _hide_chemical_chain(editor, block.chem_below)
        else:
            _undo_collapsed_group_layout(editor, group)
            _unwire_surrogate_from_chain(group)
            surrogate.setVisible(False)
            for block in group.member_blocks:
                block.setVisible(True)
                if isinstance(block, SupportAction) and not editor.show_support_actions:
                    block.setVisible(False)
                else:
                    _show_chemical_chain(editor, block.chem_below)
    editor.adapt_scene_rect()
    editor.update_support_logic()


def _wire_surrogate_into_chain(group: ComplexActionGroup) -> None:
    """Patch external horizontal links through the collapsed surrogate block."""
    if getattr(group, "chain_wired_collapsed", False) or not group.surrogate_block or not group.member_blocks:
        return

    surrogate = group.surrogate_block
    first = group.member_blocks[0]
    last = group.member_blocks[-1]
    ext_prev = first.prev_block
    ext_next = last.next_block

    surrogate.prev_block = ext_prev
    surrogate.next_block = ext_next
    if ext_prev is not None:
        ext_prev.next_block = surrogate
    if ext_next is not None:
        ext_next.prev_block = surrogate

    surrogate.set_connected(bool(ext_prev or ext_next))
    surrogate.update()
    group.chain_wired_collapsed = True


def _unwire_surrogate_from_chain(group: ComplexActionGroup) -> None:
    """Restore external horizontal links to the first/last expanded members."""
    if not getattr(group, "chain_wired_collapsed", False) or not group.surrogate_block or not group.member_blocks:
        return

    surrogate = group.surrogate_block
    first = group.member_blocks[0]
    last = group.member_blocks[-1]
    ext_prev = surrogate.prev_block
    ext_next = surrogate.next_block

    if ext_prev is not None:
        ext_prev.next_block = first
    if ext_next is not None:
        ext_next.prev_block = last

    surrogate.prev_block = None
    surrogate.next_block = None
    surrogate.set_connected(False)
    surrogate.update()
    group.chain_wired_collapsed = False


def _hide_chemical_chain(editor, chem_block) -> None:
    current = chem_block
    while current:
        current.setVisible(False)
        current = current.below_block


def _show_chemical_chain(editor, chem_block) -> None:
    current = chem_block
    while current:
        current.setVisible(True)
        current = current.below_block


def should_skip_export_block(editor: Editor, block, exported_members: set) -> bool:
    if isinstance(block, ComplexActionBlock):
        return True
    group_id = getattr(block, "complex_group_id", None)
    if not group_id:
        return False
    group = editor.complex_action_groups.get(group_id)
    if group is None:
        return False
    if block is not group.member_blocks[0]:
        return True
    if id(block) in exported_members:
        return True
    return False


def mark_group_exported(editor: Editor, block, exported_members: set) -> None:
    group_id = getattr(block, "complex_group_id", None)
    if not group_id:
        return
    group = editor.complex_action_groups.get(group_id)
    if group is None:
        return
    for member in group.member_blocks:
        exported_members.add(id(member))
