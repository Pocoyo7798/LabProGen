import sys
from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QDialog,
    QFormLayout, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QWidget, QLabel, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QFont, QPainter
import json
from block import Block, ElementaryAction, SupportAction, ChemicalBlock
from actions import Add, ChangeTemperature, Stir
from chemicals import Molecule, Material
from protocol import Protocol

class ActionSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Action")
        self.setFixedWidth(300)
        self.selected_action = None
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select an Action")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        self.add_btn = QPushButton("+ Add")
        self.change_temp_btn = QPushButton("🌡 Change Temperature")
        self.stir_btn = QPushButton("🔄 Stir")
        
        self.add_btn.clicked.connect(lambda: self.select_action("Add"))
        self.change_temp_btn.clicked.connect(lambda: self.select_action("ChangeTemperature"))
        self.stir_btn.clicked.connect(lambda: self.select_action("Stir"))
        
        layout.addWidget(self.add_btn)
        layout.addWidget(self.change_temp_btn)
        layout.addWidget(self.stir_btn)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def select_action(self, action):
        self.selected_action = action
        self.accept()

class ChemicalSelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Chemical")
        self.setFixedWidth(300)
        self.selected_chemical = None
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("Select a Chemical")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)
        
        self.molecule_btn = QPushButton("Molecule")
        self.material_btn = QPushButton("Material")
        
        self.molecule_btn.clicked.connect(lambda: self.select_chemical("Molecule"))
        self.material_btn.clicked.connect(lambda: self.select_chemical("Material"))
        
        layout.addWidget(self.molecule_btn)
        layout.addWidget(self.material_btn)
        layout.addStretch()
        
        self.setLayout(layout)
    
    def select_chemical(self, chemical):
        self.selected_chemical = chemical
        self.accept()

