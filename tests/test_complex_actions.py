from src.complex.actions import (
    COMPLEX_ACTION_MARKER,
    ComplexActionDefinition,
    ComplexActionGroup,
    ComplexActionParameter,
    ComplexActionRegistry,
    KEY_COMPLEX_ACTION_NAME,
    append_definitions_to_config,
    bindings_for_instance_section,
    build_parameter_bindings,
    collect_flow_steps_from_editor,
    complex_action_step_from_group,
    build_instance_parameters,
    copy_instance_parameters,
    dictionary_filename,
    expand_definition_steps,
    expand_complex_action,
    get_complex_action_registry,
    iter_instance_dialog_sections,
    load_complex_actions_config,
    parameters_to_block_params,
    parse_complex_actions_payload,
    register_complex_action_definitions,
    sequence_signature,
    step_action_signature,
    validate_definition,
    validate_instance_parameters,
)


def test_sequence_signature():
    steps = [{"action": "Wait"}, {"action": "Grind"}]
    assert sequence_signature(steps) == ("Wait", "Grind")


def test_build_parameter_bindings_includes_wait_duration():
    steps = [{"action": "Wait", "params": {"duration": "10 min"}}]
    bindings = build_parameter_bindings(steps)
    assert len(bindings) == 1
    assert bindings[0].param_key == "duration"
    assert bindings[0].display_name == "Duration"


def test_registry_rejects_duplicate_name():
    registry = ComplexActionRegistry()
    definition = ComplexActionDefinition(
        name="Heat and Wait",
        steps=[{"action": "Wait", "params": {"duration": "5 min"}}],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Wait",
                param_key="duration",
                display_name="Duration",
                value="5 min",
            )
        ],
    )
    registry.register(definition)
    duplicate = ComplexActionDefinition(
        name="Heat and Wait",
        steps=[{"action": "Grind", "params": {}}],
        parameters=[],
    )
    errors = validate_definition(duplicate, registry)
    assert any("already exists" in err for err in errors)


def test_registry_rejects_duplicate_sequence():
    registry = ComplexActionRegistry()
    steps = [{"action": "Wait", "params": {"duration": "1 min"}}]
    registry.register(
        ComplexActionDefinition(
            name="First",
            steps=steps,
            parameters=build_parameter_bindings(steps),
        )
    )
    duplicate = ComplexActionDefinition(
        name="Second",
        steps=steps,
        parameters=build_parameter_bindings(steps),
    )
    errors = validate_definition(duplicate, registry)
    assert any("exact action sequence" in err for err in errors)


def test_required_validation_uses_real_param_key_not_display_name():
    definition = ComplexActionDefinition(
        name="Add Step",
        steps=[{
            "action": "Add",
            "params": {
                "duration": "0 s",
                "add_quantity": "0 g",
                "add_type": "",
                "open_flame": "",
            },
        }],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="add_type",
                display_name="Custom Add Type Label",
                value="",
            ),
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="duration",
                display_name="Custom Duration",
                value="10 min",
            ),
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="add_quantity",
                display_name="Qty",
                value="1 g",
            ),
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="open_flame",
                display_name="Flame",
                value="False",
            ),
        ],
    )
    errors = validate_definition(definition)
    assert any("Custom Add Type Label" in err for err in errors)


def test_expand_complex_action_applies_locked_values():
    steps = [{"action": "Wait", "params": {"duration": "10 min"}}]
    parameters = [
        ComplexActionParameter(
            step_index=0,
            action="Wait",
            param_key="duration",
            display_name="Hold",
            editable=False,
            value="30 min",
        )
    ]
    definition = ComplexActionDefinition(name="Hold", steps=steps, parameters=parameters)
    expanded = expand_complex_action(definition)
    assert expanded[0]["params"]["duration"] == "30 min"


def test_definition_json_roundtrip():
    steps = [{"action": "Grind", "params": {}}]
    definition = ComplexActionDefinition(
        name="Crush",
        steps=steps,
        parameters=[],
    )
    restored = ComplexActionDefinition.from_json(definition.to_json())
    assert restored.name == "Crush"
    assert restored.steps == steps


