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
        """When a block is released, check if it touches another block on left/right
        and update prev/next pointers accordingly.
        If moved_block is to the right of other (their rects intersect and moved center x > other center x),
        then other -> moved (moved placed after other). If moved is to the left, moved -> other.
        """
        # clear any preview highlights
        if hasattr(self, 'preview_pair') and self.preview_pair:
            a, b = self.preview_pair
            a.set_connected(False)
            b.set_connected(False)
            self.preview_pair = None

        if moved_block not in self.blocks:
            self.update_linked_sequence()
            return
        overlap = 20
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()

        # Find any intersecting blocks (except itself) and consider
        # the closest left and right neighbors so we can insert between them
        intersects = []
        for other in self.blocks:
            if other is moved_block:
                continue
            # Ignore chemical blocks for horizontal linking, only action blocks
            if isinstance(other, ChemicalBlock):
                continue
            other_rect = other.sceneBoundingRect()
            if moved_rect.intersects(other_rect):
                other_center = other_rect.center()
                dx = moved_center.x() - other_center.x()
                dy = moved_center.y() - other_center.y()
                if abs(dx) >= abs(dy):
                    intersects.append((other, other_center))

        if not intersects:
            # no horizontal intersections. Block moved away from sequence
            # Reconnect the blocks that were on either side of moved_block if needed
            prev_block = moved_block.prev_block
            next_block = moved_block.next_block
            
            if prev_block and next_block:
                # Block was in the middle. Connect prev to next
                prev_block.next_block = next_block
                next_block.prev_block = prev_block
                # Both blocks are still connected to each other horizontally, so both should be yellow
                prev_block.set_connected(True)
                next_block.set_connected(True)
                
                # Reposition next_block to be adjacent to prev_block (with overlap)
                prev_pos = prev_block.pos()
                prev_w = prev_block.rect().width()
                overlap = 20
                new_next_x = prev_pos.x() + prev_w - overlap
                next_pos = next_block.pos()
                next_block.setPos(new_next_x, prev_pos.y())
                
                # Reposition chemical block below next_block if it exists
                if next_block.below_block:
                    action_rect = next_block.rect()
                    chem_rect = next_block.below_block.rect()
                    snap_x = new_next_x + (action_rect.width() - chem_rect.width()) * 0.25
                    snap_y = prev_pos.y() + action_rect.height()
                    next_block.below_block.setPos(snap_x, snap_y)
                    # Also move any chemicals attached below this chemical
                    self.update_chemical_chain_below(next_block.below_block, snap_x, snap_y)
                
                # Align next block's vertical position with prev block
                self.align_chain_vertical(next_block.next_block, prev_pos.y())
                
                # Reposition chemical blocks for all aligned blocks in the chain
                b = next_block.next_block
                while b:
                    if isinstance(b, (ElementaryAction, SupportAction)) and b.below_block:
                        action_rect = b.rect()
                        chem_rect = b.below_block.rect()
                        snap_x = b.pos().x() + (action_rect.width() - chem_rect.width()) * 0.25
                        snap_y = b.pos().y() + action_rect.height()
                        b.below_block.setPos(snap_x, snap_y)
                        # Also update any chemical chain below this chemical
                        self.update_chemical_chain_below(b.below_block, snap_x, snap_y)
                    b = b.next_block
            else:
                # Block was at start or end. Just clear connections
                if prev_block:
                    prev_block.next_block = None
                    # Keep highlighted if it's still part of a chain (horizontal or vertical)
                    if isinstance(prev_block, ChemicalBlock):
                        is_connected = bool(prev_block.above_block or prev_block.below_block)
                    else:
                        is_connected = bool(prev_block.prev_block or prev_block.below_block)
                    prev_block.set_connected(is_connected)
                    # Update chemical block below if exists
                    if prev_block.below_block:
                        prev_block.below_block.set_connected(is_connected)
                if next_block:
                    next_block.prev_block = None
                    # Keep highlighted if it's still part of a chain (horizontal or vertical)
                    if isinstance(next_block, ChemicalBlock):
                        is_connected = bool(next_block.above_block or next_block.below_block)
                    else:
                        is_connected = bool(next_block.next_block or next_block.below_block)
                    next_block.set_connected(is_connected)
                    # Update chemical block below if exists
                    if next_block.below_block:
                        next_block.below_block.set_connected(is_connected)
            
            # Clear the moved_block's links
            moved_block.prev_block = None
            moved_block.next_block = None
            # Keep connected based on block type
            if isinstance(moved_block, ChemicalBlock):
                moved_block.set_connected(bool(moved_block.above_block or moved_block.below_block))
            else:
                moved_block.set_connected(bool(moved_block.below_block))
            self.update_linked_sequence()
            return
        self.update_linked_sequence()

        # Find closest left (max x < moved.x) and closest right (min x > moved.x)
        left = None
        right = None
        left_x = None
        right_x = None
        for other, oc in intersects:
            ox = oc.x()
            if ox < moved_center.x():
                if left is None or ox > left_x:
                    left = other
                    left_x = ox
            elif ox > moved_center.x():
                if right is None or ox < right_x:
                    right = other
                    right_x = ox

        # Store old connections before clearing
        old_prev = moved_block.prev_block
        old_next = moved_block.next_block
        
        # Clear the moved_block's links (will be reconnected if needed below)
        moved_block.prev_block = None
        moved_block.next_block = None

        # If we have both left and right, insert between them
        if left and right:
            # Prevent linking if right block is a first block
            if right.is_first:
                # Can't link before a first block, so just move without linking
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                self.update_linked_sequence()
                return
            
            # Prevent linking if moved block is a first block
            if moved_block.is_first:
                # Can't link a first block in the middle
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                self.update_linked_sequence()
                return
            
            # Prevent Chemical blocks from linking to Elementary or Support actions
            if self.is_incompatible_horizontal_link(moved_block, left) or self.is_incompatible_horizontal_link(moved_block, right):
                # Can't link incompatible block types
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                # Restore highlighting on left and right if they're part of a chain
                if isinstance(left, ChemicalBlock):
                    left.set_connected(bool(left.above_block or left.below_block))
                else:
                    left.set_connected(bool(left.prev_block or left.next_block or left.below_block))
                if isinstance(right, ChemicalBlock):
                    right.set_connected(bool(right.above_block or right.below_block))
                else:
                    right.set_connected(bool(right.prev_block or right.next_block or right.below_block))
                self.update_linked_sequence()
                return
            
            # Reconnect old prev and next if they were connected
            if old_prev and old_next:
                old_prev.next_block = old_next
                old_next.prev_block = old_prev
                # Keep them highlighted
                old_prev.set_connected(True)
                old_next.set_connected(True)
            elif old_prev:
                # Block was at the end of chain, just clear prev's next reference
                old_prev.next_block = None
                # Keep highlighted if prev is still part of a chain
                if isinstance(old_prev, ChemicalBlock):
                    old_prev.set_connected(bool(old_prev.above_block or old_prev.below_block))
                else:
                    old_prev.set_connected(bool(old_prev.prev_block or old_prev.below_block))
            elif old_next:
                # Block was at the start of chain, just clear next's prev reference
                old_next.prev_block = None
                # Keep highlighted if next is still part of a chain
                if isinstance(old_next, ChemicalBlock):
                    old_next.set_connected(bool(old_next.above_block or old_next.below_block))
                else:
                    old_next.set_connected(bool(old_next.next_block or old_next.below_block))
            
            # Clean references on neighbors if pointing to moved
            if left.next_block and left.next_block is moved_block:
                left.next_block = None
            if right.prev_block and right.prev_block is moved_block:
                right.prev_block = None

            # Insert moved between left and right
            moved_block.prev_block = left
            moved_block.next_block = right
            left.next_block = moved_block
            right.prev_block = moved_block

            # Position moved between left and right
            left_pos = left.pos()
            left_w = left.rect().width()

            # Make room by pushing the right chain so the right block
            # ends up adjacent to the moved block (smaller gap).
            moved_w = moved_block.rect().width()
            desired_right_x = (left_pos.x() + left_w - overlap) + moved_w - overlap
            current_right_x = right.pos().x()
            shift = desired_right_x - current_right_x
            if abs(shift) > 0.1:
                self.push_chain(right, shift)

            new_x = left_pos.x() + left_w - overlap
            new_y = left_pos.y() + (left.rect().height() - moved_block.rect().height()) / 2
            moved_block.setPos(new_x, new_y)

            # Align right chain to the same vertical position as left block
            self.align_chain_vertical(right, left_pos.y())
            
            # Reposition chemical blocks below aligned right chain to stay glued
            b = right
            while b:
                if isinstance(b, (ElementaryAction, SupportAction)) and b.below_block:
                    action_rect = b.rect()
                    chem_rect = b.below_block.rect()
                    snap_x = b.pos().x() + (action_rect.width() - chem_rect.width()) * 0.25
                    snap_y = b.pos().y() + action_rect.height()
                    b.below_block.setPos(snap_x, snap_y)
                    # Also update any chemical chain below this chemical
                    self.update_chemical_chain_below(b.below_block, snap_x, snap_y)
                b = b.next_block

            left.set_connected(True)
            right.set_connected(True)
            moved_block.set_connected(True)
            self.update_linked_sequence()
            return

        # If only one neighbor, fall back to single-side insertion logic
        other = left or right
        other_rect = other.sceneBoundingRect()
        other_center = other_rect.center()
        dx = moved_center.x() - other_center.x()
        # Clean old links on other if needed
        if other.prev_block and other.prev_block is moved_block:
            other.prev_block = None
        if other.next_block and other.next_block is moved_block:
            other.next_block = None

        if dx > 0:
            # moved is to the right of other -> place moved after other
            # Prevent linking if moved block is a first block (can't place first block after another)
            if moved_block.is_first:
                # Can't link a first block after another
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                self.update_linked_sequence()
                return
            
            # Prevent Chemical blocks from linking to Elementary or Support actions
            if self.is_incompatible_horizontal_link(moved_block, other):
                # Can't link incompatible block types
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                # Restore highlighting on other if it's part of a chain
                if isinstance(other, ChemicalBlock):
                    other.set_connected(bool(other.above_block or other.below_block))
                else:
                    other.set_connected(bool(other.prev_block or other.next_block or other.below_block))
                self.update_linked_sequence()
                return
            
            old_next = other.next_block
            moved_block.prev_block = other
            moved_block.next_block = None
            other.next_block = moved_block

            if old_next:
                # connect moved -> old_next
                moved_block.next_block = old_next
                old_next.prev_block = moved_block
                # make room: position old_next so it's adjacent to moved_block
                moved_w = moved_block.rect().width()
                desired_right_x = new_x + moved_w - overlap
                current_right_x = old_next.pos().x()
                shift = desired_right_x - current_right_x
                if abs(shift) > 0.1:
                    self.push_chain(old_next, shift)

            # snap moved to the right side of other
            other_pos = other.pos()
            other_w = other.rect().width()
            new_x = other_pos.x() + other_w - overlap
            new_y = other_pos.y() + (other.rect().height() - moved_block.rect().height()) / 2
            moved_block.setPos(new_x, new_y)
            other.set_connected(True)
            moved_block.set_connected(True)
        else:
            # moved is to the left of other -> place moved before other
            # Prevent linking if other is a first block (can't place anything before first)
            if other.is_first:
                # Can't link anything before a first block
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                self.update_linked_sequence()
                return
            
            # Prevent Chemical blocks from linking to Elementary or Support actions
            if self.is_incompatible_horizontal_link(moved_block, other):
                # Can't link incompatible block types
                moved_block.prev_block = None
                moved_block.next_block = None
                moved_block.set_connected(False)
                # Restore highlighting on other if it's part of a chain
                if isinstance(other, ChemicalBlock):
                    other.set_connected(bool(other.above_block or other.below_block))
                else:
                    other.set_connected(bool(other.prev_block or other.next_block or other.below_block))
                self.update_linked_sequence()
                return
            
            old_prev = other.prev_block
            moved_block.next_block = other
            moved_block.prev_block = None
            other.prev_block = moved_block
            if old_prev:
                # connect old_prev -> moved
                old_prev.next_block = moved_block
                moved_block.prev_block = old_prev
            
            # Keep moved_block at its current position
            # Shift the other chain to the right to maintain overlap
            moved_pos = moved_block.pos()
            moved_w = moved_block.rect().width()
            other_pos = other.pos()
            
            # Calculate desired position for other block
            desired_other_x = moved_pos.x() + moved_w - overlap
            shift = desired_other_x - other_pos.x()
            
            # Shift other and its chain
            if abs(shift) > 0.1:
                self.push_chain(other, shift)
            
            # Align other to same vertical position as moved
            new_y = moved_pos.y() + (moved_block.rect().height() - other.rect().height()) / 2
            other_pos = other.pos()
            other.setPos(other_pos.x(), new_y)
            self.align_chain_vertical(other.next_block, new_y)
            
            # Reposition chemical blocks below aligned blocks to stay glued
            b = other
            while b:
                if isinstance(b, (ElementaryAction, SupportAction)) and b.below_block:
                    action_rect = b.rect()
                    chem_rect = b.below_block.rect()
                    snap_x = b.pos().x() + (action_rect.width() - chem_rect.width()) * 0.25
                    snap_y = b.pos().y() + action_rect.height()
                    b.below_block.setPos(snap_x, snap_y)
                    # Also update any chemical chain below this chemical
                    self.update_chemical_chain_below(b.below_block, snap_x, snap_y)
                b = b.next_block
            
            other.set_connected(True)
            moved_block.set_connected(True)
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
        """Export the protocol to a JSON file using the linked_sequence of ordered actions"""
        print(self.linked_sequence)
        ordered_blocks = self.linked_sequence.copy()
        # Clear and rebuild protocol with ordered blocks
        self.protocol.actions = []
        for block in ordered_blocks:
            action_classes = {
                "Add": Add,
                "ChangeTemperature": ChangeTemperature,
                "Stir": Stir
            }
            action_class = action_classes.get(block.action)
            if action_class:
                action = action_class(**block.params)
                self.protocol.add_action(action)
        self.protocol.export("protocol.json")
        print("Protocol exported to protocol.json")