class Editor(QGraphicsView):
    def __init__(self):
        scene = QGraphicsScene()
        super().__init__(scene)
        self.scene = scene
        self.setWindowTitle("Laboratory Protocol Builder")
        self.setSceneRect(0, 0, 1200, 700)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # Initialize protocol
        self.protocol = Protocol()
        self.blocks = []  # Keep track of all blocks
        self.linked_sequence = []  # Ordered list of linked actions by x-axis position
        self.link_distance = 100  # Distance threshold for linking
        
        # Create a container widget and layout for the editor + button
        container = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Title bar
        title = QLabel("Laboratory Protocol Builder")
        title_font = title.font()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        main_layout.addWidget(title)
        
        # Button bar
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        self.add_action_btn = QPushButton("+ Add Action")
        self.add_chemical_btn = QPushButton("🧪 Add Chemical")
        self.export_btn = QPushButton("📥 Export Protocol")
        self.import_btn = QPushButton("📂 Import Protocol")
        
        self.add_action_btn.clicked.connect(self.show_action_dialog)
        self.add_chemical_btn.clicked.connect(self.add_chemical_block)
        self.export_btn.clicked.connect(self.export_protocol)
        self.import_btn.clicked.connect(self.import_protocol)
        
        button_layout.addWidget(self.add_action_btn)
        button_layout.addWidget(self.add_chemical_btn)
        button_layout.addWidget(self.export_btn)
        button_layout.addWidget(self.import_btn)
        main_layout.addLayout(button_layout)
        
        # Canvas
        self.setStyleSheet("""
            QGraphicsView {
                border: 2px solid #d0d4db;
                border-radius: 8px;
                background-color: #ffffff;
            }
        """)
        
        main_layout.addWidget(self)
        
        container.setLayout(main_layout)
        
        # Store reference to container for use in main window
        self.container = container

    def show_action_dialog(self):
        dialog = ActionSelectionDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_action:
            # Map action names to action classes
            action_classes = {
                "Add": Add,
                "ChangeTemperature": ChangeTemperature,
                "Stir": Stir
            }
            
            # Define empty parameters for each action type
            default_params = {
                "Add": {"component": "", "duration": ""},
                "ChangeTemperature": {"temperature": ""},
                "Stir": {"duration": ""}
            }
            
            params = default_params.get(dialog.selected_action, {})
            action_class = action_classes.get(dialog.selected_action)
            
            # Create actual action object and add to protocol
            if action_class:
                action = action_class(**params)
                self.protocol.add_action(action)
                self.add_block(dialog.selected_action, params)
    
    def add_block(self, action, params):
        # Choose the appropriate block class based on action type
        if action in ["Add", "Stir"]:
            block = ElementaryAction(action, params, editor=self)
        elif action == "ChangeTemperature":
            block = SupportAction(action, params, editor=self)
        block.setPos(50, 50 + len(self.blocks) * 80)
        self.scene.addItem(block)
        self.blocks.append(block)
        self.update_linked_sequence()
        block.open_editor()

    def add_chemical_block(self):
        """Show dialog to select chemical type and add appropriate block"""
        dialog = ChemicalSelectionDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_chemical:
            chemical_classes = {
                "Molecule": Molecule,
                "Material": Material
            }
            
            # Define default parameters for each chemical type
            default_params = {
                "Molecule": {"name": "", "formula": "", "smile": ""},
                "Material": {"name": "", "formula": "", "structure": ""}
            }
            
            params = default_params.get(dialog.selected_chemical, {})
            chemical_class = chemical_classes.get(dialog.selected_chemical)
            
            # Create actual chemical object
            if chemical_class:
                chemical = chemical_class(**params)
                block = ChemicalBlock(dialog.selected_chemical, params, editor=self)
                block.setPos(50, 50 + len(self.blocks) * 80)
                self.scene.addItem(block)
                self.blocks.append(block)
                self.update_linked_sequence()
                block.open_editor()

    def update_linked_sequence(self):
        """Update the linked_sequence list based on current block linkages.
        Collects all blocks that are part of chains and sorts them by x-axis position.
        Includes both horizontally linked actions and vertically linked chemicals.
        """
        self.linked_sequence = []
        
        # Find all blocks that are part of chains (have prev_block, next_block, above_block, or below_block)
        linked_blocks = []
        for block in self.blocks:
            if block.prev_block or block.next_block or block.above_block or block.below_block:
                linked_blocks.append(block)
        
        # Sort by x-axis position (left to right)
        linked_blocks.sort(key=lambda b: b.pos().x())
        self.linked_sequence = linked_blocks

    def is_incompatible_horizontal_link(self, block1, block2):
        """Check if two blocks are incompatible for HORIZONTAL linking.
        Only Action blocks (Elementary/Support) can link horizontally.
        Chemical blocks cannot link horizontally to anything.
        Returns True if the link is incompatible, False otherwise.
        """
        is_chemical_1 = isinstance(block1, ChemicalBlock)
        is_chemical_2 = isinstance(block2, ChemicalBlock)
        
        # Chemical blocks cannot link horizontally to anything
        if is_chemical_1 or is_chemical_2:
            return True
        
        # Action blocks can link horizontally to other action blocks
        return False

    def is_incompatible_vertical_link(self, parent_block, child_block):
        """Check if two blocks are compatible for VERTICAL linking.
        Chemical blocks can link vertically to Action blocks (Elementary/Support) or other Chemical blocks.
        Returns True if the link is incompatible, False otherwise.
        """
        is_parent_action = isinstance(parent_block, (ElementaryAction, SupportAction))
        is_parent_chemical = isinstance(parent_block, ChemicalBlock)
        is_child_chemical = isinstance(child_block, ChemicalBlock)
        
        # Child must always be a chemical block
        if not is_child_chemical:
            return True
        
        # Parent can be either an action block or a chemical block
        return not (is_parent_action or is_parent_chemical)

    def preview_link(self, moved_block):
        """Visual feedback for both horizontal and vertical snapping."""
        # Reset previous preview to their actual logical state
        if hasattr(self, 'preview_pair') and self.preview_pair:
            a, b = self.preview_pair
            for item in [a, b]:
                if item:
                    # Check if the block is actually connected to something else
                    is_conn = bool(item.prev_block or item.next_block or 
                                   item.above_block or item.below_block or 
                                   (hasattr(item, 'chem_below') and item.chem_below))
                    item.set_connected(is_conn)
            self.preview_pair = None

        moved_rect = moved_block.sceneBoundingRect()
        for other in self.blocks:
            if other is moved_block: continue
            
            other_rect = other.sceneBoundingRect()
            if moved_rect.intersects(other_rect):
                # Highlight potential connection temporarily
                moved_block.set_connected(True)
                other.set_connected(True)
                self.preview_pair = (moved_block, other)
                return
        
        # If no intersection, current moved block follows its logical state
        is_conn = bool(moved_block.prev_block or moved_block.next_block or 
                       moved_block.above_block or moved_block.below_block or 
                       (hasattr(moved_block, 'chem_below') and moved_block.chem_below))
        moved_block.set_connected(is_conn)
    
    def update_chemical_chain_below(self, chemical_block, parent_x, parent_y):
        """Recursively update positions of chemical blocks below a chemical block."""
        if chemical_block.below_block:
            chem_rect = chemical_block.rect()
            below_rect = chemical_block.below_block.rect()
            snap_x = parent_x + (chem_rect.width() - below_rect.width()) * 0.25
            snap_y = parent_y + chem_rect.height()
            chemical_block.below_block.setPos(snap_x, snap_y)
            # Recursively update the chain below
            self.update_chemical_chain_below(chemical_block.below_block, snap_x, snap_y)

    def find_last_chemical_in_chain(self, chemical_block):
        """Find the last chemical block in a vertical chain."""
        current = chemical_block
        while current.below_block:
            current = current.below_block
        return current

    def _find_vertical_target(self, moved_block, look_below=False):
        """Find the best vertical candidate using center-to-center distance."""
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()
        best_target, best_score = None, float('inf')

        for other in self.blocks:
            if other is moved_block:
                continue

            # Actions cannot have Chemicals as flow parents
            if not isinstance(moved_block, ChemicalBlock) and isinstance(other, ChemicalBlock):
                continue

            other_rect = other.sceneBoundingRect()
            other_center = other_rect.center()

            # Center-to-center displacement
            dx = abs(moved_center.x() - other_center.x())
            dy = moved_center.y() - other_center.y()

            # Enforce horizontal alignment (40% width tolerance)
            if dx > other_rect.width() * 0.4:
                continue

            # Check directional snap zones
            if look_below:
                # Snap above target: between 75% and 10% of height above center
                is_valid = -other_rect.height() * 0.75 < dy < -other_rect.height() * 0.1
            else:
                # Snap below target: between 10% and 75% of height below center
                is_valid = other_rect.height() * 0.1 < dy < other_rect.height() * 0.75

            if not is_valid:
                continue

            # Select closest candidate via Manhattan distance
            score = dx + abs(dy)
            if score < best_score:
                best_score = score
                best_target = other

        return best_target, best_score
    
    def _link_action_as_child_vertical(self, moved_block, target_above):
        """Establishes pointers for moved_block below target_above."""
        old_child = target_above.below_block
        
        target_above.below_block = moved_block
        moved_block.above_block = target_above
        
        if old_child and not isinstance(old_child, ChemicalBlock):
            moved_block.below_block = old_child
            old_child.above_block = moved_block
            
        target_above.update()
        moved_block.update()
    
    def _link_action_flow_vertical(self, action, target):
        """Links an Action block to another Action block's vertical flow."""
        if not target or isinstance(target, ChemicalBlock):
            return
        
        # Insert between target and its current vertical child
        old_child = target.below_block
        target.below_block = action
        action.above_block = target
        
        if old_child:
            action.below_block = old_child
            old_child.above_block = action
        
        # Determine the start of the chain for reflow
        root = self.find_chain_start(target)
        self.reflow_chain(root)

    def _link_chemical_to_parent(self, chem, target):
        """Links chemical and positions it correctly based on target orientation."""
        border_overlap = 3

        if isinstance(target, (ElementaryAction, SupportAction)):
            old_stack = target.chem_below
            target.chem_below = chem
            chem.above_block = target
            if old_stack:
                chem.below_block = old_stack
                old_stack.above_block = chem
        elif isinstance(target, ChemicalBlock):
            # Target is another Chemical
            old_child = target.below_block
            target.below_block = chem
            chem.above_block = target
            if old_child:
                chem.below_block = old_child
                old_child.above_block = chem
            
            # Snap position manually before reflow to prevent jumping
            if target.orientation == "vertical":
                chem.setPos(target.pos().x() - chem.rect().width() + border_overlap, target.pos().y())
            else:
                chem.setPos(target.pos().x(), target.pos().y() + target.rect().height() - border_overlap)

        # Trigger full reflow from the top action anchor
        curr = target
        while isinstance(curr, ChemicalBlock) and curr.above_block:
            curr = curr.above_block
        self.reflow_chain(curr)

    def _get_target_and_zone(self, moved_block):
        """
        Determines which block is under the moved_block and in which zone 
        (TOP, BOTTOM, LEFT, RIGHT) it was dropped.
        """
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()
        
        target = None
        best_overlap = 0

        for other in self.blocks:
            if other is moved_block:
                continue
            
            other_rect = other.sceneBoundingRect()
            
            # Check for intersection
            if moved_rect.intersects(other_rect):
                # Calculate overlap area to pick the best target if overlapping multiple
                overlap = moved_rect.intersected(other_rect).width() * moved_rect.intersected(other_rect).height()
                if overlap > best_overlap:
                    best_overlap = overlap
                    target = other

        if not target:
            return None, None

        # Determine zone based on relative center position
        target_center = target.sceneBoundingRect().center()
        
        # Calculate horizontal and vertical bias
        dx = moved_center.x() - target_center.x()
        dy = moved_center.y() - target_center.y()

        # If it's a chemical, it always wants to go to the ingredient zone (BOTTOM or SIDE)
        if isinstance(moved_block, ChemicalBlock):
            if target.orientation == "vertical": return target, "LEFT"
            return target, "BOTTOM"

        # For Action blocks, decide based on which distance is greater (Manhattan-ish)
        if abs(dx) > abs(dy):
            return target, "RIGHT" if dx > 0 else "LEFT"
        else:
            return target, "BOTTOM" if dy > 0 else "TOP"
    
    def check_and_link_horizontal_blocks(self, moved_block):
        """Handles horizontal linking based on the drop quadrant."""
        if moved_block.orientation == "vertical":
            self.reflow_entire_cluster(moved_block)
            return

        # 1. Sever old links
        old_p, old_n = self._pluck_horizontal(moved_block)

        # 2. Find target and drop zone
        target, zone = self._get_target_and_zone(moved_block)

        # 3. Only process horizontal targets
        if target and not isinstance(target, ChemicalBlock) and target.orientation == "horizontal":
            if zone == "LEFT":
                if not target.is_first:
                    # Insert before target
                    p = target.prev_block
                    moved_block.next_block = target
                    target.prev_block = moved_block
                    if p:
                        p.next_block = moved_block
                        moved_block.prev_block = p
            elif zone == "RIGHT":
                if not moved_block.is_first:
                    # Insert after target
                    n = target.next_block
                    target.next_block = moved_block
                    moved_block.prev_block = target
                    if n:
                        moved_block.next_block = n
                        n.prev_block = moved_block

        # 4. Sync positions
        if old_p: self.reflow_entire_cluster(old_p)
        elif old_n: self.reflow_entire_cluster(old_n)
        self.reflow_entire_cluster(moved_block)
        self.update_linked_sequence()

    def _move_branch(self, block, dx, dy, visited=None):
        """Recursively moves a block and all its downstream connections (Right, Down, and Chemicals)."""
        if not block: return
        if visited is None: visited = set()
        if block in visited: return
        visited.add(block)

        block.setPos(block.pos().x() + dx, block.pos().y() + dy)

        # Move everything that follows this block
        if block.next_block:
            self._move_branch(block.next_block, dx, dy, visited)
        if block.below_block:
            self._move_branch(block.below_block, dx, dy, visited)
        if hasattr(block, 'chem_below') and block.chem_below:
            self._move_branch(block.chem_below, dx, dy, visited)
    
    def _link_action_as_parent_vertical(self, moved_block, target_below):
        """
        Connects a vertical action as the parent of target_below.
        Shifts the upstream branch UP to keep the target (and its horizontal chain) stable.
        """
        overlap = 20
        
        # 1. Calculate the ideal centered position over the target
        snap_x = target_below.pos().x() + (target_below.rect().width() - moved_block.rect().width()) / 2
        snap_y = target_below.pos().y() - moved_block.rect().height() + overlap
        
        # 2. Calculate the distance needed to move the moved_block to that position
        diff_x = snap_x - moved_block.pos().x()
        diff_y = snap_y - moved_block.pos().y()
        
        # 3. Move the moved_block and its upstream ancestors (Above and Left) to the snap position
        self._move_branch(moved_block, diff_x, diff_y)

        # 4. Establish the logical links
        old_parent = target_below.above_block
        if old_parent and not isinstance(old_parent, ChemicalBlock):
            # Insert moved_block between the old vertical parent and the target
            old_parent.below_block = moved_block
            moved_block.above_block = old_parent
            
        moved_block.below_block = target_below
        target_below.above_block = moved_block
        
        # 5. Visual update for both to ensure notches/arrows are drawn
        moved_block.update()
        target_below.update()

    def check_and_link_vertical_blocks(self, moved_block):
        """Handles vertical linking based on the drop quadrant."""
        # Reset preview colors
        if hasattr(self, 'preview_pair') and self.preview_pair:
            for item in self.preview_pair:
                if item: item.set_connected(False)
            self.preview_pair = None

        # 1. Cut old links
        old_p, old_c = self._pluck_vertical(moved_block)

        # 2. Find target and drop zone
        target, zone = self._get_target_and_zone(moved_block)

        # 3. Apply logic based on block type
        if target:
            if isinstance(moved_block, ChemicalBlock):
                # Chemicals follow the reflow positioning logic
                self._link_chemical_to_parent(moved_block, target)
            else:
                # ACTION FLOW
                if zone == "TOP":
                    # Dropped on top half -> moved becomes parent
                    if moved_block.orientation == "vertical":
                        self._link_action_as_parent_vertical(moved_block, target)
                elif zone == "BOTTOM":
                    # Dropped on bottom half -> moved becomes child
                    # Only allow if target is vertical (it's the only one with a bottom arrow)
                    if target.orientation == "vertical":
                        self._link_action_as_child_vertical(moved_block, target)
                elif zone == "LEFT" and target.orientation == "vertical":
                    # Allow horizontal to snap below vertical even if dropped slightly left
                    self._link_action_as_child_vertical(moved_block, target)

        # 4. Reflow everything
        if old_p: self.reflow_entire_cluster(old_p)
        if old_c: self.reflow_entire_cluster(old_c)
        self.reflow_entire_cluster(moved_block)
        if target: self.reflow_entire_cluster(target)

        self.update_linked_sequence()
    
    def _pluck_horizontal(self, block):
        """Sever horizontal links and stitch the old neighbors."""
        p, n = block.prev_block, block.next_block
        if p: p.next_block = n
        if n: n.prev_block = p
        block.prev_block = None
        block.next_block = None
        return p, n

    def _pluck_vertical(self, block):
        """Sever all vertical links and return the old neighbors."""
        p = block.above_block
        c = block.below_block
        
        if p:
            if isinstance(block, ChemicalBlock):
                if isinstance(p, ChemicalBlock): p.below_block = c
                else: p.chem_below = c
            else:
                if not isinstance(p, ChemicalBlock): p.below_block = c
        
        if c:
            c.above_block = p
            c.update()

        block.above_block = None
        block.below_block = None
        return p, c
    
    def _find_horizontal_neighbors(self, moved_block):
        """Finds the closest left and right action blocks that intersect with moved_block."""
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()
        
        left, right = None, None
        lx, rx = None, None

        for other in self.blocks:
            if other is moved_block or isinstance(other, ChemicalBlock):
                continue
            
            # Skip if the other block is vertical
            if other.orientation == "vertical":
                continue

            if moved_rect.intersects(other.sceneBoundingRect()):
                oc = other.sceneBoundingRect().center()
                # Check horizontal proximity
                if abs(moved_center.x() - oc.x()) >= abs(moved_center.y() - oc.y()):
                    if oc.x() < moved_center.x(): # Other is on the left
                        if left is None or oc.x() > lx:
                            left, lx = other, oc.x()
                    else: # Other is on the right
                        if right is None or oc.x() < rx:
                            right, rx = other, oc.x()
        return left, right
    
    def push_chain(self, start_block, shift_x: float):
        """Move start_block and all following blocks (via next_block)
        horizontally by shift_x (positive -> right).
        Also moves any chemical blocks attached below action blocks, preserving vertical alignment.
        """
        b = start_block
        while b:
            old_pos = b.pos()
            new_pos = QPointF(old_pos.x() + shift_x, old_pos.y())
            b.setPos(new_pos)
            # Also move any chemical block below this action block, keeping it below
            if isinstance(b, (ElementaryAction, SupportAction)) and b.below_block:
                # Reposition chemical to stay directly below the action block at its new position
                action_rect = b.rect()
                chem_rect = b.below_block.rect()
                snap_x = new_pos.x() + (action_rect.width() - chem_rect.width()) * 0.25
                snap_y = new_pos.y() + action_rect.height()
                b.below_block.setPos(snap_x, snap_y)
                # Update the full chemical chain below this chemical
                try:
                    self.update_chemical_chain_below(b.below_block, snap_x, snap_y)
                except Exception:
                    pass
            b = b.next_block

    def get_full_cluster(self, start_block):
        """Finds all blocks connected in the same graph using BFS."""
        cluster = set()
        queue = [start_block]
        while queue:
            curr = queue.pop(0)
            if curr not in cluster:
                cluster.add(curr)
                # Check all 5 possible directions
                neighbors = [
                    curr.prev_block, curr.next_block, 
                    curr.above_block, curr.below_block, 
                    curr.chem_below
                ]
                for n in neighbors:
                    if n and n not in cluster:
                        queue.append(n)
        return cluster

    def get_cluster_heads(self, cluster):
        """Returns all blocks in the cluster that have no incoming connections."""
        heads = []
        for b in cluster:
            if isinstance(b, ChemicalBlock):
                continue
            # A head is an action block with no PREV and no ABOVE 
            has_above_action = b.above_block and not isinstance(b.above_block, ChemicalBlock)
            if not b.prev_block and not has_above_action:
                heads.append(b)
        return heads

    def reflow_entire_cluster(self, any_block):
        """Starts the omnidirectional reflow from the given block."""
        if not any_block:
            return
        # Use a fresh visited set for every full sync
        self.reflow_chain(any_block, visited=set())

    def reflow_chain(self, block, visited=None):
        """Recursively align horizontal flows, vertical flows, and chemical stacks."""
        if not block:
            return
        if visited is None:
            visited = set()
        if block in visited:
            return
        visited.add(block)

        # force visual update for dynamic notches
        block.update()
        
        overlap = 20         
        border_overlap = 3   
        arrow_size = 18      
        precision = 0.01     

        # update connected highlight state
        has_conn = bool(block.prev_block or block.next_block or 
                        block.above_block or block.below_block or 
                        (hasattr(block, 'chem_below') and block.chem_below))
        block.set_connected(has_conn)

        # align horizontal next (right)
        if block.next_block:
            nb = block.next_block
            new_x = block.pos().x() + block.rect().width() - overlap
            new_y = block.pos().y()
            if abs(nb.pos().x() - new_x) > precision or abs(nb.pos().y() - new_y) > precision:
                nb.setPos(new_x, new_y)
            self.reflow_chain(nb, visited)

        # align horizontal prev (left) only if not triggered by a chemical
        if not isinstance(block, ChemicalBlock) and block.prev_block:
            pb = block.prev_block
            new_x = block.pos().x() - pb.rect().width() + overlap
            new_y = block.pos().y()
            if abs(pb.pos().x() - new_x) > precision or abs(pb.pos().y() - new_y) > precision:
                pb.setPos(new_x, new_y)
            self.reflow_chain(pb, visited)

        # align vertical action flow (down)
        if block.below_block and not isinstance(block.below_block, ChemicalBlock):
            bb = block.below_block
            new_x = block.pos().x() + (block.rect().width() - bb.rect().width()) / 2
            new_y = block.pos().y() + block.rect().height() - overlap
            if abs(bb.pos().x() - new_x) > precision or abs(bb.pos().y() - new_y) > precision:
                bb.setPos(new_x, new_y)
            self.reflow_chain(bb, visited)

        # align vertical action flow (up) only if not triggered by a chemical
        if not isinstance(block, ChemicalBlock) and block.above_block and not isinstance(block.above_block, ChemicalBlock):
            ab = block.above_block
            new_x = block.pos().x() + (block.rect().width() - ab.rect().width()) / 2
            new_y = block.pos().y() - ab.rect().height() + overlap
            if abs(ab.pos().x() - new_x) > precision or abs(ab.pos().y() - new_y) > precision:
                ab.setPos(new_x, new_y)
            self.reflow_chain(ab, visited)

        # align chemical stack ingredients
        if hasattr(block, 'chem_below') and block.chem_below:
            cb = block.chem_below
            cb.toggle_orientation(block.orientation)
            
            action_rect = block.rect()
            chem_rect = cb.rect()

            if block.orientation == "vertical":
                # side-aligned for vertical actions
                new_x = block.pos().x() - chem_rect.width() + border_overlap
                body_h = action_rect.height() - arrow_size
                body_center_y = block.pos().y() + (body_h / 2)
                new_y = body_center_y - (chem_rect.height() / 2) - 4.5
            else:
                # bottom-centered for horizontal actions
                off_x = ((action_rect.width() - chem_rect.width()) / 2) - 9
                new_x = block.pos().x() + off_x
                new_y = block.pos().y() + action_rect.height() - border_overlap

            if abs(cb.pos().x() - new_x) > precision or abs(cb.pos().y() - new_y) > precision:
                cb.setPos(new_x, new_y)
            
            self.reflow_chemicals(cb, block.orientation)
    
    def reflow_chemicals(self, first_chem, orientation):
        """Stacks chemicals based on orientation: Downwards if Horizontal, Leftwards if Vertical."""
        curr = first_chem
        border_overlap = 3 
        
        while curr:
            curr.set_connected(True)
            if curr.below_block:
                nxt = curr.below_block
                nxt.toggle_orientation(orientation)
                
                if orientation == "vertical":
                    # Stack to the left: New chemical right border overlaps current left border
                    new_x = curr.pos().x() - nxt.rect().width() + border_overlap
                    new_y = curr.pos().y()
                else:
                    # Stack downwards: Standard vertical list
                    new_x = curr.pos().x()
                    new_y = curr.pos().y() + curr.rect().height() - border_overlap
                
                nxt.setPos(new_x, new_y)
                curr = nxt
            else:
                break
    
    def find_chain_start(self, block):
        """Helper to find the first block of a horizontal chain."""
        curr = block
        while curr and curr.prev_block:
            curr = curr.prev_block
        return curr

    def align_chain_vertical(self, start_block, target_y: float):
        """Align start_block and all following blocks (via next_block)
        to the same vertical position (target_y).
        """
        b = start_block
        while b:
            pos = b.pos()
            b.setPos(pos.x(), target_y)
            b = b.next_block

    def keyPressEvent(self, event):
        """Handle key press events for the editor"""
        if event.key() == Qt.Key_Delete:
            # Delete selected block
            selected_items = self.scene.selectedItems()
            for item in selected_items:
                if hasattr(item, 'delete_block'):
                    item.delete_block()
        else:
            super().keyPressEvent(event)

    def import_protocol(self):
        """Import protocol and reconstruct intersections using block ids."""
        from PySide6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(self, "Import Protocol", "", "JSON Files (*.json)")
        if not filename: return

        try:
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            self.scene.clear()
            self.blocks = []
            self.protocol.actions = []
            
            # map to track already created blocks
            id_to_block = {}
            flows = data.get("flows", [])
            
            for i, flow in enumerate(flows):
                flow_type = flow.get("type", "horizontal")
                is_explicit_first = flow.get("is_explicit_first", False)
                steps = flow.get("steps", [])
                prev_step_block = None
                
                for j, step in enumerate(steps):
                    b_id = step.get("block_id")
                    action_name = step.get("action")
                    params = step.get("params", {})
                    
                    # reuse block if it was already created in another flow
                    if b_id in id_to_block:
                        new_block = id_to_block[b_id]
                    else:
                        new_block = self._create_block_by_name(action_name, params)
                        new_block.setPos(100 + i * 350, 100 + j * 200)
                        new_block.toggle_orientation(flow_type)
                        id_to_block[b_id] = new_block
                        
                        # handle chemicals only for new blocks
                        chemicals_data = step.get("chemicals", [])
                        prev_chem = None
                        for chem_step in chemicals_data:
                            chem_block = ChemicalBlock(chem_step.get("chemical"), chem_step.get("params", {}), editor=self)
                            self.scene.addItem(chem_block)
                            self.blocks.append(chem_block)
                            if prev_chem is None:
                                new_block.chem_below = chem_block
                                chem_block.above_block = new_block
                            else:
                                prev_chem.below_block = chem_block
                                chem_block.above_block = prev_chem
                            prev_chem = chem_block

                    if j == 0 and is_explicit_first:
                        new_block.is_first = True
                        new_block.update_visual_style()

                    # establish connections
                    if prev_step_block:
                        if flow_type == "vertical":
                            prev_step_block.below_block = new_block
                            new_block.above_block = prev_step_block
                        else:
                            prev_step_block.next_block = new_block
                            new_block.prev_block = prev_step_block
                    
                    prev_step_block = new_block

            # sync all clusters for perfect alignment
            for b in self.blocks:
                if not isinstance(b, ChemicalBlock):
                    self.reflow_entire_cluster(b)
            
            self.update_linked_sequence()

        except Exception as e:
            print(f"Error importing protocol: {e}")
    
    def _create_block_by_name(self, name, params):
        """Helper to instantiate the correct block class."""
        if name == "ChangeTemperature":
            block = SupportAction(name, params, editor=self)
        else:
            block = ElementaryAction(name, params, editor=self)
        
        self.scene.addItem(block)
        self.blocks.append(block)
        return block

    def export_protocol(self):
        """Export the protocol with block ids to handle intersections."""
        if not self.blocks:
            print("No blocks to export.")
            return

        # map each block to a unique id for this session
        block_to_id = {block: i for i, block in enumerate(self.blocks)}
        flows_list = []
        visited_globally = set()

        def get_step_data(block):
            visited_globally.add(block)
            data = {
                "block_id": block_to_id[block], # unique id for intersection tracking
                "action": block.action,
                "params": block.params.copy()
            }
            
            chemicals = []
            curr_chem = block.chem_below
            while curr_chem:
                visited_globally.add(curr_chem)
                chemicals.append({
                    "chemical": curr_chem.action,
                    "params": curr_chem.params.copy()
                })
                curr_chem = curr_chem.below_block
            
            if chemicals:
                data["chemicals"] = chemicals
            return data

        # process horizontal flows
        for b in self.blocks:
            if isinstance(b, ChemicalBlock): continue
            if b.prev_block is None:
                if b.next_block is not None or (b.is_first and b.orientation == "horizontal"):
                    content = []
                    curr = b
                    while curr:
                        content.append(get_step_data(curr))
                        curr = curr.next_block
                    flows_list.append({
                        "flow_id": len(flows_list) + 1,
                        "type": "horizontal",
                        "is_explicit_first": b.is_first,
                        "steps": content
                    })

        # process vertical flows
        for b in self.blocks:
            if isinstance(b, ChemicalBlock): continue
            has_action_above = b.above_block is not None and not isinstance(b.above_block, ChemicalBlock)
            if not has_action_above:
                if b.below_block is not None or (b.is_first and b.orientation == "vertical"):
                    content = []
                    curr = b
                    while curr:
                        content.append(get_step_data(curr))
                        curr = curr.below_block
                        if isinstance(curr, ChemicalBlock) or curr is None: break
                    flows_list.append({
                        "flow_id": len(flows_list) + 1,
                        "type": "vertical",
                        "is_explicit_first": b.is_first,
                        "steps": content
                    })

        final_output = {
            "protocol_name": "Laboratory Procedure",
            "total_flows": len(flows_list),
            "flows": flows_list
        }

        with open("protocol.json", "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