def test_definition_json_roundtrip_preserves_editable_flag():
    definition = ComplexActionDefinition(
        name="Hold",
        steps=[{"action": "Wait", "params": {"duration": "5 min"}}],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Wait",
                param_key="duration",
                display_name="Duration",
                editable=False,
                value="5 min",
            )
        ],
    )
    restored = ComplexActionDefinition.from_json(definition.to_json())
    assert restored.parameters[0].editable is False


def test_find_sequence_ranges():
    from src.complex.actions import ComplexActionDefinition, find_sequence_ranges

    definition = ComplexActionDefinition(
        name="Pair",
        steps=[{"action": "Wait"}, {"action": "Grind"}],
    )
    ranges = find_sequence_ranges(
        ["Add", "Wait", "Grind", "Wait", "Grind", "Sieve"],
        definition,
    )
    assert ranges == [(1, 3), (3, 5)]


def test_validate_instance_allows_reused_definition_name():
    definition = ComplexActionDefinition(
        name="Hold",
        steps=[{"action": "Wait", "params": {"duration": "10 min"}}],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Wait",
                param_key="duration",
                display_name="Duration",
                value="15 min",
            )
        ],
    )
    params = copy_instance_parameters(definition)
    params[0].value = "20 min"
    assert validate_instance_parameters(params, definition) == []


def test_collect_horizontal_flow_steps_avoids_cycles():
    """Export walker must not loop when complex members form a cycle."""

    class _Block:
        def __init__(self, action, *, group_id=None, step_index=None):
            self.action = action
            self.complex_group_id = group_id
            self.complex_step_index = step_index
            self.prev_block = None
            self.next_block = None
            self.params = {}
            self.chem_below = None
            self.subproduct_below = None

    m0 = _Block("Wait", group_id="g1", step_index=0)
    m1 = _Block("Grind", group_id="g1", step_index=1)
    m0.next_block = m1
    m1.next_block = m0  # cycle

    group = ComplexActionGroup(
        group_id="g1",
        definition_name="TwoStep",
        parameters=[],
        member_blocks=[m0, m1],
    )

    class _Editor:
        complex_action_groups = {"g1": group}

    exported = []

    def get_step_data(block, local_path):
        exported.append(block.action)
        return [{"action": block.action}]

    from src.ui.editor import Editor

    content = Editor._collect_horizontal_flow_steps(_Editor(), m0, get_step_data, set())
    assert exported == ["Wait", "Grind"]
    assert len(content) == 2


def test_dictionary_filename_sanitizes():
    assert dictionary_filename("My/Action").endswith(".json")
    assert "/" not in dictionary_filename("My/Action")


def test_is_horizontal_flow_head_for_complex_member():
    class _Block:
        def __init__(self, *, part_of_complex=False, prev=None, next_block=None):
            self.part_of_complex_action = part_of_complex
            self.complex_group_id = "g1" if part_of_complex else None
            self.prev_block = prev
            self.next_block = next_block
            self.is_first = False
            self.orientation = "horizontal"

    class _Group:
        member_blocks = None

    head = _Block(part_of_complex=True)
    group = _Group()
    group.member_blocks = [head]

    class _Editor:
        complex_action_groups = {"g1": group}

        def get_complex_action_group(self, block):
            return self.complex_action_groups.get(block.complex_group_id)

    from src.ui.editor import Editor

    editor = _Editor()
    assert Editor._is_horizontal_flow_head(editor, head) is True


def test_wire_surrogate_into_chain_restores_external_links():
    class _Block:
        def __init__(self):
            self.prev_block = None
            self.next_block = None
            self.is_first = False
            self.orientation = "horizontal"

        def update(self):
            pass

        def set_connected(self, _value):
            pass

    left = _Block()
    first = _Block()
    second = _Block()
    right = _Block()
    surrogate = _Block()

    left.next_block = first
    first.prev_block = left
    first.next_block = second
    second.prev_block = first
    second.next_block = right
    right.prev_block = second

    group = ComplexActionGroup(
        group_id="g1",
        definition_name="TwoStep",
        parameters=[],
        member_blocks=[first, second],
        surrogate_block=surrogate,
    )
    from src.complex.protocol import _wire_surrogate_into_chain, _unwire_surrogate_from_chain

    _wire_surrogate_into_chain(group)
    assert left.next_block is surrogate
    assert surrogate.prev_block is left
    assert surrogate.next_block is right
    assert right.prev_block is surrogate
    assert first.prev_block is left
    assert second.next_block is right

    _unwire_surrogate_from_chain(group)
    assert left.next_block is first
    assert right.prev_block is second
    assert surrogate.prev_block is None
    assert surrogate.next_block is None


