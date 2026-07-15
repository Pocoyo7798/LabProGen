"""Protocol editor integration for user-defined complex actions."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QFileDialog, QMessageBox

from .block import ChemicalBlock, ComplexActionBlock, ElementaryAction, SupportAction
from .complex_actions import (
    ComplexActionGroup,
    ComplexActionParameter,
    apply_parameter_values,
    copy_instance_parameters,
    definitions_from_payload,
    find_sequence_ranges,
    get_complex_action_registry,
    parameters_to_block_params,
    register_complex_action_definitions,
)
from .complex_action_ui import prompt_complex_action_use

if TYPE_CHECKING:
    from .editor import Editor


def _horizontal_chain_from_editor(editor: Editor | None) -> list:
    """Return the primary horizontal action chain from an editor."""
    if editor is None:
        return []
    from .block import ChemicalBlock

    heads = [
        b
        for b in editor.blocks
        if not isinstance(b, ChemicalBlock)
        and b.action != "SubProductCreation"
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
    )

    editor.complex_action_groups[group_id] = group
    editor.update_linked_sequence()
    editor.adapt_scene_rect()
    editor.update_support_logic()
    return group


def _create_member_block(editor: Editor, action_name: str, params: dict):
    elementary_list = ["Add", "Grind", "Separate", "Sieve", "Wait"]
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

    from .complex_actions import definitions_from_payload

    definitions = definitions_from_payload(data)
    if not definitions:
        QMessageBox.warning(
            editor.container if hasattr(editor, "container") else None,
            "Invalid Dictionary",
            "The dictionary file does not contain any valid complex action definitions.",
        )
        return False

    register_complex_action_definitions(definitions)
    attached = 0
    for definition in definitions:
        attached += attach_matching_groups(editor, definition)

    names = ", ".join(repr(defn.name) for defn in definitions)
    QMessageBox.information(
        editor.container if hasattr(editor, "container") else None,
        "Dictionary Imported",
        (
            f"Loaded {len(definitions)} complex action(s): {names}.\n"
            f"Matched {attached} sequence(s) in the current protocol.\n"
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
        if block.action == "SubProductCreation":
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
