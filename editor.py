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
        
        self.add_action_btn.clicked.connect(self.show_action_dialog)
        self.add_chemical_btn.clicked.connect(self.add_chemical_block)
        self.export_btn.clicked.connect(self.export_protocol)
        
        button_layout.addWidget(self.add_action_btn)
        button_layout.addWidget(self.add_chemical_btn)
        button_layout.addWidget(self.export_btn)
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
        """While dragging, highlight the block that would be linked if released.
        This sets a temporary connected visual on both blocks until release.
        """
        # Clear previous preview
        if hasattr(self, 'preview_pair') and self.preview_pair:
            a, b = self.preview_pair
            if a:
                # Restore proper connected state: should be connected if part of a chain (horizontal or vertical)
                a.set_connected(bool(a.prev_block or a.next_block or a.above_block or a.below_block))
            if b:
                # Restore proper connected state: should be connected if part of a chain (horizontal or vertical)
                b.set_connected(bool(b.prev_block or b.next_block or b.above_block or b.below_block))
            self.preview_pair = None

        moved_rect = moved_block.sceneBoundingRect()
        for other in self.blocks:
            if other is moved_block:
                continue
            other_rect = other.sceneBoundingRect()
            if moved_rect.intersects(other_rect):
                # highlight both as preview
                moved_block.set_connected(True)
                other.set_connected(True)
                self.preview_pair = (moved_block, other)
                return
        # no intersection; clear moved highlight
        moved_block.set_connected(False)

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

    def check_and_link_vertical_blocks(self, moved_block):
        """Check if a chemical block is below an action block or another chemical block and link them vertically.
        If a block is dropped where another already exists, it inserts itself and pushes others down.
        """
        if isinstance(moved_block, ChemicalBlock):
            moved_rect = moved_block.sceneBoundingRect()
            moved_center_x = moved_rect.center().x()
            moved_y = moved_rect.top()
            
            best_target = None
            best_distance = float('inf')
            
            for other in self.blocks:
                if other is moved_block:
                    continue
                
                # The target can be an ActionBlock or a ChemicalBlock
                if not isinstance(other, (ElementaryAction, SupportAction, ChemicalBlock)):
                    continue
                
                other_rect = other.sceneBoundingRect()
                other_center_x = other_rect.center().x()
                other_bottom = other_rect.bottom()
                
                dx = abs(moved_center_x - other_center_x)
                dy = moved_y - other_bottom
                
                # Tolerance for vertical proximity detection
                if -30 < dy < 60 and dx < 80:
                    distance = dx + abs(dy)
                    if distance < best_distance:
                        best_target = other
                        best_distance = distance
            
            if best_target:
                # 1. Remove moved_block from its current position in the chain (if any)
                old_parent = moved_block.above_block
                old_child = moved_block.below_block
                
                if old_parent:
                    if old_child:
                        old_parent.below_block = old_child
                        old_child.above_block = old_parent
                    else:
                        old_parent.below_block = None
                    
                    # If the previous parent was a ChemicalBlock, update its visual state
                    if isinstance(old_parent, ChemicalBlock):
                        old_parent.set_connected(bool(old_parent.above_block or old_parent.below_block))
                
                # 2. Insert moved_block between best_target and its current below_block
                target_old_child = best_target.below_block
                
                best_target.below_block = moved_block
                moved_block.above_block = best_target
                
                if target_old_child:
                    moved_block.below_block = target_old_child
                    target_old_child.above_block = moved_block
                else:
                    moved_block.below_block = None

                # 3. Reposition moved_block and the entire chain below it
                target_pos = best_target.pos()
                target_rect = best_target.rect()
                moved_rect_internal = moved_block.rect()
                
                # Visual alignment (snap)
                snap_x = target_pos.x() + (target_rect.width() - moved_rect_internal.width()) * 0.25
                snap_y = target_pos.y() + target_rect.height()
                moved_block.setPos(snap_x, snap_y)
                
                # Update visual state
                moved_block.set_connected(True)
                best_target.set_connected(True)
                
                # 4. Recursively push any blocks below to follow the new position
                self.update_chemical_chain_below(moved_block, snap_x, snap_y)
                
            else:
                # If dropped on empty space, disconnect from the vertical chain
                if moved_block.above_block:
                    parent = moved_block.above_block
                    child = moved_block.below_block
                    
                    if child:
                        parent.below_block = child
                        child.above_block = parent
                        p_pos = parent.pos()
                        self.update_chemical_chain_below(parent, p_pos.x(), p_pos.y())
                    else:
                        parent.below_block = None
                        if isinstance(parent, ChemicalBlock):
                            parent.set_connected(bool(parent.above_block))
                
                moved_block.above_block = None
                moved_block.below_block = None
                moved_block.set_connected(False)
        
        elif isinstance(moved_block, (ElementaryAction, SupportAction)):
            # If an action block is moved, ensure its first chemical child follows
            if moved_block.below_block:
                m_pos = moved_block.pos()
                m_rect = moved_block.rect()
                c_rect = moved_block.below_block.rect()
                
                snap_x = m_pos.x() + (m_rect.width() - c_rect.width()) * 0.25
                snap_y = m_pos.y() + m_rect.height()
                moved_block.below_block.setPos(snap_x, snap_y)
                self.update_chemical_chain_below(moved_block.below_block, snap_x, snap_y)

    def check_and_link_horizontal_blocks(self, moved_block):
        """When a block is released, update pointers and reflow the chain to close gaps."""
        # Clear preview highlights
        if hasattr(self, 'preview_pair') and self.preview_pair:
            a, b = self.preview_pair
            a.set_connected(False)
            b.set_connected(False)
            self.preview_pair = None

        if moved_block not in self.blocks:
            return

        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()

        # Find intersecting action blocks
        intersects = []
        for other in self.blocks:
            if other is moved_block or isinstance(other, ChemicalBlock):
                continue
            if moved_rect.intersects(other.sceneBoundingRect()):
                oc = other.sceneBoundingRect().center()
                if abs(moved_center.x() - oc.x()) >= abs(moved_center.y() - oc.y()):
                    intersects.append((other, oc))

        # 1. REMOVE: Disconnect moved_block from its old position
        old_prev = moved_block.prev_block
        old_next = moved_block.next_block

        if old_prev: old_prev.next_block = old_next
        if old_next: old_next.prev_block = old_prev

        if not intersects:
            # Case: Dropped in empty space
            moved_block.prev_block = None
            moved_block.next_block = None
            if old_prev: self.reflow_chain(self.find_chain_start(old_prev))
            elif old_next: self.reflow_chain(old_next)
            
            # Update visual state based on vertical connections
            moved_block.set_connected(bool(moved_block.below_block))
            self.update_linked_sequence()
            return

        # 2. FIND NEW NEIGHBORS
        left, right = None, None
        lx, rx = None, None
        for other, oc in intersects:
            if oc.x() < moved_center.x():
                if left is None or oc.x() > lx: left, lx = other, oc.x()
            elif oc.x() > moved_center.x():
                if right is None or oc.x() < rx: right, rx = other, oc.x()

        # 3. INSERTION LOGIC WITH REJECTION HANDLING
        link_formed = False

        if left and right:
            # Check if we can actually insert here
            if not right.is_first and not moved_block.is_first:
                moved_block.prev_block = left
                moved_block.next_block = right
                left.next_block = moved_block
                right.prev_block = moved_block
                link_formed = True
        elif left:
            if not moved_block.is_first:
                target_next = left.next_block
                left.next_block = moved_block
                moved_block.prev_block = left
                moved_block.next_block = target_next
                if target_next: target_next.prev_block = moved_block
                link_formed = True
        elif right:
            # Rejection if we try to link to the left of a 'First' block
            if not right.is_first:
                target_prev = right.prev_block
                right.prev_block = moved_block
                moved_block.next_block = right
                moved_block.prev_block = target_prev
                if target_prev: target_prev.next_block = moved_block
                link_formed = True

        # 4. FINAL REFLOW AND VISUAL SYNC
        # If no link was formed (e.g. rejected by is_first), clean up moved_block
        if not link_formed:
            moved_block.prev_block = None
            moved_block.next_block = None

        # Reflow all involved chains to ensure positions and colors are correct
        # Starting from the start of each affected chain
        for b in [left, right, moved_block, old_prev, old_next]:
            if b:
                start = self.find_chain_start(b)
                self.reflow_chain(start)

        self.update_linked_sequence()

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

    def reflow_chain(self, start_block):
        """Ensures all blocks in the chain starting from start_block are perfectly snapped."""
        if not start_block:
            return
            
        overlap = 20
        curr = start_block
        
        # Update current block's connected status
        is_conn = bool(curr.prev_block or curr.next_block or curr.below_block)
        curr.set_connected(is_conn)

        while curr and curr.next_block:
            prev = curr
            nxt = curr.next_block
            
            # Snap next to prev
            new_x = prev.pos().x() + prev.rect().width() - overlap
            new_y = prev.pos().y()
            nxt.setPos(new_x, new_y)
            
            # Update nxt visual status
            nxt.set_connected(True)
            
            # Update chemicals for the block that just moved
            if hasattr(nxt, 'below_block') and nxt.below_block:
                a_rect = nxt.rect()
                c_rect = nxt.below_block.rect()
                snap_x = nxt.pos().x() + (a_rect.width() - c_rect.width()) * 0.25
                snap_y = nxt.pos().y() + a_rect.height()
                nxt.below_block.setPos(snap_x, snap_y)
                self.update_chemical_chain_below(nxt.below_block, snap_x, snap_y)
            
            curr = nxt

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

    def export_protocol(self):
        """
        Export the protocol to JSON. 
        Ensures all blocks belong to a single, continuous chain.
        """
        if not self.blocks:
            print("No blocks to export.")
            return

        # 1. Identify the starting point
        # Priority 1: Block marked as 'is_first'
        start_node = next((b for b in self.blocks if b.is_first), None)
        
        # Priority 2: If no 'is_first', pick any action and find its chain start
        if not start_node:
            action_blocks = [b for b in self.blocks if not isinstance(b, ChemicalBlock)]
            if action_blocks:
                # Get the head of the chain containing the first action found
                start_node = self.find_chain_start(action_blocks[0])

        if not start_node:
            print("Error: Could not find a valid start for the protocol.")
            return

        # 2. Traverse and build the sequence while tracking visited blocks
        visited = set()
        self.protocol.actions = []
        
        # Mappings from UI strings to Data Classes
        action_map = {"Add": Add, "ChangeTemperature": ChangeTemperature, "Stir": Stir}
        chem_map = {"Molecule": Molecule, "Material": Material}

        current_action = start_node
        while current_action:
            visited.add(current_action)
            
            # Create Action data object
            action_cls = action_map.get(current_action.action)
            if action_cls:
                action_data = action_cls(**current_action.params)
                
                # Traverse Vertical chain for chemicals attached to this action
                current_chem = current_action.below_block
                while current_chem:
                    visited.add(current_chem)
                    chem_cls = chem_map.get(current_chem.action)
                    if chem_cls:
                        chem_data = chem_cls(**current_chem.params)
                        action_data.add_chemical(chem_data)
                    
                    # Move to the next chemical in the vertical stack
                    current_chem = current_chem.below_block
                
                self.protocol.add_action(action_data)
            
            # Move to the next action in the horizontal sequence
            current_action = current_action.next_block

        # 3. Validation: Ensure no blocks are left out (no orphans or second chains)
        all_blocks_in_scene = set(self.blocks)
        orphans = all_blocks_in_scene - visited
        
        if orphans:
            print(f"Export Aborted: {len(orphans)} blocks are disconnected from the main chain.")
            return

        # 4. Success: Write to file
        self.protocol.export("protocol.json")
        print(f"Protocol exported successfully ({len(self.protocol.actions)} actions included).")