def test_complex_group_horizontal_span():
    class _Rect:
        def __init__(self, w, h=60):
            self._w = w
            self._h = h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class _Pos:
        def __init__(self, x):
            self._x = x

        def x(self):
            return self._x

    class _Block:
        def __init__(self, x, w=140):
            self._pos = _Pos(x)
            self._rect = _Rect(w)

        def pos(self):
            return self._pos

        def rect(self):
            return self._rect

    from src.complex.protocol import _complex_group_horizontal_span

    b0 = _Block(50)
    b1 = _Block(170)
    b2 = _Block(290)
    assert _complex_group_horizontal_span([b0, b1, b2]) == 380.0
    assert _complex_group_horizontal_span([b0]) == 140.0


def test_layout_collapsed_group_pulls_right_tail():
    class _Rect:
        def __init__(self, w, h=60):
            self._w = w
            self._h = h

        def width(self):
            return self._w

        def height(self):
            return self._h

    class _Pos:
        def __init__(self, x, y=0):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class _Block:
        def __init__(self, x, w=140):
            self._pos = _Pos(x)
            self._rect = _Rect(w)
            self.prev_block = None
            self.next_block = None

        def pos(self):
            return self._pos

        def setPos(self, x, y):
            self._pos = _Pos(x, y)

        def rect(self):
            return self._rect

        def setRect(self, _x, _y, w, h):
            self._rect = _Rect(w)

        def update(self):
            pass

        def update_text(self):
            pass

        def set_connected(self, _value):
            pass

    first = _Block(0)
    second = _Block(120)
    right = _Block(400)
    surrogate = _Block(0)
    first.next_block = second
    second.prev_block = first
    second.next_block = right
    right.prev_block = second
    surrogate.next_block = right

    group = ComplexActionGroup(
        group_id="g1",
        definition_name="Two",
        parameters=[],
        member_blocks=[first, second],
        surrogate_block=surrogate,
        chain_wired_collapsed=True,
    )

    class _Editor:
        def push_chain(self, start_block, shift_x):
            start_block.setPos(start_block.pos().x() + shift_x, start_block.pos().y())

    from src.complex.protocol import _layout_collapsed_group

    _layout_collapsed_group(_Editor(), group)
    assert surrogate.rect().width() == 260.0
    assert right.pos().x() == 240.0
    assert group.collapsed_tail_shift == -160.0


def test_collect_horizontal_flow_steps_expands_collapsed_surrogate():
    class _Block:
        def __init__(self, action, *, group_id=None):
            self.action = action
            self.complex_group_id = group_id
            self.complex_step_index = None
            self.prev_block = None
            self.next_block = None
            self.params = {}
            self.chem_below = None
            self.subproduct_below = None

    m0 = _Block("Wait", group_id="g1")
    m1 = _Block("Grind", group_id="g1")
    m0.next_block = m1
    m1.prev_block = m0
    tail = _Block("Sieve")
    m1.next_block = tail
    tail.prev_block = m1

    surrogate = _Block("MyComplex")
    surrogate.is_complex_surrogate = True
    surrogate.complex_group_id = "g1"
    surrogate.next_block = tail

    group = ComplexActionGroup(
        group_id="g1",
        definition_name="MyComplex",
        parameters=[],
        member_blocks=[m0, m1],
        surrogate_block=surrogate,
    )

    class _Editor:
        complex_action_groups = {"g1": group}

    exported = []

    def get_step_data(block, local_path):
        exported.append(block.action)
        return [{"action": block.action}]

    from src.ui.editor import Editor

    content = Editor._collect_horizontal_flow_steps(_Editor(), surrogate, get_step_data, set())
    assert exported[:2] == ["Wait", "Grind"]
    assert [step["action"] for step in content][:2] == ["Wait", "Grind"]


