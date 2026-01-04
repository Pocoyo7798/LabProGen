import sys
from PySide6.QtWidgets import (
    QApplication, QGraphicsView, QGraphicsScene,
    QGraphicsRectItem, QGraphicsTextItem, QDialog,
    QFormLayout, QLineEdit, QPushButton, QVBoxLayout,
    QWidget, QLabel, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QFont, QPainter
import json
from block import ActionBlock
from actions import Add, ChangeTemperature, Stir
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
        button_layout = QVBoxLayout()
        button_layout.setSpacing(8)
        
        self.add_action_btn = QPushButton("+ Add Action")
        self.export_btn = QPushButton("📥 Export Protocol")
        
        self.add_action_btn.clicked.connect(self.show_action_dialog)
        self.export_btn.clicked.connect(self.export_protocol)
        
        button_layout.addWidget(self.add_action_btn)
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
        block = ActionBlock(action, params, editor=self)
        block.setPos(50, 50 + len(self.blocks) * 80)
        self.scene.addItem(block)
        self.blocks.append(block)
        self.update_linked_sequence()

    def update_linked_sequence(self):
        """Update the linked_sequence list based on current block linkages.
        Collects all blocks that are part of chains and sorts them by x-axis position.
        """
        self.linked_sequence = []
        
        # Find all blocks that are part of chains (have prev_block or next_block)
        linked_blocks = []
        for block in self.blocks:
            if block.prev_block or block.next_block:
                linked_blocks.append(block)
        
        # Sort by x-axis position (left to right)
        linked_blocks.sort(key=lambda b: b.pos().x())
        self.linked_sequence = linked_blocks

    def preview_link(self, moved_block):
        """While dragging, highlight the block that would be linked if released.
        This sets a temporary connected visual on both blocks until release.
        """
        # Clear previous preview
        if hasattr(self, 'preview_pair') and self.preview_pair:
            a, b = self.preview_pair
            if a:
                a.set_connected(False)
            if b:
                b.set_connected(False)
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

    def check_and_link_blocks(self, moved_block):
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
        overlap = 15
        moved_rect = moved_block.sceneBoundingRect()
        moved_center = moved_rect.center()

        # Find any intersecting blocks (except itself) and consider
        # the closest left and right neighbors so we can insert between them
        intersects = []
        for other in self.blocks:
            if other is moved_block:
                continue
            other_rect = other.sceneBoundingRect()
            if moved_rect.intersects(other_rect):
                other_center = other_rect.center()
                dx = moved_center.x() - other_center.x()
                dy = moved_center.y() - other_center.y()
                if abs(dx) >= abs(dy):
                    intersects.append((other, other_center))

        if not intersects:
            # no horizontal intersections - block moved away from sequence
            # Reconnect the blocks that were on either side of moved_block if needed
            prev_block = moved_block.prev_block
            next_block = moved_block.next_block
            
            if prev_block and next_block:
                # Block was in the middle - connect prev to next
                prev_block.next_block = next_block
                next_block.prev_block = prev_block
                # Keep them connected visually if there are more blocks in chain
                prev_block.set_connected(True)
                next_block.set_connected(True)
            else:
                # Block was at start or end - just clear connections
                if prev_block:
                    prev_block.next_block = None
                    # Keep highlighted if it's still part of a chain
                    if prev_block.prev_block:
                        prev_block.set_connected(True)
                    else:
                        prev_block.set_connected(False)
                if next_block:
                    next_block.prev_block = None
                    # Keep highlighted if it's still part of a chain
                    if next_block.next_block:
                        next_block.set_connected(True)
                    else:
                        next_block.set_connected(False)
            
            # Clear the moved_block's links
            moved_block.prev_block = None
            moved_block.next_block = None
            moved_block.set_connected(False)
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
            
            # Reconnect old prev and next if they were connected
            if old_prev and old_next:
                old_prev.next_block = old_next
                old_next.prev_block = old_prev
                # Keep them highlighted
                old_prev.set_connected(True)
                old_next.set_connected(True)
            
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
            
            other.set_connected(True)
            moved_block.set_connected(True)
        self.update_linked_sequence()

    def push_chain(self, start_block, shift_x: float):
        """Move start_block and all following blocks (via next_block)
        horizontally by shift_x (positive -> right).
        """
        b = start_block
        while b:
            pos = b.pos()
            b.setPos(pos.x() + shift_x, pos.y())
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