def test_activity_without_complex_steps_filters_linkml_validation():
    from src.linkml.exporter import _activity_without_complex_steps

    activity = {
        "has_synthesis_step": [
            {"source_action": "Wait", "part_of_complex_action": True},
            {"source_action": "Add"},
        ]
    }
    filtered = _activity_without_complex_steps(activity)
    assert len(filtered["has_synthesis_step"]) == 1
    assert filtered["has_synthesis_step"][0]["source_action"] == "Add"


def test_can_be_left_neighbor_of_complex_group_last_member():
    class _Block:
        def __init__(self, group_id, *, part=False, surrogate=False):
            self.complex_group_id = group_id
            self.part_of_complex_action = part
            self.is_complex_surrogate = surrogate
            self.isVisible = lambda: True

    class _Group:
        def __init__(self, gid, members):
            self.group_id = gid
            self.member_blocks = members

    first = _Block("g1", part=True)
    last = _Block("g1", part=True)
    group_a = _Group("g1", [first, last])
    moving = _Group("g2", [_Block("g2", part=True)])

    class _Editor:
        complex_action_groups = {"g1": group_a, "g2": moving}

        def get_complex_action_group(self, block):
            return self.complex_action_groups.get(block.complex_group_id)

        def _groups_share_block(self, group, block):
            return block.complex_group_id == group.group_id

    from src.ui.editor import Editor

    editor = _Editor()
    assert Editor._can_be_left_neighbor_of_group(editor, last, moving) is True
    assert Editor._can_be_left_neighbor_of_group(editor, first, moving) is False


def test_wire_surrogate_tolerates_legacy_group_without_chain_flag():
    class _Block:
        def __init__(self):
            self.prev_block = None
            self.next_block = None

        def update(self):
            pass

        def set_connected(self, _value):
            pass

    first = _Block()
    surrogate = _Block()
    group = ComplexActionGroup(
        group_id="legacy",
        definition_name="One",
        parameters=[],
        member_blocks=[first],
        surrogate_block=surrogate,
    )
    del group.chain_wired_collapsed

    from src.complex.protocol import _wire_surrogate_into_chain, _unwire_surrogate_from_chain

    _wire_surrogate_into_chain(group)
    assert group.chain_wired_collapsed is True
    _unwire_surrogate_from_chain(group)
    assert group.chain_wired_collapsed is False


def test_allowed_complex_link_zone_blocks_internal_insertion():
    class _Editor:
        complex_action_groups = {}

        def get_complex_action_group(self, block):
            return self.complex_action_groups.get(block.complex_group_id)

    class _Block:
        def __init__(self, group_id):
            self.complex_group_id = group_id
            self.part_of_complex_action = True

    first = _Block("g1")
    last = _Block("g1")
    _Editor.complex_action_groups = {
        "g1": ComplexActionGroup(
            group_id="g1",
            definition_name="X",
            parameters=[],
            member_blocks=[first, last],
        )
    }
    from src.ui.editor import Editor

    editor = _Editor()
    assert Editor._allowed_complex_link_zone(editor, first, "LEFT") is True
    assert Editor._allowed_complex_link_zone(editor, first, "RIGHT") is False
    assert Editor._allowed_complex_link_zone(editor, last, "RIGHT") is True
    assert Editor._allowed_complex_link_zone(editor, last, "LEFT") is False


def test_position_complex_group_preserves_relative_layout():
    class _Pos:
        def __init__(self, x, y):
            self._x = x
            self._y = y

        def x(self):
            return self._x

        def y(self):
            return self._y

    class _Rect:
        def __init__(self, right):
            self._right = right

        def right(self):
            return self._right

    class _Block:
        def __init__(self, x, *, prev=None, next_block=None):
            self._pos = _Pos(x, 10)
            self.prev_block = prev
            self.next_block = next_block
            self.action = "Wait"

        def pos(self):
            return self._pos

        def setPos(self, x, y):
            self._pos = _Pos(x, y)

        def sceneBoundingRect(self):
            return _Rect(self._pos.x() + 140)

    b0 = _Block(0)
    b1 = _Block(120, prev=b0)
    b0.next_block = b1

    class _SourceEditor:
        blocks = [b0, b1]

    class _TargetEditor:
        blocks = []

        def reflow_entire_cluster(self, block):
            raise AssertionError("reflow should not run when source layout is available")

    from src.complex.protocol import _position_complex_group

    m0 = _Block(0)
    m1 = _Block(0, prev=m0)
    m0.next_block = m1
    _position_complex_group(_TargetEditor(), [m0, m1], source_editor=_SourceEditor())
    assert m1.pos().x() - m0.pos().x() == 120


def test_nested_complex_step_signature():
    inner = parameters_to_block_params(
        "InnerAdds",
        [
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="duration",
                display_name="Duration",
                value="1 min",
            )
        ],
    )
    step = {"action": COMPLEX_ACTION_MARKER, "params": inner}
    assert step_action_signature(step) == f"{COMPLEX_ACTION_MARKER}:InnerAdds"


def test_build_parameter_bindings_skips_nested_complex_step():
    inner = parameters_to_block_params("InnerAdds", [])
    steps = [
        {"action": "Wait", "params": {"duration": "5 min"}},
        {"action": COMPLEX_ACTION_MARKER, "params": inner},
    ]
    bindings = build_parameter_bindings(steps)
    assert len(bindings) == 1
    assert bindings[0].param_key == "duration"


def test_expand_definition_steps_flattens_nested_complex():
    registry = get_complex_action_registry()
    inner = ComplexActionDefinition(
        name="InnerAddsNestedExpand",
        steps=[
            {"action": "Add", "params": {"duration": "1 min", "add_quantity": "2 g", "add_type": "", "open_flame": ""}},
            {"action": "Add", "params": {"duration": "3 min", "add_quantity": "4 g", "add_type": "", "open_flame": ""}},
        ],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="duration",
                display_name="Duration",
                value="1 min",
            ),
            ComplexActionParameter(
                step_index=1,
                action="Add",
                param_key="add_quantity",
                display_name="Quantity",
                value="4 g",
            ),
        ],
    )
    registry.register(inner)

    nested_step = {
        "action": COMPLEX_ACTION_MARKER,
        "params": parameters_to_block_params("InnerAddsNestedExpand", inner.parameters),
    }
    outer_steps = [{"action": "Wait", "params": {"duration": "10 min"}}, nested_step]
    expanded = expand_definition_steps(outer_steps, [])
    assert [step["action"] for step in expanded] == ["Wait", "Add", "Add"]
    assert expanded[1]["params"]["duration"] == "1 min"
    assert expanded[2]["params"]["add_quantity"] == "4 g"


def test_collect_flow_steps_groups_nested_complex_on_canvas():
    class _Block:
        def __init__(self, action, *, group_id=None, part=False, params=None, prev=None, next_block=None):
            self.action = action
            self.params = params or {}
            self.complex_group_id = group_id
            self.part_of_complex_action = part
            self.prev_block = prev
            self.next_block = next_block
            self.is_first = prev is None

    add1 = _Block(
        "Add",
        group_id="g1",
        part=True,
        params={"duration": "1 min", "add_quantity": "2 g"},
    )
    add1.is_first = True
    add2 = _Block(
        "Add",
        group_id="g1",
        part=True,
        params={"duration": "3 min", "add_quantity": "4 g"},
        prev=add1,
    )
    add1.next_block = add2
    wait = _Block("Wait", params={"duration": "5 min"}, prev=add2)
    add2.next_block = wait

    group = ComplexActionGroup(
        group_id="g1",
        definition_name="InnerAdds",
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="duration",
                display_name="Duration",
                value="1 min",
            ),
            ComplexActionParameter(
                step_index=1,
                action="Add",
                param_key="add_quantity",
                display_name="Quantity",
                value="4 g",
            ),
        ],
        member_blocks=[add1, add2],
    )

    class _Editor:
        complex_action_groups = {"g1": group}
        blocks = [add1, add2, wait]

    steps = collect_flow_steps_from_editor(_Editor())
    assert len(steps) == 2
    assert steps[0]["action"] == COMPLEX_ACTION_MARKER
    assert steps[0]["params"][KEY_COMPLEX_ACTION_NAME] == "InnerAdds"
    assert steps[1]["action"] == "Wait"
    bindings = build_parameter_bindings(steps)
    assert len(bindings) == 1
    assert bindings[0].step_index == 1
    assert bindings[0].param_key == "duration"


def test_complex_action_step_from_group_syncs_member_params():
    class _Block:
        def __init__(self, params):
            self.params = params

    members = [
        _Block({"duration": "1 min", "add_quantity": "2 g"}),
        _Block({"duration": "3 min", "add_quantity": "4 g"}),
    ]
    group = ComplexActionGroup(
        group_id="g1",
        definition_name="InnerAdds",
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Add",
                param_key="duration",
                display_name="Duration",
                value="0 min",
            ),
            ComplexActionParameter(
                step_index=1,
                action="Add",
                param_key="add_quantity",
                display_name="Quantity",
                value="0 g",
            ),
        ],
        member_blocks=members,
    )
    step = complex_action_step_from_group(group)
    assert step["action"] == COMPLEX_ACTION_MARKER
    assert step["params"][KEY_COMPLEX_ACTION_NAME] == "InnerAdds"
    assert group.parameters[0].value == "1 min"
    assert group.parameters[1].value == "4 g"


def test_chemical_attach_rules_for_complex_actions():
    from src.ui.editor import Editor

    editor = Editor.__new__(Editor)

    class _MemberAdd:
        part_of_complex_action = True
        is_complex_surrogate = False
        action = "Add"

    class _MemberGrind:
        part_of_complex_action = True
        is_complex_surrogate = False
        action = "Grind"

    class _Surrogate:
        part_of_complex_action = False
        is_complex_surrogate = True
        action = "MyComplex"

    assert editor._can_attach_chemical_to(_MemberAdd()) is True
    assert editor._can_attach_chemical_to(_MemberGrind()) is True
    assert editor._can_attach_chemical_to(_Surrogate()) is False
    assert editor._chemical_attach_rejection_message(_MemberAdd()) is None
    assert editor._chemical_attach_rejection_message(_MemberGrind()) == (
        "Chemicals cannot be linked to Grind"
    )
    assert "complex action" in editor._chemical_attach_rejection_message(_Surrogate())


def test_build_instance_parameters_includes_nested_complex_bindings():
    registry = get_complex_action_registry()
    inner = ComplexActionDefinition(
        name="dentroInstanceTest",
        steps=[
            {"action": "Repeat", "params": {"amount": "1"}},
            {"action": "Wait", "params": {"duration": "10 min"}},
        ],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Repeat",
                param_key="amount",
                display_name="Amount",
                editable=True,
                value="1",
            ),
            ComplexActionParameter(
                step_index=1,
                action="Wait",
                param_key="duration",
                display_name="Duration",
                editable=False,
                value="10 min",
            ),
        ],
    )
    registry.register(inner)
    outer = ComplexActionDefinition(
        name="foraInstanceTest",
        steps=[
            {"action": "Add", "params": {"duration": "0 s", "add_quantity": "0 g", "add_type": "", "open_flame": ""}},
            {
                "action": COMPLEX_ACTION_MARKER,
                "params": parameters_to_block_params("dentroInstanceTest", inner.parameters),
            },
        ],
        parameters=build_parameter_bindings([{"action": "Add", "params": {"duration": "0 s", "add_quantity": "0 g", "add_type": "", "open_flame": ""}}]),
    )

    bindings = build_instance_parameters(outer)
    nested = [param for param in bindings if param.host_step_index == 1]
    assert len(nested) == 2
    assert nested[0].param_key == "amount"
    assert nested[1].editable is False

    bindings[0].value = "5 s"
    nested[0].value = "3"
    expanded = expand_definition_steps(outer.steps, bindings)
    assert expanded[0]["params"]["duration"] == "5 s"
    assert expanded[1]["params"]["amount"] == "3"


def test_validate_instance_parameters_allows_existing_registry_definition():
    registry = get_complex_action_registry()
    steps = [{"action": "Wait", "params": {"duration": "5 min"}}]
    definition = ComplexActionDefinition(
        name="LoadedComplexAction",
        steps=steps,
        parameters=build_parameter_bindings(steps),
    )
    registry.register(definition)
    parameters = build_instance_parameters(definition)
    errors = validate_instance_parameters(parameters, definition)
    assert not any("already exists" in err for err in errors)


def test_iter_instance_dialog_sections_expands_nested_complex():
    registry = get_complex_action_registry()
    inner = ComplexActionDefinition(
        name="dentroDialogSections",
        steps=[
            {"action": "Repeat", "params": {"amount": "1"}},
            {"action": "Wait", "params": {"duration": "10 min"}},
        ],
        parameters=[
            ComplexActionParameter(
                step_index=0,
                action="Repeat",
                param_key="amount",
                display_name="Amount",
                editable=True,
                value="1",
            ),
            ComplexActionParameter(
                step_index=1,
                action="Wait",
                param_key="duration",
                display_name="Duration",
                editable=False,
                value="10 min",
            ),
        ],
    )
    registry.register(inner)
    outer = ComplexActionDefinition(
        name="foraDialogSections",
        steps=[
            {"action": "Add", "params": {"duration": "0 s", "add_quantity": "0 g", "add_type": "", "open_flame": ""}},
            {"action": "ChangeTemperature", "params": {"temperature": "50 °C", "process": "", "ramp": "0 °C/min", "power": "0 W"}},
            {
                "action": COMPLEX_ACTION_MARKER,
                "params": parameters_to_block_params("dentroDialogSections", inner.parameters),
            },
        ],
        parameters=build_parameter_bindings([
            {"action": "Add", "params": {"duration": "0 s", "add_quantity": "0 g", "add_type": "", "open_flame": ""}},
            {"action": "ChangeTemperature", "params": {"temperature": "50 °C", "process": "", "ramp": "0 °C/min", "power": "0 W"}},
        ]),
    )

    sections = iter_instance_dialog_sections(outer)
    assert [section.action_name for section in sections] == [
        "Add",
        "ChangeTemperature",
        "Repeat",
        "Wait",
    ]
    assert [section.display_index for section in sections] == [0, 1, 2, 3]

    bindings = build_instance_parameters(outer)
    repeat_items = bindings_for_instance_section(bindings, sections[2])
    assert len(repeat_items) == 1
    assert repeat_items[0][1].param_key == "amount"


def test_parse_complex_actions_payload_supports_single_and_multi_formats():
    single = {"complex_action_name": "A", "steps": [{"action": "Wait"}]}
    multi = {"version": 1, "complex_actions": [single]}
    raw_list = [single]

    assert len(parse_complex_actions_payload(single)) == 1
    assert len(parse_complex_actions_payload(multi)) == 1
    assert len(parse_complex_actions_payload(raw_list)) == 1


def test_register_and_append_definitions_to_config(tmp_path):
    registry = ComplexActionRegistry()
    config_path = tmp_path / "complex_actions.json"
    steps = [{"action": "Wait", "params": {"duration": "1 min"}}]
    first = ComplexActionDefinition(
        name="Alpha",
        steps=steps,
        parameters=build_parameter_bindings(steps),
    )
    second = ComplexActionDefinition(
        name="Beta",
        steps=steps,
        parameters=build_parameter_bindings(steps),
    )

    register_complex_action_definitions(
        [first, second],
        registry=registry,
        persist=True,
        config_path=config_path,
    )
    assert registry.list_names() == ["Alpha", "Beta"]
    assert config_path.exists()

    reloaded = ComplexActionRegistry()
    loaded = load_complex_actions_config(reloaded, path=config_path)
    assert loaded == 2
    assert reloaded.list_names() == ["Alpha", "Beta"]

    updated = ComplexActionDefinition(
        name="Alpha",
        steps=[{"action": "Grind", "params": {}}],
        parameters=[],
    )
    append_definitions_to_config([updated], path=config_path)
    final_registry = ComplexActionRegistry()
    load_complex_actions_config(final_registry, path=config_path)
    assert final_registry.get("Alpha").steps == [{"action": "Grind", "params": {}}]
    assert final_registry.get("Beta") is not None
